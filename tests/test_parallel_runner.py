import csv
import json
import os
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from parallel_runner import (
    _build_jobs,
    _build_summary,
    _job_seed,
    _parse_instances,
    _parse_worker_log,
    _select_cores,
    _write_results_csv,
)


class ParallelRunnerTests(unittest.TestCase):
    def test_parse_instances_supports_ranges_and_deduplicates(self):
        self.assertEqual(_parse_instances("1-3, 2, 5,7-8"), [1, 2, 3, 5, 7, 8])

    def test_parse_instances_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            _parse_instances("3-1")
        with self.assertRaises(ValueError):
            _parse_instances("abc")

    def test_build_jobs_is_instance_major_and_has_unique_seeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            jobs = _build_jobs("batch", temporary, [1, 2], 3, 0)

        self.assertEqual(
            [(job["instance_id"], job["repetition"]) for job in jobs],
            [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)],
        )
        self.assertEqual(len({job["seed"] for job in jobs}), 6)
        self.assertEqual(_job_seed(0, 20, 5), 20005)

    def test_worker_limit_selects_only_requested_cores(self):
        args = Namespace(cores=None, workers=2)
        with patch("parallel_runner._available_cores", return_value=[4, 6, 8]):
            self.assertEqual(_select_cores(args), [4, 6])

    def test_parse_worker_log_reads_final_score_and_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            log_path = os.path.join(temporary, "worker.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("SUCCESS\n")
                handle.write("Thoi gian thuc hien thuat toan: 1.25\n")
                handle.write("Score of instance_1: 42.5, runtime: 3.50s\n")

            result = _parse_worker_log(log_path, 1, 0)

        self.assertEqual(result[0], "SUCCESS")
        self.assertEqual(result[1], 42.5)
        self.assertEqual(result[2], 3.5)
        self.assertEqual(result[3], 1.25)
        self.assertEqual(result[4], 1)
        self.assertEqual(result[5], "")

    def test_parse_worker_log_rejects_missing_success_and_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            log_path = os.path.join(temporary, "worker.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("FAIL\n")

            result = _parse_worker_log(log_path, 1, 1)

        self.assertEqual(result[0], "FAILED")
        self.assertIsNone(result[1])
        self.assertIn("worker exited with code 1", result[5])
        self.assertIn("missing SUCCESS marker", result[5])
        self.assertIn("missing final score", result[5])

    def test_summary_and_csv_are_machine_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = {
                "batch_id": "batch",
                "instance_id": 1,
                "repetition": 1,
                "seed": 1001,
                "core": 0,
                "pid": 123,
                "started_at_utc": "start",
                "finished_at_utc": "finish",
                "wall_time_seconds": 5.0,
                "simulation_runtime_seconds": 4.5,
                "algorithm_time_seconds": 2.0,
                "algorithm_dispatch_count": 1,
                "score": 10.0,
                "return_code": 0,
                "status": "SUCCESS",
                "workspace": "jobs/instance_001/repetition_001_seed_1001",
                "log_path": "jobs/instance_001/repetition_001_seed_1001/worker.log",
                "error": "",
            }
            csv_path = os.path.join(temporary, "results.csv")
            _write_results_csv(csv_path, [result])
            with open(csv_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            manifest = {
                "batch_id": "batch",
                "instances": [1],
                "repetitions": 1,
                "total_jobs": 1,
            }
            summary = _build_summary(manifest, [result], "SUCCESS", 5.0)
            json_path = os.path.join(temporary, "summary.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(summary, handle)
            with open(json_path, encoding="utf-8") as handle:
                loaded = json.load(handle)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "SUCCESS")
        self.assertEqual(loaded["per_instance"]["1"]["mean_score"], 10.0)
        self.assertEqual(
            loaded["per_instance"]["1"]["mean_simulation_runtime_seconds"],
            4.5,
        )

    def test_summary_reports_runtime_distribution(self):
        results = []
        for instance_id, runtime in ((1, 2.0), (1, 4.0), (2, 8.0)):
            results.append(
                {
                    "batch_id": "batch",
                    "instance_id": instance_id,
                    "repetition": len([r for r in results if r["instance_id"] == instance_id]) + 1,
                    "wall_time_seconds": runtime + 0.5,
                    "simulation_runtime_seconds": runtime,
                    "status": "SUCCESS",
                    "score": 1.0,
                }
            )

        summary = _build_summary(
            {"batch_id": "batch", "instances": [1, 2], "total_jobs": 3},
            results,
            "SUCCESS",
            10.0,
        )

        self.assertEqual(summary["min_simulation_runtime_seconds"], 2.0)
        self.assertEqual(summary["max_simulation_runtime_seconds"], 8.0)
        self.assertEqual(summary["standard_deviation_simulation_runtime_seconds"], 2.494438)
        self.assertEqual(summary["per_instance"]["1"]["min_simulation_runtime_seconds"], 2.0)
        self.assertEqual(summary["per_instance"]["1"]["max_simulation_runtime_seconds"], 4.0)
        self.assertEqual(summary["per_instance"]["1"]["standard_deviation_simulation_runtime_seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()
