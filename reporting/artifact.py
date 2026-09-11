import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


REPORT_STORAGE_ROOT = Path(
    os.getenv("REPORT_STORAGE_ROOT", "/data/reports")
)

GENERATED_DIR = REPORT_STORAGE_ROOT / "generated"
PUBLISH_QUEUE_DIR = REPORT_STORAGE_ROOT / "publish_queue"
PUBLISHED_DIR = REPORT_STORAGE_ROOT / "published"


def ensure_storage_directories():
    for directory in (
        GENERATED_DIR,
        PUBLISH_QUEUE_DIR,
        PUBLISHED_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def new_report_id():
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    suffix = uuid.uuid4().hex[:8]

    return f"report-{timestamp}-{suffix}"


def save_png(image_stream, report_id=None):
    ensure_storage_directories()

    if report_id is None:
        report_id = new_report_id()

    destination = GENERATED_DIR / f"{report_id}.png"

    image_stream.seek(0)

    with destination.open("wb") as file:
        shutil.copyfileobj(image_stream, file)

    image_stream.seek(0)

    return destination


def queue_for_publication(artifact_path):
    ensure_storage_directories()

    source = Path(artifact_path)

    if not source.exists():
        raise FileNotFoundError(source)

    destination = PUBLISH_QUEUE_DIR / source.name

    shutil.copy2(source, destination)

    return destination


def mark_as_published(queued_path):
    ensure_storage_directories()

    source = Path(queued_path)

    if not source.exists():
        raise FileNotFoundError(source)

    destination = PUBLISHED_DIR / source.name

    shutil.move(str(source), str(destination))

    return destination
