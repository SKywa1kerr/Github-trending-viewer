from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import config

scheduler = AsyncIOScheduler()


def start_scheduler():
    from app.routers.system import _do_refresh
    scheduler.add_job(
        _do_refresh,
        trigger="cron",
        hour=config.UPDATE_HOUR,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
        timezone="Asia/Shanghai"
    )
    scheduler.start()
