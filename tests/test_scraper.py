import pytest
import os
import asyncio
import json
from contextlib import closing
from urllib.parse import parse_qs, urlsplit

from app import config as cfg
from app.database import get_connection, init_db
from app.scraper import parse_trending_html, build_search_url, save_projects


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_path = os.path.join(os.getcwd(), "data", "test_scraper.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_build_search_url_with_topic():
    url = build_search_url(topic="machine-learning", sort="stars")
    assert parse_qs(urlsplit(url).query) == {
        "q": ["topic:machine-learning"], "sort": ["stars"], "per_page": ["30"],
    }


def test_build_search_url_with_keyword():
    url = build_search_url(keyword="ai agent", sort="stars")
    assert "q=ai+agent" in url


@pytest.mark.parametrize("keyword", [
    "language:C++", "C#", "R&D", "AI & tools", "中文 topic:llm", "100% coverage",
])
def test_search_query_preserves_special_characters(keyword):
    url = urlsplit(build_search_url(keyword=keyword))
    assert parse_qs(url.query) == {
        "q": [keyword], "sort": ["stars"], "per_page": ["30"],
    }
    assert url.fragment == ""


def test_parse_trending_html_empty():
    result = parse_trending_html("<html><body></body></html>")
    assert result == []


def test_save_projects_marks_changed_rows_pending_translation():
    save_projects([
        {
            "repo_full_name": "owner/repo",
            "description": "first description",
            "stars": 10,
            "stars_gained": 1,
            "language": "Python",
            "topics": ["ai"],
            "repo_url": "https://github.com/owner/repo",
            "last_updated": "2026-04-12 10:00:00",
        }
    ], "ai")

    conn = get_connection()
    conn.execute(
        "UPDATE projects SET translation_status = 'done', description_zh = ?, translated_signature = ? "
        "WHERE repo_full_name = ?",
        ("中文简介", "old-signature", "owner/repo"),
    )
    conn.commit()
    conn.close()

    save_projects([
        {
            "repo_full_name": "owner/repo",
            "description": "updated description",
            "stars": 15,
            "stars_gained": 2,
            "language": "Python",
            "topics": ["ai"],
            "repo_url": "https://github.com/owner/repo",
            "last_updated": "2026-04-12 12:00:00",
        }
    ], "ai")

    conn = get_connection()
    row = conn.execute(
        "SELECT description, translation_status, translation_error, translation_next_retry_at "
        "FROM projects WHERE repo_full_name = ?",
        ("owner/repo",),
    ).fetchone()
    conn.close()

    assert row["description"] == "updated description"
    assert row["translation_status"] == "pending"
    assert row["translation_error"] == ""
    assert row["translation_next_retry_at"] == ""


@pytest.fixture
def known_project():
    project = {
        "repo_full_name": "owner/known", "description": "A useful project",
        "stars": 100, "stars_gained": 5, "language": "Python", "topics": ["cli"],
        "repo_url": "https://github.com/owner/known", "last_updated": "2026-09-01T10:00:00Z",
    }
    save_projects([project], "devtools")
    return project


@pytest.mark.parametrize("metadata", [{}, {"last_updated": "", "topics": None}])
def test_save_projects_preserves_unknown_metadata(known_project, metadata):
    partial = {key: value for key, value in known_project.items() if key not in ("topics", "last_updated")}
    save_projects([{**partial, **metadata, "stars": 120}], "other")

    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM projects WHERE repo_full_name = 'owner/known'").fetchone()
    assert json.loads(row["topics"]) == ["cli"]
    assert row["last_updated"] == known_project["last_updated"]
    assert row["stars"] == 120


def test_save_projects_accepts_explicit_metadata_updates(known_project):
    save_projects([{**known_project, "topics": [], "last_updated": "2026-09-12T10:00:00Z"}], "devtools")

    with closing(get_connection()) as conn:
        row = conn.execute("SELECT topics, last_updated FROM projects").fetchone()
    assert json.loads(row["topics"]) == []
    assert row["last_updated"] == "2026-09-12T10:00:00Z"


def test_failed_topic_fetch_keeps_existing_metadata(known_project, monkeypatch):
    from app.github_client import GitHubRequestError
    from app.scraper import run_full_scrape

    async def trending_html(url, **kwargs):
        return '<article class="Box-row"><h2><a href="/owner/known">known</a></h2>' \
            '<p>A useful project</p><a href="/owner/known/stargazers">120</a></article>'

    async def unavailable_topics(url, **kwargs):
        raise GitHubRequestError("GitHub request failed with status 503")

    monkeypatch.setattr(cfg.config, "CATEGORIES", {})
    monkeypatch.setattr("app.scraper.github_get_text", trending_html)
    monkeypatch.setattr("app.scraper.github_get_json", unavailable_topics)
    asyncio.run(run_full_scrape())

    with closing(get_connection()) as conn:
        row = conn.execute("SELECT topics, last_updated, stars FROM projects").fetchone()
    assert json.loads(row["topics"]) == ["cli"]
    assert row["last_updated"] == known_project["last_updated"]
    assert row["stars"] == 120


@pytest.mark.parametrize("transport_error", [False, True], ids=["http-status", "timeout"])
def test_online_search_reports_github_failure(monkeypatch, transport_error):
    import httpx
    from fastapi.testclient import TestClient
    from app.github_client import GitHubRequestError
    from app.main import app

    async def unavailable_search(url, **kwargs):
        if transport_error:
            raise httpx.ConnectTimeout("GitHub connection timed out")
        raise GitHubRequestError("GitHub request failed with status 403")

    monkeypatch.setattr("app.scraper.github_get_json", unavailable_search)
    response = TestClient(app, raise_server_exceptions=False).get("/api/search/github", params={"q": "language:C++"})
    assert response.status_code == 502


def test_online_search_keeps_legitimate_empty_results(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    async def empty_search(url, **kwargs):
        return {"items": []}

    monkeypatch.setattr("app.scraper.github_get_json", empty_search)
    response = TestClient(app).get("/api/search/github", params={"q": "no-matching-project"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_refresh_reports_failure_when_all_sources_fail(known_project, monkeypatch):
    from app.github_client import GitHubRequestError
    from app.routers.system import _do_refresh
    from app.state_store import get_runtime_state, set_runtime_state

    async def unavailable_source(url, **kwargs):
        raise GitHubRequestError("GitHub request failed with status 503")

    previous_completed = "2026-09-01 00:00:00"
    set_runtime_state(last_refresh_completed_at=previous_completed)
    monkeypatch.setattr(cfg.config, "CATEGORIES", {"ai": {"topics": ["llm"]}})
    monkeypatch.setattr("app.scraper.github_get_text", unavailable_source)
    monkeypatch.setattr("app.scraper.github_get_json", unavailable_source)
    monkeypatch.setattr("app.translator.start_translation_worker", lambda: True)
    asyncio.run(_do_refresh())

    state = get_runtime_state("last_refresh_error", "last_refresh_completed_at", "is_refreshing")
    assert state["last_refresh_error"]
    assert state["last_refresh_completed_at"] == previous_completed
    assert state["is_refreshing"] == "0"
    with closing(get_connection()) as conn:
        assert conn.execute("SELECT stars FROM projects").fetchone()[0] == known_project["stars"]


def test_refresh_keeps_results_from_available_sources(monkeypatch):
    from app.github_client import GitHubRequestError
    from app.routers.system import _do_refresh
    from app.state_store import get_runtime_state

    async def unavailable_trending(url, **kwargs):
        raise GitHubRequestError("GitHub request failed with status 503")

    async def available_search(url, **kwargs):
        return {"items": [{
            "full_name": "available/repo", "description": "Available source", "stargazers_count": 42,
            "language": "Python", "html_url": "https://github.com/available/repo", "topics": ["llm"],
            "updated_at": "2026-09-12T00:00:00Z",
        }]}

    monkeypatch.setattr(cfg.config, "CATEGORIES", {"ai": {"topics": ["llm"]}})
    monkeypatch.setattr("app.scraper.github_get_text", unavailable_trending)
    monkeypatch.setattr("app.scraper.github_get_json", available_search)
    monkeypatch.setattr("app.translator.start_translation_worker", lambda: True)
    asyncio.run(_do_refresh())

    state = get_runtime_state("last_refresh_error", "last_refresh_completed_at")
    assert state["last_refresh_error"] == ""
    assert state["last_refresh_completed_at"]
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT repo_full_name, stars FROM projects").fetchone()
    assert tuple(row) == ("available/repo", 42)


def test_classify_project_prefers_topics_over_description():
    from app.scraper import classify_project

    assert classify_project(["cli"], "An AI agent framework") == "devtools"
    assert classify_project(["LLM"], "") == "ai"


def test_classify_project_uses_whole_word_description_matching():
    from app.scraper import classify_project

    # substrings must not match: toolkit != tool, clients != cli
    assert classify_project([], "A toolkit for building clients") is None
    assert classify_project([], "Stooling around") is None
    assert classify_project([], "Fast HTTP client library") == "devtools"
    assert classify_project([], "Lightweight CLI for notes") == "devtools"
    assert classify_project([], "Self hosted photo manager") == "tools"
    assert classify_project([], "Open source LLM playground") == "ai"
    assert classify_project([], "A tool for everything") == "tools"


def test_reclassify_projects_only_touches_other_category():
    from app.scraper import _reclassify_projects

    save_projects([
        {"repo_full_name": "a/toolkit", "description": "A toolkit for clients", "stars": 1, "stars_gained": 0,
         "language": "", "topics": [], "repo_url": "https://github.com/a/toolkit", "last_updated": ""},
        {"repo_full_name": "b/agent", "description": "An autonomous agent", "stars": 1, "stars_gained": 0,
         "language": "", "topics": [], "repo_url": "https://github.com/b/agent", "last_updated": ""},
    ], "other")

    _reclassify_projects()

    conn = get_connection()
    rows = {r["repo_full_name"]: r["category"] for r in conn.execute("SELECT repo_full_name, category FROM projects")}
    conn.close()

    assert rows["a/toolkit"] == "other"
    assert rows["b/agent"] == "ai"
