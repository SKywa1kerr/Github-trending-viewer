import json
import logging
import re
from collections.abc import AsyncIterator

import httpx

from app.config import config


logger = logging.getLogger("ai_client")

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think>.*\Z", re.DOTALL)
_JSON_OBJECT_MODE = {"type": "json_object"}


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks that reasoning models may prepend to content."""
    if not text:
        return ""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _THINK_OPEN_RE.sub("", cleaned)
    return cleaned.strip()


def extract_message_content(data: dict) -> str:
    """Return the assistant text from a chat completion response, ignoring reasoning fields."""
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return strip_thinking(content or "")


def _is_json_mode_rejection(response: httpx.Response) -> bool:
    if response.status_code not in (400, 422):
        return False
    body = response.text.lower()
    return "response_format" in body or "json_object" in body or "json" in body


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
        json_mode: bool = False,
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
        if json_mode:
            payload["response_format"] = dict(_JSON_OBJECT_MODE)
        return payload

    async def chat_completion(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> dict:
        use_json_mode = bool(json_mode and config.AI_JSON_MODE)
        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.proxy) as client:
            resp = await client.post(
                self.endpoint,
                json=self._payload(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=use_json_mode,
                ),
                headers=self._headers(),
            )
            if use_json_mode and _is_json_mode_rejection(resp):
                logger.warning(
                    "Model endpoint rejected response_format=json_object (HTTP %s); retrying without it",
                    resp.status_code,
                )
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
        in_think = False
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
                    if not content:
                        continue
                    content, in_think = _filter_stream_thinking(content, in_think)
                    if content:
                        yield content


def _filter_stream_thinking(chunk: str, in_think: bool) -> tuple[str, bool]:
    """Drop <think>...</think> spans from a streamed chunk, carrying state across chunks."""
    output = []
    rest = chunk
    while rest:
        if in_think:
            end = rest.find("</think>")
            if end == -1:
                return "".join(output), True
            rest = rest[end + len("</think>"):]
            in_think = False
            continue
        start = rest.find("<think>")
        if start == -1:
            output.append(rest)
            break
        output.append(rest[:start])
        rest = rest[start + len("<think>"):]
        in_think = True
    return "".join(output), in_think


def _strip_markdown_fence(text: str, opener: str) -> str:
    pattern = r"```(?:json)?\s*(" + re.escape(opener) + r".*?)\s*```"
    md_match = re.search(pattern, text, re.DOTALL)
    return md_match.group(1) if md_match else text


def _find_balanced(text: str, open_char: str, close_char: str) -> str | None:
    start = text.find(open_char)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def extract_json_object(content: str) -> dict:
    """Best-effort extraction of a JSON object from model output (fences, prose, think tags)."""
    text = strip_thinking(content or "")
    text = _strip_markdown_fence(text, "{")
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    candidate = _find_balanced(text, "{", "}")
    if not candidate:
        return {}
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def extract_json_array(content: str) -> list:
    text = strip_thinking(content or "")
    text = _strip_markdown_fence(text, "[")
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    candidate = _find_balanced(text, "[", "]")
    if not candidate:
        return []
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _models_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/completions"):
        if base.endswith(suffix):
            return base[: -len(suffix)] + "/models"
    return base + "/models"


def list_available_models(timeout: float = 8.0) -> list[str]:
    """Synchronously query the OpenAI-compatible /models endpoint. Raises on failure."""
    url = _models_url(config.API_ENDPOINT)
    headers = {"Authorization": f"Bearer {config.API_KEY}"}
    with httpx.Client(timeout=timeout, proxy=config.PROXY or None) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    items = data.get("data", []) if isinstance(data, dict) else []
    return [str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")]


def build_ai_client(
    *,
    model: str | None = None,
    timeout: int | None = None,
) -> OpenAICompatibleAIClient:
    return OpenAICompatibleAIClient(model=model, timeout=timeout)
