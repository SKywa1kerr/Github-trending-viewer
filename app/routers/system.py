import asyncio
from fastapi import APIRouter, BackgroundTasks
from app.database import get_connection
from app.models import StatusOut

router = APIRouter(prefix="/api")

_is_refreshing = False


@router.get("/status", response_model=StatusOut)
def get_status():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    last = conn.execute(
        "SELECT fetched_at FROM projects ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return StatusOut(
        total_projects=total,
        last_fetched=last[0] if last else "",
        is_refreshing=_is_refreshing
    )


@router.post("/refresh")
async def refresh(background_tasks: BackgroundTasks):
    global _is_refreshing
    if _is_refreshing:
        return {"message": "already refreshing"}
    _is_refreshing = True
    background_tasks.add_task(_do_refresh)
    return {"message": "refresh started"}


async def _do_refresh():
    global _is_refreshing
    try:
        from app.scraper import run_full_scrape
        from app.translator import translate_untranslated_projects
        from app.scorer import update_all_scores
        await run_full_scrape()
        await translate_untranslated_projects()
        update_all_scores()
    finally:
        _is_refreshing = False


@router.get("/categories")
def get_categories():
    from app.config import config
    conn = get_connection()
    results = []
    for key, info in config.CATEGORIES.items():
        count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE category = ?", (key,)
        ).fetchone()[0]
        results.append({"key": key, "name": info["name"], "count": count})
    other_count = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE category = 'other'"
    ).fetchone()[0]
    results.append({"key": "other", "name": "其他热门", "count": other_count})
    conn.close()
    return results


@router.get("/languages")
def get_languages():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT language FROM projects WHERE language != '' ORDER BY language"
    ).fetchall()
    conn.close()
    return [r["language"] for r in rows]
