import os


class Config:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_TIMEOUT_SECONDS: int = int(os.getenv("GITHUB_TIMEOUT_SECONDS", "30"))
    GITHUB_MAX_RETRIES: int = int(os.getenv("GITHUB_MAX_RETRIES", "3"))
    GITHUB_BACKOFF_SECONDS: float = float(os.getenv("GITHUB_BACKOFF_SECONDS", "1"))
    API_ENDPOINT: str = os.getenv("API_ENDPOINT", "https://models.sjtu.edu.cn/api/v1/chat/completions")
    API_KEY: str = os.getenv("API_KEY", "")
    API_MODEL: str = os.getenv("API_MODEL", "deepseek-chat")
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "openai-compatible")
    TRANSLATION_MODEL: str = os.getenv("TRANSLATION_MODEL", API_MODEL)
    TRANSLATION_TIMEOUT_SECONDS: int = int(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "60"))
    TRANSLATION_CONCURRENCY: int = int(os.getenv("TRANSLATION_CONCURRENCY", "2"))
    TRANSLATION_BATCH_SIZE: int = int(os.getenv("TRANSLATION_BATCH_SIZE", "8"))
    TRANSLATION_MAX_RETRIES: int = int(os.getenv("TRANSLATION_MAX_RETRIES", "3"))
    TRANSLATION_README_CHARS: int = int(os.getenv("TRANSLATION_README_CHARS", "1600"))
    TRANSLATION_MAX_OUTPUT_TOKENS: int = int(os.getenv("TRANSLATION_MAX_OUTPUT_TOKENS", "700"))
    TRANSLATION_REQUEST_INTERVAL_SECONDS: float = float(os.getenv("TRANSLATION_REQUEST_INTERVAL_SECONDS", "6.0"))
    UPDATE_HOUR: int = int(os.getenv("UPDATE_HOUR", "8"))
    DATA_STALE_HOURS: int = int(os.getenv("DATA_STALE_HOURS", "72"))
    DB_PATH: str = os.getenv("DB_PATH", "data/trending.db")
    MAX_DAILY_TOKENS: int = int(os.getenv("MAX_DAILY_TOKENS", "1000000"))
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10"))
    PROXY: str = os.getenv("HTTPS_PROXY", os.getenv("HTTP_PROXY", ""))
    CATEGORIES: dict = {
        "ai": {
            "name": "AI",
            "topics": ["artificial-intelligence", "machine-learning", "deep-learning",
                       "llm", "large-language-model", "gpt", "agent", "nlp",
                       "computer-vision", "stable-diffusion"]
        },
        "tools": {
            "name": "实用工具",
            "topics": ["tool", "productivity", "utility", "automation", "self-hosted"]
        },
        "devtools": {
            "name": "开发工具",
            "topics": ["developer-tools", "devops", "cli", "framework", "library"]
        }
    }


config = Config()
