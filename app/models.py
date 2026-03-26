from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: int
    repo_full_name: str
    description: str
    description_zh: str
    readme_summary_zh: str
    stars: int
    stars_gained: int
    language: str
    topics: list[str]
    category: str
    repo_url: str
    score: float
    last_updated: str
    fetched_at: str


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


class CategoryOut(BaseModel):
    key: str
    name: str
    count: int
