from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import config

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
    scheduler.start()


def stop_scheduler():
    if getattr(scheduler, "running", False):
        scheduler.shutdown(wait=False)
