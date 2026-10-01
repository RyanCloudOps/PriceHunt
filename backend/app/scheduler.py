from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.services.refresh import refresh_if_stale, run_refresh

_scheduler: BackgroundScheduler | None = None


def start() -> None:
    global _scheduler
    settings = get_settings()
    _scheduler = BackgroundScheduler(timezone=settings.timezone)
    # Refresco diario a hora fija
    _scheduler.add_job(
        run_refresh,
        # Ojo: un trigger explícito no hereda la zona del scheduler
        CronTrigger(hour=settings.refresh_cron_hour, minute=0, timezone=settings.timezone),
        args=["schedule"],
        id="daily_refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    # Si el equipo estuvo apagado/suspendido a esa hora, esto lo recupera
    _scheduler.add_job(
        refresh_if_stale,
        IntervalTrigger(minutes=settings.stale_check_minutes),
        id="stale_check",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


def shutdown() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


def next_run() -> datetime | None:
    if not _scheduler:
        return None
    job = _scheduler.get_job("daily_refresh")
    return job.next_run_time if job else None
