import asyncio
import json


def test_chat_completion_posts_openai_compatible_payload(monkeypatch):
    from app import config as cfg
    from app.ai_client import OpenAICompatibleAIClient

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeAsyncClient:
        def __init__(self, timeout, proxy):
            captured["timeout"] = timeout
            captured["proxy"] = proxy

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, json, headers):
            captured["endpoint"] = endpoint
            captured["payload"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.ai_client.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(cfg.config, "API_ENDPOINT", "https://model.example/chat")
    monkeypatch.setattr(cfg.config, "API_KEY", "test-key")
    monkeypatch.setattr(cfg.config, "API_MODEL", "test-model")
    monkeypatch.setattr(cfg.config, "PROXY", "http://127.0.0.1:7897")

    client = OpenAICompatibleAIClient()
    result = asyncio.run(client.chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
        max_tokens=123,
    ))

    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["endpoint"] == "https://model.example/chat"
    assert captured["proxy"] == "http://127.0.0.1:7897"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0.2,
        "max_tokens": 123,
    }


def test_stream_chat_completion_yields_content_chunks(monkeypatch):
    from app.ai_client import OpenAICompatibleAIClient

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"你"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"好"}}]}'
            yield "data: [DONE]"

    class FakeAsyncClient:
        def __init__(self, timeout, proxy):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, endpoint, json, headers):
            return FakeStream()

    monkeypatch.setattr("app.ai_client.httpx.AsyncClient", FakeAsyncClient)

    client = OpenAICompatibleAIClient(endpoint="https://model.example/chat", api_key="k", model="m")

    async def collect():
        return [chunk async for chunk in client.stream_chat_completion(
            messages=[{"role": "user", "content": "hello"}]
        )]

    assert asyncio.run(collect()) == ["你", "好"]


def test_extract_json_array_from_markdown():
    from app.ai_client import extract_json_array

    content = '```json\n[{"repo": "a/b", "score": 99}]\n```'

    assert extract_json_array(content) == [{"repo": "a/b", "score": 99}]


def test_extract_json_array_returns_empty_on_invalid_json():
    from app.ai_client import extract_json_array

    assert extract_json_array("not json") == []
