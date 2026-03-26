import os


class Config:
    API_ENDPOINT: str = os.getenv("API_ENDPOINT", "https://models.sjtu.edu.cn/api/v1/chat/completions")
    API_KEY: str = os.getenv("API_KEY", "")
    API_MODEL: str = os.getenv("API_MODEL", "deepseek-chat")
    UPDATE_HOUR: int = int(os.getenv("UPDATE_HOUR", "8"))
    DB_PATH: str = os.getenv("DB_PATH", "data/trending.db")
    MAX_DAILY_TOKENS: int = 150000
    MAX_REQUESTS_PER_MINUTE: int = 30
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
