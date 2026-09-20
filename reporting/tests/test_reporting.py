from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd

import app
import artifact
import audit
from query_service import NoDataError, NonNumericDataError


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        paths = patch.multiple(
            artifact,
            GENERATED_DIR=self.root / "generated",
            PUBLISH_QUEUE_DIR=self.root / "publish_queue",
            PUBLISHED_DIR=self.root / "published",
        )
        paths.start()
        self.addCleanup(paths.stop)


class ChartResponseTests(StorageTestCase):
    endpoint = (
        "/chart?measurement=W&entity_id=sensor_example&range=24h"
        "&aggregation=15m&function=mean&chart_type=line"
    )

    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.data = pd.DataFrame({
            "_time": pd.date_range("2026-01-01", periods=2, freq="15min", tz="UTC"),
            "_value": [10.0, 20.0],
        })
        audit_patch = patch.object(app, "write_query_audit")
        self.audit = audit_patch.start()
        self.addCleanup(audit_patch.stop)

    def test_saved_png_matches_response_and_audit_id(self):
        with patch.object(app, "run_historical_query", return_value=self.data):
            for _ in range(2):
                response = self.client.get(self.endpoint)
                self.assertEqual(response.mimetype, "image/png")
                request_id = response.headers["X-Query-ID"]
                path = self.root / "generated" / f"{request_id}.png"
                self.assertEqual(path.read_bytes(), response.data)
                self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(self.audit.call_args.kwargs["request_id"], request_id)
                response.close()
        self.assertEqual(len(list((self.root / "generated").glob("*.png"))), 2)

    def test_audit_outage_preserves_successful_png(self):
        self.audit.side_effect = ConnectionError("PRIVATE_TOKEN_MUST_NOT_BE_LOGGED")
        with patch.object(app, "run_historical_query", return_value=self.data), \
                self.assertLogs(app.app.logger, level="WARNING") as logs:
            response = self.client.get(self.endpoint)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(self.audit.call_count, 1)
        self.assertNotIn("PRIVATE_TOKEN", "\n".join(logs.output))
        self.assertIn(response.headers["X-Query-ID"], "\n".join(logs.output))
        response.close()

    def test_audit_outage_preserves_validation_and_query_errors(self):
        self.audit.side_effect = ConnectionError("offline")
        with self.assertLogs(app.app.logger, level="WARNING"):
            response = self.client.get("/chart")
        self.assertEqual(response.mimetype, "application/json")
        self.assertFalse(response.json["ok"])
        for error in (NoDataError("empty"), NonNumericDataError("text"), RuntimeError("offline")):
            with self.subTest(error=type(error).__name__), \
                    patch.object(app, "run_historical_query", side_effect=error), \
                    self.assertLogs(app.app.logger, level="WARNING"):
                response = self.client.get(self.endpoint)
            self.assertEqual(response.mimetype, "application/json")
            self.assertFalse(response.json["ok"])
        self.assertFalse((self.root / "generated").exists())

    def test_storage_failure_returns_error_and_not_success_audit(self):
        with patch.object(app, "run_historical_query", return_value=self.data), \
                patch.object(app, "save_png", side_effect=OSError("disk full")):
            response = self.client.get(self.endpoint)
        self.assertEqual(response.mimetype, "application/json")
        self.assertFalse(response.json["ok"])
        self.assertEqual(self.audit.call_args.kwargs["status"], "error")

    def test_health_status_is_pass_or_fail_inside_json(self):
        for status in ("pass", "fail"):
            with patch.object(app, "get_health", return_value={"status": status, "message": "test"}):
                response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["status"], status)


class AtomicArtifactTests(StorageTestCase):
    def test_success_rewinds_stream_and_leaves_no_temporary_file(self):
        stream = BytesIO(b"example PNG bytes")
        path = artifact.save_png(stream)
        self.assertEqual(path.read_bytes(), stream.read())
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_interrupted_copy_preserves_previous_file(self):
        class BrokenStream(BytesIO):
            calls = 0

            def read(self, size=-1):
                self.calls += 1
                if self.calls == 1:
                    return b"partial"
                raise OSError("write interrupted")

        destination = artifact.save_png(BytesIO(b"previous complete image"), report_id="existing")
        with self.assertRaises(OSError):
            artifact.save_png(BrokenStream(), report_id="existing")
        self.assertEqual(destination.read_bytes(), b"previous complete image")
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_rename_failure_does_not_publish_or_leave_temporary_files(self):
        with patch.object(artifact.os, "replace", side_effect=OSError("rename failed")), \
                self.assertRaises(OSError):
            artifact.save_png(BytesIO(b"image"))
        self.assertEqual(list((self.root / "generated").iterdir()), [])


class AuditWriterTests(unittest.TestCase):
    def test_audit_write_is_synchronous_and_closes_writer(self):
        client = MagicMock()
        with patch.object(audit, "get_client", return_value=client):
            audit.write_query_audit(
                request_id="Q-test", measurement="W", entity_id="sensor_example",
                range_name="24h", aggregation="15m", function="mean",
                chart_type="line", status="success",
            )
        api = client.__enter__.return_value.write_api
        api.assert_called_once_with(write_options=SYNCHRONOUS)
        api.return_value.__enter__.return_value.write.assert_called_once()
        api.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
