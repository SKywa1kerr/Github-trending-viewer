import asyncio

import httpx

from app.config import config


class GitHubRequestError(Exception):
    pass


def _get_proxy():
    return config.PROXY or None


def build_github_headers(accept: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": "GitHub Trending Viewer"}
    if accept:
        headers["Accept"] = accept
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return headers


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


async def _github_get(url: str, *, accept: str | None, retries: int, backoff_seconds: float, sleeper):
    headers = build_github_headers(accept=accept)
    last_status = 0

    async with httpx.AsyncClient(timeout=config.GITHUB_TIMEOUT_SECONDS, proxy=_get_proxy()) as client:
        for attempt in range(retries + 1):
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response

            last_status = response.status_code
            if attempt >= retries or not _is_retryable_status(response.status_code):
                break

            await sleeper(backoff_seconds * (2 ** attempt))

    raise GitHubRequestError(f"GitHub request failed with status {last_status} for {url}")


async def github_get_json(
    url: str,
    *,
    accept: str = "application/vnd.github.v3+json",
    retries: int | None = None,
    backoff_seconds: float | None = None,
    sleeper=asyncio.sleep,
):
    response = await _github_get(
        url,
        accept=accept,
        retries=config.GITHUB_MAX_RETRIES if retries is None else retries,
        backoff_seconds=config.GITHUB_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds,
        sleeper=sleeper,
    )
    return response.json()


async def github_get_text(
    url: str,
    *,
    accept: str | None = None,
    retries: int | None = None,
    backoff_seconds: float | None = None,
    sleeper=asyncio.sleep,
):
    response = await _github_get(
        url,
        accept=accept,
        retries=config.GITHUB_MAX_RETRIES if retries is None else retries,
        backoff_seconds=config.GITHUB_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds,
        sleeper=sleeper,
    )
    return response.text
