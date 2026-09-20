import logging
import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from influx import get_health
from scheduled_reports import load_schedules, register_report_jobs


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

INTERVAL_MINUTES = int(
    os.getenv(
        "REPORT_INTERVAL_MINUTES",
        "15",
    )
)

scheduler = BlockingScheduler(
    timezone=os.getenv("TZ", "Europe/Rome"),
    # Matplotlib rendering is serialized within the scheduler process.
    executors={"reports": ThreadPoolExecutor(max_workers=1)},
)


def scheduled_job():
    try:
        health = get_health()

        logger.info(
            "InfluxDB health: status=%s message=%s",
            health["status"],
            health["message"],
        )

    except Exception:
        logger.exception(
            "Scheduled InfluxDB check failed"
        )


def shutdown(signum, frame):
    logger.info(
        "Stopping scheduler"
    )

    scheduler.shutdown(
        wait=False
    )


signal.signal(
    signal.SIGTERM,
    shutdown,
)

signal.signal(
    signal.SIGINT,
    shutdown,
)


scheduler.add_job(
    scheduled_job,
    trigger="interval",
    minutes=INTERVAL_MINUTES,
    id="influx-health-check",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)


if __name__ == "__main__":
    register_report_jobs(
        scheduler,
        load_schedules(os.getenv("REPORT_SCHEDULES", "[]")),
    )

    logger.info(
        "Starting scheduler with interval=%s minutes",
        INTERVAL_MINUTES,
    )

    scheduled_job()

    try:
        scheduler.start()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
