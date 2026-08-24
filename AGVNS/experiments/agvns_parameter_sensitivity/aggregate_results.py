"""Parse and aggregate metrics produced by AGVNS screening workers."""

import argparse
import csv
import json
import math
import os
import re
import statistics
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

try:
    from design import configuration_by_id
except ImportError:  # pragma: no cover - supports package and script execution
    from .design import configuration_by_id


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_SCORE = re.compile(r"Score of instance_(\d+):\s*(%s)" % _NUMBER)
_SCORE_RUNTIME = re.compile(r"Score of instance_(\d+):.*?runtime:\s*(%s)\s*(?:seconds|s)" % _NUMBER)
_TOTAL_DISTANCE = re.compile(r"Total distance:\s*(%s)" % _NUMBER, re.IGNORECASE)
_SUM_OVER_TIME = re.compile(r"Sum over time:\s*(%s)" % _NUMBER, re.IGNORECASE)
_TOTAL_SCORE = re.compile(r"Total score:\s*(%s)" % _NUMBER, re.IGNORECASE)
_ALGORITHM_TIME = re.compile(r"Thoi gian thuc hien thuat toan:\s*(%s)" % _NUMBER)
_CONFIG = re.compile(
    r"Applied AGVNS experiment config:\s*id=(\d+)\s+T=(\d+)\s+population=(\d+)\s+"
    r"perturbation=(%s)\s+mutation_subset=(%s)\s+seed=(\d+)" % (_NUMBER, _NUMBER)
)


def _last_float(pattern: re.Pattern, message: str, group: int = 1) -> Optional[float]:
    matches = list(pattern.finditer(message))
    return float(matches[-1].group(group)) if matches else None


def parse_worker_log_text(message: str, instance_id: int, return_code: int) -> Dict[str, Any]:
    scores = [float(match.group(2)) for match in _SCORE.finditer(message) if int(match.group(1)) == instance_id]
    runtime_matches = [float(match.group(2)) for match in _SCORE_RUNTIME.finditer(message) if int(match.group(1)) == instance_id]
    config_match = _CONFIG.search(message)
    algorithm_times = [float(match.group(1)) for match in _ALGORITHM_TIME.finditer(message)]

    score = scores[-1] if scores else None
    simulation_runtime = runtime_matches[-1] if runtime_matches else None
    errors = []
    if return_code != 0:
        errors.append("worker exited with code %d" % return_code)
    if "SUCCESS" not in message:
        errors.append("missing SUCCESS marker")
    if score is None:
        errors.append("missing final score")
    elif not math.isfinite(score):
        errors.append("final score is not finite")
    if simulation_runtime is None:
        errors.append("missing simulation runtime")
    if "FAIL" in message:
        errors.append("worker emitted FAIL")

    result: Dict[str, Any] = {
        "status": "SUCCESS" if not errors else "FAILED",
        "score": score,
        "total_distance": _last_float(_TOTAL_DISTANCE, message),
        "sum_over_time": _last_float(_SUM_OVER_TIME, message),
        "total_score": _last_float(_TOTAL_SCORE, message),
        "simulation_runtime_seconds": simulation_runtime,
        "algorithm_time_seconds": sum(algorithm_times),
        "algorithm_dispatch_count": len(algorithm_times),
        "error": "; ".join(errors),
    }
    if config_match:
        result.update(
            {
                "configuration_id": int(config_match.group(1)),
                "threshold_orders": int(config_match.group(2)),
                "population_size": int(config_match.group(3)),
                "perturbation_rate": float(config_match.group(4)),
                "mutation_rate": float(config_match.group(5)),
                "seed": int(config_match.group(6)),
            }
        )
    return result


def _summary(values: Iterable[Optional[float]]) -> Dict[str, Optional[float]]:
    numbers = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not numbers:
        return {"count": 0, "mean": None, "standard_deviation": None, "median": None, "minimum": None, "maximum": None, "ci95": None}
    mean = statistics.mean(numbers)
    standard_deviation = statistics.stdev(numbers) if len(numbers) > 1 else 0.0
    ci95 = 1.96 * standard_deviation / math.sqrt(len(numbers)) if len(numbers) > 1 else 0.0
    return {
        "count": len(numbers),
        "mean": mean,
        "standard_deviation": standard_deviation,
        "median": statistics.median(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
        "ci95": ci95,
    }


def _group_summary(rows: List[Dict[str, Any]], group_key: str) -> List[Dict[str, Any]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get(group_key)].append(row)
    output = []
    for key in sorted(grouped, key=lambda value: (value is None, value)):
        group = grouped[key]
        successful = [row for row in group if row.get("status") == "SUCCESS"]
        score = _summary(row.get("score") for row in successful)
        simulation_runtime = _summary(row.get("simulation_runtime_seconds") for row in successful)
        algorithm_runtime = _summary(row.get("algorithm_time_seconds") for row in successful)
        output.append(
            {
                group_key: key,
                "total_jobs": len(group),
                "successful_jobs": len(successful),
                "failed_jobs": len(group) - len(successful),
                "score_mean": score["mean"],
                "score_standard_deviation": score["standard_deviation"],
                "score_median": score["median"],
                "score_ci95": score["ci95"],
                "score_minimum": score["minimum"],
                "score_maximum": score["maximum"],
                "simulation_runtime_mean_seconds": simulation_runtime["mean"],
                "simulation_runtime_standard_deviation_seconds": simulation_runtime["standard_deviation"],
                "algorithm_runtime_mean_seconds": algorithm_runtime["mean"],
                "algorithm_runtime_standard_deviation_seconds": algorithm_runtime["standard_deviation"],
            }
        )
    return output


def aggregate_rows(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Build paper-ready summaries while retaining raw rows separately."""
    enriched = []
    for row in rows:
        current = dict(row)
        instance_id = int(current["instance_id"])
        current["set_id"] = ((instance_id - 1) // 8) + 1
        if current.get("configuration_id") is not None:
            config = configuration_by_id(int(current["configuration_id"]))
            current["threshold_orders"] = config.threshold_orders
            current["population_size"] = config.population_size
            current["perturbation_rate"] = config.perturbation_rate
            current["mutation_rate"] = config.mutation_rate
        enriched.append(current)
    return {
        "by_configuration": _group_summary(enriched, "configuration_id"),
        "by_set": _group_summary(enriched, "set_id"),
        "by_instance": _group_summary(enriched, "instance_id"),
    }


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            handle.write("\n")
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_run(run_dir: str) -> Dict[str, Any]:
    raw_path = os.path.join(run_dir, "results.jsonl")
    rows = []
    with open(raw_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    summaries = aggregate_rows(rows)
    for name, summary_rows in summaries.items():
        _write_csv(os.path.join(run_dir, "%s.csv" % name), summary_rows)
    output = {
        "run_dir": os.path.abspath(run_dir),
        "total_rows": len(rows),
        "successful_rows": sum(row.get("status") == "SUCCESS" for row in rows),
        "failed_rows": sum(row.get("status") != "SUCCESS" for row in rows),
        "summaries": summaries,
    }
    with open(os.path.join(run_dir, "aggregate_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate AGVNS screening results")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    output = aggregate_run(args.run_dir)
    print("Aggregated %d rows; successful=%d failed=%d" % (output["total_rows"], output["successful_rows"], output["failed_rows"]))


if __name__ == "__main__":
    main()
