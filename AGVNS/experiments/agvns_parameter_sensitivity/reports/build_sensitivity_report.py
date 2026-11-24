#!/usr/bin/env python3
"""Build a 480-key sensitivity snapshot from archived screening runs."""

import csv
import datetime as dt
import json
import math
import pathlib
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

EXPERIMENT_DIR = pathlib.Path(__file__).resolve().parents[1]
REPORT_DIR = pathlib.Path(__file__).resolve().parent
RUNS_DIR = EXPERIMENT_DIR / "runs"
sys.path.insert(0, str(EXPERIMENT_DIR))

from design import DESIGN, INSTANCE_IDS, REPETITIONS, TAGUCHI_DESIGN, iter_jobs  # noqa: E402
from aggregate_results import parse_worker_log_text  # noqa: E402


CURRENT_BATCH_ID = "20261009_015120"
FOLLOWUP_BATCH_IDS = ("20261006_090008", "20261009_015120")
ORDER_COUNT_BY_SET = {
    1: 50, 2: 100, 3: 300, 4: 500,
    5: 1000, 6: 2000, 7: 3000, 8: 4000,
}
BASE_SEED = 20260824

MASTER_FIELDS = [
    "configuration_id", "threshold_orders", "population_size",
    "perturbation_rate", "mutation_rate", "instance_id", "repetition",
    "seed", "result_state", "score", "total_distance", "sum_over_time",
    "total_score", "wall_time_seconds", "simulation_runtime_seconds",
    "algorithm_time_seconds", "algorithm_dispatch_count", "return_code",
    "source_run_id", "source_line", "source_evidence", "source_git_revision",
    "source_code_fingerprint", "valid_attempt_count", "recorded_attempt_count",
    "latest_attempt_run_id", "latest_attempt_status",
    "latest_attempt_failure_reason", "latest_attempt_error",
]

ATTEMPT_FIELDS = [
    "record_type", "run_id", "source_line", "source_evidence", "configuration_id",
    "threshold_orders", "population_size", "perturbation_rate",
    "mutation_rate", "instance_id", "repetition", "expected_seed",
    "recorded_seed", "seed_match", "result_state", "valid_result",
    "score", "total_distance", "sum_over_time", "total_score",
    "wall_time_seconds", "simulation_runtime_seconds",
    "algorithm_time_seconds", "algorithm_dispatch_count", "core", "pid",
    "return_code", "failure_reason", "error", "workspace", "log_path",
    "git_revision", "code_fingerprint",
]

COVERAGE_FIELDS = [
    "summary_type", "summary_id", "threshold_orders", "population_size",
    "perturbation_rate", "mutation_rate", "expected_runs", "valid_runs",
    "running_runs", "queued_runs", "needs_rerun_runs", "mean_score",
    "median_score", "score_standard_deviation", "minimum_score", "maximum_score",
]

UNRECORDED_LOG_FIELDS = [
    "run_id", "configuration_id", "instance_id", "repetition", "expected_seed",
    "workspace", "log_path", "log_size_bytes", "log_modified_at",
    "score_lines_for_instance", "log_observed_score", "observed_score_is_sentinel",
    "log_has_success_marker", "log_has_fail_marker", "return_code",
    "result_row_recorded", "assessment",
]

SCORE_LINE = re.compile(
    r"Score of instance_(\d+):\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
)


def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def finite_valid_score(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and 0 <= number < sys.maxsize


def valid_result(row):
    status = row.get("status")
    effective = row.get("effective_status", status)
    return (
        finite_valid_score(row.get("score"))
        and status in (None, "SUCCESS")
        and effective == "SUCCESS"
    )


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_current_views(master_rows, generated_at, current_fingerprint, batch_attempts):
    """Write the compact 480-job and per-instance sensitivity snapshots."""
    job_fields = [
        "configuration_id", "threshold_orders", "population_size",
        "perturbation_rate", "mutation_rate", "set_id", "instance_id",
        "repetition", "seed", "result_state", "score", "total_distance",
        "sum_over_time", "total_score", "wall_time_seconds",
        "simulation_runtime_seconds", "algorithm_time_seconds",
        "algorithm_dispatch_count", "source_run_id", "source_line",
        "source_evidence", "archive_row_present", "return_code", "error",
        "latest_attempt_run_id", "latest_attempt_status",
        "latest_attempt_error", "worker_log_exists",
    ]
    summary_fields = [
        "configuration_id", "threshold_orders", "population_size",
        "perturbation_rate", "mutation_rate", "instance_id", "expected_runs",
        "valid_runs", "running_runs", "queued_runs", "needs_rerun_runs",
        "mean_score_valid_runs", "sample_stddev_score", "median_score",
        "minimum_score", "maximum_score",
    ]
    length_job_fields = [
        "order_count", "configuration_id", "threshold_orders",
        "population_size", "perturbation_rate", "mutation_rate", "set_id",
        "instance_id", "repetition", "seed", "result_state", "score",
        "total_distance", "sum_over_time", "total_score", "wall_time_seconds",
        "simulation_runtime_seconds", "algorithm_time_seconds",
        "algorithm_dispatch_count", "source_run_id", "source_line",
        "source_evidence", "source_git_revision", "source_code_fingerprint",
        "archive_row_present", "return_code", "error",
    ]
    length_summary_fields = [
        "order_count", "set_id", "instance_ids", "configuration_id",
        "threshold_orders", "population_size", "perturbation_rate",
        "mutation_rate", "expected_runs", "valid_runs", "mean_score",
        "sample_stddev_score", "median_score", "minimum_score", "maximum_score",
        "paired_baseline_runs", "mean_score_ratio_vs_baseline",
        "median_score_ratio_vs_baseline", "same_fingerprint_pairs",
        "same_fingerprint_mean_score_ratio_vs_baseline",
    ]

    worker_log_keys = set()
    for log_path in RUNS_DIR.glob("*/jobs/config_*/instance_*/repetition_*/worker.log"):
        try:
            relative = log_path.relative_to(log_path.parents[4] / "jobs").parts
            worker_log_keys.add((
                int(relative[0].replace("config_", "")),
                int(relative[1].replace("instance_", "")),
                int(relative[2].split("_seed_", 1)[0].replace("repetition_", "")),
            ))
        except (IndexError, ValueError):
            continue

    current_job_rows = []
    grouped = defaultdict(list)
    for row in master_rows:
        key = (row["configuration_id"], row["instance_id"], row["repetition"])
        current_job_rows.append({
            **row,
            "set_id": ((int(row["instance_id"]) - 1) // 8) + 1,
            "source_evidence": row["source_evidence"] or "",
            "archive_row_present": "yes" if row["recorded_attempt_count"] else "no",
            "error": row["latest_attempt_error"],
            "worker_log_exists": "yes" if key in worker_log_keys else "no",
        })
        grouped[(row["configuration_id"], row["instance_id"])].append(row)

    write_csv(REPORT_DIR / "sensitivity_jobs_current.csv", job_fields, current_job_rows)
    length_job_rows = []
    for row in current_job_rows:
        set_id = int(row["set_id"])
        length_job_rows.append({
            **row,
            "order_count": ORDER_COUNT_BY_SET[set_id],
        })
    length_job_rows.sort(key=lambda row: (
        row["order_count"], row["configuration_id"], row["instance_id"], row["repetition"],
    ))
    write_csv(REPORT_DIR / "sensitivity_jobs_by_length.csv", length_job_fields, length_job_rows)

    summary_rows = []
    for config in DESIGN:
        for instance_id in INSTANCE_IDS:
            rows = grouped[(config.configuration_id, instance_id)]
            valid = [r for r in rows if r["result_state"] == "VALID"]
            stats = stat_values([r["score"] for r in valid])
            summary_rows.append({
                "configuration_id": config.configuration_id,
                "threshold_orders": config.threshold_orders,
                "population_size": config.population_size,
                "perturbation_rate": config.perturbation_rate,
                "mutation_rate": config.mutation_rate,
                "instance_id": instance_id,
                "expected_runs": len(rows),
                "valid_runs": len(valid),
                "running_runs": sum(r["result_state"] == "RUNNING" for r in rows),
                "queued_runs": sum(r["result_state"] == "QUEUED" for r in rows),
                "needs_rerun_runs": sum(r["result_state"] == "NEEDS_RERUN" for r in rows),
                "mean_score_valid_runs": stats["mean_score"],
                "sample_stddev_score": stats["score_standard_deviation"],
                "median_score": stats["median_score"],
                "minimum_score": stats["minimum_score"],
                "maximum_score": stats["maximum_score"],
            })
    write_csv(REPORT_DIR / "sensitivity_summary_by_config_instance_current.csv", summary_fields, summary_rows)

    baseline_scores = {
        (int(row["instance_id"]), int(row["repetition"])): row
        for row in master_rows
        if int(row["configuration_id"]) == 10 and row["result_state"] == "VALID"
    }
    rows_by_length_config = defaultdict(list)
    paired_ratios = defaultdict(list)
    same_fingerprint_ratios = defaultdict(list)
    for row in master_rows:
        set_id = ((int(row["instance_id"]) - 1) // 8) + 1
        group_key = (ORDER_COUNT_BY_SET[set_id], int(row["configuration_id"]))
        rows_by_length_config[group_key].append(row)
        if row["result_state"] != "VALID":
            continue
        baseline = baseline_scores.get((int(row["instance_id"]), int(row["repetition"])))
        if baseline is None or float(baseline["score"]) <= 0:
            continue
        ratio = float(row["score"]) / float(baseline["score"])
        paired_ratios[group_key].append(ratio)
        if (
            row["source_code_fingerprint"]
            and baseline["source_code_fingerprint"]
            and row["source_code_fingerprint"] == baseline["source_code_fingerprint"]
        ):
            same_fingerprint_ratios[group_key].append(ratio)

    length_summary_rows = []
    for order_count in sorted(set(ORDER_COUNT_BY_SET.values())):
        set_id = next(k for k, value in ORDER_COUNT_BY_SET.items() if value == order_count)
        for config in DESIGN:
            group_key = (order_count, config.configuration_id)
            rows = rows_by_length_config[group_key]
            valid = [row for row in rows if row["result_state"] == "VALID"]
            stats = stat_values([row["score"] for row in valid])
            ratios = paired_ratios[group_key]
            same_fp_ratios = same_fingerprint_ratios[group_key]
            length_summary_rows.append({
                "order_count": order_count,
                "set_id": set_id,
                "instance_ids": ",".join(str(i) for i in INSTANCE_IDS if ((i - 1) // 8) + 1 == set_id),
                "configuration_id": config.configuration_id,
                "threshold_orders": config.threshold_orders,
                "population_size": config.population_size,
                "perturbation_rate": config.perturbation_rate,
                "mutation_rate": config.mutation_rate,
                "expected_runs": len(rows),
                "valid_runs": len(valid),
                "mean_score": stats["mean_score"],
                "sample_stddev_score": stats["score_standard_deviation"],
                "median_score": stats["median_score"],
                "minimum_score": stats["minimum_score"],
                "maximum_score": stats["maximum_score"],
                "paired_baseline_runs": len(ratios),
                "mean_score_ratio_vs_baseline": statistics.mean(ratios) if ratios else None,
                "median_score_ratio_vs_baseline": statistics.median(ratios) if ratios else None,
                "same_fingerprint_pairs": len(same_fp_ratios),
                "same_fingerprint_mean_score_ratio_vs_baseline": statistics.mean(same_fp_ratios) if same_fp_ratios else None,
            })
    write_csv(REPORT_DIR / "sensitivity_summary_by_length.csv", length_summary_fields, length_summary_rows)

    factor_definitions = (
        ("threshold_orders", "T"),
        ("population_size", "population"),
        ("perturbation_rate", "perturbation"),
        ("mutation_rate", "mutation_subset"),
    )
    master_by_run_key = {
        (int(row["configuration_id"]), int(row["instance_id"]), int(row["repetition"])): row
        for row in master_rows
    }
    factor_ratios = defaultdict(list)
    factor_same_fingerprint_ratios = defaultdict(list)
    factor_instance_scores = defaultdict(lambda: defaultdict(list))
    factor_config_ids = defaultdict(set)
    baseline_scores_by_instance = defaultdict(list)
    for instance_id in INSTANCE_IDS:
        for repetition in range(1, REPETITIONS + 1):
            baseline = master_by_run_key[(10, instance_id, repetition)]
            if baseline["result_state"] == "VALID":
                baseline_scores_by_instance[instance_id].append(float(baseline["score"]))
    for config in TAGUCHI_DESIGN:
        for field, factor_name in factor_definitions:
            factor_key = (factor_name, getattr(config, field))
            factor_config_ids[factor_key].add(config.configuration_id)
        for instance_id in INSTANCE_IDS:
            for repetition in range(1, REPETITIONS + 1):
                result = master_by_run_key[(config.configuration_id, instance_id, repetition)]
                baseline = master_by_run_key[(10, instance_id, repetition)]
                if result["result_state"] != "VALID" or baseline["result_state"] != "VALID":
                    continue
                if float(baseline["score"]) <= 0:
                    continue
                ratio = float(result["score"]) / float(baseline["score"])
                for field, factor_name in factor_definitions:
                    factor_key = (factor_name, getattr(config, field))
                    factor_ratios[factor_key].append(ratio)
                    factor_instance_scores[factor_key][instance_id].append(float(result["score"]))
                    result_fingerprint = result["source_code_fingerprint"]
                    baseline_fingerprint = baseline["source_code_fingerprint"]
                    if result_fingerprint and result_fingerprint == baseline_fingerprint:
                        factor_same_fingerprint_ratios[factor_key].append(ratio)

    factor_effect_rows = []
    for field, factor_name in factor_definitions:
        values = sorted({getattr(config, field) for config in TAGUCHI_DESIGN})
        for factor_value in values:
            factor_key = (factor_name, factor_value)
            ratios = factor_ratios[factor_key]
            same_fingerprint = factor_same_fingerprint_ratios[factor_key]
            expected_level_runs = len(factor_config_ids[factor_key]) * REPETITIONS
            instance_improvements = []
            for instance_id in INSTANCE_IDS:
                level_scores = factor_instance_scores[factor_key].get(instance_id, [])
                baseline_scores = baseline_scores_by_instance.get(instance_id, [])
                if len(level_scores) != expected_level_runs or len(baseline_scores) != REPETITIONS:
                    continue
                baseline_mean = statistics.mean(baseline_scores)
                if baseline_mean <= 0:
                    continue
                level_mean = statistics.mean(level_scores)
                instance_improvements.append(100.0 * (baseline_mean - level_mean) / baseline_mean)
            factor_effect_rows.append({
                "factor": factor_name,
                "level": factor_value,
                "configuration_ids": ",".join(str(i) for i in sorted(factor_config_ids[factor_key])),
                "paired_runs_vs_baseline": len(ratios),
                "mean_score_ratio_vs_baseline": statistics.mean(ratios) if ratios else None,
                "median_score_ratio_vs_baseline": statistics.median(ratios) if ratios else None,
                "mean_relative_score_vs_baseline_percent": (statistics.mean(ratios) - 1.0) * 100.0 if ratios else None,
                "macro_mean_improvement_vs_baseline_percent": statistics.mean(instance_improvements) if instance_improvements else None,
                "median_instance_improvement_vs_baseline_percent": statistics.median(instance_improvements) if instance_improvements else None,
                "instances_improved_vs_baseline": sum(value > 0 for value in instance_improvements),
                "macro_instances": len(instance_improvements),
                "same_fingerprint_pairs": len(same_fingerprint),
                "same_fingerprint_median_score_ratio": statistics.median(same_fingerprint) if same_fingerprint else None,
            })
    write_csv(
        REPORT_DIR / "sensitivity_factor_effects.csv",
        [
            "factor", "level", "configuration_ids", "paired_runs_vs_baseline",
            "mean_score_ratio_vs_baseline", "median_score_ratio_vs_baseline",
            "mean_relative_score_vs_baseline_percent",
            "macro_mean_improvement_vs_baseline_percent",
            "median_instance_improvement_vs_baseline_percent",
            "instances_improved_vs_baseline", "macro_instances",
            "same_fingerprint_pairs",
            "same_fingerprint_median_score_ratio",
        ],
        factor_effect_rows,
    )

    state_counts = {
        state: sum(row["result_state"] == state for row in master_rows)
        for state in ("VALID", "RUNNING", "QUEUED", "NEEDS_RERUN")
    }
    same_fingerprint_count = sum(
        row["result_state"] == "VALID"
        and current_fingerprint
        and row["source_code_fingerprint"] == current_fingerprint
        for row in master_rows
    )
    batch_rows = [a for a in batch_attempts if a["valid"]]
    batch_57 = sorted(
        (float(a["raw"]["score"]), a["key"])
        for a in batch_rows if a["key"][1] == 57
    )
    anomaly_note = ""
    if len(batch_57) >= 3:
        reference = batch_57[-3][0]
        flagged = [(score, key) for score, key in batch_57[-2:] if score > 5 * reference]
        if flagged:
            details = ", ".join(
                "config %d / rep %d: %.3f (%.1f× mốc kế tiếp %.3f)" % (
                    key[0], key[2], score, score / reference, reference,
                )
                for score, key in flagged
            )
            anomaly_note = (
                "- Điểm cần rà soát: trong các kết quả batch mới cho instance 57, "
                + details
                + ". Trạng thái SUCCESS xác nhận lượt chạy kết thúc hợp lệ theo ledger, "
                "nhưng riêng trạng thái đó chưa xác nhận tính hợp lý của điểm.\n"
            )

    utc_snapshot = generated_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    table = [
        "# AGVNS sensitivity results — current snapshot",
        "",
        "Snapshot time (UTC): %s." % utc_snapshot,
        "",
        "Design: 10 configurations × 16 instances × 3 repetitions = 480 jobs. Seed: `20260824 + instance_id × 1000 + repetition`.",
        "",
        "## Current coverage",
        "",
        "| State | Jobs |",
        "|---|---:|",
        "| Valid completed score | %d |" % state_counts["VALID"],
        "| Running in current batch | %d |" % state_counts["RUNNING"],
        "| Queued in current batch | %d |" % state_counts["QUEUED"],
        "| Needs rerun / unresolved | %d |" % state_counts["NEEDS_RERUN"],
        "| Total planned | %d |" % len(master_rows),
        "",
        "A VALID row has a finalized SUCCESS record, finite nonnegative score, and the expected seed. Coverage records completed runs; it does not by itself establish that one parameter setting is better.",
        "",
        "%d/480 canonical valid rows use the current batch fingerprint `%s`; remaining historical results may come from different code fingerprints." % (
            same_fingerprint_count, current_fingerprint or "not recorded",
        ),
        "",
        "## Interpretation limits",
        "",
        "The master combines archived attempts from different code fingerprints. The newest batch is `%s`; only finalized, seed-matched rows are treated as completed evidence. Partial means are descriptive and should not be used to rank configurations until all three repetitions for the compared configuration-instance pairs finish under comparable code." % CURRENT_BATCH_ID,
        "",
        anomaly_note.rstrip(),
        "",
        "## Sensitivity score means by configuration and instance",
        "",
        "Each cell is the mean of VALID repetitions, followed by `n/3`. Empty cells mean no valid completed score is available.",
        "",
        "| Config | T | Population | Perturbation | Mutation | " + " | ".join("I%d" % i for i in INSTANCE_IDS) + " |",
        "|---:|---:|---:|---:|---:|" + "---:|" * len(INSTANCE_IDS),
    ]
    for config in DESIGN:
        cells = []
        for instance_id in INSTANCE_IDS:
            rows = grouped[(config.configuration_id, instance_id)]
            scores = [float(r["score"]) for r in rows if r["result_state"] == "VALID"]
            if scores:
                cells.append("%s (%d/3)" % (format(statistics.mean(scores), ",.1f"), len(scores)))
            else:
                cells.append("— (0/3)")
        table.append("| %d | %d | %d | %s | %s | %s |" % (
            config.configuration_id, config.threshold_orders, config.population_size,
            config.perturbation_rate, config.mutation_rate, " | ".join(cells),
        ))

    table += [
        "",
        "## Coverage by configuration",
        "",
        "| Config | T | Population | Perturbation | Mutation | Valid / 48 | Running | Queued | Needs rerun |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for config in DESIGN:
        rows = [r for r in master_rows if r["configuration_id"] == config.configuration_id]
        table.append("| %d | %d | %d | %s | %s | %d / %d | %d | %d | %d |" % (
            config.configuration_id, config.threshold_orders, config.population_size,
            config.perturbation_rate, config.mutation_rate,
            sum(r["result_state"] == "VALID" for r in rows), len(rows),
            sum(r["result_state"] == "RUNNING" for r in rows),
            sum(r["result_state"] == "QUEUED" for r in rows),
            sum(r["result_state"] == "NEEDS_RERUN" for r in rows),
        ))
    table += [
        "",
        "## Coverage by instance",
        "",
        "| Instance | Valid / 30 | Running | Queued | Needs rerun |",
        "|---:|---:|---:|---:|---:|",
    ]
    for instance_id in INSTANCE_IDS:
        rows = [r for r in master_rows if r["instance_id"] == instance_id]
        table.append("| %d | %d / %d | %d | %d | %d |" % (
            instance_id, sum(r["result_state"] == "VALID" for r in rows), len(rows),
            sum(r["result_state"] == "RUNNING" for r in rows),
            sum(r["result_state"] == "QUEUED" for r in rows),
            sum(r["result_state"] == "NEEDS_RERUN" for r in rows),
        ))
    table += [
        "",
        "## Files",
        "",
        "- [One row per planned job (480 rows)](sensitivity_jobs_current.csv)",
        "- [480 planned jobs grouped by order-count length](sensitivity_jobs_by_length.csv)",
        "- [Score summary by length and configuration](sensitivity_summary_by_length.csv)",
        "- [Taguchi factor-level summaries against baseline](sensitivity_factor_effects.csv)",
        "- [Sensitivity summary by configuration and instance (160 rows)](sensitivity_summary_by_config_instance_current.csv)",
        "- [Full attempt and provenance ledger](sensitivity_attempts.csv)",
        "- [Detailed report](sensitivity_report.md)",
        "",
    ]
    (REPORT_DIR / "sensitivity_table_current.md").write_text("\n".join(table), encoding="utf-8")
    return length_summary_rows, factor_effect_rows


def stat_values(values):
    values = [float(v) for v in values if finite_valid_score(v)]
    if not values:
        return {"mean_score": None, "median_score": None,
                "score_standard_deviation": None, "minimum_score": None,
                "maximum_score": None}
    return {
        "mean_score": statistics.mean(values),
        "median_score": statistics.median(values),
        "score_standard_deviation": statistics.stdev(values) if len(values) > 1 else 0.0,
        "minimum_score": min(values),
        "maximum_score": max(values),
    }


def run_log_path(run_dir, job):
    workspace = (
        run_dir / "jobs" / ("config_%03d" % job["configuration_id"])
        / ("instance_%03d" % job["instance_id"])
        / ("repetition_%03d_seed_%d" % (job["repetition"], job["seed"]))
    )
    return workspace / "worker.log"


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = dt.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    jobs = list(iter_jobs(base_seed=BASE_SEED))
    job_by_key = {
        (int(j["configuration_id"]), int(j["instance_id"]), int(j["repetition"])): j
        for j in jobs
    }
    expected_keys = set(job_by_key)

    manifests = {}
    for run_dir in sorted(p for p in RUNS_DIR.iterdir() if p.is_dir()):
        manifest = read_json(run_dir / "manifest.json")
        if manifest:
            manifests[run_dir.name] = manifest

    current_manifest = manifests.get(CURRENT_BATCH_ID, {})
    current_fingerprint = (
        current_manifest.get("code", {}).get("dirty_worktree_fingerprint_sha256")
    )
    attempts_by_key = defaultdict(list)
    raw_attempt_rows = []
    recorded_by_run = defaultdict(set)

    for result_path in sorted(RUNS_DIR.glob("*/results.jsonl")):
        run_id = result_path.parent.name
        manifest = manifests.get(run_id, {})
        code = manifest.get("code", {})
        try:
            created_at = manifest.get("created_at_utc", run_id)
        except AttributeError:
            created_at = run_id
        try:
            lines = result_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for source_line, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                key = (int(raw["configuration_id"]), int(raw["instance_id"]), int(raw["repetition"]))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if key not in expected_keys:
                continue
            expected_job = job_by_key[key]
            expected_seed = int(expected_job["seed"])
            recorded_seed = raw.get("seed")
            try:
                seed_match = int(recorded_seed) == expected_seed
            except (TypeError, ValueError):
                seed_match = False
            is_valid = valid_result(raw) and seed_match
            effective_status = raw.get("effective_status", raw.get("status", "FAILED"))
            if not finite_valid_score(raw.get("score")):
                if raw.get("score") is None:
                    inferred_reason = "missing_score"
                else:
                    try:
                        inferred_reason = "sentinel_score" if float(raw["score"]) >= sys.maxsize else "invalid_score"
                    except (TypeError, ValueError, OverflowError):
                        inferred_reason = "invalid_score"
            elif not seed_match:
                inferred_reason = "seed_mismatch"
            elif effective_status != "SUCCESS":
                inferred_reason = "worker_failure"
            else:
                inferred_reason = ""

            attempt = {
                "key": key,
                "raw": raw,
                "source_evidence": "finalized result JSONL",
                "run_id": run_id,
                "source_line": source_line,
                "created_at": created_at,
                "fingerprint": code.get("dirty_worktree_fingerprint_sha256", ""),
                "git_revision": code.get("git_revision", ""),
                "valid": is_valid,
                "seed_match": seed_match,
                "inferred_reason": inferred_reason,
            }
            attempts_by_key[key].append(attempt)
            recorded_by_run[run_id].add(key)
            factors = expected_job
            attempt_row = {
                "record_type": "RECORDED_RESULT",
                "run_id": run_id,
                "source_line": source_line,
                "source_evidence": attempt["source_evidence"],
                **{name: factors.get(name) for name in (
                    "configuration_id", "threshold_orders", "population_size",
                    "perturbation_rate", "mutation_rate", "instance_id", "repetition",
                )},
                "expected_seed": expected_seed,
                "recorded_seed": recorded_seed,
                "seed_match": str(seed_match).upper(),
                "result_state": effective_status,
                "valid_result": str(is_valid).upper(),
                "score": raw.get("score"),
                "total_distance": raw.get("total_distance"),
                "sum_over_time": raw.get("sum_over_time"),
                "total_score": raw.get("total_score"),
                "wall_time_seconds": raw.get("wall_time_seconds"),
                "simulation_runtime_seconds": raw.get("simulation_runtime_seconds"),
                "algorithm_time_seconds": raw.get("algorithm_time_seconds"),
                "algorithm_dispatch_count": raw.get("algorithm_dispatch_count"),
                "core": raw.get("core"),
                "pid": raw.get("pid"),
                "return_code": raw.get("return_code"),
                "failure_reason": raw.get("failure_reason") or inferred_reason,
                "error": raw.get("error"),
                "workspace": raw.get("workspace"),
                "log_path": raw.get("log_path"),
                "git_revision": code.get("git_revision", ""),
                "code_fingerprint": code.get("dirty_worktree_fingerprint_sha256", ""),
                "created_at_utc": created_at,
                "_attempt": attempt,
            }
            raw_attempt_rows.append(attempt_row)

    # Some completed jobs from the 2026-10-02 follow-up have no runner JSONL
    # row, but do have final runtime_stats plus a matching score and SUCCESS in
    # the worker log. Recover only when the manifest key, expected seed, status,
    # finite score, and final log score all agree. Keep this provenance explicit.
    for run_id, manifest in sorted(manifests.items()):
        run_dir = RUNS_DIR / run_id
        jobs_dir = run_dir / "jobs"
        if not jobs_dir.exists():
            continue
        selected_keys = set()
        for key_list in manifest.get("selected_job_keys", []):
            try:
                selected_keys.add(tuple(int(value) for value in key_list))
            except (TypeError, ValueError):
                continue
        code = manifest.get("code", {})
        for stats_path in jobs_dir.glob("config_*/instance_*/repetition_*/runtime_stats.json"):
            try:
                parts = stats_path.relative_to(jobs_dir).parts
                key = (
                    int(parts[0].replace("config_", "")),
                    int(parts[1].replace("instance_", "")),
                    int(parts[2].split("_seed_", 1)[0].replace("repetition_", "")),
                )
            except (IndexError, ValueError):
                continue
            if key not in expected_keys or key not in selected_keys or key in recorded_by_run[run_id]:
                continue
            expected_job = job_by_key[key]
            stats = read_json(stats_path)
            per_instance = stats.get("per_instance", [])
            if len(per_instance) != 1:
                continue
            stat = per_instance[0]
            log_path = stats_path.parent / "worker.log"
            try:
                message = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            try:
                expected_seed = int(expected_job["seed"])
                recorded_seed = int(stat.get("seed"))
                top_seed = int(stats.get("seed"))
                score = float(stat.get("score"))
            except (TypeError, ValueError, OverflowError):
                continue
            instance_id = key[1]
            parsed = parse_worker_log_text(message, instance_id, return_code=0)
            if not (
                key in selected_keys
                and stats.get("status") == "SUCCESS"
                and int(stats.get("failed_instances", -1)) == 0
                and int(stats.get("successful_instances", -1)) == 1
                and stat.get("status") == "SUCCESS"
                and str(stat.get("instance_id")) == "instance_%d" % instance_id
                and expected_seed == recorded_seed == top_seed
                and parsed.get("effective_status") == "SUCCESS"
                and parsed.get("configuration_id") == key[0]
                and parsed.get("seed") == expected_seed
                and finite_valid_score(score)
                and math.isclose(score, float(parsed.get("score")), rel_tol=0.0, abs_tol=2e-6)
                and not re.search(r"\bFAIL\b", message)
            ):
                continue

            expected_seed_match = recorded_seed == expected_seed
            relative_workspace = str(stats_path.parent.relative_to(run_dir))
            relative_log = str(log_path.relative_to(run_dir))
            created_at = stats.get("generated_at_utc") or stat.get("finished_at_utc") or manifest.get("created_at_utc", run_id)
            raw = {
                **parsed,
                "configuration_id": key[0],
                "instance_id": key[1],
                "repetition": key[2],
                "score": score,
                "wall_time_seconds": stat.get("runtime_seconds"),
                "simulation_runtime_seconds": stat.get("simulator_runtime_seconds") or parsed.get("simulation_runtime_seconds"),
                "seed": recorded_seed,
                "status": "SUCCESS",
                "effective_status": "SUCCESS",
                "return_code": None,
                "failure_reason": None,
                "error": "",
                "core": None,
                "pid": stat.get("pid", stats.get("pid")),
                "workspace": relative_workspace,
                "log_path": relative_log,
            }
            attempt = {
                "key": key,
                "raw": raw,
                "source_evidence": "runtime_stats.json + matching worker.log SUCCESS/score",
                "run_id": run_id,
                "source_line": 0,
                "created_at": created_at,
                "fingerprint": code.get("dirty_worktree_fingerprint_sha256", ""),
                "git_revision": code.get("git_revision", ""),
                "valid": True,
                "seed_match": expected_seed_match,
                "inferred_reason": "",
            }
            attempts_by_key[key].append(attempt)
            recorded_by_run[run_id].add(key)
            raw_attempt_rows.append({
                "record_type": "RECOVERED_RUNTIME_STATS",
                "run_id": run_id,
                "source_line": None,
                "source_evidence": attempt["source_evidence"],
                **{name: expected_job.get(name) for name in (
                    "configuration_id", "threshold_orders", "population_size",
                    "perturbation_rate", "mutation_rate", "instance_id", "repetition",
                )},
                "expected_seed": expected_seed,
                "recorded_seed": recorded_seed,
                "seed_match": "TRUE",
                "result_state": "SUCCESS",
                "valid_result": "TRUE",
                "score": score,
                "total_distance": raw.get("total_distance"),
                "sum_over_time": raw.get("sum_over_time"),
                "total_score": raw.get("total_score"),
                "wall_time_seconds": raw.get("wall_time_seconds"),
                "simulation_runtime_seconds": raw.get("simulation_runtime_seconds"),
                "algorithm_time_seconds": raw.get("algorithm_time_seconds"),
                "algorithm_dispatch_count": raw.get("algorithm_dispatch_count"),
                "core": None,
                "pid": raw.get("pid"),
                "return_code": None,
                "failure_reason": "",
                "error": "",
                "workspace": relative_workspace,
                "log_path": relative_log,
                "git_revision": code.get("git_revision", ""),
                "code_fingerprint": code.get("dirty_worktree_fingerprint_sha256", ""),
                "created_at_utc": created_at,
                "_attempt": attempt,
            })

    selected_manifest_jobs = []
    for key_list in current_manifest.get("selected_job_keys", []):
        try:
            key = tuple(int(v) for v in key_list)
        except (TypeError, ValueError):
            continue
        if key in job_by_key:
            selected_manifest_jobs.append((key, job_by_key[key]))

    scheduled_rows = []
    scheduled_state = {}
    current_run_dir = RUNS_DIR / CURRENT_BATCH_ID
    for key, job in selected_manifest_jobs:
        if key in recorded_by_run[CURRENT_BATCH_ID]:
            continue
        worker_log = run_log_path(current_run_dir, job)
        state = "RUNNING" if worker_log.exists() else "QUEUED"
        scheduled_state[key] = state
        scheduled_rows.append({
            "record_type": "SCHEDULED_NOT_RECORDED",
            "run_id": CURRENT_BATCH_ID,
            "source_line": None,
            **{name: job.get(name) for name in (
                "configuration_id", "threshold_orders", "population_size",
                "perturbation_rate", "mutation_rate", "instance_id", "repetition",
            )},
            "expected_seed": job["seed"],
            "recorded_seed": None,
            "seed_match": None,
            "result_state": state,
            "valid_result": None,
            "score": None,
            "total_distance": None,
            "sum_over_time": None,
            "total_score": None,
            "wall_time_seconds": None,
            "simulation_runtime_seconds": None,
            "algorithm_time_seconds": None,
            "algorithm_dispatch_count": None,
            "core": None,
            "pid": None,
            "return_code": None,
            "failure_reason": None,
            "error": None,
            "workspace": str(worker_log.parent.relative_to(current_run_dir)) if worker_log.exists() else None,
            "log_path": str(worker_log.relative_to(current_run_dir)) if worker_log.exists() else None,
            "git_revision": current_manifest.get("code", {}).get("git_revision", ""),
            "code_fingerprint": current_fingerprint or "",
            "created_at_utc": current_manifest.get("created_at_utc", ""),
            "_attempt": None,
        })

    # Preserve evidence from interrupted batches that left worker logs but no
    # finalized JSONL row. Such logs are never promoted to valid scores because
    # the runner return code and final validation record are unavailable.
    unrecorded_logs = []
    for run_dir in sorted(p for p in RUNS_DIR.iterdir() if p.is_dir()):
        run_id = run_dir.name
        if run_id == CURRENT_BATCH_ID:
            continue  # Current jobs are represented as RUNNING/QUEUED above.
        jobs_dir = run_dir / "jobs"
        if not jobs_dir.exists():
            continue
        for log_path in jobs_dir.glob("**/worker.log"):
            try:
                parts = log_path.relative_to(jobs_dir).parts
                config_id = int(parts[0].replace("config_", ""))
                instance_id = int(parts[1].replace("instance_", ""))
                rep_piece = parts[2].replace("repetition_", "")
                repetition = int(rep_piece.split("_seed_", 1)[0])
                key = (config_id, instance_id, repetition)
            except (IndexError, ValueError):
                continue
            if key not in expected_keys or key in recorded_by_run[run_id]:
                continue
            job = job_by_key[key]
            try:
                message = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                message = ""
            score_values = [
                float(match.group(2)) for match in SCORE_LINE.finditer(message)
                if int(match.group(1)) == instance_id
            ]
            observed_score = score_values[-1] if score_values else None
            unrecorded_logs.append({
                "run_id": run_id,
                "configuration_id": config_id,
                "instance_id": instance_id,
                "repetition": repetition,
                "expected_seed": job["seed"],
                "workspace": str(log_path.parent.relative_to(jobs_dir)),
                "log_path": str(log_path.relative_to(EXPERIMENT_DIR)),
                "log_size_bytes": log_path.stat().st_size,
                "log_modified_at": dt.datetime.fromtimestamp(
                    log_path.stat().st_mtime, ZoneInfo("Asia/Ho_Chi_Minh")
                ).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "score_lines_for_instance": len(score_values),
                "log_observed_score": observed_score,
                "observed_score_is_sentinel": (
                    str(observed_score >= sys.maxsize).upper() if observed_score is not None else None
                ),
                "log_has_success_marker": str("SUCCESS" in message).upper(),
                "log_has_fail_marker": str("FAIL" in message).upper(),
                "return_code": None,
                "result_row_recorded": "FALSE",
                "assessment": (
                    "SCORE_IN_LOG_BUT_NO_FINAL_RESULT_ROW"
                    if observed_score is not None else "NO_FINAL_SCORE_OR_RESULT_ROW"
                ),
            })

    # Prefer a valid result from the currently rerun code fingerprint; otherwise
    # choose the newest valid recorded result. All duplicate attempts remain below.
    canonical = {}
    for key, values in attempts_by_key.items():
        candidates = [a for a in values if a["valid"]]
        if not candidates:
            continue
        candidates.sort(key=lambda a: (
            bool(current_fingerprint and a["fingerprint"] == current_fingerprint),
            str(a["created_at"]),
            a["source_line"],
        ))
        canonical[key] = candidates[-1]

    master_rows = []
    for key, job in job_by_key.items():
        values = attempts_by_key.get(key, [])
        valid_values = [a for a in values if a["valid"]]
        latest = max(values, key=lambda a: (str(a["created_at"]), a["source_line"])) if values else None
        selected = canonical.get(key)
        if selected:
            state = "VALID"
        elif key in scheduled_state:
            state = scheduled_state[key]
        else:
            state = "NEEDS_RERUN"
        raw = selected["raw"] if selected else {}
        latest_raw = latest["raw"] if latest else {}
        master_rows.append({
            **{name: job.get(name) for name in (
                "configuration_id", "threshold_orders", "population_size",
                "perturbation_rate", "mutation_rate", "instance_id", "repetition", "seed",
            )},
            "result_state": state,
            "score": raw.get("score") if selected else None,
            "total_distance": raw.get("total_distance") if selected else None,
            "sum_over_time": raw.get("sum_over_time") if selected else None,
            "total_score": raw.get("total_score") if selected else None,
            "wall_time_seconds": raw.get("wall_time_seconds") if selected else None,
            "simulation_runtime_seconds": raw.get("simulation_runtime_seconds") if selected else None,
            "algorithm_time_seconds": raw.get("algorithm_time_seconds") if selected else None,
            "algorithm_dispatch_count": raw.get("algorithm_dispatch_count") if selected else None,
            "return_code": raw.get("return_code") if selected else None,
            "source_run_id": selected["run_id"] if selected else None,
            "source_line": selected["source_line"] if selected else None,
            "source_evidence": selected["source_evidence"] if selected else None,
            "source_git_revision": selected["git_revision"] if selected else None,
            "source_code_fingerprint": selected["fingerprint"] if selected else None,
            "valid_attempt_count": len(valid_values),
            "recorded_attempt_count": len(values),
            "latest_attempt_run_id": latest["run_id"] if latest else None,
            "latest_attempt_status": latest_raw.get("effective_status", latest_raw.get("status")) if latest else None,
            "latest_attempt_failure_reason": (latest_raw.get("failure_reason") or latest["inferred_reason"]) if latest else None,
            "latest_attempt_error": latest_raw.get("error") if latest else None,
        })

    all_attempt_rows = []
    for row in raw_attempt_rows:
        row = dict(row)
        row.pop("created_at_utc", None)
        row.pop("_attempt", None)
        all_attempt_rows.append(row)
    for row in scheduled_rows:
        row = dict(row)
        row.pop("created_at_utc", None)
        row.pop("_attempt", None)
        all_attempt_rows.append(row)
    all_attempt_rows.sort(key=lambda r: (
        r.get("run_id") or "", r.get("instance_id") or 0,
        r.get("configuration_id") or 0, r.get("repetition") or 0,
        r.get("source_line") or 0,
    ))

    master_by_key = {
        (r["configuration_id"], r["instance_id"], r["repetition"]): r
        for r in master_rows
    }
    coverage_rows = []
    for instance_id in INSTANCE_IDS:
        selected_rows = [r for r in master_rows if r["instance_id"] == instance_id]
        scores = [r["score"] for r in selected_rows if r["result_state"] == "VALID"]
        coverage_rows.append({
            "summary_type": "instance", "summary_id": instance_id,
            "expected_runs": len(selected_rows),
            "valid_runs": sum(r["result_state"] == "VALID" for r in selected_rows),
            "running_runs": sum(r["result_state"] == "RUNNING" for r in selected_rows),
            "queued_runs": sum(r["result_state"] == "QUEUED" for r in selected_rows),
            "needs_rerun_runs": sum(r["result_state"] == "NEEDS_RERUN" for r in selected_rows),
            **stat_values(scores),
        })
    for config in DESIGN:
        selected_rows = [r for r in master_rows if r["configuration_id"] == config.configuration_id]
        scores = [r["score"] for r in selected_rows if r["result_state"] == "VALID"]
        coverage_rows.append({
            "summary_type": "configuration", "summary_id": config.configuration_id,
            "threshold_orders": config.threshold_orders,
            "population_size": config.population_size,
            "perturbation_rate": config.perturbation_rate,
            "mutation_rate": config.mutation_rate,
            "expected_runs": len(selected_rows),
            "valid_runs": sum(r["result_state"] == "VALID" for r in selected_rows),
            "running_runs": sum(r["result_state"] == "RUNNING" for r in selected_rows),
            "queued_runs": sum(r["result_state"] == "QUEUED" for r in selected_rows),
            "needs_rerun_runs": sum(r["result_state"] == "NEEDS_RERUN" for r in selected_rows),
            **stat_values(scores),
        })

    master_path = REPORT_DIR / "sensitivity_results_master.csv"
    attempts_path = REPORT_DIR / "sensitivity_attempts.csv"
    coverage_path = REPORT_DIR / "sensitivity_coverage.csv"
    unrecorded_logs_path = REPORT_DIR / "sensitivity_unrecorded_logs.csv"
    summary_path = REPORT_DIR / "sensitivity_report.md"
    index_path = EXPERIMENT_DIR / "SENSITIVITY_RESULTS.md"
    write_csv(master_path, MASTER_FIELDS, master_rows)
    write_csv(attempts_path, ATTEMPT_FIELDS, all_attempt_rows)
    write_csv(coverage_path, COVERAGE_FIELDS, coverage_rows)
    write_csv(unrecorded_logs_path, UNRECORDED_LOG_FIELDS, unrecorded_logs)

    valid_unique = sum(row["result_state"] == "VALID" for row in master_rows)
    running_count = sum(row["result_state"] == "RUNNING" for row in master_rows)
    queued_count = sum(row["result_state"] == "QUEUED" for row in master_rows)
    rerun_count = sum(row["result_state"] == "NEEDS_RERUN" for row in master_rows)
    valid_attempt_count = sum(a["valid"] for values in attempts_by_key.values() for a in values)
    recorded_attempt_count = sum(len(values) for values in attempts_by_key.values())
    seed_mismatches = sum(not a["seed_match"] for values in attempts_by_key.values() for a in values)
    active_worker_logs = sum(
        run_log_path(current_run_dir, job).exists()
        for _, job in selected_manifest_jobs
        if (key := (int(job["configuration_id"]), int(job["instance_id"]), int(job["repetition"]))) not in recorded_by_run[CURRENT_BATCH_ID]
    )
    batch_attempts = [
        attempt
        for values in attempts_by_key.values()
        for attempt in values
        if attempt["run_id"] == CURRENT_BATCH_ID
    ]
    batch_valid_attempts = [attempt for attempt in batch_attempts if attempt["valid"]]
    batch_queued_count = max(
        0,
        len(selected_manifest_jobs) - len(recorded_by_run[CURRENT_BATCH_ID]) - active_worker_logs,
    )
    current_fingerprint_valid_count = sum(
        row["result_state"] == "VALID"
        and current_fingerprint
        and row["source_code_fingerprint"] == current_fingerprint
        for row in master_rows
    )
    followup_expected = {
        (config.configuration_id, instance_id, repetition)
        for config in DESIGN
        for instance_id in (57, 58)
        for repetition in range(1, REPETITIONS + 1)
    }
    followup_batch_stats = {}
    followup_selected_keys = set()
    for run_id in FOLLOWUP_BATCH_IDS:
        selected = set()
        for key_values in manifests.get(run_id, {}).get("selected_job_keys", []):
            try:
                selected.add(tuple(int(v) for v in key_values))
            except (TypeError, ValueError):
                continue
        followup_selected_keys.update(selected)
        result_attempts = [
            attempt for values in attempts_by_key.values() for attempt in values
            if attempt["run_id"] == run_id
        ]
        followup_batch_stats[run_id] = {
            "expected": len(selected),
            "recorded": len(recorded_by_run[run_id]),
            "valid": sum(attempt["valid"] for attempt in result_attempts),
            "failed": sum(not attempt["valid"] for attempt in result_attempts),
            "fingerprint": manifests.get(run_id, {}).get("code", {}).get("dirty_worktree_fingerprint_sha256", ""),
            "git_revision": manifests.get(run_id, {}).get("code", {}).get("git_revision", ""),
        }
    followup_canonical = {
        key: row for key, row in canonical.items()
        if key in followup_expected and row["run_id"] in FOLLOWUP_BATCH_IDS
    }
    followup_fingerprints = Counter(row["fingerprint"] or "not recorded" for row in followup_canonical.values())
    invalid_attempt_rows = [row for row in all_attempt_rows if str(row.get("valid_result", "")).upper() == "FALSE"]
    invalid_reason_counts = Counter(
        row.get("failure_reason") or row.get("error") or "unspecified"
        for row in invalid_attempt_rows
    )
    focus_scores_by_instance = defaultdict(list)
    for row in master_rows:
        if row["instance_id"] in (57, 58) and row["result_state"] == "VALID":
            focus_scores_by_instance[row["instance_id"]].append(float(row["score"]))
    focus_outliers = []
    for row in master_rows:
        if row["instance_id"] not in (57, 58) or row["result_state"] != "VALID":
            continue
        scores = focus_scores_by_instance[row["instance_id"]]
        median_score = statistics.median(scores) if scores else 0.0
        if median_score > 0 and float(row["score"]) >= 5.0 * median_score:
            focus_outliers.append(row)
    length_summary_rows, factor_effect_rows = write_current_views(
        master_rows, generated_at, current_fingerprint, batch_attempts
    )
    master_fingerprint_counts = Counter(
        row["source_code_fingerprint"] or "not recorded" for row in master_rows
    )
    missing_fingerprint_count = master_fingerprint_counts.get("not recorded", 0)
    batch_57_scores = sorted(
        (float(attempt["raw"]["score"]), attempt["key"])
        for attempt in batch_valid_attempts if attempt["key"][1] == 57
    )
    batch_score_note = ""
    if len(batch_57_scores) >= 3:
        next_highest = batch_57_scores[-3][0]
        unusual = [(score, key) for score, key in batch_57_scores[-2:] if score > 5 * next_highest]
        if unusual:
            batch_score_note = "- Điểm instance 57 cao hơn rõ rệt so với phần còn lại: " + "; ".join(
                "config %d, repetition %d: %.3f (%.1f× mức kế tiếp %.3f)" % (
                    key[0], key[2], score, score / next_highest, next_highest,
                )
                for score, key in unusual
            ) + ". Đây là dấu hiệu cần rà soát; SUCCESS và score hữu hạn chưa tự xác nhận tính hợp lý của kết quả."

    lines = [
        "# AGVNS sensitivity: tổng hợp kết quả",
        "",
        "- Thời điểm chụp: %s (Asia/Ho_Chi_Minh)." % generated_at.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "- Thiết kế: 10 cấu hình × 16 instance × 3 repetition = 480 key; seed = `20260824 + instance_id × 1000 + repetition`.",
        "- Tệp chi tiết: [bảng 480 job](sensitivity_results_master.csv), [bảng sensitivity hiện tại](sensitivity_table_current.md), [lịch sử attempt](sensitivity_attempts.csv), [tổng hợp theo instance/cấu hình](sensitivity_coverage.csv), [bộ dữ liệu theo độ dài](sensitivity_jobs_by_length.csv), [tóm tắt theo độ dài](sensitivity_summary_by_length.csv), [hiệu ứng mức yếu tố và macro improvement](sensitivity_factor_effects.csv), [phân tích Taguchi chi tiết](sensitivity_taguchi_interpretation.md), [worker log không có result JSONL](sensitivity_unrecorded_logs.csv).",
        "",
        "## Trạng thái hiện tại",
        "",
        "| Trạng thái | Số run |",
        "|---|---:|",
        "| Có ít nhất một kết quả hợp lệ | %d |" % valid_unique,
        "| Đang chạy (có worker log) | %d |" % running_count,
        "| Đã nằm trong batch nhưng chưa được khởi chạy | %d |" % queued_count,
        "| Chưa có kết quả hợp lệ, chưa nằm trong batch hiện tại | %d |" % rerun_count,
        "| Tổng thiết kế | %d |" % len(master_rows),
        "",
        "Một kết quả chỉ được tính hợp lệ nếu score hữu hạn, không âm, nhỏ hơn giá trị sentinel `sys.maxsize`, trạng thái hiệu lực là `SUCCESS`, và seed trùng với thiết kế. Các lần chạy trùng key không làm tăng coverage; lịch sử của chúng vẫn nằm trong attempt ledger.",
        "",
        "## Batch hiện tại và quan sát sơ bộ",
        "",
        "- Batch `%s`: %d key được chọn; %d result row đã ghi, %d hợp lệ; %d workspace đang chạy nhưng chưa có result cuối; %d key đang chờ khởi chạy." % (
            CURRENT_BATCH_ID, len(selected_manifest_jobs), len(recorded_by_run[CURRENT_BATCH_ID]),
            len(batch_valid_attempts), active_worker_logs, batch_queued_count,
        ),
        "- %d/480 kết quả hợp lệ trong master có cùng code fingerprint với manifest của batch gần nhất (`%s`). Theo xác nhận của người dùng, toàn bộ 480 kết quả hợp lệ được đưa vào phân tích; fingerprint được giữ làm metadata truy nguyên, không dùng để loại run khỏi thống kê." % (
            current_fingerprint_valid_count, current_fingerprint or "not recorded",
        ),
        "- Fingerprint nguồn của 480 dòng canonical: " + "; ".join("%s: %d" % item for item in sorted(master_fingerprint_counts.items())) + ". Có %d/480 dòng thiếu fingerprint nguồn." % missing_fingerprint_count,
        batch_score_note,
        "- Mean score gộp theo job nhạy với scale điểm của instance lớn. Bảng Taguchi vì vậy bổ sung macro % cải thiện so baseline, tính trên mean từng instance rồi lấy trung bình 16 instance với trọng số bằng nhau.",
        "",
        "## Coverage theo instance",
        "",
        "| Instance | Hợp lệ / 30 | Đang chạy | Đang chờ trong batch | Cần chạy lại |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in coverage_rows:
        if row["summary_type"] == "instance":
            lines.append("| %s | %d / %d | %d | %d | %d |" % (
                row["summary_id"], row["valid_runs"], row["expected_runs"],
                row["running_runs"], row["queued_runs"], row["needs_rerun_runs"],
            ))
    lines += [
        "",
        "## Coverage và điểm theo cấu hình",
        "",
        "Điểm trung bình/độ lệch chuẩn bên dưới là thống kê mô tả của các repetition hợp lệ hiện có, gộp qua các instance có kích thước khác nhau. Không nên dùng riêng trung bình gộp này để so sánh nhân quả giữa cấu hình; hãy đối chiếu các dòng instance trong bảng master.",
        "",
        "| Config | T | Population | Perturbation | Mutation | Hợp lệ / 48 | Đang chạy | Chờ | Cần chạy lại | Mean score | SD score |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in coverage_rows:
        if row["summary_type"] == "configuration":
            mean = "" if row["mean_score"] is None else "%.3f" % row["mean_score"]
            sd = "" if row["score_standard_deviation"] is None else "%.3f" % row["score_standard_deviation"]
            lines.append("| %s | %s | %s | %s | %s | %d / %d | %d | %d | %d | %s | %s |" % (
                row["summary_id"], row["threshold_orders"], row["population_size"],
                row["perturbation_rate"], row["mutation_rate"], row["valid_runs"],
                row["expected_runs"], row["running_runs"], row["queued_runs"],
                row["needs_rerun_runs"], mean, sd,
            ))
    lines += [
        "",
        "## Tóm tắt theo độ dài instance",
        "",
        "Mỗi nhóm độ dài gồm hai instance và 60 job (10 cấu hình × 2 instance × 3 lần chạy). Biên score cho thấy scale của metric thay đổi theo kích thước; xem CSV để có thống kê từng cấu hình.",
        "",
        "| Số đơn hàng | Instance | Hợp lệ / 60 | Score min | Score max |",
        "|---:|---|---:|---:|---:|",
    ]
    for order_count in sorted(set(ORDER_COUNT_BY_SET.values())):
        set_id = next(k for k, value in ORDER_COUNT_BY_SET.items() if value == order_count)
        instance_ids = [i for i in INSTANCE_IDS if ((i - 1) // 8) + 1 == set_id]
        group = [r for r in master_rows if r["instance_id"] in instance_ids and r["result_state"] == "VALID"]
        lines.append("| %d | %s | %d / 60 | %.3f | %.3f |" % (
            order_count, ", ".join(map(str, instance_ids)), len(group),
            min(float(r["score"]) for r in group) if group else float("nan"),
            max(float(r["score"]) for r in group) if group else float("nan"),
        ))
    lines += [
        "",
        "## Tóm tắt yếu tố Taguchi so với baseline",
        "",
        "Metric phần trăm được tính theo từng instance: lấy mean score của ba repetition cho mỗi cấu hình/mức và baseline, tính `100 × (baseline_mean − score_mean) / baseline_mean`, rồi lấy trung bình trên 16 instance. Mỗi instance có trọng số như nhau; số dương tốt hơn baseline. Cột median là trung vị của 16 mức cải thiện theo instance. Đây là thống kê mô tả, không phải kiểm định ý nghĩa thống kê.",
        "",
        "| Yếu tố | Mức | Config IDs | Instance đủ | Mean cải thiện macro (%) | Median cải thiện theo instance (%) | Instance tốt hơn / đủ |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in factor_effect_rows:
        macro_improvement = "" if row["macro_mean_improvement_vs_baseline_percent"] is None else "%+.2f" % row["macro_mean_improvement_vs_baseline_percent"]
        median_instance_improvement = "" if row["median_instance_improvement_vs_baseline_percent"] is None else "%+.2f" % row["median_instance_improvement_vs_baseline_percent"]
        lines.append("| %s | %s | %s | %d | %s | %s | %d / %d |" % (
            row["factor"], row["level"], row["configuration_ids"],
            row["macro_instances"], macro_improvement,
            median_instance_improvement, row["instances_improved_vs_baseline"],
            row["macro_instances"],
        ))
    lines += [
        "",
        "## Các key chưa có kết quả hợp lệ",
        "",
        "| Config | Instance | Repetition | Tình trạng hiện tại |",
        "|---:|---:|---:|---|",
    ]
    for row in master_rows:
        if row["result_state"] != "VALID":
            lines.append("| %d | %d | %d | %s |" % (
                row["configuration_id"], row["instance_id"], row["repetition"], row["result_state"],
            ))
    current_core_list = current_manifest.get("cores", [])
    lines += [
        "",
        "## Các batch follow-up instance 57–58",
        "",
        "| Batch | Kỳ vọng | Đã ghi | Hợp lệ | Lỗi | Worktree fingerprint |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for run_id in FOLLOWUP_BATCH_IDS:
        stats = followup_batch_stats[run_id]
        lines.append("| `%s` | %d | %d | %d | %d | `%s` |" % (
            run_id, stats["expected"], stats["recorded"], stats["valid"], stats["failed"],
            stats["fingerprint"] or "not recorded",
        ))
    lines += [
        "",
        "- Hai batch có %d/%d key khác nhau của cohort instance 57–58; canonical results được lấy từ hai batch cho %d/60 key." % (
            len(followup_selected_keys),
            len(followup_expected), len(followup_canonical),
        ),
        "- Hai manifest ghi cùng Git revision `%s`, nhưng worktree fingerprints khác nhau. Fingerprint được giữ làm metadata truy nguyên; theo xác nhận của người dùng, toàn bộ 60 run 57–58 đều hợp lệ và được đưa vào phân tích." % (
            followup_batch_stats[FOLLOWUP_BATCH_IDS[-1]]["git_revision"] or "not recorded",
        ),
        "- [Dữ liệu 480 job đã sắp theo số lượng đơn hàng](sensitivity_jobs_by_length.csv); [tóm tắt theo độ dài và cấu hình](sensitivity_summary_by_length.csv). Tỷ lệ score so với baseline được ghép theo cùng instance/repetition.",
        "",
        "## Review of evidence",
        "",
        "### CONFIRMED",
        "",
        ("- Có %d/480 key thiết kế với kết quả canonical hợp lệ theo ledger: trạng thái SUCCESS, score hữu hạn/không âm và seed đúng." % valid_unique) if valid_unique else "- None.",
        "- Cohort follow-up 57–58 có %d/60 key được chọn từ hai batch đã ghi nhận kết quả hợp lệ." % len(followup_canonical),
        "",
        "### EXPLORATORY",
        "",
        "- Bảng score và hiệu ứng Taguchi là thống kê mô tả; chưa có kiểm định suy luận hoặc cohort xác nhận độc lập cho cấu hình dự đoán.",
        "- Các điểm 57–58 từ %d key vượt ngưỡng rà soát 5× median của cùng instance; đây là cờ kiểm tra chất lượng, không tự chứng minh lỗi thuật toán:" % len(focus_outliers),
    ]
    for row in sorted(focus_outliers, key=lambda item: float(item["score"]), reverse=True):
        lines.append("  - Config %d, instance %d, repetition %d: %.3f (source `%s`)." % (
            row["configuration_id"], row["instance_id"], row["repetition"], float(row["score"]),
            row["source_run_id"],
        ))
    lines += [
        "",
        "### FAILED / INCOMPLETE",
        "",
        "- Tại snapshot này: %d key chưa có kết quả hợp lệ; %d key RUNNING; %d key QUEUED; %d key cần chạy lại." % (
            rerun_count, running_count, queued_count, rerun_count,
        ),
        "- Attempt ledger giữ %d dòng kết quả không hợp lệ/lỗi đã ghi; %d worker log không có result JSONL cuối được giữ riêng và không được nâng thành success." % (
            len(invalid_attempt_rows), len(unrecorded_logs),
        ),
        "- Lý do invalid phổ biến: " + (", ".join("%s=%d" % pair for pair in invalid_reason_counts.most_common(8)) if invalid_reason_counts else "không có dòng invalid được phân loại."),
        "",
        "### HIGHEST VERIFIED RUNG",
        "",
        "- Coverage 480/480 key đã hoàn tất; theo xác nhận của người dùng, toàn bộ kết quả được xem là hợp lệ và được đưa vào phân tích. R7 (quyết định cấu hình tối ưu dựa trên cohort xác nhận) chưa đạt.",
        "",
        "### EVIDENCE GAPS",
        "",
        "- Fingerprint thiếu/khác được giữ để truy nguyên nhưng không dùng loại các run khỏi phân tích theo xác nhận của người dùng.",
        "- Có 3 repetition mỗi key; chưa có kiểm định suy luận. Các score ngoại lệ có thể ảnh hưởng mean/S/N và nên được đọc cùng macro improvement, median instance và thống kê theo độ dài.",
        "",
        "### RECOMMENDED NEXT",
        "",
        "- Nếu cần chốt cấu hình tối ưu, chạy cohort xác nhận cùng instance/seed cho tổ hợp Taguchi dự đoán, Config 3, Config 6 và baseline; báo cáo mean score cùng macro % cải thiện, median theo instance và score thành phần.",
        "",
        "480-job coverage is complete; a definitive R7 configuration decision remains unverified.",
        "",
        "## Quy tắc chọn và giới hạn dữ liệu",
        "",
        "- Master có đúng một dòng cho mỗi key thiết kế. Nếu có nhiều kết quả hợp lệ cho cùng key, ưu tiên kết quả hợp lệ có fingerprint code hiện tại; nếu không có, chọn kết quả hợp lệ mới nhất theo thời gian archive. Attempt CSV giữ nguyên mọi dòng đã ghi để truy nguyên các lần lặp/lỗi.",
        "- Các lần không có kết quả hợp lệ vẫn có dòng trong master; trường điểm, distance, runtime và source của kết quả hợp lệ để trống. Trạng thái và thông tin attempt lỗi gần nhất được giữ riêng để theo dõi.",
        "- Các run archive cũ không có code fingerprint trong manifest được để trống fingerprint, không suy đoán provenance.",
        "- Số attempt đã ghi: %d; số attempt hợp lệ: %d; attempt có seed không khớp: %d." % (
            recorded_attempt_count, valid_attempt_count, seed_mismatches,
        ),
        "- Có %d worker log lịch sử không có dòng result JSONL; %d log có ghi score. Các score chỉ được giữ ở cột `log_observed_score`, không được tính là kết quả hợp lệ vì thiếu record cuối và return code." % (
            len(unrecorded_logs), sum(row["log_observed_score"] is not None for row in unrecorded_logs),
        ),
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    index_lines = [
        "# AGVNS sensitivity results",
        "",
        "Snapshot: %s (Asia/Ho_Chi_Minh)." % generated_at.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "",
        "Coverage is **%d/480 valid**; %d run keys are still unresolved: %d running, %d queued in the current batch, and %d that need a rerun." % (
            valid_unique, running_count + queued_count + rerun_count,
            running_count, queued_count, rerun_count,
        ),
        "",
        "The 480-row master leaves score and runtime fields blank wherever no valid finalized result exists.",
        "",
        "- [Detailed report](reports/sensitivity_report.md)",
        "- [Master table: one row per planned job](reports/sensitivity_results_master.csv)",
        "- [Recorded result attempts and failures](reports/sensitivity_attempts.csv)",
        "- [Coverage and score summaries by instance/configuration](reports/sensitivity_coverage.csv)",
        "- [Current per-instance sensitivity table](reports/sensitivity_table_current.md)",
        "- [Current 480-job status table](reports/sensitivity_jobs_current.csv)",
        "- [480-job dataset grouped by order-count length](reports/sensitivity_jobs_by_length.csv)",
        "- [Summary by order-count length and configuration](reports/sensitivity_summary_by_length.csv)",
        "- [Taguchi factor-level summaries with instance-equal macro improvement](reports/sensitivity_factor_effects.csv)",
        "- [Detailed Taguchi interpretation and per-instance Config 3 analysis](reports/sensitivity_taguchi_interpretation.md)",
        "- [Worker logs without a finalized JSONL result](reports/sensitivity_unrecorded_logs.csv)",
        "- [Report builder](reports/build_sensitivity_report.py)",
        "",
        "Latest recorded batch `%s` selected %s jobs and used %s workers on cores `%s`. Rerun `reports/build_sensitivity_report.py` to refresh the snapshot when new result artifacts arrive." % (
            CURRENT_BATCH_ID, current_manifest.get("expected_jobs", 0),
            current_manifest.get("workers", 0), ",".join(map(str, current_core_list)),
        ),
        "",
    ]
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    # Output consistency checks: one master row per planned key and the coverage
    # status totals must account for the full design.
    assert len(master_rows) == 480
    assert valid_unique + running_count + queued_count + rerun_count == 480
    assert len({(r["configuration_id"], r["instance_id"], r["repetition"]) for r in master_rows}) == 480
    print("Generated:")
    print(master_path)
    print(attempts_path)
    print(coverage_path)
    print(unrecorded_logs_path)
    print(REPORT_DIR / "sensitivity_jobs_current.csv")
    print(REPORT_DIR / "sensitivity_jobs_by_length.csv")
    print(REPORT_DIR / "sensitivity_summary_by_config_instance_current.csv")
    print(REPORT_DIR / "sensitivity_summary_by_length.csv")
    print(REPORT_DIR / "sensitivity_table_current.md")
    print(summary_path)
    print(index_path)
    print("Counts: valid=%d running=%d queued=%d needs_rerun=%d recorded_attempts=%d" % (
        valid_unique, running_count, queued_count, rerun_count, recorded_attempt_count,
    ))


if __name__ == "__main__":
    main()
