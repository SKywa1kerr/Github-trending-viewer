from app.config import config
from app.ai_client import OpenAICompatibleAIClient


class OpenAICompatibleTranslationProvider:
    name = "openai-compatible"

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
        )


def build_translation_provider():
    proxy = config.PROXY or None
    return OpenAICompatibleTranslationProvider(
        endpoint=config.API_ENDPOINT,
        api_key=config.API_KEY,
        model=config.TRANSLATION_MODEL,
        proxy=proxy,
    )
