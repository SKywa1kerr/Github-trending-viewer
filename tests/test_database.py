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
