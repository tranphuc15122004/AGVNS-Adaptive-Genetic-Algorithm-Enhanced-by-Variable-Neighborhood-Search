import csv
import json
import os
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from run_parallel import (
    _build_jobs,
    _build_summary,
    _job_seed,
    _parse_instances,
    _parse_worker_log,
    _select_cores,
    _write_results_csv,
)


class RunParallelTests(unittest.TestCase):
    def test_parse_instances_supports_ranges_and_deduplicates(self):
        self.assertEqual(_parse_instances("1-3, 2, 5,7-8"), [1, 2, 3, 5, 7, 8])

    def test_parse_instances_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            _parse_instances("3-1")
        with self.assertRaises(ValueError):
            _parse_instances("abc")

    def test_build_jobs_is_instance_major_and_has_unique_seeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            jobs = _build_jobs("batch", temporary, [1, 2], 5, 0)

        self.assertEqual(len(jobs), 10)
        self.assertEqual(
            [(job["instance_id"], job["repetition"]) for job in jobs],
            [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5),
             (2, 1), (2, 2), (2, 3), (2, 4), (2, 5)],
        )
        self.assertEqual(len({job["seed"] for job in jobs}), 10)
        self.assertEqual(_job_seed(0, 20, 5), 20005)

    def test_build_jobs_for_requested_experiment_has_100_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            jobs = _build_jobs("batch", temporary, range(1, 21), 5, 0)

        self.assertEqual(len(jobs), 100)
        self.assertEqual(jobs[0]["instance_id"], 1)
        self.assertEqual(jobs[-1]["instance_id"], 20)
        self.assertEqual(jobs[-1]["repetition"], 5)

    def test_worker_limit_selects_only_requested_cores(self):
        args = Namespace(cores=None, workers=2)
        with patch("run_parallel._available_cores", return_value=[4, 6, 8]):
            self.assertEqual(_select_cores(args), [4, 6])

    def test_parse_worker_log_sums_dispatch_times_and_reads_final_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            log_path = os.path.join(temporary, "worker.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("SUCCESS\n")
                handle.write("Thoi gian thuc hien thuat toan: 1.25\n")
                handle.write("SUCCESS\n")
                handle.write("Thoi gian thuc hien thuat toan: 0.75\n")
                handle.write("Score of instance_1: 42.5, runtime: 3.50s\n")

            (
                status,
                score,
                simulation_runtime,
                algorithm_time,
                dispatch_count,
                error,
            ) = _parse_worker_log(log_path, 1, 0)

        self.assertEqual(status, "SUCCESS")
        self.assertEqual(score, 42.5)
        self.assertEqual(simulation_runtime, 3.5)
        self.assertEqual(algorithm_time, 2.0)
        self.assertEqual(dispatch_count, 2)
        self.assertEqual(error, "")

    def test_parse_worker_log_detects_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            log_path = os.path.join(temporary, "worker.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("FAIL\n")
            (
                status,
                score,
                simulation_runtime,
                algorithm_time,
                dispatch_count,
                error,
            ) = _parse_worker_log(log_path, 1, 0)

        self.assertEqual(status, "FAILED")
        self.assertIsNone(score)
        self.assertIsNone(simulation_runtime)
        self.assertIn("worker emitted FAIL", error)

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
                "algorithm_dispatch_count": 2,
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


if __name__ == "__main__":
    unittest.main()
