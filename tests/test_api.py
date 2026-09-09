import os
import tempfile
import asyncio
import hashlib
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app import config as cfg
from app.database import get_connection


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_path = os.path.join(os.getcwd(), "data", "test_api.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
    # Never hit the real model gateway from tests.
    monkeypatch.setattr(cfg.config, "AI_MODEL_CHECK", False)
    from app.routers.system import reset_model_check_cache
    reset_model_check_cache()
    from app.database import init_db
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(temp_db):
    from app.main import app
    return TestClient(app)


def test_get_status(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_projects" in data


def test_get_status_reports_data_freshness(client, monkeypatch):
    monkeypatch.setattr(cfg.config, "DATA_STALE_HOURS", 72)

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, fetched_at) VALUES (?, ?, ?)",
        ("old/repo", "https://github.com/old/repo", "2000-01-01 00:00:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["is_data_stale"] is True
    assert data["data_stale_after_hours"] == 72
    assert data["data_age_hours"] > 72


def test_get_health_reports_config_and_database_state(client, monkeypatch):
    from app.state_store import set_runtime_state

    monkeypatch.setattr(cfg.config, "API_KEY", "")
    monkeypatch.setattr(cfg.config, "GITHUB_TOKEN", "")
    monkeypatch.setattr(cfg.config, "PROXY", "http://host.docker.internal:7897")
    set_runtime_state(last_refresh_error="GitHub timeout")

    resp = client.get("/api/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "warning"
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["model_api_key"]["ok"] is False
    assert data["checks"]["github_token"]["ok"] is False
    assert data["checks"]["proxy"]["value"] == "http://host.docker.internal:7897"
    assert data["checks"]["last_refresh"]["ok"] is False
    assert "API_KEY is not configured" in data["problems"]
    assert "Last refresh failed: GitHub timeout" in data["problems"]


def test_get_health_reports_stale_project_data(client, monkeypatch):
    monkeypatch.setattr(cfg.config, "DATA_STALE_HOURS", 72)

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, fetched_at) VALUES (?, ?, ?)",
        ("old/repo", "https://github.com/old/repo", "2000-01-01 00:00:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["checks"]["data_freshness"]["ok"] is False
    assert data["checks"]["data_freshness"]["stale_after_hours"] == 72
    assert "Project data is stale" in data["problems"]


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


def test_get_status_includes_translation_counts(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("pending/repo", "https://github.com/pending/repo", "pending"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("processing/repo", "https://github.com/processing/repo", "processing"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("retry/repo", "https://github.com/retry/repo", "retry"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("failed/repo", "https://github.com/failed/repo", "failed"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("done/repo", "https://github.com/done/repo", "done"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/status")
    data = resp.json()

    assert data["translation_pending"] == 1
    assert data["translation_processing"] == 1
    assert data["translation_retry"] == 1
    assert data["translation_failed"] == 1
    assert data["translation_done"] == 1


def test_projects_api_returns_translation_state_fields(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_attempts) "
        "VALUES (?, ?, ?, ?)",
        ("pending/repo", "https://github.com/pending/repo", "retry", 2),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["translation_status"] == "retry"
    assert item["translation_attempts"] == 2


def test_retry_failed_translations_marks_retry_projects_pending(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_error, translation_attempts) "
        "VALUES (?, ?, ?, ?, ?)",
        ("retry/repo", "https://github.com/retry/repo", "retry", "timeout", 2),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_error, translation_attempts) "
        "VALUES (?, ?, ?, ?, ?)",
        ("failed/repo", "https://github.com/failed/repo", "failed", "parse error", 3),
    )
    conn.commit()
    conn.close()

    resp = client.post("/api/translations/retry-failed")
    assert resp.status_code == 200

    conn = get_connection()
    rows = conn.execute(
        "SELECT repo_full_name, translation_status, translation_error, translation_attempts "
        "FROM projects ORDER BY repo_full_name"
    ).fetchall()
    conn.close()

    assert [
        (row["repo_full_name"], row["translation_status"], row["translation_error"], row["translation_attempts"])
        for row in rows
    ] == [
        ("failed/repo", "pending", "", 0),
        ("retry/repo", "pending", "", 0),
    ]


def test_import_project_creates_row_that_can_be_favorited(client):
    payload = {
        "repo_full_name": "owner/new-repo",
        "description": "Imported from GitHub search",
        "stars": 321,
        "stars_gained": 12,
        "language": "Python",
        "topics": ["ai", "agent"],
        "repo_url": "https://github.com/owner/new-repo",
        "last_updated": "2026-04-13T08:00:00Z",
    }

    resp = client.post("/api/projects/import", json=payload)
    assert resp.status_code == 200

    imported = resp.json()
    assert imported["repo_full_name"] == "owner/new-repo"
    assert imported["id"] > 0
    assert imported["is_favorited"] is False

    favorite_resp = client.post(f"/api/favorites/{imported['id']}")
    assert favorite_resp.status_code == 200

    details_resp = client.get(f"/api/projects/{imported['id']}")
    assert details_resp.status_code == 200
    assert details_resp.json()["is_favorited"] is True


def test_get_status_reads_persisted_runtime_state(client):
    from app.state_store import set_runtime_state

    set_runtime_state(
        is_refreshing="1",
        refresh_stage="scraping",
        refresh_detail="loading data",
        progress_total="4",
        progress_done="2",
        last_refresh_error="GitHub request failed",
        last_refresh_failed_at="2026-06-02 04:00:00",
        last_refresh_completed_at="2026-06-02 03:00:00",
    )

    resp = client.get("/api/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["is_refreshing"] is True
    assert data["refresh_stage"] == "scraping"
    assert data["refresh_detail"] == "loading data"
    assert data["translate_total"] == 4
    assert data["translate_done"] == 2
    assert data["last_refresh_error"] == "GitHub request failed"
    assert data["last_refresh_failed_at"] == "2026-06-02 04:00:00"
    assert data["last_refresh_completed_at"] == "2026-06-02 03:00:00"


def test_recommendations_uses_persisted_cache_metadata(client):
    from app.state_store import set_runtime_state

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, language, topics, description) VALUES (?, ?, ?, ?, ?)",
        ("favorite/repo", "https://github.com/favorite/repo", "Python", '["ai"]', "fav"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, language, topics, description) VALUES (?, ?, ?, ?, ?)",
        ("candidate/repo", "https://github.com/candidate/repo", "Python", '["ai"]', "candidate"),
    )
    favorite_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?",
        ("favorite/repo",),
    ).fetchone()["id"]
    candidate_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?",
        ("candidate/repo",),
    ).fetchone()["id"]
    conn.execute("INSERT INTO favorites (project_id) VALUES (?)", (favorite_id,))
    conn.execute(
        "INSERT INTO recommendations (project_id, reason, score, generated_at) VALUES (?, ?, ?, ?)",
        (candidate_id, "cached reason", 91.0, "2026-04-13 08:00:00"),
    )
    conn.commit()
    conn.close()

    fav_hash = hashlib.md5(str(favorite_id).encode()).hexdigest()
    set_runtime_state(
        recommendation_fav_hash=fav_hash,
        recommendation_generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200

    data = resp.json()
    assert data["message"] == "ok"
    assert data["items"][0]["repo_full_name"] == "candidate/repo"
    assert data["items"][0]["recommendation_reason"] == "cached reason"


def test_recommendations_uses_shared_ai_client_when_cache_misses(client, monkeypatch):
    from app.state_store import set_runtime_state

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, language, topics, description) VALUES (?, ?, ?, ?, ?)",
        ("favorite/repo", "https://github.com/favorite/repo", "Python", '["ai"]', "fav"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, language, topics, description) VALUES (?, ?, ?, ?, ?)",
        ("candidate/repo", "https://github.com/candidate/repo", "Python", '["ai"]', "candidate"),
    )
    favorite_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?",
        ("favorite/repo",),
    ).fetchone()["id"]
    conn.execute("INSERT INTO favorites (project_id) VALUES (?)", (favorite_id,))
    conn.commit()
    conn.close()
    set_runtime_state(recommendation_fav_hash="", recommendation_generated_at="")

    class FakeAIClient:
        async def chat_completion(self, messages, temperature=0.3, max_tokens=None, **kwargs):
            return {
                "choices": [{
                    "message": {
                        "content": '{"recommendations": [{"repo":"candidate/repo","reason":"AI reason","score":88}]}',
                    },
                }],
            }

    monkeypatch.setattr("app.routers.projects.build_ai_client", lambda timeout=None: FakeAIClient())

    resp = client.get("/api/recommendations?force=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["repo_full_name"] == "candidate/repo"
    assert data["items"][0]["recommendation_reason"] == "AI reason"


def test_chat_stream_uses_shared_ai_client(client, monkeypatch):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, description) VALUES (?, ?, ?)",
        ("chat/repo", "https://github.com/chat/repo", "chat project"),
    )
    conn.commit()
    conn.close()

    async def fake_fetch_readme(repo_full_name):
        return "# README"

    class FakeAIClient:
        async def stream_chat_completion(self, messages, temperature=0.5):
            yield "你好"
            yield "，项目"

    monkeypatch.setattr("app.routers.projects.fetch_readme", fake_fetch_readme)
    monkeypatch.setattr("app.routers.projects.build_ai_client", lambda timeout=None: FakeAIClient())

    resp = client.post("/api/chat", json={"repo_full_name": "chat/repo", "message": "介绍一下"})

    assert resp.status_code == 200
    assert 'data: {"content": "你好"}' in resp.text
    assert 'data: {"content": "，项目"}' in resp.text
    assert "data: [DONE]" in resp.text


def test_do_refresh_starts_translation_worker_without_waiting_for_translation(monkeypatch):
    from app.routers import system

    calls = []

    async def fake_scrape():
        calls.append("scrape")

    def fake_score():
        calls.append("score")

    async def forbidden_translate():
        raise AssertionError("refresh should not await translate_untranslated_projects")

    def fake_start_worker():
        calls.append("worker")
        return True

    monkeypatch.setattr("app.scraper.run_full_scrape", fake_scrape)
    monkeypatch.setattr("app.scorer.update_all_scores", fake_score)
    monkeypatch.setattr("app.translator.translate_untranslated_projects", forbidden_translate)
    monkeypatch.setattr("app.translator.start_translation_worker", fake_start_worker)

    asyncio.run(system._do_refresh())

    assert calls == ["scrape", "worker", "score"]


def test_do_refresh_records_refresh_failure(monkeypatch):
    from app.routers import system
    from app.state_store import get_runtime_value

    async def fake_scrape():
        raise RuntimeError("network down")

    monkeypatch.setattr("app.scraper.run_full_scrape", fake_scrape)

    asyncio.run(system._do_refresh())

    assert get_runtime_value("last_refresh_error") == "network down"
    assert get_runtime_value("last_refresh_failed_at") != ""


def test_do_refresh_clears_previous_error_after_success(monkeypatch):
    from app.routers import system
    from app.state_store import get_runtime_value, set_runtime_state

    set_runtime_state(
        last_refresh_error="old failure",
        last_refresh_failed_at="2026-06-02 04:00:00",
    )

    async def fake_scrape():
        pass

    def fake_score():
        pass

    def fake_start_worker():
        return True

    monkeypatch.setattr("app.scraper.run_full_scrape", fake_scrape)
    monkeypatch.setattr("app.scorer.update_all_scores", fake_score)
    monkeypatch.setattr("app.translator.start_translation_worker", fake_start_worker)

    asyncio.run(system._do_refresh())

    assert get_runtime_value("last_refresh_error") == ""
    assert get_runtime_value("last_refresh_completed_at") != ""


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


def test_get_health_flags_model_missing_from_endpoint(client, monkeypatch):
    from app.routers.system import reset_model_check_cache

    monkeypatch.setattr(cfg.config, "API_KEY", "test-key")
    monkeypatch.setattr(cfg.config, "API_MODEL", "glm")
    monkeypatch.setattr(cfg.config, "AI_MODEL_CHECK", True)
    monkeypatch.setattr("app.ai_client.list_available_models", lambda timeout=8.0: ["qwen", "deepseek-chat"])
    reset_model_check_cache()

    resp = client.get("/api/health")
    assert resp.status_code == 200

    data = resp.json()
    check = data["checks"]["model_available"]
    assert check["ok"] is False
    assert check["available_models"] == ["qwen", "deepseek-chat"]
    assert any(p.startswith("Model 'glm' is not available") for p in data["problems"])


def test_get_health_accepts_configured_model_and_caches_lookup(client, monkeypatch):
    from app.routers.system import reset_model_check_cache

    calls = []

    def fake_list(timeout=8.0):
        calls.append(1)
        return ["qwen", "qwen3.8-27b"]

    monkeypatch.setattr(cfg.config, "API_KEY", "test-key")
    monkeypatch.setattr(cfg.config, "API_MODEL", "qwen")
    monkeypatch.setattr(cfg.config, "AI_MODEL_CHECK", True)
    monkeypatch.setattr("app.ai_client.list_available_models", fake_list)
    reset_model_check_cache()

    first = client.get("/api/health").json()
    second = client.get("/api/health").json()

    assert first["checks"]["model_available"]["ok"] is True
    assert second["checks"]["model_available"]["ok"] is True
    assert len(calls) == 1


def test_get_health_does_not_fail_when_models_endpoint_unreachable(client, monkeypatch):
    from app.routers.system import reset_model_check_cache

    def broken_list(timeout=8.0):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(cfg.config, "API_KEY", "test-key")
    monkeypatch.setattr(cfg.config, "AI_MODEL_CHECK", True)
    monkeypatch.setattr("app.ai_client.list_available_models", broken_list)
    reset_model_check_cache()

    data = client.get("/api/health").json()
    check = data["checks"]["model_available"]

    assert check["ok"] is True
    assert "unreachable" in check["skipped"]


def test_do_refresh_sets_refreshing_flag_for_scheduled_runs(monkeypatch):
    from app.routers import system
    from app.state_store import get_runtime_bool, set_runtime_state

    set_runtime_state(is_refreshing="0")
    observed = {}

    async def fake_scrape():
        observed["during"] = get_runtime_bool("is_refreshing")

    monkeypatch.setattr("app.scraper.run_full_scrape", fake_scrape)
    monkeypatch.setattr("app.scorer.update_all_scores", lambda: None)
    monkeypatch.setattr("app.translator.start_translation_worker", lambda: True)

    asyncio.run(system._do_refresh())

    assert observed["during"] is True
    assert get_runtime_bool("is_refreshing") is False


def test_star_history_batch_returns_most_recent_points(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url) VALUES (?, ?)",
        ("trend/repo", "https://github.com/trend/repo"),
    )
    project_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?", ("trend/repo",)
    ).fetchone()["id"]
    for date, stars in (("2026-06-01", 100), ("2026-06-02", 120), ("2026-06-03", 150)):
        conn.execute(
            "INSERT INTO star_history (project_id, stars, recorded_date) VALUES (?, ?, ?)",
            (project_id, stars, date),
        )
    conn.commit()
    conn.close()

    resp = client.get(f"/api/star-history?ids={project_id},abc,&points=2")
    assert resp.status_code == 200

    # newest two points, returned oldest -> newest so the sparkline reads left to right
    assert resp.json() == {
        str(project_id): [
            {"date": "2026-06-02", "stars": 120},
            {"date": "2026-06-03", "stars": 150},
        ]
    }

    everything = client.get(f"/api/star-history?ids={project_id}").json()
    assert len(everything[str(project_id)]) == 3
