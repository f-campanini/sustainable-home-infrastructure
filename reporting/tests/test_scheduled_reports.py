import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pandas as pd

import artifact
import scheduled_reports as reports
from query_service import NoDataError, NonNumericDataError


class ScheduledReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = patch.multiple(
            artifact,
            GENERATED_DIR=self.root / "generated",
            PUBLISH_QUEUE_DIR=self.root / "publish_queue",
            PUBLISHED_DIR=self.root / "published",
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.data = pd.DataFrame({
            "_time": pd.date_range("2026-01-01", periods=3, freq="15min", tz="UTC"),
            "_value": [10.0, 20.0, 15.0],
        })

    def schedule(self, **overrides):
        entry = {"name": "daily_power", **overrides}
        return reports.load_schedules(json.dumps([entry]))[0]

    def pngs(self):
        return list((self.root / "generated").glob("*.png"))

    def test_discovery_generates_real_unique_pngs_on_each_run(self):
        schedule = self.schedule()
        with patch.object(reports, "list_entities", return_value=["one", "two"]) as discover, \
                patch.object(reports, "run_historical_query", return_value=self.data) as query:
            reports.generate_scheduled_report(schedule)
            reports.generate_scheduled_report(schedule)
        self.assertEqual(discover.call_count, 2)
        self.assertEqual(len(self.pngs()), 4)
        self.assertEqual({call.args[0].entity_id for call in query.call_args_list}, {"one", "two"})
        for png in self.pngs():
            self.assertTrue(png.name.startswith("scheduled-daily_power-report-"))
            self.assertTrue(png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(list((self.root / "publish_queue").iterdir()), [])

    def test_explicit_entities_are_deduplicated_and_do_not_discover(self):
        schedule = self.schedule(entities=["one", "one"], chart_type="bar")
        with patch.object(reports, "list_entities") as discover, \
                patch.object(reports, "run_historical_query", return_value=self.data) as query:
            reports.generate_scheduled_report(schedule)
        discover.assert_not_called()
        self.assertEqual(query.call_count, 1)
        self.assertEqual(len(self.pngs()), 1)

    def test_sensor_failures_do_not_stop_remaining_reports(self):
        schedule = self.schedule(entities=["empty", "text", "broken", "good"])
        outcomes = [NoDataError("empty"), NonNumericDataError("text"), RuntimeError("offline"), self.data]
        with patch.object(reports, "run_historical_query", side_effect=outcomes), \
                self.assertLogs(reports.logger, level=logging.WARNING) as logs:
            reports.generate_scheduled_report(schedule)
        self.assertEqual(len(self.pngs()), 1)
        self.assertEqual(len(logs.output), 3)

    def test_write_failure_is_logged_and_next_sensor_still_saves(self):
        real_save = artifact.save_png
        count = 0

        def save(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 1:
                raise OSError("disk unavailable")
            return real_save(*args, **kwargs)

        with patch.object(reports, "run_historical_query", return_value=self.data), \
                patch.object(reports, "save_png", side_effect=save), \
                self.assertLogs(reports.logger, level=logging.INFO) as logs:
            reports.generate_scheduled_report(self.schedule(entities=["one", "two"]))
        self.assertEqual(len(self.pngs()), 1)
        self.assertTrue(any("failed entity=one" in item for item in logs.output))
        self.assertTrue(any("saved" in item and "entity=two" in item for item in logs.output))

    def test_empty_or_failed_discovery_creates_no_artifacts(self):
        for result in ([], RuntimeError("offline")):
            with self.subTest(result=type(result).__name__), \
                    patch.object(reports, "list_entities", side_effect=result if isinstance(result, Exception) else None, return_value=[]), \
                    self.assertLogs(reports.logger, level=logging.INFO):
                reports.generate_scheduled_report(self.schedule())
            self.assertEqual(self.pngs(), [])

    def test_invalid_configuration_is_rejected(self):
        invalid_entries = [
            {"name": "../escape"}, {"name": ""}, {"name": "x", "hour": 24},
            {"name": "x", "hour": True}, {"name": "x", "minute": -1},
            {"name": "x", "entities": "one"}, {"name": "x", "entities": [""]},
            {"name": "x", "measurement": "unsupported"},
            {"name": "x", "range_name": "1y"}, {"name": "x", "aggregation": []},
            {"name": "x", "unexpected": True},
        ]
        for entry in invalid_entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                reports.load_schedules(json.dumps([entry]))
        for raw in ('invalid JSON', '{}', '[{"name":"x"},{"name":"x"}]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reports.load_schedules(raw)
        self.assertEqual(reports.load_schedules("[]"), [])

    def test_scheduler_runs_job_without_a_web_request(self):
        scheduler = BackgroundScheduler(
            timezone="Europe/Rome",
            executors={"reports": ThreadPoolExecutor(max_workers=1)},
        )
        reports.register_report_jobs(scheduler, [self.schedule(entities=["one"])])
        job = scheduler.get_job("report-daily_power")
        self.assertEqual(job.executor, "reports")
        self.assertEqual(job.max_instances, 1)
        self.assertTrue(job.coalesce)
        next_fire = job.trigger.get_next_fire_time(None, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual((next_fire.hour, next_fire.minute), (0, 5))
        self.assertEqual(str(job.trigger.timezone), "Europe/Rome")

        # Accelerate only the test trigger; execute the registered production job.
        job.modify(trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(milliseconds=100)))
        completed = Event()
        scheduler.add_listener(lambda event: completed.set(), EVENT_JOB_EXECUTED)
        with patch.object(reports, "run_historical_query", return_value=self.data):
            scheduler.start()
            try:
                self.assertTrue(completed.wait(10), "Scheduled job did not execute")
            finally:
                scheduler.shutdown(wait=True)
        self.assertEqual(len(self.pngs()), 1)


if __name__ == "__main__":
    unittest.main()
