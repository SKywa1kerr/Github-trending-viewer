import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from app import config as cfg
from app.database import get_connection


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


def test_favorites_api_returns_translation_state_fields(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_attempts) "
        "VALUES (?, ?, ?, ?)",
        ("favorite/repo", "https://github.com/favorite/repo", "failed", 3),
    )
    project_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?",
        ("favorite/repo",),
    ).fetchone()["id"]
    conn.execute("INSERT INTO favorites (project_id) VALUES (?)", (project_id,))
    conn.commit()
    conn.close()

    resp = client.get("/api/favorites")
    assert resp.status_code == 200

    item = resp.json()["items"][0]
    assert item["translation_status"] == "failed"
    assert item["translation_attempts"] == 3
