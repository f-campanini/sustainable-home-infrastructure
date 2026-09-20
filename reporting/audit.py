import time
import uuid
from datetime import datetime, timezone

from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from influx import (
    INFLUXDB_AUDIT_BUCKET,
    get_client,
)


def new_request_id():
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d%H%M%S")

    suffix = uuid.uuid4().hex[:8]

    return f"Q-{timestamp}-{suffix}"


class QueryTimer:
    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.execution_ms = int(
            (time.perf_counter() - self.started) * 1000
        )


def write_query_audit(
    *,
    request_id,
    measurement,
    entity_id,
    range_name,
    aggregation,
    function,
    chart_type,
    status,
    result_points=0,
    execution_ms=0,
    error_message="",
):
    point = (
        Point("query_audit")
        .tag("status", status)
        .tag("chart_type", chart_type)
        .tag("function", function)
        .tag("aggregation", aggregation)
        .field("request_id", request_id)
        .field("measurement", measurement)
        .field("entity_id", entity_id)
        .field("range_name", range_name)
        .field("result_points", int(result_points))
        .field("execution_ms", int(execution_ms))
        .field("error_message", error_message or "")
    )

    with get_client() as client:
        with client.write_api(write_options=SYNCHRONOUS) as write_api:
            write_api.write(
                bucket=INFLUXDB_AUDIT_BUCKET,
                record=point,
            )
