from app import scheduler as scheduler_module


def test_start_scheduler_registers_daily_refresh_and_translation_retry_jobs(monkeypatch):
    calls = []

    class FakeScheduler:
        def add_job(self, func, **kwargs):
            calls.append(("add_job", kwargs["id"], kwargs["trigger"]))

        def start(self):
            calls.append(("start",))

    monkeypatch.setattr(scheduler_module, "scheduler", FakeScheduler())

    scheduler_module.start_scheduler()

    assert ("add_job", "daily_refresh", "cron") in calls
    assert ("add_job", "translation_retry", "interval") in calls
    assert ("start",) in calls


def test_missed_daily_refresh_is_caught_up_once(monkeypatch):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from app import state_store
    from app.routers import system

    runs = []

    async def fake_refresh():
        runs.append(1)

    state = {"refreshing": False, "completed": "", "failed": ""}
    monkeypatch.setattr(system, "_do_refresh", fake_refresh)
    monkeypatch.setattr(state_store, "get_runtime_bool", lambda key: state["refreshing"])
    monkeypatch.setattr(state_store, "get_runtime_value", lambda key, default="":
                        state["completed"] if key == "last_refresh_completed_at" else state["failed"])
    stamp = lambda hours: (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    assert asyncio.run(scheduler_module.refresh_if_overdue()) is True  # never refreshed
    state["completed"] = stamp(30)
    assert asyncio.run(scheduler_module.refresh_if_overdue()) is True  # missed a day
    state["failed"] = stamp(2)
    assert asyncio.run(scheduler_module.refresh_if_overdue()) is False  # tried recently, do not hammer
    state.update(failed="", completed=stamp(3))
    assert asyncio.run(scheduler_module.refresh_if_overdue()) is False  # fresh
    state.update(completed=stamp(30), refreshing=True)
    assert asyncio.run(scheduler_module.refresh_if_overdue()) is False  # already running
    assert len(runs) == 2
