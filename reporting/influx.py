import os

from influxdb_client import InfluxDBClient


INFLUXDB_URL = os.getenv(
    "INFLUXDB_URL",
    "http://influxdb:8086",
)

INFLUXDB_ORG = os.getenv(
    "INFLUXDB_ORG",
    "home",
)

INFLUXDB_BUCKET = os.getenv(
    "INFLUXDB_BUCKET",
    "homeassistant",
)

INFLUXDB_AUDIT_BUCKET = os.getenv(
    "INFLUXDB_AUDIT_BUCKET",
    "reporting_audit",
)

INFLUXDB_TOKEN_FILE = os.getenv(
    "INFLUXDB_TOKEN_FILE",
    "/run/secrets/influxdb_token",
)


def get_token():
    with open(
        INFLUXDB_TOKEN_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return file.read().strip()


def get_client():
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=get_token(),
        org=INFLUXDB_ORG,
    )


def get_health():
    try:
        with get_client() as client:
            health = client.health()

        return {
            "status": health.status,
            "message": health.message,
        }

    except Exception as error:
        return {
            "status": "fail",
            "message": str(error),
        }
