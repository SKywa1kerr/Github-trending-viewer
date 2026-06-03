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
