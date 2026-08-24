"""Run the approved AGVNS parameter screening design with isolated workers."""

import argparse
import csv
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

EXPERIMENT_DIR = pathlib.Path(__file__).resolve().parent
AGVNS_ROOT = EXPERIMENT_DIR.parents[1]
REPO_ROOT = AGVNS_ROOT.parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))
if str(AGVNS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGVNS_ROOT))

from aggregate_results import aggregate_run, parse_worker_log_text
from design import DESIGN, expected_job_count, iter_jobs, validate_design


RESULT_FIELDS = (
    "configuration_id", "threshold_orders", "population_size", "perturbation_rate", "mutation_rate",
    "instance_id", "repetition", "seed", "core", "pid", "status", "return_code",
    "wall_time_seconds", "score", "total_distance", "sum_over_time", "total_score",
    "simulation_runtime_seconds", "algorithm_time_seconds", "algorithm_dispatch_count",
    "workspace", "log_path", "error",
)


def parse_cores(raw: Optional[str]) -> List[int]:
    if raw:
        cores = [int(value.strip()) for value in raw.split(",") if value.strip()]
    else:
        cores = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else list(range(os.cpu_count() or 1))
    if not cores or any(core < 0 for core in cores):
        raise ValueError("At least one non-negative CPU core is required")
    available = set(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else set(range(os.cpu_count() or 1))
    unavailable = [core for core in cores if core not in available]
    if unavailable:
        raise ValueError("Unavailable CPU cores: %s" % unavailable)
    return cores


def create_run_dir(run_root: str) -> pathlib.Path:
    root = pathlib.Path(run_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = root / stamp
    suffix = 1
    while run_dir.exists():
        run_dir = root / ("%s_%02d" % (stamp, suffix))
        suffix += 1
    (run_dir / "jobs").mkdir(parents=True)
    return run_dir


def job_key(job: Dict[str, Any]) -> Tuple[int, int, int]:
    return int(job["configuration_id"]), int(job["instance_id"]), int(job["repetition"])


def build_jobs(base_seed: int, configuration_id: Optional[int] = None) -> List[Dict[str, Any]]:
    jobs = list(iter_jobs(base_seed=base_seed))
    if configuration_id is not None:
        jobs = [job for job in jobs if job["configuration_id"] == configuration_id]
    return jobs


def write_manifest(run_dir: pathlib.Path, args: argparse.Namespace, jobs: List[Dict[str, Any]], cores: List[int]) -> None:
    manifest = {
        "experiment": "agvns_parameter_sensitivity_screening",
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "expected_jobs": len(jobs),
        "design_jobs": expected_job_count(),
        "base_seed": args.base_seed,
        "seed_formula": "base_seed + instance_id * 1000 + repetition",
        "cores": cores,
        "workers": args.workers or len(cores),
        "command": " ".join(sys.argv),
    }
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with open(run_dir / "design_matrix.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["configuration_id", "T", "population", "perturbation", "mutation_subset"])
        for row in DESIGN:
            writer.writerow([row.configuration_id, row.threshold_orders, row.population_size, row.perturbation_rate, row.mutation_rate])


def append_result(run_dir: pathlib.Path, result: Dict[str, Any]) -> None:
    path = run_dir / "results.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")


def load_completed(run_dir: pathlib.Path) -> Set[Tuple[int, int, int]]:
    path = run_dir / "results.jsonl"
    if not path.exists():
        return set()
    completed = set()
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row.get("status") == "SUCCESS":
                    completed.add(job_key(row))
    return completed


def _worker_environment(job: Dict[str, Any], workspace: pathlib.Path) -> Dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "MA_DATA_INTERACTION_DIR": str(workspace),
            "DPDP_DATA_INTERACTION_DIR": str(workspace),
            "DPDP_RANDOM_SEED": str(job["seed"]),
            "AGVNS_RANDOM_SEED": str(job["seed"]),
            "AGVNS_EXPERIMENT_ID": str(job["configuration_id"]),
            "AGVNS_EXPERIMENT_T": str(job["threshold_orders"]),
            "AGVNS_EXPERIMENT_POPULATION": str(job["population_size"]),
            "AGVNS_EXPERIMENT_PERTURBATION": str(job["perturbation_rate"]),
            "AGVNS_EXPERIMENT_MUTATION_SUBSET": str(job["mutation_rate"]),
            "AGVNS_EXPERIMENT_DISABLE_VISUALIZATION": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return environment


def launch(job: Dict[str, Any], run_dir: pathlib.Path, core: int, python_exec: str) -> Dict[str, Any]:
    workspace = run_dir / "jobs" / ("config_%03d" % job["configuration_id"]) / ("instance_%03d" % job["instance_id"]) / ("repetition_%03d_seed_%d" % (job["repetition"], job["seed"]))
    workspace.mkdir(parents=True, exist_ok=True)
    log_path = workspace / "worker.log"
    command = [python_exec, str(AGVNS_ROOT / "main.py"), "--instances", str(job["instance_id"]), "--data-dir", str(workspace), "--cpu", str(core), "--seed", str(job["seed"])]
    log_handle = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=str(AGVNS_ROOT), stdout=log_handle, stderr=subprocess.STDOUT, env=_worker_environment(job, workspace), text=True)
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(process.pid, {core})
    return {
        "job": job,
        "workspace": workspace,
        "log_path": log_path,
        "process": process,
        "log_handle": log_handle,
        "core": core,
        "started_monotonic": time.monotonic(),
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def finish(worker: Dict[str, Any]) -> Dict[str, Any]:
    process = worker["process"]
    return_code = process.returncode
    worker["log_handle"].close()
    message = worker["log_path"].read_text(encoding="utf-8", errors="replace")
    parsed = parse_worker_log_text(message, int(worker["job"]["instance_id"]), return_code)
    result = dict(worker["job"])
    result.update(parsed)
    result.update(
        {
            "core": worker["core"],
            "pid": process.pid,
            "return_code": return_code,
            "wall_time_seconds": round(time.monotonic() - worker["started_monotonic"], 3),
            "workspace": str(worker["workspace"].relative_to(worker["workspace"].parents[3])),
            "log_path": str(worker["log_path"].relative_to(worker["workspace"].parents[3])),
        }
    )
    return result


def run_jobs(args: argparse.Namespace, run_dir: pathlib.Path, jobs: List[Dict[str, Any]], cores: List[int]) -> None:
    workers = max(1, min(args.workers or len(cores), len(cores)))
    core_queue: Deque[int] = deque(cores[:workers])
    pending: Deque[Dict[str, Any]] = deque(jobs)
    active: List[Dict[str, Any]] = []
    completed = load_completed(run_dir) if args.resume else set()
    pending = deque(job for job in pending if job_key(job) not in completed)
    while pending or active:
        while pending and core_queue:
            job = pending.popleft()
            core = core_queue.popleft()
            active.append(launch(job, run_dir, core, args.python))
            print("Started config_%03d instance_%d repetition_%d on core %d" % (job["configuration_id"], job["instance_id"], job["repetition"], core), flush=True)
        time.sleep(0.2)
        remaining = []
        for worker in active:
            if worker["process"].poll() is None:
                remaining.append(worker)
                continue
            result = finish(worker)
            append_result(run_dir, result)
            core_queue.append(worker["core"])
            print("Finished config_%03d instance_%d repetition_%d: %s score=%s" % (result["configuration_id"], result["instance_id"], result["repetition"], result["status"], result.get("score")), flush=True)
        active = remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AGVNS parameter screening")
    parser.add_argument("--execute", action="store_true", help="Run real simulator jobs")
    parser.add_argument("--dry-run", action="store_true", help="Print job count without running")
    parser.add_argument("--run-root", default=str(EXPERIMENT_DIR / "runs"))
    parser.add_argument("--config-id", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--cores")
    parser.add_argument("--base-seed", type=int, default=20260824)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    validate_design()
    if not args.execute and not args.dry_run:
        parser.error("Use --dry-run or --execute explicitly")
    jobs = build_jobs(args.base_seed, args.config_id)
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit must be positive")
        jobs = jobs[: args.limit]
    cores = parse_cores(args.cores)
    print("Validated jobs: %d; cores: %s" % (len(jobs), cores))
    if args.dry_run:
        return
    run_dir = create_run_dir(args.run_root) if not args.resume else pathlib.Path(args.run_root).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(run_dir, args, jobs, cores)
    run_jobs(args, run_dir, jobs, cores)
    output = aggregate_run(str(run_dir))
    print("Completed rows=%d successful=%d failed=%d" % (output["total_rows"], output["successful_rows"], output["failed_rows"]))
    print("Run directory: %s" % run_dir)
    if output["failed_rows"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
