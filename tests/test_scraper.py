import pytest
import os

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
    assert "q=topic:machine-learning" in url
    assert "sort=stars" in url


def test_build_search_url_with_keyword():
    url = build_search_url(keyword="ai agent", sort="stars")
    assert "q=ai+agent" in url


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
