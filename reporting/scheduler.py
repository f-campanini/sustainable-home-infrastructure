import logging
import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from influx import get_health


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
    timezone="Europe/Rome"
)


def scheduled_job():
    try:
        health = get_health()

        logger.info(
            "InfluxDB health: status=%s version=%s",
            health["status"],
            health["version"],
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
    logger.info(
        "Starting scheduler with interval=%s minutes",
        INTERVAL_MINUTES,
    )

    scheduled_job()

    try:
        scheduler.start()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
