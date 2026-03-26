# GitHub 热门项目中文浏览器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Docker 部署的本地应用，自动抓取 GitHub 热门项目并通过大模型翻译为中文展示。

**Architecture:** Python FastAPI 单容器架构。后端负责定时抓取 GitHub Trending/Search/Topics 数据，调用 DeepSeek V3.2 API 翻译并总结 README，存入 SQLite。前端为 FastAPI 托管的静态 HTML/CSS/JS 页面，精美卡片式布局。通过 Docker Compose 一键部署，桌面 VBS 快捷方式打开无边框浏览器窗口。

**Tech Stack:** Python 3.11, FastAPI, SQLite, APScheduler, httpx, BeautifulSoup4, HTML5/CSS3/Vanilla JS, Docker

**Spec:** `docs/design.md`

---

## 文件结构

```
github-trending-viewer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口，挂载路由 + 静态文件 + 启动定时任务
│   ├── config.py             # 环境变量配置读取
│   ├── database.py           # SQLite 连接、建表、WAL 模式
│   ├── models.py             # Pydantic 模型（请求/响应）
│   ├── scraper.py            # GitHub 数据抓取（Trending + Search API + Topics）
│   ├── translator.py         # 大模型翻译服务（调用 DeepSeek API）
│   ├── scorer.py             # 综合评分计算
│   ├── scheduler.py          # 定时任务调度（APScheduler）
│   └── routers/
│       ├── __init__.py
│       ├── projects.py       # /api/projects 相关路由
│       ├── keywords.py       # /api/keywords 相关路由
│       └── system.py         # /api/status, /api/refresh, /api/categories
├── static/
│   ├── index.html            # 主页面
│   ├── css/
│   │   └── style.css         # 样式（深色/浅色主题、卡片、动画）
│   └── js/
│       └── app.js            # 前端逻辑（API 调用、渲染、交互）
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_scraper.py
│   ├── test_translator.py
│   ├── test_scorer.py
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── launch.vbs               # 桌面快捷方式脚本
└── docs/
    └── design.md
```

---

### Task 1: 项目骨架 + 配置 + 数据库

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/database.py`, `app/models.py`, `app/main.py`
- Create: `app/routers/__init__.py`
- Create: `requirements.txt`, `.env.example`, `.gitignore`
- Test: `tests/__init__.py`, `tests/test_database.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.0
uvicorn==0.30.0
httpx==0.27.0
beautifulsoup4==4.12.3
apscheduler==3.10.4
```

- [ ] **Step 2: 创建 .env.example 和 .gitignore**

`.env.example`:
```
API_ENDPOINT=https://models.sjtu.edu.cn/api/v1/chat/completions
API_KEY=your-api-key-here
API_MODEL=deepseek-chat
UPDATE_HOUR=8
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
data/
*.db
```

- [ ] **Step 3: 创建 app/config.py**

```python
import os

class Config:
    API_ENDPOINT: str = os.getenv("API_ENDPOINT", "https://models.sjtu.edu.cn/api/v1/chat/completions")
    API_KEY: str = os.getenv("API_KEY", "")
    API_MODEL: str = os.getenv("API_MODEL", "deepseek-chat")
    UPDATE_HOUR: int = int(os.getenv("UPDATE_HOUR", "8"))
    DB_PATH: str = os.getenv("DB_PATH", "data/trending.db")
    MAX_DAILY_TOKENS: int = 150000
    MAX_REQUESTS_PER_MINUTE: int = 30
    CATEGORIES: dict = {
        "ai": {
            "name": "AI",
            "topics": ["artificial-intelligence", "machine-learning", "deep-learning",
                       "llm", "large-language-model", "gpt", "agent", "nlp",
                       "computer-vision", "stable-diffusion"]
        },
        "tools": {
            "name": "实用工具",
            "topics": ["tool", "productivity", "utility", "automation", "self-hosted"]
        },
        "devtools": {
            "name": "开发工具",
            "topics": ["developer-tools", "devops", "cli", "framework", "library"]
        }
    }

config = Config()
```

- [ ] **Step 4: 创建 app/database.py**

```python
import sqlite3
import os
from app.config import config

def get_db_path():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return config.DB_PATH

def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            description_zh TEXT DEFAULT '',
            readme_summary_zh TEXT DEFAULT '',
            stars INTEGER DEFAULT 0,
            stars_gained INTEGER DEFAULT 0,
            language TEXT DEFAULT '',
            topics TEXT DEFAULT '[]',
            category TEXT DEFAULT 'other',
            repo_url TEXT DEFAULT '',
            score REAL DEFAULT 0.0,
            last_updated TEXT DEFAULT '',
            translated_at TEXT DEFAULT '',
            fetched_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT DEFAULT 'other',
            created_at TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()

def is_db_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return count == 0
```

- [ ] **Step 5: 创建 app/models.py**

```python
from pydantic import BaseModel
from typing import Optional

class ProjectOut(BaseModel):
    id: int
    repo_full_name: str
    description: str
    description_zh: str
    readme_summary_zh: str
    stars: int
    stars_gained: int
    language: str
    topics: list[str]
    category: str
    repo_url: str
    score: float
    last_updated: str
    fetched_at: str

class KeywordIn(BaseModel):
    keyword: str
    category: str = "other"

class KeywordOut(BaseModel):
    id: int
    keyword: str
    category: str
    created_at: str

class StatusOut(BaseModel):
    total_projects: int
    last_fetched: str
    is_refreshing: bool

class CategoryOut(BaseModel):
    key: str
    name: str
    count: int
```

- [ ] **Step 6: 创建 app/__init__.py 和 app/routers/__init__.py**

两个文件都为空的 `__init__.py`。

- [ ] **Step 7: 创建 app/main.py 最小骨架**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db

app = FastAPI(title="GitHub Trending Viewer")

@app.on_event("startup")
def startup():
    init_db()

# 静态文件托管（前端页面），放在路由注册之后
# app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 8: 写数据库测试**

```python
# tests/test_database.py
import os
import tempfile
import pytest
from app.database import get_connection, init_db, is_db_empty
from app import config as cfg

@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
        init_db()
        yield db_path

def test_init_db_creates_tables():
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t["name"] for t in tables}
    assert "projects" in table_names
    assert "keywords" in table_names
    conn.close()

def test_is_db_empty_returns_true_on_fresh_db():
    assert is_db_empty() is True

def test_is_db_empty_returns_false_after_insert():
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url) VALUES (?, ?)",
        ("test/repo", "https://github.com/test/repo")
    )
    conn.commit()
    conn.close()
    assert is_db_empty() is False
```

- [ ] **Step 9: 运行测试验证通过**

Run: `cd github-trending-viewer && python -m pytest tests/test_database.py -v`
Expected: 3 tests PASS

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: project skeleton with config, database, and models"
```

---

### Task 2: GitHub 数据抓取模块

**Files:**
- Create: `app/scraper.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: 写 scraper 测试**

```python
# tests/test_scraper.py
import pytest
from app.scraper import parse_trending_html, build_search_url

def test_build_search_url_with_topic():
    url = build_search_url(topic="machine-learning", sort="stars")
    assert "q=topic:machine-learning" in url
    assert "sort=stars" in url

def test_build_search_url_with_keyword():
    url = build_search_url(keyword="ai agent", sort="stars")
    assert "q=ai+agent" in url

def test_parse_trending_html_empty():
    result = parse_trending_html("<html><body></body></html>")
    assert result == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: FAIL（scraper 模块不存在）

- [ ] **Step 3: 实现 app/scraper.py**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/scraper.py tests/test_scraper.py
git commit -m "feat: GitHub data scraper with trending, search, and topics"
```

---

### Task 3: 大模型翻译模块

**Files:**
- Create: `app/translator.py`
- Test: `tests/test_translator.py`

- [ ] **Step 1: 写翻译模块测试**

```python
# tests/test_translator.py
import json
import pytest
from app.translator import build_translate_prompt, parse_translate_response

def test_build_translate_prompt():
    prompt = build_translate_prompt("test/repo", "A test project", "# README\nThis is a test.")
    assert "test/repo" in prompt
    assert "A test project" in prompt
    assert "README" in prompt

def test_parse_translate_response_valid_json():
    response = json.dumps({
        "description_zh": "测试项目",
        "readme_summary_zh": "这是一个测试项目的摘要。"
    })
    result = parse_translate_response(response)
    assert result["description_zh"] == "测试项目"
    assert result["readme_summary_zh"] == "这是一个测试项目的摘要。"

def test_parse_translate_response_invalid_json():
    result = parse_translate_response("not json at all")
    assert result["description_zh"] == ""
    assert result["readme_summary_zh"] == ""

def test_parse_translate_response_json_in_markdown():
    response = '```json\n{"description_zh": "测试", "readme_summary_zh": "摘要"}\n```'
    result = parse_translate_response(response)
    assert result["description_zh"] == "测试"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_translator.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 app/translator.py**

```python
import httpx
import json
import re
import time
import asyncio
from app.config import config
from app.database import get_connection

_daily_tokens_used = 0
_last_reset_date = ""

def build_translate_prompt(repo_name: str, description: str, readme: str) -> str:
    return f"""你是一个技术项目翻译助手。请将以下 GitHub 项目信息翻译为中文。

项目名：{repo_name}
项目描述：{description}
README 内容：{readme[:3000]}

请返回 JSON 格式：
{{
  "description_zh": "中文简介（1-2句）",
  "readme_summary_zh": "README 中文摘要（3-5句，涵盖核心功能、使用场景、亮点）"
}}"""

def parse_translate_response(text: str) -> dict:
    default = {"description_zh": "", "readme_summary_zh": ""}
    # 尝试从 markdown 代码块中提取 JSON
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    try:
        data = json.loads(text)
        return {
            "description_zh": data.get("description_zh", ""),
            "readme_summary_zh": data.get("readme_summary_zh", "")
        }
    except (json.JSONDecodeError, TypeError):
        return default

async def translate_project(repo_name: str, description: str, readme: str) -> dict:
    global _daily_tokens_used, _last_reset_date
    today = time.strftime("%Y-%m-%d")
    if _last_reset_date != today:
        _daily_tokens_used = 0
        _last_reset_date = today
    if _daily_tokens_used >= config.MAX_DAILY_TOKENS:
        return {"description_zh": "", "readme_summary_zh": ""}

    prompt = build_translate_prompt(repo_name, description, readme)
    payload = {
        "model": config.API_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(config.API_ENDPOINT, json=payload, headers=headers)
            if resp.status_code != 200:
                return {"description_zh": "", "readme_summary_zh": ""}
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            _daily_tokens_used += usage.get("total_tokens", 0)
            return parse_translate_response(content)
    except Exception:
        return {"description_zh": "", "readme_summary_zh": ""}

async def translate_untranslated_projects():
    from app.scraper import fetch_readme

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, repo_full_name, description FROM projects "
        "WHERE description_zh = '' OR description_zh IS NULL "
        "LIMIT 50"
    ).fetchall()
    conn.close()

    for row in rows:
        readme = await fetch_readme(row["repo_full_name"])
        result = await translate_project(row["repo_full_name"], row["description"], readme)
        if result["description_zh"]:
            conn = get_connection()
            conn.execute(
                "UPDATE projects SET description_zh = ?, readme_summary_zh = ?, "
                "translated_at = datetime('now') WHERE id = ?",
                (result["description_zh"], result["readme_summary_zh"], row["id"])
            )
            conn.commit()
            conn.close()
        # 频率控制: 30 次/分钟 = 每 2 秒一次
        await asyncio.sleep(2)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_translator.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/translator.py tests/test_translator.py
git commit -m "feat: LLM translation module with rate limiting and token budget"
```

---

### Task 4: 评分模块

**Files:**
- Create: `app/scorer.py`
- Test: `tests/test_scorer.py`

- [ ] **Step 1: 写评分测试**

```python
# tests/test_scorer.py
from app.scorer import compute_score

def test_high_stars_high_growth():
    score = compute_score(stars=50000, stars_gained=1000,
                          last_updated="2026-03-26T00:00:00Z",
                          has_readme=True, has_topics=True)
    assert score > 0.7

def test_low_stars_no_growth():
    score = compute_score(stars=10, stars_gained=0,
                          last_updated="2024-01-01T00:00:00Z",
                          has_readme=False, has_topics=False)
    assert score < 0.3

def test_score_between_0_and_1():
    score = compute_score(stars=1000, stars_gained=50,
                          last_updated="2026-03-20T00:00:00Z",
                          has_readme=True, has_topics=True)
    assert 0 <= score <= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scorer.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 app/scorer.py**

```python
import math
from datetime import datetime, timezone

def compute_score(stars: int, stars_gained: int,
                  last_updated: str, has_readme: bool, has_topics: bool) -> float:
    # Star 总数 (30%) — 对数归一化，10万星为满分
    star_score = min(math.log10(max(stars, 1)) / 5.0, 1.0)

    # Star 增长速度 (30%) — 对数归一化，1000 新增为满分
    growth_score = min(math.log10(max(stars_gained, 1)) / 3.0, 1.0)

    # 最近更新活跃度 (20%) — 7天内满分，逐渐衰减
    try:
        updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - updated).days
        recency_score = max(1.0 - days_ago / 180.0, 0.0)
    except (ValueError, TypeError):
        recency_score = 0.0

    # 项目质量 (20%)
    quality_score = 0.0
    if has_readme:
        quality_score += 0.5
    if has_topics:
        quality_score += 0.5

    total = (star_score * 0.3 + growth_score * 0.3 +
             recency_score * 0.2 + quality_score * 0.2)
    return round(min(total, 1.0), 4)

def update_all_scores():
    from app.database import get_connection
    import json
    conn = get_connection()
    rows = conn.execute("SELECT id, stars, stars_gained, last_updated, topics FROM projects").fetchall()
    for row in rows:
        topics = json.loads(row["topics"]) if row["topics"] else []
        score = compute_score(
            stars=row["stars"],
            stars_gained=row["stars_gained"],
            last_updated=row["last_updated"],
            has_readme=True,  # 如果有 readme_summary_zh 则认为有
            has_topics=len(topics) > 0
        )
        conn.execute("UPDATE projects SET score = ? WHERE id = ?", (score, row["id"]))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_scorer.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/scorer.py tests/test_scorer.py
git commit -m "feat: project scoring module with multi-factor ranking"
```

---

### Task 5: 后端 API 路由

**Files:**
- Create: `app/routers/projects.py`, `app/routers/keywords.py`, `app/routers/system.py`
- Modify: `app/main.py`（注册路由）
- Test: `tests/test_api.py`

- [ ] **Step 1: 写 API 测试**

```python
# tests/test_api.py
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from app import config as cfg

@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
        from app.database import init_db
        init_db()
        yield db_path

@pytest.fixture
def client(temp_db):
    from app.main import app
    return TestClient(app)

def test_get_status(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_projects" in data

def test_get_projects_empty(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []

def test_get_categories(client):
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3

def test_keywords_crud(client):
    # Create
    resp = client.post("/api/keywords", json={"keyword": "test-kw", "category": "ai"})
    assert resp.status_code == 200
    kw_id = resp.json()["id"]
    # List
    resp = client.get("/api/keywords")
    assert len(resp.json()) == 1
    # Delete
    resp = client.delete(f"/api/keywords/{kw_id}")
    assert resp.status_code == 200
    resp = client.get("/api/keywords")
    assert len(resp.json()) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 app/routers/system.py**

```python
import asyncio
from fastapi import APIRouter, BackgroundTasks
from app.database import get_connection
from app.models import StatusOut

router = APIRouter(prefix="/api")

_is_refreshing = False

@router.get("/status", response_model=StatusOut)
def get_status():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    last = conn.execute(
        "SELECT fetched_at FROM projects ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return StatusOut(
        total_projects=total,
        last_fetched=last[0] if last else "",
        is_refreshing=_is_refreshing
    )

@router.post("/refresh")
async def refresh(background_tasks: BackgroundTasks):
    global _is_refreshing
    if _is_refreshing:
        return {"message": "already refreshing"}
    _is_refreshing = True
    background_tasks.add_task(_do_refresh)
    return {"message": "refresh started"}

async def _do_refresh():
    global _is_refreshing
    try:
        from app.scraper import run_full_scrape
        from app.translator import translate_untranslated_projects
        from app.scorer import update_all_scores
        await run_full_scrape()
        await translate_untranslated_projects()
        update_all_scores()
    finally:
        _is_refreshing = False

@router.get("/categories")
def get_categories():
    from app.config import config
    conn = get_connection()
    results = []
    for key, info in config.CATEGORIES.items():
        count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE category = ?", (key,)
        ).fetchone()[0]
        results.append({"key": key, "name": info["name"], "count": count})
    # other
    other_count = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE category = 'other'"
    ).fetchone()[0]
    results.append({"key": "other", "name": "其他热门", "count": other_count})
    conn.close()
    return results

@router.get("/languages")
def get_languages():
    """获取数据库中所有出现过的编程语言列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT language FROM projects WHERE language != '' ORDER BY language"
    ).fetchall()
    conn.close()
    return [r["language"] for r in rows]
```

- [ ] **Step 4: 实现 app/routers/projects.py**

```python
import json
from fastapi import APIRouter, Query
from app.database import get_connection

router = APIRouter(prefix="/api")

@router.get("/projects")
def list_projects(
    category: str = Query(None),
    language: str = Query(None),
    sort: str = Query("score"),
    q: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_connection()
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if language:
        conditions.append("language = ?")
        params.append(language)
    if q:
        conditions.append("(repo_full_name LIKE ? OR description LIKE ? OR description_zh LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sort_map = {
        "score": "score DESC",
        "stars": "stars DESC",
        "stars_gained": "stars_gained DESC",
        "updated": "last_updated DESC",
    }
    order = sort_map.get(sort, "score DESC")

    offset = (page - 1) * page_size

    total = conn.execute(f"SELECT COUNT(*) FROM projects {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM projects {where} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    items = []
    for r in rows:
        topics = json.loads(r["topics"]) if r["topics"] else []
        items.append({
            "id": r["id"],
            "repo_full_name": r["repo_full_name"],
            "description": r["description"],
            "description_zh": r["description_zh"],
            "readme_summary_zh": r["readme_summary_zh"],
            "stars": r["stars"],
            "stars_gained": r["stars_gained"],
            "language": r["language"],
            "topics": topics,
            "category": r["category"],
            "repo_url": r["repo_url"],
            "score": r["score"],
            "last_updated": r["last_updated"],
            "fetched_at": r["fetched_at"],
        })
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": items}

@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    topics = json.loads(row["topics"]) if row["topics"] else []
    return {
        "id": row["id"],
        "repo_full_name": row["repo_full_name"],
        "description": row["description"],
        "description_zh": row["description_zh"],
        "readme_summary_zh": row["readme_summary_zh"],
        "stars": row["stars"],
        "stars_gained": row["stars_gained"],
        "language": row["language"],
        "topics": topics,
        "category": row["category"],
        "repo_url": row["repo_url"],
        "score": row["score"],
        "last_updated": row["last_updated"],
        "fetched_at": row["fetched_at"],
    }
```

- [ ] **Step 5: 实现 app/routers/keywords.py**

```python
from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.models import KeywordIn

router = APIRouter(prefix="/api")

@router.get("/keywords")
def list_keywords():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM keywords ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "keyword": r["keyword"],
             "category": r["category"], "created_at": r["created_at"]} for r in rows]

@router.post("/keywords")
def add_keyword(kw: KeywordIn):
    if not kw.keyword or len(kw.keyword) > 100:
        raise HTTPException(status_code=400, detail="Invalid keyword")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO keywords (keyword, category, created_at) VALUES (?, ?, datetime('now'))",
            (kw.keyword, kw.category)
        )
        conn.commit()
        kw_id = cur.lastrowid
    except Exception:
        conn.close()
        raise HTTPException(status_code=409, detail="Keyword already exists")
    conn.close()
    return {"id": kw_id, "keyword": kw.keyword, "category": kw.category}

@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
    conn.commit()
    conn.close()
    return {"message": "deleted"}
```

- [ ] **Step 6: 更新 app/main.py 注册所有路由**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db, is_db_empty
from app.routers import projects, keywords, system

app = FastAPI(title="GitHub Trending Viewer")

app.include_router(projects.router)
app.include_router(keywords.router)
app.include_router(system.router)

@app.on_event("startup")
async def startup():
    init_db()
    if is_db_empty():
        from app.routers.system import _do_refresh
        import asyncio
        asyncio.create_task(_do_refresh())
```

- [ ] **Step 7: 运行测试验证通过**

Run: `python -m pytest tests/test_api.py -v`
Expected: 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/routers/ app/main.py tests/test_api.py
git commit -m "feat: REST API routes for projects, keywords, and system"
```

---

### Task 6: 定时任务调度

**Files:**
- Create: `app/scheduler.py`
- Modify: `app/main.py`（启动调度器）

- [ ] **Step 1: 实现 app/scheduler.py**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import config

scheduler = AsyncIOScheduler()

def start_scheduler():
    from app.routers.system import _do_refresh
    scheduler.add_job(
        _do_refresh,
        trigger="cron",
        hour=config.UPDATE_HOUR,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
        timezone="Asia/Shanghai"
    )
    scheduler.start()
```

- [ ] **Step 2: 更新 app/main.py 启动调度器**

在 `startup` 函数中添加:
```python
from app.scheduler import start_scheduler
start_scheduler()
```

完整的 `startup`:
```python
@app.on_event("startup")
async def startup():
    init_db()
    from app.scheduler import start_scheduler
    start_scheduler()
    if is_db_empty():
        from app.routers.system import _do_refresh
        import asyncio
        asyncio.create_task(_do_refresh())
```

- [ ] **Step 3: Commit**

```bash
git add app/scheduler.py app/main.py
git commit -m "feat: daily scheduled refresh with APScheduler"
```

---

### Task 7: 前端页面 — HTML 结构

**Files:**
- Create: `static/index.html`

- [ ] **Step 1: 创建 static/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub 热门项目</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <div id="app">
        <!-- 加载页面 -->
        <div id="loading-screen" class="loading-screen">
            <div class="loading-spinner"></div>
            <p>正在初始化数据，请稍候...</p>
        </div>

        <!-- 主内容 -->
        <div id="main-content" class="main-content hidden">
            <!-- 顶部栏 -->
            <header class="header">
                <div class="header-left">
                    <h1 class="title">GitHub 热门项目</h1>
                    <span id="last-updated" class="last-updated"></span>
                </div>
                <div class="header-right">
                    <button id="btn-refresh" class="btn btn-refresh" title="刷新数据">
                        <svg class="icon-refresh" viewBox="0 0 24 24" width="18" height="18">
                            <path d="M17.65 6.35A7.96 7.96 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="currentColor"/>
                        </svg>
                        <span>刷新</span>
                    </button>
                    <button id="btn-theme" class="btn btn-theme" title="切换主题">
                        <svg class="icon-theme" viewBox="0 0 24 24" width="18" height="18">
                            <path d="M12 3a9 9 0 109 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 01-4.4 2.26 5.403 5.403 0 01-3.14-9.8c-.44-.06-.9-.1-1.36-.1z" fill="currentColor"/>
                        </svg>
                    </button>
                </div>
            </header>

            <!-- 板块切换 -->
            <nav class="category-tabs">
                <button class="tab active" data-category="ai">AI</button>
                <button class="tab" data-category="tools">实用工具</button>
                <button class="tab" data-category="devtools">开发工具</button>
                <button class="tab" data-category="other">其他热门</button>
            </nav>

            <!-- 筛选栏 -->
            <div class="filters">
                <div class="filter-group">
                    <label>语言</label>
                    <select id="filter-language">
                        <option value="">全部</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>排序</label>
                    <select id="filter-sort">
                        <option value="score">综合</option>
                        <option value="stars">Star 总数</option>
                        <option value="stars_gained">新增 Star</option>
                        <option value="updated">最近更新</option>
                    </select>
                </div>
                <div class="filter-group search-group">
                    <input type="text" id="search-input" placeholder="搜索项目...">
                </div>
                <button id="btn-add-keyword" class="btn btn-small" title="添加关注词">+ 添加关注词</button>
            </div>

            <!-- 项目卡片列表 -->
            <div id="project-list" class="project-list"></div>

            <!-- 加载更多 -->
            <div id="load-more" class="load-more hidden">
                <button id="btn-load-more" class="btn">加载更多</button>
            </div>

            <!-- 空状态 -->
            <div id="empty-state" class="empty-state hidden">
                <p>暂无项目数据</p>
            </div>
        </div>

        <!-- 添加关注词弹窗 -->
        <div id="keyword-modal" class="modal hidden">
            <div class="modal-content">
                <h3>添加关注词</h3>
                <input type="text" id="keyword-input" placeholder="输入关键词，如 ai agent">
                <select id="keyword-category">
                    <option value="ai">AI</option>
                    <option value="tools">实用工具</option>
                    <option value="devtools">开发工具</option>
                    <option value="other">其他</option>
                </select>
                <div class="modal-actions">
                    <button id="btn-save-keyword" class="btn btn-primary">保存</button>
                    <button id="btn-cancel-keyword" class="btn">取消</button>
                </div>
                <div id="keyword-list" class="keyword-list"></div>
            </div>
        </div>
    </div>
    <script src="/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat: HTML structure for frontend"
```

---

### Task 8: 前端页面 — CSS 样式

**Files:**
- Create: `static/css/style.css`

- [ ] **Step 1: 创建 static/css/style.css**

```css
/* ========== CSS Variables & Themes ========== */
:root {
    --bg-primary: #f5f7fa;
    --bg-secondary: #eef1f5;
    --bg-card: #ffffff;
    --text-primary: #1a1a2e;
    --text-secondary: #6b7280;
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --accent-light: rgba(99, 102, 241, 0.1);
    --border: #e5e7eb;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-hover: 0 10px 30px rgba(0,0,0,0.12);
    --radius: 12px;
    --radius-sm: 8px;
    --transition: 0.3s ease;
    --max-width: 1100px;
    --tag-bg: #eef2ff;
    --tag-text: #4f46e5;
    --star-color: #f59e0b;
    --gained-color: #10b981;
}

[data-theme="dark"] {
    --bg-primary: #0f172a;
    --bg-secondary: #1a2236;
    --bg-card: #1e293b;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --accent: #818cf8;
    --accent-hover: #a5b4fc;
    --accent-light: rgba(129, 140, 248, 0.15);
    --border: #334155;
    --shadow: 0 1px 3px rgba(0,0,0,0.2);
    --shadow-hover: 0 10px 30px rgba(0,0,0,0.3);
    --tag-bg: #312e81;
    --tag-text: #c7d2fe;
    --star-color: #fbbf24;
    --gained-color: #34d399;
}

/* ========== Reset & Base ========== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    transition: background var(--transition), color var(--transition);
}

.hidden { display: none !important; }

/* ========== Loading Screen ========== */
.loading-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 20px;
    color: var(--text-secondary);
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ========== Header ========== */
.main-content { max-width: var(--max-width); margin: 0 auto; padding: 24px 20px; }

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.title {
    font-size: 24px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), #ec4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.last-updated { font-size: 13px; color: var(--text-secondary); margin-left: 12px; }

.header-right { display: flex; gap: 8px; }

/* ========== Buttons ========== */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-card);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    transition: all var(--transition);
}

.btn:hover { border-color: var(--accent); color: var(--accent); }

.btn-primary {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

.btn-primary:hover { background: var(--accent-hover); }

.btn-small { padding: 6px 12px; font-size: 13px; }

.btn-refresh.refreshing .icon-refresh { animation: spin 1s linear infinite; }

/* ========== Category Tabs ========== */
.category-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
    border-bottom: 2px solid var(--border);
    padding-bottom: 0;
}

.tab {
    padding: 10px 20px;
    border: none;
    background: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 15px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all var(--transition);
}

.tab:hover { color: var(--text-primary); }

.tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
}

/* ========== Filters ========== */
.filters {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 24px;
    flex-wrap: wrap;
}

.filter-group {
    display: flex;
    align-items: center;
    gap: 6px;
}

.filter-group label {
    font-size: 13px;
    color: var(--text-secondary);
    white-space: nowrap;
}

.filter-group select,
.filter-group input {
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-card);
    color: var(--text-primary);
    font-size: 14px;
    outline: none;
    transition: border-color var(--transition);
}

.filter-group select:focus,
.filter-group input:focus { border-color: var(--accent); }

.search-group { flex: 1; min-width: 200px; }
.search-group input { width: 100%; }

/* ========== Project Cards ========== */
.project-list { display: flex; flex-direction: column; gap: 16px; }

.project-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    box-shadow: var(--shadow);
    transition: transform var(--transition), box-shadow var(--transition);
}

.project-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-hover);
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
}

.card-stats { display: flex; gap: 12px; align-items: center; flex-shrink: 0; }

.star-count {
    font-weight: 600;
    color: var(--star-color);
    font-size: 15px;
}

.star-gained {
    color: var(--gained-color);
    font-size: 13px;
    font-weight: 500;
}

.card-language {
    font-size: 13px;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    padding: 2px 10px;
    border-radius: 12px;
}

.card-repo a {
    font-size: 17px;
    font-weight: 600;
    color: var(--accent);
    text-decoration: none;
}

.card-repo a:hover { text-decoration: underline; }

.card-description {
    color: var(--text-primary);
    font-size: 15px;
    margin: 8px 0;
    line-height: 1.7;
}

/* ========== README Toggle ========== */
.readme-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 12px 0 4px;
    padding: 6px 0;
    border: none;
    background: none;
    color: var(--accent);
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
}

.readme-toggle:hover { opacity: 0.8; }

.readme-content {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.4s ease, opacity 0.3s ease;
    opacity: 0;
}

.readme-content.expanded {
    max-height: 500px;
    opacity: 1;
}

.readme-text {
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    font-size: 14px;
    line-height: 1.8;
    color: var(--text-secondary);
    border-left: 3px solid var(--accent);
}

/* ========== Tags ========== */
.card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
    flex-wrap: wrap;
    gap: 8px;
}

.card-tags { display: flex; gap: 6px; flex-wrap: wrap; }

.tag {
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 12px;
    background: var(--tag-bg);
    color: var(--tag-text);
    cursor: pointer;
    transition: opacity var(--transition);
}

.tag:hover { opacity: 0.7; }

.card-time { font-size: 12px; color: var(--text-secondary); }

/* ========== Load More & Empty ========== */
.load-more { text-align: center; padding: 24px 0; }

.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
    font-size: 16px;
}

/* ========== Modal ========== */
.modal {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(4px);
}

.modal-content {
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 28px;
    width: 90%;
    max-width: 460px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

.modal-content h3 { margin-bottom: 16px; font-size: 18px; }

.modal-content input,
.modal-content select {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 14px;
    margin-bottom: 12px;
    outline: none;
}

.modal-content input:focus,
.modal-content select:focus { border-color: var(--accent); }

.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-bottom: 16px; }

.keyword-list { display: flex; flex-direction: column; gap: 8px; }

.keyword-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    font-size: 14px;
}

.keyword-delete {
    border: none;
    background: none;
    color: #ef4444;
    cursor: pointer;
    font-size: 16px;
    padding: 2px 6px;
}

.keyword-delete:hover { opacity: 0.7; }

/* ========== Responsive ========== */
@media (max-width: 640px) {
    .header { flex-direction: column; gap: 12px; align-items: flex-start; }
    .filters { flex-direction: column; align-items: stretch; }
    .filter-group { width: 100%; }
    .search-group { min-width: auto; }
    .card-header { flex-direction: column; gap: 8px; }
    .project-card { padding: 16px; }
}
```

- [ ] **Step 2: Commit**

```bash
git add static/css/style.css
git commit -m "feat: CSS styles with dark/light theme and animations"
```

---

### Task 9: 前端页面 — JavaScript 交互

**Files:**
- Create: `static/js/app.js`

- [ ] **Step 1: 创建 static/js/app.js**

```javascript
// ========== State ==========
const state = {
    category: 'ai',
    language: '',
    sort: 'score',
    query: '',
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    theme: localStorage.getItem('theme') || 'light'
};

// ========== API Helper ==========
async function api(path, options = {}) {
    const resp = await fetch(`/api${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

// ========== Init ==========
async function init() {
    applyTheme();
    await checkStatus();
    await loadLanguages();
    await loadProjects();
    setupEventListeners();
}

async function checkStatus() {
    try {
        const status = await api('/status');
        const loading = document.getElementById('loading-screen');
        const main = document.getElementById('main-content');
        if (status.total_projects === 0 && status.is_refreshing) {
            loading.classList.remove('hidden');
            main.classList.add('hidden');
            // Poll until data is ready
            const poll = setInterval(async () => {
                const s = await api('/status');
                if (s.total_projects > 0 || !s.is_refreshing) {
                    clearInterval(poll);
                    loading.classList.add('hidden');
                    main.classList.remove('hidden');
                    await loadProjects();
                }
            }, 3000);
        } else {
            loading.classList.add('hidden');
            main.classList.remove('hidden');
        }
        if (status.last_fetched) {
            document.getElementById('last-updated').textContent =
                `最后更新：${timeAgo(status.last_fetched)}`;
        }
    } catch (e) {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
    }
}

// ========== Load Languages Dropdown ==========
async function loadLanguages() {
    try {
        const langs = await api('/languages');
        const sel = document.getElementById('filter-language');
        langs.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            sel.appendChild(opt);
        });
    } catch (e) { /* ignore */ }
}

// ========== Load Projects ==========
async function loadProjects(append = false) {
    if (state.loading) return;
    state.loading = true;

    const params = new URLSearchParams({
        category: state.category,
        sort: state.sort,
        page: state.page,
        page_size: state.pageSize
    });
    if (state.language) params.set('language', state.language);
    if (state.query) params.set('q', state.query);

    try {
        const data = await api(`/projects?${params}`);
        state.total = data.total;
        const list = document.getElementById('project-list');
        const empty = document.getElementById('empty-state');
        const loadMore = document.getElementById('load-more');

        if (!append) list.innerHTML = '';

        if (data.items.length === 0 && !append) {
            empty.classList.remove('hidden');
            loadMore.classList.add('hidden');
        } else {
            empty.classList.add('hidden');
            data.items.forEach(p => list.appendChild(renderCard(p)));
            // Show/hide load more
            const shown = list.children.length;
            if (shown < state.total) {
                loadMore.classList.remove('hidden');
            } else {
                loadMore.classList.add('hidden');
            }
        }
    } catch (e) {
        console.error('Failed to load projects:', e);
    }
    state.loading = false;
}

// ========== Render Card ==========
function renderCard(p) {
    const card = document.createElement('div');
    card.className = 'project-card';

    const gainedHtml = p.stars_gained > 0
        ? `<span class="star-gained">+${formatStars(p.stars_gained)}</span>` : '';
    const langHtml = p.language
        ? `<span class="card-language">${p.language}</span>` : '';
    const desc = p.description_zh || p.description || '暂无描述';
    const readmeSummary = p.readme_summary_zh || '';
    const tags = (p.topics || []).slice(0, 5);
    const tagsHtml = tags.map(t =>
        `<span class="tag" data-topic="${t}">#${t}</span>`
    ).join('');

    card.innerHTML = `
        <div class="card-header">
            <div class="card-repo">
                <a href="${p.repo_url}" target="_blank" rel="noopener">${p.repo_full_name}</a>
            </div>
            <div class="card-stats">
                <span class="star-count">\u2B50 ${formatStars(p.stars)}</span>
                ${gainedHtml}
                ${langHtml}
            </div>
        </div>
        <div class="card-description">${desc}</div>
        ${readmeSummary ? `
            <button class="readme-toggle" onclick="toggleReadme(this)">
                \uD83D\uDCD6 README 摘要 <span>\u25BC</span>
            </button>
            <div class="readme-content">
                <div class="readme-text">${readmeSummary}</div>
            </div>
        ` : ''}
        <div class="card-footer">
            <div class="card-tags">${tagsHtml}</div>
            <span class="card-time">${p.last_updated ? timeAgo(p.last_updated) : ''}</span>
        </div>
    `;

    // Tag click => filter
    card.querySelectorAll('.tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const topic = tag.dataset.topic;
            document.getElementById('search-input').value = topic;
            state.query = topic;
            state.page = 1;
            loadProjects();
        });
    });

    return card;
}

// ========== Utilities ==========
function formatStars(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
    if (diff < 2592000) return Math.floor(diff / 86400) + ' 天前';
    if (diff < 31536000) return Math.floor(diff / 2592000) + ' 个月前';
    return Math.floor(diff / 31536000) + ' 年前';
}

// ========== Event Listeners ==========
function setupEventListeners() {
    // Category tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelector('.tab.active').classList.remove('active');
            tab.classList.add('active');
            state.category = tab.dataset.category;
            state.page = 1;
            loadProjects();
        });
    });

    // Language filter
    document.getElementById('filter-language').addEventListener('change', (e) => {
        state.language = e.target.value;
        state.page = 1;
        loadProjects();
    });

    // Sort filter
    document.getElementById('filter-sort').addEventListener('change', (e) => {
        state.sort = e.target.value;
        state.page = 1;
        loadProjects();
    });

    // Search with debounce
    let searchTimer;
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.query = e.target.value.trim();
            state.page = 1;
            loadProjects();
        }, 300);
    });

    // Refresh button
    document.getElementById('btn-refresh').addEventListener('click', onRefresh);

    // Theme toggle
    document.getElementById('btn-theme').addEventListener('click', toggleTheme);

    // Load more
    document.getElementById('btn-load-more').addEventListener('click', () => {
        state.page++;
        loadProjects(true);
    });

    // Keyword modal
    document.getElementById('btn-add-keyword').addEventListener('click', showKeywordModal);
    document.getElementById('btn-save-keyword').addEventListener('click', saveKeyword);
    document.getElementById('btn-cancel-keyword').addEventListener('click', () => {
        document.getElementById('keyword-modal').classList.add('hidden');
    });

    // Close modal on backdrop click
    document.getElementById('keyword-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.add('hidden');
        }
    });
}

// ========== Theme ==========
function applyTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
}

function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', state.theme);
    applyTheme();
}

// ========== Refresh ==========
async function onRefresh() {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('refreshing');
    btn.disabled = true;
    try {
        await api('/refresh', { method: 'POST' });
        // Poll status until refresh completes
        const poll = setInterval(async () => {
            const s = await api('/status');
            if (!s.is_refreshing) {
                clearInterval(poll);
                btn.classList.remove('refreshing');
                btn.disabled = false;
                document.getElementById('last-updated').textContent =
                    `最后更新：${timeAgo(s.last_fetched)}`;
                state.page = 1;
                await loadLanguages();
                await loadProjects();
            }
        }, 5000);
    } catch (e) {
        btn.classList.remove('refreshing');
        btn.disabled = false;
    }
}

// ========== README Toggle ==========
function toggleReadme(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('span');
    content.classList.toggle('expanded');
    arrow.textContent = content.classList.contains('expanded') ? '\u25B2' : '\u25BC';
}

// ========== Keyword Modal ==========
async function showKeywordModal() {
    document.getElementById('keyword-modal').classList.remove('hidden');
    document.getElementById('keyword-input').value = '';
    await loadKeywords();
}

async function loadKeywords() {
    try {
        const keywords = await api('/keywords');
        const list = document.getElementById('keyword-list');
        list.innerHTML = keywords.map(kw => `
            <div class="keyword-item">
                <span>${kw.keyword} (${kw.category})</span>
                <button class="keyword-delete" onclick="deleteKeyword(${kw.id})">\u2715</button>
            </div>
        `).join('');
    } catch (e) { /* ignore */ }
}

async function saveKeyword() {
    const keyword = document.getElementById('keyword-input').value.trim();
    const category = document.getElementById('keyword-category').value;
    if (!keyword) return;
    try {
        await api('/keywords', {
            method: 'POST',
            body: JSON.stringify({ keyword, category })
        });
        document.getElementById('keyword-input').value = '';
        await loadKeywords();
    } catch (e) {
        alert('添加失败，关键词可能已存在');
    }
}

async function deleteKeyword(id) {
    try {
        await api(`/keywords/${id}`, { method: 'DELETE' });
        await loadKeywords();
    } catch (e) { /* ignore */ }
}

// ========== Start ==========
document.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 2: Commit**

```bash
git add static/js/app.js
git commit -m "feat: frontend JavaScript with all interactions"
```

---

### Task 10: 连接前端 + 完善 main.py

**Files:**
- Modify: `app/main.py`（挂载静态文件）

- [ ] **Step 1: 更新 app/main.py 挂载静态文件**

在所有路由注册之后添加：
```python
import os
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

- [ ] **Step 2: 本地测试验证**

Run: `cd github-trending-viewer && python -m uvicorn app.main:app --reload --port 8000`
打开 `http://localhost:8000`，确认页面能正常加载。

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: serve static frontend files via FastAPI"
```

---

### Task 11: Docker 部署

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.env.example`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
services:
  github-trending:
    build: .
    container_name: github-trending
    ports:
      - "127.0.0.1:8088:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

- [ ] **Step 3: 创建 .env 文件（从 .env.example 复制并填入真实 key）**

```bash
cp .env.example .env
# 编辑 .env，填入真实的 API_KEY
```

- [ ] **Step 4: 构建并启动**

Run: `docker-compose up --build -d`
验证: `curl http://localhost:8088/api/status`
Expected: 返回 JSON，包含 `total_projects`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker deployment with docker-compose"
```

---

### Task 12: 桌面快捷方式

**Files:**
- Create: `launch.vbs`

- [ ] **Step 1: 创建 launch.vbs**

```vbscript
Set WshShell = CreateObject("WScript.Shell")

' 检查 Docker 容器是否运行
Set exec = WshShell.Exec("docker ps --filter name=github-trending --format ""{{.Names}}""")
output = exec.StdOut.ReadAll()

If InStr(output, "github-trending") = 0 Then
    ' 启动容器
    WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
    WshShell.Run "docker-compose up -d", 0, True
    ' 等待服务就绪
    WScript.Sleep 5000
    Dim attempts
    attempts = 0
    Do While attempts < 30
        On Error Resume Next
        Set http = CreateObject("MSXML2.XMLHTTP")
        http.Open "GET", "http://localhost:8088/api/status", False
        http.Send
        If http.Status = 200 Then Exit Do
        On Error GoTo 0
        WScript.Sleep 2000
        attempts = attempts + 1
    Loop
End If

' 尝试用 Edge --app 模式打开
WshShell.Run "msedge --app=http://localhost:8088 --window-size=1200,800", 1, False
```

- [ ] **Step 2: 测试快捷方式**

双击 `launch.vbs`，确认：
1. Docker 容器启动（如果未运行）
2. Edge 以无边框窗口打开页面

- [ ] **Step 3: Commit**

```bash
git add launch.vbs
git commit -m "feat: desktop shortcut with VBS launcher script"
```

---

### Task 13: 端到端集成测试

- [ ] **Step 1: 运行所有单元测试**

Run: `python -m pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 2: Docker 集成测试**

```bash
docker-compose up --build -d
# 等待启动
sleep 10
# 测试 API
curl http://localhost:8088/api/status
curl http://localhost:8088/api/categories
curl "http://localhost:8088/api/projects?category=ai"
# 测试前端页面
curl http://localhost:8088/ | head -5
```

Expected: 所有请求返回正常数据，前端 HTML 正常返回

- [ ] **Step 3: 手动触发刷新测试**

```bash
curl -X POST http://localhost:8088/api/refresh
# 等待 30 秒后检查
curl "http://localhost:8088/api/projects?category=ai" | python -m json.tool | head -20
```

Expected: 项目数据已填充，包含中文翻译

- [ ] **Step 4: 浏览器验证**

打开 `http://localhost:8088`：
1. 页面加载正常
2. 卡片显示中文简介
3. 板块切换正常
4. 深色/浅色主题切换正常
5. 搜索和筛选正常

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete GitHub trending viewer with Chinese translations"
```
