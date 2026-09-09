import asyncio
import time
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks
from app.database import get_connection
from app.models import HealthOut, StatusOut
from app.state_store import (
    get_runtime_bool,
    get_runtime_int,
    get_runtime_state,
    set_runtime_state,
)

router = APIRouter(prefix="/api")


def set_progress(stage="", total=0, done=0, detail=""):
    set_runtime_state(
        refresh_stage=stage,
        refresh_detail=detail,
        progress_total=total,
        progress_done=done,
    )


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _parse_datetime(value: str):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _get_latest_fetched_at() -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT fetched_at FROM projects WHERE fetched_at != '' ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["fetched_at"] if row else ""


_MODEL_CHECK_TTL_SECONDS = 600
_model_check_cache: dict = {"key": None, "checked_at": 0.0, "result": None}


def _check_model_available(config, api_key_ok: bool) -> dict:
    """Confirm API_MODEL is listed by the endpoint's /models. Cached to avoid hammering the gateway."""
    from app.ai_client import list_available_models

    if not config.AI_MODEL_CHECK:
        return {"ok": True, "model": config.API_MODEL, "skipped": "disabled"}
    if not api_key_ok:
        return {"ok": True, "model": config.API_MODEL, "skipped": "no api key"}

    cache_key = (config.API_ENDPOINT, config.API_MODEL, config.API_KEY)
    now = time.monotonic()
    if (
        _model_check_cache["key"] == cache_key
        and _model_check_cache["result"] is not None
        and now - _model_check_cache["checked_at"] < _MODEL_CHECK_TTL_SECONDS
    ):
        return _model_check_cache["result"]

    try:
        models = list_available_models()
    except Exception as exc:
        # Cannot reach /models: don't block on it, but surface the reason.
        result = {
            "ok": True,
            "model": config.API_MODEL,
            "skipped": f"models endpoint unreachable: {str(exc)[:120]}",
        }
    else:
        available = config.API_MODEL in models
        result = {
            "ok": available,
            "model": config.API_MODEL,
            "available_models": models,
        }
        if not available:
            result["problem"] = (
                f"Model '{config.API_MODEL}' is not available on the endpoint; "
                f"available: {', '.join(models) or 'none'}"
            )
    _model_check_cache.update(key=cache_key, checked_at=now, result=result)
    return result


def reset_model_check_cache():
    _model_check_cache.update(key=None, checked_at=0.0, result=None)


def _build_data_freshness(latest_fetched_at: str, stale_after_hours: int) -> dict:
    latest_fetched = _parse_datetime(latest_fetched_at)
    age_hours = None
    if latest_fetched:
        age_hours = round((datetime.now(timezone.utc) - latest_fetched).total_seconds() / 3600, 1)
    is_stale = age_hours is not None and age_hours > stale_after_hours
    return {
        "ok": not is_stale,
        "latest_fetched_at": latest_fetched_at,
        "age_hours": age_hours,
        "stale_after_hours": stale_after_hours,
    }


@router.get("/status", response_model=StatusOut)
def get_status():
    from app.config import config

    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    last = conn.execute(
        "SELECT fetched_at FROM projects ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    counts = {
        row["translation_status"] or "pending": row["count"]
        for row in conn.execute(
            "SELECT translation_status, COUNT(*) AS count FROM projects GROUP BY translation_status"
        ).fetchall()
    }
    conn.close()
    runtime_state = get_runtime_state(
        "refresh_stage",
        "refresh_detail",
        "progress_total",
        "progress_done",
        "last_refresh_error",
        "last_refresh_failed_at",
        "last_refresh_completed_at",
    )
    latest_fetched = last[0] if last else ""
    freshness = _build_data_freshness(latest_fetched, config.DATA_STALE_HOURS)
    return StatusOut(
        total_projects=total,
        last_fetched=latest_fetched,
        is_refreshing=get_runtime_bool("is_refreshing"),
        refresh_stage=runtime_state["refresh_stage"],
        refresh_detail=runtime_state["refresh_detail"],
        translate_total=get_runtime_int("progress_total"),
        translate_done=get_runtime_int("progress_done"),
        translation_pending=counts.get("pending", 0),
        translation_processing=counts.get("processing", 0),
        translation_retry=counts.get("retry", 0),
        translation_failed=counts.get("failed", 0),
        translation_done=counts.get("done", 0),
        last_refresh_error=runtime_state["last_refresh_error"],
        last_refresh_failed_at=runtime_state["last_refresh_failed_at"],
        last_refresh_completed_at=runtime_state["last_refresh_completed_at"],
        data_age_hours=freshness["age_hours"],
        data_stale_after_hours=freshness["stale_after_hours"],
        is_data_stale=not freshness["ok"],
    )


@router.get("/health", response_model=HealthOut)
def get_health():
    from app.config import config

    checks = {}
    problems = []

    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database"] = {"ok": True, "path": config.DB_PATH}
    except Exception as exc:
        checks["database"] = {"ok": False, "path": config.DB_PATH, "error": str(exc)}
        problems.append("Database check failed")

    checks["data_freshness"] = _build_data_freshness(
        _get_latest_fetched_at(),
        config.DATA_STALE_HOURS,
    )
    if not checks["data_freshness"]["ok"]:
        problems.append("Project data is stale")

    api_key_ok = bool((config.API_KEY or "").strip())
    checks["model_api_key"] = {
        "ok": api_key_ok,
        "endpoint": config.API_ENDPOINT,
        "model": config.API_MODEL,
    }
    if not api_key_ok:
        problems.append("API_KEY is not configured")

    checks["model_available"] = _check_model_available(config, api_key_ok)
    if not checks["model_available"]["ok"]:
        problems.append(checks["model_available"]["problem"])

    github_token_ok = bool((config.GITHUB_TOKEN or "").strip())
    checks["github_token"] = {"ok": github_token_ok}
    if not github_token_ok:
        problems.append("GITHUB_TOKEN is not configured; GitHub API rate limits will be lower")

    proxy = config.PROXY or ""
    checks["proxy"] = {
        "ok": bool(proxy),
        "value": proxy,
    }
    if not proxy:
        problems.append("Proxy is not configured")

    refresh_state = get_runtime_state("last_refresh_error", "last_refresh_failed_at")
    last_refresh_error = refresh_state["last_refresh_error"]
    checks["last_refresh"] = {
        "ok": not bool(last_refresh_error),
        "failed_at": refresh_state["last_refresh_failed_at"],
    }
    if last_refresh_error:
        problems.append(f"Last refresh failed: {last_refresh_error}")

    status = "ok" if all(check.get("ok") for check in checks.values()) else "warning"
    return HealthOut(status=status, checks=checks, problems=problems)


@router.post("/refresh")
async def refresh(background_tasks: BackgroundTasks):
    if get_runtime_bool("is_refreshing"):
        return {"message": "already refreshing"}
    set_runtime_state(is_refreshing="1")
    background_tasks.add_task(_do_refresh)
    return {"message": "refresh started"}


async def _do_refresh():
    import logging
    logger = logging.getLogger("refresh")
    try:
        from app.scraper import run_full_scrape
        from app.translator import start_translation_worker
        from app.scorer import update_all_scores
        set_runtime_state(is_refreshing="1", last_refresh_error="")
        set_progress("scraping")
        logger.info("Starting scrape...")
        await run_full_scrape()
        logger.info("Scrape done. Starting translation worker...")
        start_translation_worker()
        set_progress("scoring")
        logger.info("Updating scores...")
        update_all_scores()
        set_progress()
        set_runtime_state(
            last_refresh_error="",
            last_refresh_completed_at=_utc_now_str(),
        )
        logger.info("Refresh complete.")
    except Exception as e:
        set_runtime_state(
            last_refresh_error=str(e)[:500],
            last_refresh_failed_at=_utc_now_str(),
        )
        logger.error(f"Refresh failed: {e}", exc_info=True)
    finally:
        set_progress()
        set_runtime_state(is_refreshing="0")


@router.post("/translations/retry-failed")
async def retry_failed_translations():
    from app.translator import start_translation_worker

    conn = get_connection()
    conn.execute(
        """
        UPDATE projects
        SET translation_status = 'pending',
            translation_error = '',
            translation_next_retry_at = '',
            translation_attempts = 0
        WHERE translation_status IN ('retry', 'failed')
        """
    )
    conn.commit()
    conn.close()
    start_translation_worker()
    return {"message": "retry queued"}


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
