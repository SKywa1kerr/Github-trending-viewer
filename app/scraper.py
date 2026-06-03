import json
import asyncio
import time
from bs4 import BeautifulSoup
from app.config import config
from app.database import get_connection
from app.github_client import GitHubRequestError, github_get_json, github_get_text


def build_search_url(topic: str = None, keyword: str = None, sort: str = "stars") -> str:
    base = "https://api.github.com/search/repositories"
    if topic:
        q = f"topic:{topic}"
    elif keyword:
        q = keyword.replace(" ", "+")
    else:
        q = "stars:>100"
    return f"{base}?q={q}&sort={sort}&per_page=30"


def parse_trending_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    repos = []
    for article in soup.select("article.Box-row"):
        h2 = article.select_one("h2 a")
        if not h2:
            continue
        repo_name = h2.get("href", "").strip("/")
        desc_p = article.select_one("p")
        description = desc_p.get_text(strip=True) if desc_p else ""
        stars_el = article.select_one("a[href$='/stargazers']")
        stars_text = stars_el.get_text(strip=True).replace(",", "") if stars_el else "0"
        stars = int(stars_text) if stars_text.isdigit() else 0
        gained_el = article.select_one("span.d-inline-block.float-sm-right")
        gained_text = ""
        if gained_el:
            gained_text = gained_el.get_text(strip=True).replace(",", "").split()[0]
        stars_gained = int(gained_text) if gained_text.isdigit() else 0
        lang_el = article.select_one("span[itemprop='programmingLanguage']")
        language = lang_el.get_text(strip=True) if lang_el else ""
        repos.append({
            "repo_full_name": repo_name,
            "description": description,
            "stars": stars,
            "stars_gained": stars_gained,
            "language": language,
            "repo_url": f"https://github.com/{repo_name}",
        })
    return repos


async def fetch_trending(period: str = "daily") -> list[dict]:
    period_map = {"daily": "", "weekly": "?since=weekly", "monthly": "?since=monthly"}
    url = f"https://github.com/trending{period_map.get(period, '')}"
    try:
        html = await github_get_text(url)
    except GitHubRequestError:
        return []
    return parse_trending_html(html)


async def fetch_search_results(topic: str = None, keyword: str = None) -> list[dict]:
    url = build_search_url(topic=topic, keyword=keyword)
    try:
        data = await github_get_json(url)
    except GitHubRequestError:
        return []
    repos = []
    for item in data.get("items", [])[:30]:
        repos.append({
            "repo_full_name": item["full_name"],
            "description": item.get("description") or "",
            "stars": item.get("stargazers_count", 0),
            "stars_gained": 0,
            "language": item.get("language") or "",
            "repo_url": item.get("html_url", ""),
            "topics": item.get("topics", []),
            "last_updated": item.get("updated_at", ""),
        })
    return repos


async def fetch_readme(repo_full_name: str) -> str:
    url = f"https://api.github.com/repos/{repo_full_name}/readme"
    try:
        text = await github_get_text(url, accept="application/vnd.github.v3.raw")
    except GitHubRequestError:
        return ""
    if text:
        return text[:3000]
    return ""


def save_projects(projects: list[dict], category: str):
    conn = get_connection()
    today = time.strftime("%Y-%m-%d")
    for p in projects:
        topics_json = json.dumps(p.get("topics", []))
        conn.execute("""
            INSERT INTO projects (repo_full_name, description, stars, stars_gained,
                                  language, topics, category, repo_url, last_updated,
                                  fetched_at, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(repo_full_name) DO UPDATE SET
                description = excluded.description,
                stars = excluded.stars,
                stars_gained = CASE WHEN excluded.stars_gained > 0
                               THEN excluded.stars_gained ELSE stars_gained END,
                language = excluded.language,
                topics = excluded.topics,
                last_updated = excluded.last_updated,
                fetched_at = datetime('now'),
                translation_status = CASE
                    WHEN projects.description != excluded.description
                         OR projects.description_zh = ''
                         OR projects.description_zh IS NULL
                    THEN 'pending'
                    ELSE projects.translation_status
                END,
                translation_error = CASE
                    WHEN projects.description != excluded.description
                    THEN ''
                    ELSE projects.translation_error
                END,
                translation_next_retry_at = CASE
                    WHEN projects.description != excluded.description
                    THEN ''
                    ELSE projects.translation_next_retry_at
                END
        """, (p["repo_full_name"], p["description"], p["stars"], p["stars_gained"],
              p["language"], topics_json, category, p["repo_url"],
              p.get("last_updated", "")))
        # Record star history
        if p["stars"] > 0:
            row = conn.execute(
                "SELECT id FROM projects WHERE repo_full_name = ?",
                (p["repo_full_name"],)
            ).fetchone()
            if row:
                conn.execute("""
                    INSERT INTO star_history (project_id, stars, recorded_date)
                    VALUES (?, ?, ?)
                    ON CONFLICT(project_id, recorded_date) DO UPDATE SET stars = excluded.stars
                """, (row["id"], p["stars"], today))
    conn.commit()
    conn.close()


async def fetch_repo_topics(repo_full_name: str) -> list[str]:
    """通过 GitHub API 获取仓库的 topics（Trending 页面不含 topics 信息）"""
    url = f"https://api.github.com/repos/{repo_full_name}/topics"
    try:
        data = await github_get_json(url, accept="application/vnd.github.mercy-preview+json")
        return data.get("names", [])
    except GitHubRequestError:
        pass
    return []


async def run_full_scrape():
    import logging
    from app.routers.system import set_progress
    logger = logging.getLogger("scraper")

    # 1. Trending（每日）
    set_progress("scraping", 4, 1, "获取 Trending 列表...")
    trending = await fetch_trending("daily")
    logger.info(f"Fetched {len(trending)} trending repos")

    # 并发获取 topics（提高到 10 并发）
    set_progress("scraping", 4, 1, f"获取 {len(trending)} 个项目的标签...")
    sem = asyncio.Semaphore(10)

    async def _fetch_topics_for(p):
        async with sem:
            try:
                p["topics"] = await fetch_repo_topics(p["repo_full_name"])
            except Exception:
                p["topics"] = []

    await asyncio.gather(*[_fetch_topics_for(p) for p in trending])
    save_projects(trending, "other")

    # 2. 按板块话题 + 关键词并发搜索（3 个一批，避免触发 GitHub 限流）
    all_tasks = []
    for cat_key, cat_info in config.CATEGORIES.items():
        for topic in cat_info["topics"][:3]:
            all_tasks.append(("topic", cat_key, topic))

    conn = get_connection()
    keywords = conn.execute("SELECT keyword, category FROM keywords").fetchall()
    conn.close()
    for kw in keywords:
        all_tasks.append(("keyword", kw["category"], kw["keyword"]))

    set_progress("scraping", 4, 2, f"搜索 {len(all_tasks)} 个分类和关键词...")
    search_sem = asyncio.Semaphore(3)
    done_count = [0]

    async def _search_one(task_type, category, query):
        async with search_sem:
            try:
                if task_type == "topic":
                    results = await fetch_search_results(topic=query)
                else:
                    results = await fetch_search_results(keyword=query)
                save_projects(results, category)
                logger.info(f"Fetched {len(results)} repos for {task_type}:{query}")
            except Exception as e:
                logger.warning(f"Failed {task_type} {query}: {e}")
            done_count[0] += 1
            set_progress("scraping", 4, 2, f"搜索进度 {done_count[0]}/{len(all_tasks)}")

    await asyncio.gather(*[_search_one(t, c, q) for t, c, q in all_tasks])

    # 3. 重新分类
    set_progress("scraping", 4, 3, "重新分类项目...")
    _reclassify_projects()
    set_progress("scraping", 4, 4, "抓取完成")
    logger.info("Scrape complete")


def _reclassify_projects():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, topics, description FROM projects WHERE category = 'other'"
    ).fetchall()
    for row in rows:
        topics = json.loads(row["topics"]) if row["topics"] else []
        desc = (row["description"] or "").lower()
        for cat_key, cat_info in config.CATEGORIES.items():
            # 通过 topics 或 description 关键词匹配分类
            if any(t in cat_info["topics"] for t in topics):
                conn.execute(
                    "UPDATE projects SET category = ? WHERE id = ?",
                    (cat_key, row["id"])
                )
                break
            elif any(t in desc for t in cat_info["topics"]):
                conn.execute(
                    "UPDATE projects SET category = ? WHERE id = ?",
                    (cat_key, row["id"])
                )
                break
    conn.commit()
    conn.close()
