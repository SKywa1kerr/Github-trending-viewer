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
