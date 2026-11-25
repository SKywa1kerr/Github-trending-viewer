"""Local translation must stay independent of remote services and quotas."""
import asyncio
import json

import httpx
import pytest

from app.config import config
from app.database import get_connection, init_db
from app.translation_provider import build_translation_provider, check_local_translation


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "translations.db"))
    monkeypatch.setattr(config, "TRANSLATION_PROVIDER", "ollama")
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "AI_MODEL_CHECK", False)
    init_db()


def mock_ollama(monkeypatch, handler):
    original = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs["trust_env"] is False, "Local traffic must bypass global proxies"
        return original(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.translation_provider.httpx.AsyncClient", client)


def test_local_translation_works_without_key_budget_or_remote_rate_limiter(monkeypatch):
    from app import translator
    from app.state_store import get_runtime_value, set_runtime_state

    set_runtime_state(translation_daily_tokens_used="9999")
    monkeypatch.setattr(config, "MAX_DAILY_TOKENS", 0)
    async def forbidden():
        pytest.fail("Local translation called the remote rate limiter")
    monkeypatch.setattr(translator, "_wait_for_translation_rate_limit", forbidden)
    requests = []
    def respond(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert request.url == "http://127.0.0.1:11434/api/chat"
        assert "authorization" not in request.headers
        assert payload["model"] == "qwen3:8b"
        assert payload["think"] is False and payload["stream"] is False
        assert payload["format"]["required"] == ["description_zh", "readme_summary_zh"]
        return httpx.Response(200, json={"done": True, "message": {
            "content": json.dumps({"description_zh": "本地工具", "readme_summary_zh": "支持离线运行"})}})
    mock_ollama(monkeypatch, respond)

    result = asyncio.run(translator.translate_project("tools/local", "Offline tool", "Runs locally"))
    assert result == {"description_zh": "本地工具", "readme_summary_zh": "支持离线运行"}
    assert len(requests) == 1
    assert get_runtime_value("translation_daily_tokens_used") == "9999"


@pytest.mark.parametrize("payload", [
    {"error": "model not found"},
    {"done": False, "message": {"content": "{}"}},
    {"done": True, "done_reason": "length", "message": {"content": "{}"}},
    {"done": True, "message": {"content": "{}"}},
])
def test_local_errors_are_retryable_and_do_not_call_remote(monkeypatch, payload):
    from app.translator import TranslationRetryableError, translate_project
    requests = []
    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, json=payload)
    mock_ollama(monkeypatch, respond)
    with pytest.raises(TranslationRetryableError):
        asyncio.run(translate_project("a/b", "description", "readme"))
    assert requests == ["http://127.0.0.1:11434/api/chat"]


def test_connection_failure_keeps_cached_chinese_and_queues_retry(monkeypatch):
    from app import translator
    conn = get_connection()
    conn.execute("INSERT INTO projects (repo_full_name, repo_url, description_zh, readme_summary_zh) "
                 "VALUES ('a/b', 'https://github.com/a/b', '已有简介', '已有摘要')")
    conn.commit()
    row = conn.execute("SELECT * FROM projects").fetchone()
    conn.close()
    async def readme(_):
        return "Updated README"
    monkeypatch.setattr(translator, "fetch_readme_for_translation", readme)
    def unavailable(request):
        raise httpx.ConnectError("Ollama is stopped", request=request)
    mock_ollama(monkeypatch, unavailable)
    assert asyncio.run(translator.translate_project_row(row)) is False
    conn = get_connection()
    saved = conn.execute("SELECT * FROM projects").fetchone()
    conn.close()
    assert saved["translation_status"] == "retry"
    assert saved["description_zh"] == "已有简介"
    assert saved["readme_summary_zh"] == "已有摘要"


def test_local_success_persists_actual_model_and_source_cache(monkeypatch):
    from app import translator
    conn = get_connection()
    conn.execute("INSERT INTO projects (repo_full_name, repo_url) VALUES ('a/b', 'https://github.com/a/b')")
    conn.commit()
    row = conn.execute("SELECT * FROM projects").fetchone()
    conn.close()
    async def readme(_):
        return "A useful tool"
    monkeypatch.setattr(translator, "fetch_readme_for_translation", readme)
    count = 0
    def respond(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json={"done": True, "message": {
            "content": '{"description_zh":"工具", "readme_summary_zh":"功能"}'}})
    mock_ollama(monkeypatch, respond)
    assert asyncio.run(translator.translate_project_row(row))
    conn = get_connection()
    saved = conn.execute("SELECT * FROM projects").fetchone()
    conn.close()
    assert saved["translation_provider"] == "ollama"
    assert saved["translation_model"] == "qwen3:8b"
    assert saved["translated_signature"] == saved["source_signature"]
    assert asyncio.run(translator.translate_project_row(saved))
    assert count == 1


@pytest.mark.parametrize("model,names,ready", [
    ("qwen3:8b", ["qwen3:8b"], True),
    ("qwen3", ["qwen3:latest"], True),
    ("qwen3:8b", ["qwen3:4b"], False),
])
def test_model_probe_checks_installed_model_without_generation(monkeypatch, model, names, ready):
    monkeypatch.setattr(config, "OLLAMA_MODEL", model)
    original = httpx.Client
    def respond(request):
        assert request.method == "GET" and request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": name} for name in names]})
    def client(**kwargs):
        assert kwargs["trust_env"] is False
        return original(**kwargs, transport=httpx.MockTransport(respond))
    monkeypatch.setattr("app.translation_provider.httpx.Client", client)
    assert check_local_translation()["ok"] is ready


def test_health_distinguishes_local_translation_from_optional_remote_features(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr("app.translation_provider.check_local_translation", lambda: {
        "ok": True, "provider": "ollama", "model": "qwen3:8b", "local": True, "detail": "本地模型已就绪"})
    data = TestClient(app).get("/api/health").json()
    assert data["checks"]["translation"]["ok"] is True
    assert "API_KEY is not configured" not in data["problems"]
    assert "Remote AI features are not configured" in data["problems"]


def test_unknown_provider_never_silently_uses_remote(monkeypatch):
    monkeypatch.setattr(config, "TRANSLATION_PROVIDER", "typo")
    with pytest.raises(ValueError, match="Unsupported translation provider"):
        build_translation_provider()
