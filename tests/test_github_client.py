import asyncio
import pytest

from app import config as cfg


class DummyResponse:
    def __init__(self, status_code=200, text="", json_data=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data


def test_github_get_adds_token_and_accept_headers(monkeypatch):
    from app.github_client import github_get_json

    requests = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            requests.append((url, headers))
            return DummyResponse(status_code=200, json_data={"ok": True})

    monkeypatch.setattr(cfg.config, "GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr("app.github_client.httpx.AsyncClient", lambda **kwargs: FakeClient())

    data = asyncio.run(github_get_json("https://api.github.com/test", accept="application/vnd.github+json"))

    assert data == {"ok": True}
    assert requests[0][1]["Authorization"] == "Bearer secret-token"
    assert requests[0][1]["Accept"] == "application/vnd.github+json"
    assert requests[0][1]["User-Agent"] == "GitHub Trending Viewer"


def test_github_get_retries_rate_limited_and_transient_failures(monkeypatch):
    from app.github_client import github_get_json

    sleeps = []
    responses = [
        DummyResponse(status_code=429, json_data={}),
        DummyResponse(status_code=502, json_data={}),
        DummyResponse(status_code=200, json_data={"items": [1, 2, 3]}),
    ]

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return responses.pop(0)

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("app.github_client.httpx.AsyncClient", lambda **kwargs: FakeClient())

    data = asyncio.run(github_get_json(
        "https://api.github.com/test",
        retries=3,
        backoff_seconds=0.25,
        sleeper=fake_sleep,
    ))

    assert data == {"items": [1, 2, 3]}
    assert sleeps == [0.25, 0.5]


def test_github_get_raises_after_retry_budget(monkeypatch):
    from app.github_client import GitHubRequestError, github_get_text

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return DummyResponse(status_code=503, text="nope")

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("app.github_client.httpx.AsyncClient", lambda **kwargs: FakeClient())

    with pytest.raises(GitHubRequestError, match="503"):
        asyncio.run(github_get_text(
            "https://api.github.com/test",
            retries=1,
            backoff_seconds=0.1,
            sleeper=fake_sleep,
        ))
