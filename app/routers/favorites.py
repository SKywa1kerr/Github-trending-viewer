import json
from fastapi import APIRouter, HTTPException, Query
from app.database import get_connection
from app.project_filters import build_project_filters

router = APIRouter(prefix="/api")


@router.get("/favorites/ids")
def get_favorite_ids():
    conn = get_connection()
    rows = conn.execute("SELECT project_id FROM favorites").fetchall()
    conn.close()
    return [r["project_id"] for r in rows]


@router.get("/favorites")
def list_favorites(
    sort: str = Query("score"),
    language: str = Query(None),
    q: str = Query(None),
    min_stars: int = Query(0, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_connection()
    sort_map = {
        "score": "p.score DESC",
        "stars": "p.stars DESC",
        "stars_gained": "p.stars_gained DESC",
        "updated": "p.last_updated DESC",
        "favorited": "f.created_at DESC",
        "newest": "p.first_seen_at DESC",
    }
    order = sort_map.get(sort, "f.created_at DESC") + ", p.id DESC"
    offset = (page - 1) * page_size
    where, params = build_project_filters(language=language, q=q, min_stars=min_stars, prefix="p.")

    total = conn.execute(
        f"SELECT COUNT(*) FROM favorites f JOIN projects p ON f.project_id = p.id {where}",
        params,
    ).fetchone()[0]

    rows = conn.execute(
        f"SELECT p.*, f.created_at AS favorited_at FROM projects p "
        f"JOIN favorites f ON f.project_id = p.id "
        f"{where} "
        f"ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    items = []
    for r in rows:
        topics = json.loads(r["topics"]) if r["topics"] else []
        is_new = False
        if r["first_seen_at"]:
            is_new = r["first_seen_at"] > _one_day_ago()
        items.append({
            "id": r["id"],
            "repo_full_name": r["repo_full_name"],
            "description": r["description"],
            "description_zh": r["description_zh"],
            "readme_summary_zh": r["readme_summary_zh"],
            "translation_status": r["translation_status"] if "translation_status" in r.keys() else "",
            "translation_attempts": r["translation_attempts"] if "translation_attempts" in r.keys() else 0,
            "stars": r["stars"],
            "stars_gained": r["stars_gained"],
            "language": r["language"],
            "topics": topics,
            "category": r["category"],
            "repo_url": r["repo_url"],
            "score": r["score"],
            "last_updated": r["last_updated"],
            "fetched_at": r["fetched_at"],
            "first_seen_at": r["first_seen_at"],
            "is_favorited": True,
            "is_new": is_new,
        })
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/favorites/{project_id}")
def add_favorite(project_id: int):
    conn = get_connection()
    exists = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        conn.execute("INSERT INTO favorites (project_id) VALUES (?)", (project_id,))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=409, detail="Already favorited")
    conn.close()
    return {"status": "ok"}


@router.delete("/favorites/{project_id}")
def remove_favorite(project_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM favorites WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


def _one_day_ago():
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
