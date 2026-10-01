from zoneinfo import ZoneInfo

from app import scheduler


def test_daily_refresh_runs_at_local_hour(monkeypatch):
    monkeypatch.setenv("TIMEZONE", "Europe/Madrid")
    monkeypatch.setenv("REFRESH_CRON_HOUR", "7")
    scheduler.get_settings.cache_clear()
    try:
        scheduler.start()
        nxt = scheduler.next_run()
        local = nxt.astimezone(ZoneInfo("Europe/Madrid"))
        assert (local.hour, local.minute) == (7, 0)
    finally:
        scheduler.shutdown()
        scheduler.get_settings.cache_clear()
