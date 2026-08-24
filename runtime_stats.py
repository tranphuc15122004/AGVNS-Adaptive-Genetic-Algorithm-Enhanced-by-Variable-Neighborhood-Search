"""Machine-readable per-instance runtime statistics for DPDP simulators.

The simulator variants are kept independently runnable, so this module only
uses the Python standard library and exposes a small, stable interface for all
entrypoints.
"""

import csv
import datetime
import json
import math
import os
import statistics
import tempfile
from typing import Any, Dict, List, Optional


CSV_FIELDS = [
    "algorithm",
    "instance_id",
    "status",
    "score",
    "runtime_seconds",
    "simulator_runtime_seconds",
    "started_at_utc",
    "finished_at_utc",
    "seed",
    "pid",
    "error",
]


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _number_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, 6)


def _atomic_write(path: str, writer: Any) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".runtime_stats_",
        suffix=".tmp",
        dir=directory,
    )
    os.close(descriptor)
    try:
        writer(temporary_path)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


class RuntimeStats:
    """Collect and persist one runtime row per simulator instance."""

    def __init__(
        self,
        stats_file: str,
        algorithm: str,
        seed: Optional[int] = None,
        pid: Optional[int] = None,
    ) -> None:
        if not stats_file:
            raise ValueError("stats_file must not be empty")

        root, extension = os.path.splitext(os.path.abspath(stats_file))
        self.csv_path = os.path.abspath(stats_file)
        if not extension:
            self.csv_path += ".csv"
            root = self.csv_path[:-4]
        self.json_path = root + ".json"
        self.algorithm = algorithm
        self.seed = seed
        self.pid = os.getpid() if pid is None else pid
        self._records: List[Dict[str, Any]] = []
        self._starts: Dict[str, str] = {}

    def start_instance(self, instance_id: str) -> str:
        """Return and retain an ISO-8601 UTC start timestamp."""
        started_at = _utc_now()
        self._starts[str(instance_id)] = started_at
        return started_at

    def record(
        self,
        instance_id: str,
        status: str,
        score: Any = None,
        runtime_seconds: Any = None,
        simulator_runtime_seconds: Any = None,
        started_at_utc: Optional[str] = None,
        finished_at_utc: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append a row and persist the complete report immediately."""
        instance_key = str(instance_id)
        remembered_start = self._starts.pop(instance_key, None)
        record = {
            "algorithm": self.algorithm,
            "instance_id": instance_key,
            "status": str(status),
            "score": _number_or_none(score),
            "runtime_seconds": _number_or_none(runtime_seconds),
            "simulator_runtime_seconds": _number_or_none(
                simulator_runtime_seconds
            ),
            "started_at_utc": started_at_utc or remembered_start or _utc_now(),
            "finished_at_utc": finished_at_utc or _utc_now(),
            "seed": self.seed,
            "pid": self.pid,
            "error": str(error) if error else "",
        }
        self._records.append(record)
        self.write()

    def _summary(self) -> Dict[str, Any]:
        successful = [
            record
            for record in self._records
            if record["status"] == "SUCCESS"
        ]
        failed = [
            record
            for record in self._records
            if record["status"] != "SUCCESS"
        ]
        runtimes = [
            record["runtime_seconds"]
            for record in successful
            if record["runtime_seconds"] is not None
        ]
        if not self._records:
            report_status = "EMPTY"
        elif failed and successful:
            report_status = "PARTIAL"
        elif failed:
            report_status = "FAILED"
        else:
            report_status = "SUCCESS"

        runtime_summary = {
            "total": round(sum(runtimes), 6),
            "mean": round(statistics.mean(runtimes), 6) if runtimes else None,
            "minimum": min(runtimes) if runtimes else None,
            "maximum": max(runtimes) if runtimes else None,
            "standard_deviation": (
                round(statistics.pstdev(runtimes), 6) if runtimes else None
            ),
        }
        return {
            "schema_version": 1,
            "algorithm": self.algorithm,
            "seed": self.seed,
            "pid": self.pid,
            "generated_at_utc": _utc_now(),
            "status": report_status,
            "instance_count": len(self._records),
            "successful_instances": len(successful),
            "failed_instances": len(failed),
            "runtime_seconds": runtime_summary,
            "per_instance": list(self._records),
        }

    def write(self) -> None:
        """Atomically rewrite CSV and JSON reports from collected rows."""

        def write_csv(path: str) -> None:
            with open(path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for record in self._records:
                    row = dict(record)
                    for field in ("runtime_seconds", "simulator_runtime_seconds"):
                        if row[field] is not None:
                            row[field] = "%.6f" % row[field]
                    writer.writerow(row)

        def write_json(path: str) -> None:
            with open(path, "w") as handle:
                json.dump(self._summary(), handle, indent=2, sort_keys=True)
                handle.write("\n")

        _atomic_write(self.csv_path, write_csv)
        _atomic_write(self.json_path, write_json)


__all__ = ["CSV_FIELDS", "RuntimeStats"]
