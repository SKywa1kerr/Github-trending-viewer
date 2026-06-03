import json
import re
from collections.abc import AsyncIterator

import httpx

from app.config import config


class OpenAICompatibleAIClient:
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        proxy: str | None = None,
        timeout: int | None = None,
    ):
        self.endpoint = endpoint if endpoint is not None else config.API_ENDPOINT
        self.api_key = api_key if api_key is not None else config.API_KEY
        self.model = model if model is not None else config.API_MODEL
        self.proxy = proxy if proxy is not None else (config.PROXY or None)
        self.timeout = timeout if timeout is not None else config.TRANSLATION_TIMEOUT_SECONDS

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True
        return payload

    async def chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.proxy) as client:
            resp = await client.post(
                self.endpoint,
                json=self._payload(messages, temperature=temperature, max_tokens=max_tokens),
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def stream_chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.proxy) as client:
            async with client.stream(
                "POST",
                self.endpoint,
                json=self._payload(messages, temperature=temperature, stream=True),
                headers=self._headers(),
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    if content:
                        yield content


def extract_json_array(content: str) -> list:
    text = content or ""
    md_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    else:
        arr_match = re.search(r"\[.*\]", text, re.DOTALL)
        if arr_match:
            text = arr_match.group(0)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def build_ai_client(
    *,
    model: str | None = None,
    timeout: int | None = None,
) -> OpenAICompatibleAIClient:
    return OpenAICompatibleAIClient(model=model, timeout=timeout)
