import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from app.ai_client import extract_json_object, extract_message_content
from app.config import config
from app.database import get_connection
from app.state_store import get_runtime_value, set_runtime_state
from app.translation_provider import build_translation_provider


logger = logging.getLogger("translator")

_worker_task = None
_translation_rate_lock = asyncio.Lock()
_last_translation_request_at = 0.0


class TranslationRetryableError(Exception):
    pass


def build_translate_prompt(repo_name: str, description: str, readme: str) -> str:
    readme_excerpt = (readme or "")[:config.TRANSLATION_README_CHARS]
    return (
        "You are a GitHub project translation assistant. Translate the project into natural Chinese. "
        "Return JSON only.\n"
        f"repo_name: {repo_name}\n"
        f"description: {description}\n"
        f"readme: {readme_excerpt}\n\n"
        "JSON schema:\n"
        "{\n"
        '  "description_zh": "One concise Chinese sentence that explains what the project does and who it helps.",\n'
        '  "readme_summary_zh": "3-5 concise Chinese bullet-style points covering core features, use cases, and highlights."\n'
        "}\n"
    )


def parse_translate_response(text: str) -> dict:
    data = extract_json_object(text)
    return {
        "description_zh": _normalize_translation_value(data.get("description_zh")),
        "readme_summary_zh": _normalize_translation_value(data.get("readme_summary_zh")),
    }


def _normalize_translation_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip()).strip()
    return str(value).strip()


def make_source_signature(repo_name: str, description: str, readme: str) -> str:
    content = "\n".join([repo_name or "", description or "", readme or ""])
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_str() -> str:
    return _utc_now().strftime("%Y-%m-%d %H:%M:%S")


def _next_retry_at(attempt: int) -> str:
    delays = [5, 30, 120]
    minutes = delays[min(max(attempt - 1, 0), len(delays) - 1)]
    return (_utc_now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def _next_throttle_retry_at() -> str:
    return (_utc_now() + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")


def _is_external_throttle_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message
        or "too many requests" in message
        or "rate limit" in message
        or "daily token budget reached" in message
    )


def _reset_daily_budget_if_needed():
    today = time.strftime("%Y-%m-%d")
    if get_runtime_value("translation_budget_date") != today:
        set_runtime_state(
            translation_daily_tokens_used="0",
            translation_budget_date=today,
        )


def _get_daily_tokens_used() -> int:
    _reset_daily_budget_if_needed()
    try:
        return int(get_runtime_value("translation_daily_tokens_used", "0"))
    except (TypeError, ValueError):
        return 0


def _add_daily_tokens_used(tokens: int):
    current = _get_daily_tokens_used()
    set_runtime_state(
        translation_daily_tokens_used=str(current + max(tokens, 0)),
        translation_budget_date=time.strftime("%Y-%m-%d"),
    )


async def fetch_readme_for_translation(repo_full_name: str) -> str:
    from app.scraper import fetch_readme

    return await fetch_readme(repo_full_name)


async def translate_project(repo_name: str, description: str, readme: str) -> dict:
    if _get_daily_tokens_used() >= config.MAX_DAILY_TOKENS:
        raise TranslationRetryableError("daily token budget reached")

    prompt = build_translate_prompt(repo_name, description, readme)
    provider = build_translation_provider()

    try:
        await _wait_for_translation_rate_limit()
        data = await provider.translate(prompt)
        content = extract_message_content(data)
        usage = data.get("usage", {})
        _add_daily_tokens_used(usage.get("total_tokens", 0))
    except Exception as exc:
        raise TranslationRetryableError(str(exc)) from exc

    result = parse_translate_response(content)
    if not result["description_zh"] and not result["readme_summary_zh"]:
        raise TranslationRetryableError("empty translation result")
    return result


async def _wait_for_translation_rate_limit():
    global _last_translation_request_at

    interval = max(float(config.TRANSLATION_REQUEST_INTERVAL_SECONDS), 0.0)
    if config.MAX_REQUESTS_PER_MINUTE > 0:
        interval = max(interval, 60.0 / config.MAX_REQUESTS_PER_MINUTE)
    if interval <= 0:
        return

    async with _translation_rate_lock:
        now = time.monotonic()
        wait_seconds = interval - (now - _last_translation_request_at)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        _last_translation_request_at = time.monotonic()


def select_translation_candidates(limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM projects
        WHERE translation_status = 'pending'
           OR (
               translation_status = 'retry'
               AND (
                   translation_next_retry_at = ''
                   OR translation_next_retry_at IS NULL
                   OR translation_next_retry_at <= datetime('now')
               )
           )
        ORDER BY
            CASE WHEN translation_status = 'pending' THEN 0 ELSE 1 END,
            stars_gained DESC,
            stars DESC,
            fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def _update_translation_state(project_id: int, **fields):
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields.keys())
    conn = get_connection()
    conn.execute(
        f"UPDATE projects SET {assignments} WHERE id = ?",
        [*fields.values(), project_id],
    )
    conn.commit()
    conn.close()


def reset_processing_translations() -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE projects
        SET translation_status = 'pending',
            translation_error = '',
            translation_next_retry_at = ''
        WHERE translation_status = 'processing'
        """
    )
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return changed


async def translate_project_row(row) -> bool:
    readme = ""
    try:
        readme = await fetch_readme_for_translation(row["repo_full_name"])
    except Exception:
        readme = ""

    signature = make_source_signature(row["repo_full_name"], row["description"], readme)
    _update_translation_state(
        row["id"],
        translation_status="processing",
        source_signature=signature,
        readme_fetched_at=_utc_now_str(),
        translation_error="",
    )

    if row["description_zh"] and row["translated_signature"] == signature:
        _update_translation_state(row["id"], translation_status="done")
        return True

    try:
        result = await translate_project(row["repo_full_name"], row["description"], readme)
    except Exception as exc:
        is_throttle = _is_external_throttle_error(exc)
        attempts = row["translation_attempts"] or 0
        if not is_throttle:
            attempts += 1
        status = "retry" if is_throttle or attempts < config.TRANSLATION_MAX_RETRIES else "failed"
        _update_translation_state(
            row["id"],
            translation_status=status,
            translation_attempts=attempts,
            translation_next_retry_at=_next_throttle_retry_at() if is_throttle else _next_retry_at(attempts),
            translation_error=str(exc)[:300],
        )
        return False

    _update_translation_state(
        row["id"],
        description_zh=result["description_zh"],
        readme_summary_zh=result["readme_summary_zh"],
        translated_at=_utc_now_str(),
        translation_status="done",
        translation_attempts=0,
        translation_next_retry_at="",
        translation_error="",
        translated_signature=signature,
        translation_provider=config.TRANSLATION_PROVIDER,
        translation_model=config.TRANSLATION_MODEL,
    )
    return True


async def process_translation_queue(limit: int | None = None) -> int:
    rows = select_translation_candidates(limit or config.TRANSLATION_BATCH_SIZE)
    if not rows:
        return 0

    semaphore = asyncio.Semaphore(config.TRANSLATION_CONCURRENCY)

    async def _run(row):
        async with semaphore:
            return await translate_project_row(row)

    results = await asyncio.gather(*[_run(row) for row in rows], return_exceptions=True)
    return sum(1 for result in results if result is True)


async def run_translation_worker():
    while True:
        processed = await process_translation_queue()
        if processed == 0:
            if not select_translation_candidates(limit=1):
                break
            await asyncio.sleep(1)


def is_translation_worker_running() -> bool:
    return _worker_task is not None and not _worker_task.done()


async def _run_translation_worker_task():
    global _worker_task

    try:
        await run_translation_worker()
    finally:
        set_runtime_state(translation_worker_running="0")
        _worker_task = None


def start_translation_worker() -> bool:
    global _worker_task
    if is_translation_worker_running():
        return False
    loop = asyncio.get_running_loop()
    set_runtime_state(translation_worker_running="1")
    _worker_task = loop.create_task(_run_translation_worker_task())
    return True


async def translate_untranslated_projects():
    logger.info("Processing translation queue")
    await run_translation_worker()
