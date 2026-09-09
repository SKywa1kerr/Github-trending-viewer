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


class _FakeResponse:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload if payload is not None else {"choices": [{"message": {"content": "ok"}}]}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected raise_for_status on {self.status_code}")

    def json(self):
        return self._payload


def _fake_async_client(post_handler):
    class FakeAsyncClient:
        def __init__(self, timeout, proxy):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, json, headers):
            return post_handler(json)

    return FakeAsyncClient


def test_chat_completion_json_mode_adds_response_format(monkeypatch):
    from app import config as cfg
    from app.ai_client import OpenAICompatibleAIClient

    payloads = []
    monkeypatch.setattr(
        "app.ai_client.httpx.AsyncClient",
        _fake_async_client(lambda payload: (payloads.append(payload), _FakeResponse())[1]),
    )
    monkeypatch.setattr(cfg.config, "AI_JSON_MODE", True)

    client = OpenAICompatibleAIClient(endpoint="https://model.example/chat", api_key="k", model="qwen")
    asyncio.run(client.chat_completion(messages=[{"role": "user", "content": "hi"}], json_mode=True))

    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert payloads[0]["model"] == "qwen"


def test_chat_completion_falls_back_when_json_mode_rejected(monkeypatch):
    from app import config as cfg
    from app.ai_client import OpenAICompatibleAIClient

    payloads = []

    def handler(payload):
        payloads.append(payload)
        if "response_format" in payload:
            return _FakeResponse(400, '{"error": {"message": "response_format is not supported"}}')
        return _FakeResponse()

    monkeypatch.setattr("app.ai_client.httpx.AsyncClient", _fake_async_client(handler))
    monkeypatch.setattr(cfg.config, "AI_JSON_MODE", True)

    client = OpenAICompatibleAIClient(endpoint="https://model.example/chat", api_key="k", model="qwen")
    result = asyncio.run(client.chat_completion(messages=[{"role": "user", "content": "hi"}], json_mode=True))

    assert result["choices"][0]["message"]["content"] == "ok"
    assert len(payloads) == 2
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]


def test_chat_completion_json_mode_respects_global_switch(monkeypatch):
    from app import config as cfg
    from app.ai_client import OpenAICompatibleAIClient

    payloads = []
    monkeypatch.setattr(
        "app.ai_client.httpx.AsyncClient",
        _fake_async_client(lambda payload: (payloads.append(payload), _FakeResponse())[1]),
    )
    monkeypatch.setattr(cfg.config, "AI_JSON_MODE", False)

    client = OpenAICompatibleAIClient(endpoint="https://model.example/chat", api_key="k", model="qwen")
    asyncio.run(client.chat_completion(messages=[{"role": "user", "content": "hi"}], json_mode=True))

    assert "response_format" not in payloads[0]


def test_stream_chat_completion_drops_think_blocks_across_chunks(monkeypatch):
    from app.ai_client import OpenAICompatibleAIClient

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"<think>let me"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" reason</think>你"}}]}'
            yield 'data: {"choices":[{"delta":{"reasoning_content":"ignored"}}]}'
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


def test_strip_thinking_removes_closed_and_unclosed_blocks():
    from app.ai_client import strip_thinking

    assert strip_thinking("<think>plan</think>{\"a\": 1}") == '{"a": 1}'
    assert strip_thinking("<think>never closed") == ""
    assert strip_thinking("plain") == "plain"


def test_extract_message_content_ignores_reasoning_and_handles_parts():
    from app.ai_client import extract_message_content

    data = {"choices": [{"message": {"reasoning_content": "hidden", "content": "<think>x</think>visible"}}]}
    assert extract_message_content(data) == "visible"

    parts = {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}
    assert extract_message_content(parts) == "ab"

    assert extract_message_content({}) == ""


def test_extract_json_object_from_prose_and_think_tags():
    from app.ai_client import extract_json_object

    content = '<think>thinking</think>Here is the result:\n{"description_zh": "中文 {带括号}", "n": [1, 2]}\nDone.'
    assert extract_json_object(content) == {"description_zh": "中文 {带括号}", "n": [1, 2]}
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object("[1, 2]") == {}
    assert extract_json_object("nothing here") == {}


def test_extract_json_array_from_prose_with_nested_brackets():
    from app.ai_client import extract_json_array

    content = 'Sure:\n[{"repo": "a/b", "tags": ["x", "y"]}, {"repo": "c/d", "tags": []}]\nEnjoy.'
    assert extract_json_array(content) == [
        {"repo": "a/b", "tags": ["x", "y"]},
        {"repo": "c/d", "tags": []},
    ]


def test_list_available_models_derives_models_url(monkeypatch):
    from app import config as cfg
    from app.ai_client import list_available_models

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "qwen"}, {"id": "deepseek-chat"}, {"object": "no-id"}]}

    class FakeClient:
        def __init__(self, timeout, proxy):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.ai_client.httpx.Client", FakeClient)
    monkeypatch.setattr(cfg.config, "API_ENDPOINT", "https://models.sjtu.edu.cn/api/v1/chat/completions")
    monkeypatch.setattr(cfg.config, "API_KEY", "secret")

    assert list_available_models() == ["qwen", "deepseek-chat"]
    assert captured["url"] == "https://models.sjtu.edu.cn/api/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer secret"
