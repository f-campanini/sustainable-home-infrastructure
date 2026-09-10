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

INFLUXDB_TOKEN_FILE = os.getenv(
    "INFLUXDB_TOKEN_FILE",
    "/run/secrets/influxdb_token",
)


def read_token():
    with open(
        INFLUXDB_TOKEN_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return file.read().strip()


def get_client():
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=read_token(),
        org=INFLUXDB_ORG,
    )


def get_health():
    with get_client() as client:
        health = client.health()

        return {
            "status": health.status,
            "version": health.version,
        }
