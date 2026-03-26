import httpx
import json
import asyncio
import time
from bs4 import BeautifulSoup
from app.config import config
from app.database import get_connection


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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return parse_trending_html(resp.text)
    return []


async def fetch_search_results(topic: str = None, keyword: str = None) -> list[dict]:
    url = build_search_url(topic=topic, keyword=keyword)
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return []
        data = resp.json()
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
    headers = {"Accept": "application/vnd.github.v3.raw", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            text = resp.text
            return text[:3000]
    return ""


def save_projects(projects: list[dict], category: str):
    conn = get_connection()
    for p in projects:
        topics_json = json.dumps(p.get("topics", []))
        conn.execute("""
            INSERT INTO projects (repo_full_name, description, stars, stars_gained,
                                  language, topics, category, repo_url, last_updated, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(repo_full_name) DO UPDATE SET
                description = excluded.description,
                stars = excluded.stars,
                stars_gained = CASE WHEN excluded.stars_gained > 0
                               THEN excluded.stars_gained ELSE stars_gained END,
                language = excluded.language,
                topics = excluded.topics,
                last_updated = excluded.last_updated,
                fetched_at = datetime('now')
        """, (p["repo_full_name"], p["description"], p["stars"], p["stars_gained"],
              p["language"], topics_json, category, p["repo_url"],
              p.get("last_updated", "")))
    conn.commit()
    conn.close()


async def fetch_repo_topics(repo_full_name: str) -> list[str]:
    """通过 GitHub API 获取仓库的 topics（Trending 页面不含 topics 信息）"""
    url = f"https://api.github.com/repos/{repo_full_name}/topics"
    headers = {
        "Accept": "application/vnd.github.mercy-preview+json",
        "User-Agent": "Mozilla/5.0"
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("names", [])
    return []


async def run_full_scrape():
    # 1. Trending（每日）
    trending = await fetch_trending("daily")
    # 获取每个 trending 项目的 topics 用于分类
    for p in trending:
        topics = await fetch_repo_topics(p["repo_full_name"])
        p["topics"] = topics
        await asyncio.sleep(1)  # GitHub API rate limit: 60/hour unauthenticated
    save_projects(trending, "other")

    # 2. 按板块话题搜索（每个板块只取前3个话题，减少 API 调用）
    for cat_key, cat_info in config.CATEGORIES.items():
        for topic in cat_info["topics"][:3]:
            results = await fetch_search_results(topic=topic)
            save_projects(results, cat_key)
            await asyncio.sleep(3)  # 避免触发 GitHub rate limit

    # 3. 自定义关键词
    conn = get_connection()
    keywords = conn.execute("SELECT keyword, category FROM keywords").fetchall()
    conn.close()
    for kw in keywords:
        results = await fetch_search_results(keyword=kw["keyword"])
        save_projects(results, kw["category"])
        await asyncio.sleep(3)

    # 4. 重新分类 trending 中匹配话题的项目
    _reclassify_projects()


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
