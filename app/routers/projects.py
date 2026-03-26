import json
from fastapi import APIRouter, Query
from app.database import get_connection

router = APIRouter(prefix="/api")


@router.get("/projects")
def list_projects(
    category: str = Query(None),
    language: str = Query(None),
    sort: str = Query("score"),
    q: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_connection()
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if language:
        conditions.append("language = ?")
        params.append(language)
    if q:
        conditions.append("(repo_full_name LIKE ? OR description LIKE ? OR description_zh LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sort_map = {
        "score": "score DESC",
        "stars": "stars DESC",
        "stars_gained": "stars_gained DESC",
        "updated": "last_updated DESC",
    }
    order = sort_map.get(sort, "score DESC")

    offset = (page - 1) * page_size

    total = conn.execute(f"SELECT COUNT(*) FROM projects {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM projects {where} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    items = []
    for r in rows:
        topics = json.loads(r["topics"]) if r["topics"] else []
        items.append({
            "id": r["id"],
            "repo_full_name": r["repo_full_name"],
            "description": r["description"],
            "description_zh": r["description_zh"],
            "readme_summary_zh": r["readme_summary_zh"],
            "stars": r["stars"],
            "stars_gained": r["stars_gained"],
            "language": r["language"],
            "topics": topics,
            "category": r["category"],
            "repo_url": r["repo_url"],
            "score": r["score"],
            "last_updated": r["last_updated"],
            "fetched_at": r["fetched_at"],
        })
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    topics = json.loads(row["topics"]) if row["topics"] else []
    return {
        "id": row["id"],
        "repo_full_name": row["repo_full_name"],
        "description": row["description"],
        "description_zh": row["description_zh"],
        "readme_summary_zh": row["readme_summary_zh"],
        "stars": row["stars"],
        "stars_gained": row["stars_gained"],
        "language": row["language"],
        "topics": topics,
        "category": row["category"],
        "repo_url": row["repo_url"],
        "score": row["score"],
        "last_updated": row["last_updated"],
        "fetched_at": row["fetched_at"],
    }
