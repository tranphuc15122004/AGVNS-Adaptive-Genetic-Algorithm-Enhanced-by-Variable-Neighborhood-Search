import csv
import json
import os
import tempfile
import unittest

from runtime_stats import RuntimeStats


class RuntimeStatsTests(unittest.TestCase):
    def test_record_persists_each_instance_and_writes_json_aggregates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "runtime_stats.csv")
            stats = RuntimeStats(csv_path, algorithm="MA", seed=7, pid=123)

            started_at = stats.start_instance("instance_1")
            stats.record(
                "instance_1",
                status="SUCCESS",
                score=10.5,
                runtime_seconds=1.0,
                started_at_utc=started_at,
                finished_at_utc="2026-08-24T00:00:01+00:00",
            )

            self.assertTrue(os.path.isfile(csv_path))
            with open(csv_path, newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["instance_id"], "instance_1")
            self.assertEqual(rows[0]["runtime_seconds"], "1.000000")

            stats.record(
                "instance_2",
                status="SUCCESS",
                score=12,
                runtime_seconds=3.0,
                started_at_utc=stats.start_instance("instance_2"),
                finished_at_utc="2026-08-24T00:00:03+00:00",
            )
            stats.record(
                "instance_3",
                status="FAILED",
                runtime_seconds=2.0,
                error="simulator failed",
                started_at_utc=stats.start_instance("instance_3"),
                finished_at_utc="2026-08-24T00:00:04+00:00",
            )

            with open(stats.json_path) as handle:
                report = json.load(handle)

            self.assertEqual(report["algorithm"], "MA")
            self.assertEqual(report["successful_instances"], 2)
            self.assertEqual(report["failed_instances"], 1)
            self.assertEqual(report["runtime_seconds"]["total"], 4.0)
            self.assertEqual(report["runtime_seconds"]["mean"], 2.0)
            self.assertEqual(report["runtime_seconds"]["minimum"], 1.0)
            self.assertEqual(report["runtime_seconds"]["maximum"], 3.0)
            self.assertEqual(report["runtime_seconds"]["standard_deviation"], 1.0)
            self.assertEqual(len(report["per_instance"]), 3)

    def test_simulator_runtime_and_error_are_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stats = RuntimeStats(
                os.path.join(temp_dir, "custom.csv"),
                algorithm="TS",
                seed=11,
            )
            stats.record(
                "instance_4",
                status="FAILED",
                runtime_seconds=0.25,
                simulator_runtime_seconds=0.2,
                error="ValueError: bad input",
            )

            with open(stats.csv_path, newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["status"], "FAILED")
            self.assertEqual(row["simulator_runtime_seconds"], "0.200000")
            self.assertEqual(row["error"], "ValueError: bad input")


if __name__ == "__main__":
    unittest.main()
