import json
import math
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.config import config
from app.database import get_connection, init_db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "recommendations.db"))
    init_db()
    with closing(get_connection()) as conn:
        for name, topics in [
            ("favorite/repo", ["ai"]),
            ("candidate/first", ["ai"]),
            ("candidate/second", ["cli"]),
        ]:
            conn.execute(
                "INSERT INTO projects (repo_full_name, repo_url, language, topics, description) "
                "VALUES (?, ?, 'Python', ?, 'A useful project')",
                (name, f"https://github.com/{name}", json.dumps(topics)),
            )
        conn.execute("INSERT INTO favorites (project_id) SELECT id FROM projects WHERE repo_full_name = 'favorite/repo'")
        conn.commit()
    # No lifespan context: these API tests must not start scheduled network jobs.
    return TestClient(app, raise_server_exceptions=False)


def mock_ai_response(monkeypatch, recommendations):
    calls = []

    class FakeAIClient:
        async def chat_completion(self, messages, **kwargs):
            calls.append(messages)
            return {"choices": [{"message": {"content": json.dumps({"recommendations": recommendations})}}]}

    monkeypatch.setattr("app.routers.projects.build_ai_client", lambda **kwargs: FakeAIClient())
    return calls


@pytest.mark.parametrize("recommendations", [
    [None, "candidate/first", 42],
    [{"repo": "unknown/repo", "reason": "Not a candidate", "score": 90}],
    [{"repo": ["candidate/first"], "reason": "Invalid repository", "score": 90}],
    [{"repo": "candidate/first", "reason": {"text": "Invalid reason"}, "score": 90}],
    [{"repo": "candidate/first", "reason": "Invalid score", "score": [90]}],
    [{"repo": "candidate/first", "reason": "Invalid score", "score": "NaN"}],
    [{"repo": "candidate/first", "reason": "Invalid score", "score": 101}],
])
def test_unusable_ai_recommendations_fall_back_and_cache(client, monkeypatch, recommendations):
    calls = mock_ai_response(monkeypatch, recommendations)

    response = client.get("/api/recommendations?force=true")
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["repo_full_name"] for item in data["items"]] == ["candidate/first", "candidate/second"]
    assert all(item["recommendation_reason"] == "基于相似标签和语言推荐" for item in data["items"])
    assert all(math.isfinite(item["score"]) for item in data["items"])

    cached = client.get("/api/recommendations")
    assert cached.status_code == 200
    assert cached.json() == data
    assert len(calls) == 1


def test_recommendations_drop_duplicates(client, monkeypatch):
    mock_ai_response(monkeypatch, [
        {"repo": "candidate/first", "reason": "First choice", "score": 95},
        {"repo": "candidate/first", "reason": "Repeated choice", "score": 94},
        {"repo": "candidate/second", "reason": "Second choice", "score": 90},
    ])

    response = client.get("/api/recommendations?force=true")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["repo_full_name"] for item in items] == ["candidate/first", "candidate/second"]
    assert items[0]["recommendation_reason"] == "First choice"


def test_invalid_entries_do_not_hide_later_valid_recommendations(client, monkeypatch):
    mock_ai_response(monkeypatch, [None] * 10 + [
        {"repo": "candidate/second", "reason": "A valid choice", "score": 90},
    ])

    response = client.get("/api/recommendations?force=true")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["repo_full_name"] for item in items] == ["candidate/second"]
    assert items[0]["recommendation_reason"] == "A valid choice"
