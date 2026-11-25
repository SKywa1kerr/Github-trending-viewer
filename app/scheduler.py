from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import config

# A day plus slack: only a run the cron job missed (computer off or asleep) is overdue.
OVERDUE_AFTER = timedelta(hours=25)


def _last_refresh_attempt():
    from app.state_store import get_runtime_value

    attempts = []
    for key in ("last_refresh_completed_at", "last_refresh_failed_at"):
        try:
            attempts.append(datetime.strptime(get_runtime_value(key, ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc))
        except (TypeError, ValueError):
            continue
    return max(attempts, default=None)


async def refresh_if_overdue() -> bool:
    """Catch up when the daily refresh was missed; the in-memory cron job does not replay it."""
    from app.routers.system import _do_refresh
    from app.state_store import get_runtime_bool

    if get_runtime_bool("is_refreshing"):
        return False
    last = _last_refresh_attempt()
    if last is not None and datetime.now(timezone.utc) - last < OVERDUE_AFTER:
        return False
    await _do_refresh()
    return True

scheduler = AsyncIOScheduler()


def start_scheduler():
    if getattr(scheduler, "running", False):
        return
    from app.routers.system import _do_refresh
    from app.translator import start_translation_worker
    scheduler.add_job(
        _do_refresh,
        trigger="cron",
        hour=config.UPDATE_HOUR,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
        timezone="Asia/Shanghai"
    )
    scheduler.add_job(
        start_translation_worker,
        trigger="interval",
        minutes=10,
        id="translation_retry",
        replace_existing=True,
        timezone="Asia/Shanghai"
    )
    scheduler.add_job(
        refresh_if_overdue,
        trigger="interval",
        minutes=30,
        id="refresh_catch_up",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=3),
        timezone="Asia/Shanghai"
    )
    scheduler.start()


def stop_scheduler():
    if getattr(scheduler, "running", False):
        scheduler.shutdown(wait=False)
