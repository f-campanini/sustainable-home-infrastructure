from dataclasses import dataclass

import pandas as pd

from influx import INFLUXDB_BUCKET, get_client


ALLOWED_MEASUREMENTS = {
    "W": "Power",
    "kWh": "Energy",
    "V": "Voltage",
    "A": "Current",
}

ALLOWED_RANGES = {
    "24h": "-24h",
    "48h": "-48h",
    "7d": "-7d",
    "30d": "-30d",
    "90d": "-90d",
}

ALLOWED_AGGREGATIONS = {
    "raw": None,
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "1d": "1d",
}

ALLOWED_FUNCTIONS = {
    "mean",
    "min",
    "max",
    "sum",
}

ALLOWED_CHART_TYPES = {
    "line",
    "bar",
}


@dataclass(frozen=True)
class HistoricalQuery:
    measurement: str
    entity_id: str
    range_name: str
    aggregation: str
    function: str
    chart_type: str


class QueryValidationError(ValueError):
    pass


class NoDataError(Exception):
    pass


class NonNumericDataError(Exception):
    pass


def validate_query(
    *,
    measurement,
    entity_id,
    range_name,
    aggregation,
    function,
    chart_type,
):
    if measurement not in ALLOWED_MEASUREMENTS:
        raise QueryValidationError(
            "The selected measurement is not supported."
        )

    if not entity_id:
        raise QueryValidationError(
            "Please select a sensor."
        )

    if range_name not in ALLOWED_RANGES:
        raise QueryValidationError(
            "The selected time period is not supported."
        )

    if aggregation not in ALLOWED_AGGREGATIONS:
        raise QueryValidationError(
            "The selected aggregation is not supported."
        )

    if function not in ALLOWED_FUNCTIONS:
        raise QueryValidationError(
            "The selected calculation is not supported."
        )

    if chart_type not in ALLOWED_CHART_TYPES:
        raise QueryValidationError(
            "The selected chart type is not supported."
        )

    return HistoricalQuery(
        measurement=measurement,
        entity_id=entity_id,
        range_name=range_name,
        aggregation=aggregation,
        function=function,
        chart_type=chart_type,
    )


def _escape_flux_string(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def list_entities(measurement):
    if measurement not in ALLOWED_MEASUREMENTS:
        raise QueryValidationError(
            "The selected measurement is not supported."
        )

    escaped_measurement = _escape_flux_string(
        measurement
    )

    flux = f'''
import "influxdata/influxdb/schema"

schema.tagValues(
    bucket: "{INFLUXDB_BUCKET}",
    tag: "entity_id",
    predicate: (r) =>
        r._measurement == "{escaped_measurement}",
    start: -90d,
)
'''

    values = set()

    with get_client() as client:
        tables = client.query_api().query(
            query=flux
        )

        for table in tables:
            for record in table.records:
                value = record.get_value()

                if value:
                    values.add(str(value))

    return sorted(values)


def _validate_data_exists(query):
    escaped_measurement = _escape_flux_string(
        query.measurement
    )

    escaped_entity = _escape_flux_string(
        query.entity_id
    )

    start = ALLOWED_RANGES[
        query.range_name
    ]

    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: {start})
  |> filter(fn: (r) =>
      r["_measurement"] == "{escaped_measurement}")
  |> filter(fn: (r) =>
      r["entity_id"] == "{escaped_entity}")
  |> filter(fn: (r) =>
      r["_field"] == "value")
  |> limit(n: 1)
'''

    with get_client() as client:
        tables = client.query_api().query(
            query=flux
        )

    for table in tables:
        if table.records:
            value = table.records[0].get_value()

            if not isinstance(value, (int, float)):
                raise NonNumericDataError(
                    "The selected sensor does not contain "
                    "numeric historical data."
                )

            return

    raise NoDataError(
        "No historical data is available for the "
        "selected sensor during this period."
    )


def run_historical_query(query):
    _validate_data_exists(query)

    escaped_measurement = _escape_flux_string(
        query.measurement
    )

    escaped_entity = _escape_flux_string(
        query.entity_id
    )

    start = ALLOWED_RANGES[
        query.range_name
    ]

    window = ALLOWED_AGGREGATIONS[
        query.aggregation
    ]

    flux_lines = [
        f'from(bucket: "{INFLUXDB_BUCKET}")',
        f'  |> range(start: {start})',
        (
            '  |> filter(fn: (r) => '
            f'r["_measurement"] == "{escaped_measurement}")'
        ),
        (
            '  |> filter(fn: (r) => '
            f'r["entity_id"] == "{escaped_entity}")'
        ),
        '  |> filter(fn: (r) => r["_field"] == "value")',
    ]

    if window:
        flux_lines.append(
            "  |> aggregateWindow("
            f"every: {window}, "
            f"fn: {query.function}, "
            "createEmpty: false"
            ")"
        )

    flux_lines.append(
        '  |> keep(columns: ["_time", "_value"])'
    )

    flux = "\n".join(flux_lines)

    with get_client() as client:
        frames = client.query_api().query_data_frame(
            query=flux
        )

    if isinstance(frames, list):
        frames = [
            frame
            for frame in frames
            if not frame.empty
        ]

        if not frames:
            raise NoDataError(
                "No historical data is available for the "
                "selected sensor during this period."
            )

        data = pd.concat(
            frames,
            ignore_index=True,
        )

    else:
        data = frames

    if data.empty:
        raise NoDataError(
            "No historical data is available for the "
            "selected sensor during this period."
        )

    data = data[
        ["_time", "_value"]
    ].copy()

    data["_time"] = pd.to_datetime(
        data["_time"],
        utc=True,
    )

    numeric_values = pd.to_numeric(
        data["_value"],
        errors="coerce",
    )

    if numeric_values.isna().any():
        raise NonNumericDataError(
            "Some historical values for this sensor "
            "are not numeric."
        )

    data["_value"] = numeric_values

    data = data.sort_values(
        "_time"
    )

    return data
