"""Configured daily charts using the Historical Explorer data path."""

import json
import logging
import re
from dataclasses import dataclass

from artifact import new_report_id, save_png
from charts import render_chart
from query_service import (
    NoDataError,
    NonNumericDataError,
    list_entities,
    run_historical_query,
    validate_query,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportSchedule:
    name: str
    hour: int
    minute: int
    entities: tuple
    query: dict


def load_schedules(raw):
    """Validate configuration before registering any jobs."""
    entries = json.loads(raw)
    if not isinstance(entries, list):
        raise ValueError("REPORT_SCHEDULES must be a JSON list.")

    schedules = []
    names = set()
    allowed = {
        "name", "hour", "minute", "entities", "measurement",
        "range_name", "aggregation", "function", "chart_type",
    }
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError("Invalid scheduled report fields.")
        name = entry.get("name")
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name)
            or name in names
        ):
            raise ValueError("Report names must be unique safe identifiers.")

        hour = entry.get("hour", 0)
        minute = entry.get("minute", 5)
        if type(hour) is not int or not 0 <= hour <= 23:
            raise ValueError("Report hour must be an integer from 0 to 23.")
        if type(minute) is not int or not 0 <= minute <= 59:
            raise ValueError("Report minute must be an integer from 0 to 59.")

        entities = entry.get("entities", [])
        if not isinstance(entities, list) or any(
            not isinstance(entity, str) or not entity.strip()
            for entity in entities
        ):
            raise ValueError("Report entities must be a list of non-empty strings.")

        query = {
            "measurement": entry.get("measurement", "W"),
            "range_name": entry.get("range_name", "24h"),
            "aggregation": entry.get("aggregation", "15m"),
            "function": entry.get("function", "mean"),
            "chart_type": entry.get("chart_type", "line"),
        }
        if not all(isinstance(value, str) for value in query.values()):
            raise ValueError("Report query options must be strings.")
        validate_query(entity_id="configuration-check", **query)
        schedules.append(ReportSchedule(
            name, hour, minute, tuple(dict.fromkeys(entities)), query,
        ))
        names.add(name)
    return schedules


def generate_scheduled_report(schedule):
    """Save one PNG per sensor; a failed sensor does not stop the others."""
    try:
        entities = schedule.entities or list_entities(schedule.query["measurement"])
    except Exception:
        logger.exception("Scheduled report %s: sensor discovery failed", schedule.name)
        return

    if not entities:
        logger.info("Scheduled report %s: no sensors found", schedule.name)
        return

    for entity in entities:
        try:
            query = validate_query(entity_id=entity, **schedule.query)
            data = run_historical_query(query)
            image = render_chart(
                data,
                chart_type=query.chart_type,
                title=f"{query.entity_id} ({query.range_name})",
            )
            with image:
                path = save_png(
                    image,
                    report_id=f"scheduled-{schedule.name}-{new_report_id()}",
                )
            logger.info(
                "Scheduled report %s: saved %s entity=%s points=%s",
                schedule.name, path.name, entity, len(data),
            )
        except (NoDataError, NonNumericDataError) as error:
            logger.warning(
                "Scheduled report %s: skipped entity=%s: %s",
                schedule.name, entity, error,
            )
        except Exception:
            logger.exception(
                "Scheduled report %s: failed entity=%s", schedule.name, entity,
            )


def register_report_jobs(scheduler, schedules):
    for schedule in schedules:
        scheduler.add_job(
            generate_scheduled_report,
            trigger="cron",
            hour=schedule.hour,
            minute=schedule.minute,
            args=[schedule],
            id=f"report-{schedule.name}",
            executor="reports",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        logger.info(
            "Scheduled report %s: daily at %02d:%02d (%s)",
            schedule.name, schedule.hour, schedule.minute, scheduler.timezone,
        )
