from pydantic import BaseModel, Field


class ProjectOut(BaseModel):
    id: int
    repo_full_name: str
    description: str
    description_zh: str
    readme_summary_zh: str
    translation_status: str = ""
    translation_attempts: int = 0
    stars: int
    stars_gained: int
    language: str
    topics: list[str]
    category: str
    repo_url: str
    score: float
    last_updated: str
    fetched_at: str


class ProjectImportIn(BaseModel):
    repo_full_name: str
    description: str = ""
    stars: int = 0
    stars_gained: int = 0
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    repo_url: str = ""
    last_updated: str = ""
    category: str = "other"


class KeywordIn(BaseModel):
    keyword: str
    category: str = "other"


class KeywordOut(BaseModel):
    id: int
    keyword: str
    category: str
    created_at: str


class StatusOut(BaseModel):
    total_projects: int
    last_fetched: str
    is_refreshing: bool
    refresh_stage: str = ""
    refresh_detail: str = ""
    translate_total: int = 0
    translate_done: int = 0
    translation_pending: int = 0
    translation_processing: int = 0
    translation_retry: int = 0
    translation_failed: int = 0
    translation_done: int = 0
    last_refresh_error: str = ""
    last_refresh_failed_at: str = ""
    last_refresh_completed_at: str = ""
    data_age_hours: float | None = None
    data_stale_after_hours: int = 0
    is_data_stale: bool = False


class HealthOut(BaseModel):
    status: str
    checks: dict
    problems: list[str] = Field(default_factory=list)


class CategoryOut(BaseModel):
    key: str
    name: str
    count: int
