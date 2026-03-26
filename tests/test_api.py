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
