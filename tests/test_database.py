import os
import tempfile
import pytest
from app.database import get_connection, init_db, is_db_empty
from app import config as cfg


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_path = os.path.join(os.getcwd(), "data", "test_database.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_init_db_creates_tables():
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t["name"] for t in tables}
    assert "projects" in table_names
    assert "keywords" in table_names
    conn.close()


def test_init_db_adds_translation_state_columns():
    conn = get_connection()
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
    }
    conn.close()

    expected = {
        "translation_status",
        "translation_attempts",
        "translation_next_retry_at",
        "translation_error",
        "source_signature",
        "translated_signature",
        "translation_provider",
        "translation_model",
        "readme_fetched_at",
    }
    assert expected.issubset(columns)


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


def test_init_db_creates_project_query_indexes():
    conn = get_connection()
    indexes = {
        row["name"] for row in conn.execute("PRAGMA index_list(projects)").fetchall()
    }
    conn.close()

    assert {
        "idx_projects_category_score",
        "idx_projects_language_score",
        "idx_projects_translation_queue",
        "idx_projects_last_updated",
    }.issubset(indexes)
