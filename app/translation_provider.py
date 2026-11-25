import httpx

from app.config import config
from app.ai_client import OpenAICompatibleAIClient


class OpenAICompatibleTranslationProvider:
    name = "openai-compatible"
    is_local = False

    def __init__(self, endpoint: str, api_key: str, model: str, proxy: str | None = None):
        self.client = OpenAICompatibleAIClient(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            proxy=proxy,
            timeout=config.TRANSLATION_TIMEOUT_SECONDS,
        )

    async def translate(self, prompt: str, temperature: float = 0.3) -> dict:
        return await self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=config.TRANSLATION_MAX_OUTPUT_TOKENS,
            json_mode=True,
        )


class OllamaTranslationProvider:
    """Local inference; never falls back to a paid or external endpoint."""

    name = "ollama"
    is_local = True

    async def translate(self, prompt: str, temperature: float = 0.3) -> dict:
        async with httpx.AsyncClient(
            timeout=config.OLLAMA_TIMEOUT_SECONDS, trust_env=False,
        ) as client:
            response = await client.post(
                config.OLLAMA_BASE_URL + "/api/chat",
                json={
                    "model": config.OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "think": False,
                    "keep_alive": "5m",
                    "format": {
                        "type": "object",
                        "properties": {
                            "description_zh": {"type": "string"},
                            "readme_summary_zh": {"type": "string"},
                        },
                        "required": ["description_zh", "readme_summary_zh"],
                        "additionalProperties": False,
                    },
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 4096,
                        "num_predict": config.TRANSLATION_MAX_OUTPUT_TOKENS,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
        if data.get("error"):
            raise RuntimeError(str(data["error"]))
        if data.get("done") is not True or data.get("done_reason") == "length":
            raise RuntimeError("Ollama returned an incomplete translation")
        # The queue uses a single normalized response format for both providers.
        return {"choices": [{"message": data.get("message", {})}]}


def translation_model() -> str:
    return config.OLLAMA_MODEL if config.TRANSLATION_PROVIDER == "ollama" else config.TRANSLATION_MODEL


def check_local_translation() -> dict:
    """Probe installed models without loading a model or generating text."""
    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            response = client.get(config.OLLAMA_BASE_URL + "/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
        names = {model.get("name", "") for model in models}
        expected = config.OLLAMA_MODEL
        ready = expected in names or (":" not in expected and expected + ":latest" in names)
        return {"ok": ready, "model": expected, "provider": "ollama", "local": True,
                "detail": "本地模型已就绪" if ready else "本地模型尚未下载"}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return {"ok": False, "model": config.OLLAMA_MODEL, "provider": "ollama", "local": True,
                "detail": "无法连接 Ollama，请检查本地服务与地址"}


def build_translation_provider():
    if config.TRANSLATION_PROVIDER == "ollama":
        return OllamaTranslationProvider()
    if config.TRANSLATION_PROVIDER != "openai-compatible":
        raise ValueError("Unsupported translation provider: " + config.TRANSLATION_PROVIDER)
    proxy = config.PROXY or None
    return OpenAICompatibleTranslationProvider(
        endpoint=config.API_ENDPOINT,
        api_key=config.API_KEY,
        model=config.TRANSLATION_MODEL,
        proxy=proxy,
    )
