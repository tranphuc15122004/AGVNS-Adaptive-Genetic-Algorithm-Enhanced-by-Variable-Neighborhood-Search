"""Shared queue-based runner for isolated DPDP simulator experiments.

The target-specific ``run_parallel.py`` files only provide metadata.  Keeping
the scheduler here prevents the seven benchmark implementations from drifting
apart while still allowing Java and C++ adapters to customize their workers.
"""

import argparse
import collections
import csv
import datetime
import importlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple


_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_SCORE_RE = re.compile(r"Score of instance_(\d+):\s*(%s)" % _NUMBER_RE)
_SCORE_RUNTIME_RE = re.compile(
    r"Score of instance_(\d+):.*?runtime:\s*(%s)\s*(?:seconds|s)" % _NUMBER_RE
)
_SIMULATION_RUNTIME_RE = re.compile(
    r"Simulation instance_(\d+) completed in\s*(%s)\s*(?:seconds|s)"
    % _NUMBER_RE
)
_ALGORITHM_TIME_RE = re.compile(
    r"Thoi gian thuc hien thuat toan:\s*(%s)" % _NUMBER_RE
)

CSV_FIELDS = [
    "batch_id",
    "instance_id",
    "repetition",
    "seed",
    "core",
    "pid",
    "started_at_utc",
    "finished_at_utc",
    "wall_time_seconds",
    "simulation_runtime_seconds",
    "algorithm_time_seconds",
    "algorithm_dispatch_count",
    "score",
    "return_code",
    "status",
    "workspace",
    "log_path",
    "error",
]


def _parse_instances(raw_value: str) -> List[int]:
    """Parse comma-separated IDs and ascending inclusive ranges."""
    instances: List[int] = []
    seen = set()
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not all(bound.strip().isdigit() for bound in bounds):
                raise ValueError("Invalid instance range: %s" % part)
            start, end = (int(bound.strip()) for bound in bounds)
            if start > end:
                raise ValueError("Instance range must be ascending: %s" % part)
            values = range(start, end + 1)
        elif part.isdigit():
            values = (int(part),)
        else:
            raise ValueError("Invalid instance ID: %s" % part)

        for instance in values:
            if instance <= 0:
                raise ValueError("Instance IDs must be positive: %s" % instance)
            if instance not in seen:
                instances.append(instance)
                seen.add(instance)

    if not instances:
        raise ValueError("At least one instance must be selected.")
    return instances


def _parse_instance_tokens(tokens: Sequence[str]) -> List[int]:
    return _parse_instances(",".join(tokens))


def _parse_cores(raw_value: str) -> List[int]:
    cores: List[int] = []
    seen = set()
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError("Invalid CPU core ID: %s" % part)
        core = int(part)
        if core < 0:
            raise ValueError("CPU core IDs must be non-negative: %s" % core)
        if core not in seen:
            cores.append(core)
            seen.add(core)
    if not cores:
        raise ValueError("No CPU cores were selected.")
    return cores


def _available_cores() -> List[int]:
    if hasattr(os, "sched_getaffinity"):
        return sorted(os.sched_getaffinity(0))
    return list(range(os.cpu_count() or 1))


def _select_cores(args: argparse.Namespace) -> List[int]:
    available = _available_cores()
    cores = _parse_cores(args.cores) if args.cores else available
    unavailable = [core for core in cores if core not in available]
    if unavailable:
        raise ValueError(
            "Requested CPU cores are unavailable: %s (available: %s)"
            % (unavailable, available)
        )
    if args.workers is not None and args.workers <= 0:
        raise ValueError("--workers must be positive.")
    worker_count = args.workers or len(cores)
    if worker_count > len(cores):
        raise ValueError(
            "--workers=%d requires at least %d selected CPU cores; got %d."
            % (worker_count, worker_count, len(cores))
        )
    return cores[:worker_count]


def _job_seed(base_seed: int, instance: int, repetition: int) -> int:
    """Keep a job's seed stable when the selected instance set changes."""
    return base_seed + instance * 1000 + repetition


def _build_jobs(
    batch_id: str,
    batch_root: str,
    instances: Iterable[int],
    repetitions: int,
    base_seed: int,
) -> List[Dict[str, Any]]:
    if repetitions <= 0:
        raise ValueError("--repetitions must be positive.")
    jobs: List[Dict[str, Any]] = []
    for instance in instances:
        for repetition in range(1, repetitions + 1):
            seed = _job_seed(base_seed, instance, repetition)
            workspace = os.path.join(
                batch_root,
                "jobs",
                "instance_%03d" % instance,
                "repetition_%03d_seed_%d" % (repetition, seed),
            )
            jobs.append(
                {
                    "batch_id": batch_id,
                    "instance_id": instance,
                    "repetition": repetition,
                    "seed": seed,
                    "workspace": workspace,
                }
            )
    return jobs


def _build_worker_env(
    data_dir: str,
    data_env: str,
    seed_env: Optional[str],
    seed: int,
    explicit_c_paths: bool = False,
    algorithm_executable: Optional[str] = None,
    checkpoint: Optional[str] = None,
    allow_heuristic: bool = False,
) -> Dict[str, str]:
    env = os.environ.copy()
    absolute_data_dir = os.path.abspath(data_dir)
    env[data_env] = absolute_data_dir
    # Keep this compatibility name available to the shared simulator helpers.
    env["MA_DATA_INTERACTION_DIR"] = absolute_data_dir
    env["DPDP_DATA_INTERACTION_DIR"] = absolute_data_dir
    if seed_env:
        env[seed_env] = str(seed)
    env["DPDP_RANDOM_SEED"] = str(seed)
    if explicit_c_paths:
        env["DPDP_USE_EXPLICIT_PATHS"] = "1"
    if algorithm_executable:
        env["DPDP_ALGORITHM_EXECUTABLE"] = os.path.abspath(algorithm_executable)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    if checkpoint:
        env["EVORL_CHECKPOINT"] = os.path.abspath(checkpoint)
        env["EVORL_REQUIRE_CHECKPOINT"] = "1"
        env["EVORL_LEGACY_FALLBACK"] = "0"
    elif allow_heuristic:
        env.pop("EVORL_CHECKPOINT", None)
        env["EVORL_REQUIRE_CHECKPOINT"] = "0"
        env["EVORL_LEGACY_FALLBACK"] = "1"
    return env


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _new_batch_root(run_root: str) -> Tuple[str, str]:
    os.makedirs(run_root, exist_ok=True)
    base_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_id = base_id
    suffix = 1
    batch_root = os.path.join(run_root, batch_id)
    while os.path.exists(batch_root):
        batch_id = "%s_%02d" % (base_id, suffix)
        batch_root = os.path.join(run_root, batch_id)
        suffix += 1
    os.makedirs(os.path.join(batch_root, "jobs"))
    return batch_id, batch_root


def _write_json(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _relative_path(path: str, batch_root: str) -> str:
    return os.path.relpath(path, batch_root)


def _parse_worker_log(
    log_path: str,
    instance: int,
    return_code: int,
) -> Tuple[str, Optional[float], Optional[float], float, int, str]:
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
            message = handle.read()
    except OSError as exc:
        return "FAILED", None, None, 0.0, 0, "Cannot read worker log: %s" % exc

    scores = [
        float(match.group(2))
        for match in _SCORE_RE.finditer(message)
        if int(match.group(1)) == instance
    ]
    score_runtime_matches = [
        float(match.group(2))
        for match in _SCORE_RUNTIME_RE.finditer(message)
        if int(match.group(1)) == instance
    ]
    simulation_runtime_matches = [
        float(match.group(2))
        for match in _SIMULATION_RUNTIME_RE.finditer(message)
        if int(match.group(1)) == instance
    ]
    simulation_runtime = (
        score_runtime_matches[-1]
        if score_runtime_matches
        else simulation_runtime_matches[-1]
        if simulation_runtime_matches
        else None
    )
    algorithm_times = [
        float(match.group(1)) for match in _ALGORITHM_TIME_RE.finditer(message)
    ]
    score = scores[-1] if scores else None
    errors: List[str] = []
    if return_code != 0:
        errors.append("worker exited with code %d" % return_code)
    if "FAIL" in message:
        errors.append("worker emitted FAIL")
    if "SUCCESS" not in message:
        errors.append("missing SUCCESS marker")
    if score is None:
        errors.append("missing final score")
    elif not math.isfinite(score):
        errors.append("final score is not finite")
    if simulation_runtime is None:
        errors.append("missing simulation runtime")
    elif not math.isfinite(simulation_runtime) or simulation_runtime < 0:
        errors.append("simulation runtime is invalid")
    status = "SUCCESS" if not errors else "FAILED"
    return (
        status,
        score,
        simulation_runtime,
        sum(algorithm_times),
        len(algorithm_times),
        "; ".join(errors),
    )


def _launch_job(
    job: Dict[str, Any],
    batch_root: str,
    target_root: str,
    python_exec: str,
    core: int,
    data_env: str,
    seed_env: Optional[str],
    explicit_c_paths: bool,
    checkpoint: Optional[str] = None,
    allow_heuristic: bool = False,
) -> Dict[str, Any]:
    workspace = job["workspace"]
    os.makedirs(workspace, exist_ok=True)
    log_path = os.path.join(workspace, "worker.log")
    log_handle = open(log_path, "w", encoding="utf-8")
    algorithm_executable = None
    if explicit_c_paths:
        source_executable = os.path.join(target_root, "main_algorithm.out")
        if os.path.isfile(source_executable):
            algorithm_executable = os.path.join(workspace, "main_algorithm.out")
            shutil.copyfile(source_executable, algorithm_executable)
            os.chmod(algorithm_executable, 0o755)
    command = [
        python_exec,
        "main.py",
        "--instances",
        str(job["instance_id"]),
        "--data-dir",
        workspace,
        "--cpu",
        str(core),
        "--seed",
        str(job["seed"]),
    ]
    if checkpoint:
        command.extend(["--checkpoint", os.path.abspath(checkpoint)])
    elif allow_heuristic:
        command.append("--allow-heuristic")
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    process = None
    try:
        process = subprocess.Popen(
            command,
            cwd=target_root,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=_build_worker_env(
                workspace,
                data_env,
                seed_env,
                job["seed"],
                explicit_c_paths=explicit_c_paths,
                algorithm_executable=algorithm_executable,
                checkpoint=checkpoint,
                allow_heuristic=allow_heuristic,
            ),
            text=True,
        )
        if hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(process.pid, {core})
    except Exception:
        if process is not None:
            process.terminate()
            process.wait()
        log_handle.close()
        raise
    return dict(
        job,
        core=core,
        process=process,
        pid=process.pid,
        log_handle=log_handle,
        log_path=log_path,
        started_at_utc=started_at,
        started_monotonic=started_monotonic,
        batch_root=batch_root,
    )


def _complete_worker(worker: Dict[str, Any]) -> Dict[str, Any]:
    return_code = worker["process"].returncode
    worker["log_handle"].close()
    (
        status,
        score,
        simulation_runtime,
        algorithm_time,
        dispatch_count,
        error,
    ) = _parse_worker_log(worker["log_path"], worker["instance_id"], return_code)
    return {
        "batch_id": worker["batch_id"],
        "instance_id": worker["instance_id"],
        "repetition": worker["repetition"],
        "seed": worker["seed"],
        "core": worker["core"],
        "pid": worker["pid"],
        "started_at_utc": worker["started_at_utc"],
        "finished_at_utc": _utc_now(),
        "wall_time_seconds": round(time.monotonic() - worker["started_monotonic"], 3),
        "simulation_runtime_seconds": simulation_runtime,
        "algorithm_time_seconds": round(algorithm_time, 3),
        "algorithm_dispatch_count": dispatch_count,
        "score": score,
        "return_code": return_code,
        "status": status,
        "workspace": _relative_path(worker["workspace"], worker["batch_root"]),
        "log_path": _relative_path(worker["log_path"], worker["batch_root"]),
        "error": error,
    }


def _write_results_csv(path: str, results: Sequence[Dict[str, Any]]) -> None:
    ordered = sorted(results, key=lambda result: (result["instance_id"], result["repetition"]))
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in ordered:
            writer.writerow({field: result.get(field, "") for field in CSV_FIELDS})


def _build_summary(
    manifest: Dict[str, Any],
    results: Sequence[Dict[str, Any]],
    batch_status: str,
    batch_wall_time_seconds: Optional[float],
) -> Dict[str, Any]:
    def runtime_distribution(values: Sequence[float]) -> Dict[str, Optional[float]]:
        if not values:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "standard_deviation": None,
            }
        return {
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "mean": round(statistics.mean(values), 6),
            "standard_deviation": (
                round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0
            ),
        }

    successful = [result for result in results if result["status"] == "SUCCESS"]
    failed = [result for result in results if result["status"] != "SUCCESS"]
    per_instance: Dict[str, Dict[str, Any]] = {}
    for instance in manifest["instances"]:
        current = [result for result in results if result["instance_id"] == instance]
        scores = [
            result["score"]
            for result in current
            if result["status"] == "SUCCESS" and result["score"] is not None
        ]
        wall_runtimes = [result["wall_time_seconds"] for result in current]
        simulation_runtimes = [
            result["simulation_runtime_seconds"]
            for result in current
            if result["status"] == "SUCCESS"
            and result["simulation_runtime_seconds"] is not None
        ]
        runtime_summary = runtime_distribution(simulation_runtimes)
        per_instance[str(instance)] = {
            "successful_repetitions": sum(result["status"] == "SUCCESS" for result in current),
            "failed_repetitions": sum(result["status"] != "SUCCESS" for result in current),
            "min_score": min(scores) if scores else None,
            "max_score": max(scores) if scores else None,
            "mean_score": statistics.mean(scores) if scores else None,
            "standard_deviation_score": (
                statistics.pstdev(scores)
                if len(scores) > 1
                else 0.0
                if scores
                else None
            ),
            "mean_simulation_runtime_seconds": (
                runtime_summary["mean"]
            ),
            "min_simulation_runtime_seconds": runtime_summary["min"],
            "max_simulation_runtime_seconds": runtime_summary["max"],
            "standard_deviation_simulation_runtime_seconds": runtime_summary[
                "standard_deviation"
            ],
            "mean_wall_time_seconds": (
                statistics.mean(wall_runtimes) if wall_runtimes else None
            ),
        }
    successful_simulation_runtimes = [
        result["simulation_runtime_seconds"]
        for result in successful
        if result["simulation_runtime_seconds"] is not None
    ]
    runtime_summary = runtime_distribution(successful_simulation_runtimes)
    return {
        "batch_id": manifest["batch_id"],
        "status": batch_status,
        "configuration": manifest,
        "total_jobs": manifest["total_jobs"],
        "completed_jobs": len(results),
        "successful_jobs": len(successful),
        "failed_jobs": len(failed),
        "batch_wall_time_seconds": batch_wall_time_seconds,
        "total_simulation_runtime_seconds": round(sum(successful_simulation_runtimes), 3),
        "min_simulation_runtime_seconds": runtime_summary["min"],
        "max_simulation_runtime_seconds": runtime_summary["max"],
        "mean_simulation_runtime_seconds": runtime_summary["mean"],
        "standard_deviation_simulation_runtime_seconds": runtime_summary[
            "standard_deviation"
        ],
        "summed_job_wall_time_seconds": round(
            sum(result["wall_time_seconds"] for result in results), 3
        ),
        "per_instance": per_instance,
        "jobs": list(sorted(results, key=lambda result: (result["instance_id"], result["repetition"]))),
    }


def _persist_progress(
    batch_root: str,
    manifest: Dict[str, Any],
    results: Sequence[Dict[str, Any]],
    batch_status: str,
    batch_wall_time_seconds: Optional[float] = None,
) -> None:
    _write_results_csv(os.path.join(batch_root, "results.csv"), results)
    _write_json(
        os.path.join(batch_root, "summary.json"),
        _build_summary(manifest, results, batch_status, batch_wall_time_seconds),
    )


def _build_parser(spec: Dict[str, Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run repeated %s simulations in parallel with isolated workspaces."
        % spec["algorithm"]
    )
    parser.add_argument("instance_ids", nargs="*", help="Instance IDs/ranges, e.g. 1 2 5-8")
    parser.add_argument("--instances", help="Comma-separated IDs/ranges, e.g. 1,3,5-10")
    parser.add_argument("--all", action="store_true", help="Run all benchmark instances")
    parser.add_argument("--repetitions", type=int, default=1, help="Repetitions per instance")
    parser.add_argument("--workers", type=int, help="Maximum active jobs")
    parser.add_argument("--cores", help="Comma-separated CPU core IDs")
    parser.add_argument("--base-seed", type=int, default=0, help="Base seed for deterministic jobs")
    parser.add_argument(
        "--run-root",
        default=os.path.join("algorithm", "data_interaction_runs"),
        help="Directory where timestamped experiment batches are created",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable for workers")
    if spec.get("checkpoint"):
        parser.add_argument("--checkpoint", help="RPPO checkpoint passed to every worker")
        parser.add_argument(
            "--allow-heuristic",
            action="store_true",
            help="Allow the legacy heuristic path for compatibility/debugging",
        )
    return parser


def _load_configs(target_root: str):
    if target_root not in sys.path:
        sys.path.insert(0, target_root)
    return importlib.import_module("src.conf.configs").Configs


def _select_instances(args: argparse.Namespace, configs: Any) -> List[int]:
    if args.instance_ids:
        instances = _parse_instance_tokens(args.instance_ids)
    elif args.all:
        instances = list(configs.all_test_instances)
    elif args.instances:
        instances = _parse_instances(args.instances)
    elif configs.selected_instances:
        instances = list(configs.selected_instances)
    else:
        instances = list(configs.all_test_instances)
    valid_instances = set(configs.all_test_instances)
    invalid = [instance for instance in instances if instance not in valid_instances]
    if invalid:
        raise ValueError(
            "Instance IDs outside the benchmark range 1-%d: %s"
            % (max(valid_instances), ", ".join(str(item) for item in invalid))
        )
    return instances


def _failure_result(job: Dict[str, Any], batch_root: str, core: int, exc: Exception) -> Dict[str, Any]:
    workspace = job["workspace"]
    os.makedirs(workspace, exist_ok=True)
    log_path = os.path.join(workspace, "worker.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("Failed to launch worker: %s\n" % exc)
    return {
        "batch_id": job["batch_id"],
        "instance_id": job["instance_id"],
        "repetition": job["repetition"],
        "seed": job["seed"],
        "core": core,
        "pid": None,
        "started_at_utc": None,
        "finished_at_utc": _utc_now(),
        "wall_time_seconds": 0.0,
        "simulation_runtime_seconds": None,
        "algorithm_time_seconds": 0.0,
        "algorithm_dispatch_count": 0,
        "score": None,
        "return_code": None,
        "status": "FAILED",
        "workspace": _relative_path(workspace, batch_root),
        "log_path": _relative_path(log_path, batch_root),
        "error": "Failed to launch worker: %s" % exc,
    }


def _run_batch(
    args: argparse.Namespace,
    spec: Dict[str, Any],
    configs: Any,
    instances: List[int],
    cores: List[int],
) -> Tuple[str, List[Dict[str, Any]]]:
    if args.repetitions <= 0:
        raise ValueError("--repetitions must be positive.")
    checkpoint = getattr(args, "checkpoint", None)
    allow_heuristic = bool(getattr(args, "allow_heuristic", False))
    if spec.get("checkpoint"):
        if not checkpoint and not allow_heuristic:
            raise ValueError(
                "Parallel EvoRL inference requires --checkpoint; use "
                "--allow-heuristic only for an explicit compatibility/debug run."
            )
        if checkpoint and not os.path.isfile(checkpoint):
            raise FileNotFoundError("EvoRL checkpoint does not exist: %s" % checkpoint)

    target_root = spec["target_root"]
    run_root = os.path.abspath(os.path.join(target_root, args.run_root))
    batch_id, batch_root = _new_batch_root(run_root)
    jobs = _build_jobs(batch_id, batch_root, instances, args.repetitions, args.base_seed)
    manifest = {
        "batch_id": batch_id,
        "algorithm": spec["algorithm"],
        "created_at_utc": _utc_now(),
        "instances": instances,
        "repetitions": args.repetitions,
        "total_jobs": len(jobs),
        "workers": len(cores),
        "cores": cores,
        "base_seed": args.base_seed,
        "seed_formula": "base_seed + instance_id * 1000 + repetition",
        "job_order": "instance-major",
        "runtime_source": "simulate() elapsed return value logged by %s/main.py" % spec["algorithm"],
    }
    if spec.get("checkpoint"):
        manifest["checkpoint"] = os.path.abspath(checkpoint) if checkpoint else None
        manifest["allow_heuristic"] = allow_heuristic
    _write_json(os.path.join(batch_root, "manifest.json"), manifest)
    _persist_progress(batch_root, manifest, [], "RUNNING")

    pending: Deque[Dict[str, Any]] = collections.deque(jobs)
    available_cores: Deque[int] = collections.deque(cores)
    active: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    batch_started = time.monotonic()
    print("Batch root: %s" % batch_root)
    print("Instances: %s" % instances)
    print("Repetitions: %d" % args.repetitions)
    print("Jobs: %d" % len(jobs))
    print("Cores: %s" % cores)

    try:
        while pending or active:
            while pending and available_cores:
                job = pending.popleft()
                core = available_cores.popleft()
                try:
                    worker = _launch_job(
                        job,
                        batch_root,
                        target_root,
                        args.python,
                        core,
                        spec["data_env"],
                        spec.get("seed_env"),
                        bool(spec.get("explicit_c_paths")),
                        checkpoint=checkpoint,
                        allow_heuristic=allow_heuristic,
                    )
                except Exception as exc:
                    results.append(_failure_result(job, batch_root, core, exc))
                    available_cores.append(core)
                    _persist_progress(batch_root, manifest, results, "RUNNING")
                    continue
                active.append(worker)
                print(
                    "Started instance_%d repetition_%d on core %d"
                    % (job["instance_id"], job["repetition"], core)
                )

            time.sleep(0.2)
            still_active: List[Dict[str, Any]] = []
            for worker in active:
                if worker["process"].poll() is None:
                    still_active.append(worker)
                    continue
                result = _complete_worker(worker)
                results.append(result)
                available_cores.append(worker["core"])
                print(
                    "Finished instance_%d repetition_%d on core %d with code %s "
                    "in %.3fs; simulation runtime %.3fs (%s)"
                    % (
                        result["instance_id"],
                        result["repetition"],
                        result["core"],
                        result["return_code"],
                        result["wall_time_seconds"],
                        result["simulation_runtime_seconds"]
                        if result["simulation_runtime_seconds"] is not None
                        else float("nan"),
                        result["status"],
                    )
                )
                print("Log: %s" % os.path.join(batch_root, result["log_path"]))
                _persist_progress(batch_root, manifest, results, "RUNNING")
            active = still_active
    except KeyboardInterrupt:
        for worker in active:
            worker["process"].terminate()
        for worker in active:
            worker["process"].wait()
            worker["log_handle"].close()
        _persist_progress(
            batch_root,
            manifest,
            results,
            "INTERRUPTED",
            time.monotonic() - batch_started,
        )
        raise

    batch_elapsed = time.monotonic() - batch_started
    batch_status = (
        "FAILED"
        if any(result["status"] != "SUCCESS" for result in results)
        else "SUCCESS"
    )
    _persist_progress(batch_root, manifest, results, batch_status, batch_elapsed)
    return batch_root, results


def run_parallel_main(
    target_root: str,
    algorithm: str,
    data_env: str = "MA_DATA_INTERACTION_DIR",
    seed_env: Optional[str] = None,
    explicit_c_paths: bool = False,
    checkpoint: bool = False,
) -> None:
    """Run a target-specific batch using the common command-line contract."""
    target_root = os.path.abspath(target_root)
    spec = {
        "target_root": target_root,
        "algorithm": algorithm,
        "data_env": data_env,
        "seed_env": seed_env,
        "explicit_c_paths": explicit_c_paths,
        "checkpoint": checkpoint,
    }
    args = _build_parser(spec).parse_args()
    configs = _load_configs(target_root)
    instances = _select_instances(args, configs)
    cores = _select_cores(args)
    batch_root, results = _run_batch(args, spec, configs, instances, cores)
    failed = [result for result in results if result["status"] != "SUCCESS"]
    print(
        "Completed %d/%d jobs. Failed: %d"
        % (len(results), len(instances) * args.repetitions, len(failed))
    )
    print("Summary: %s" % os.path.join(batch_root, "summary.json"))
    if failed:
        raise SystemExit(1)


__all__ = [
    "CSV_FIELDS",
    "_build_jobs",
    "_build_summary",
    "_job_seed",
    "_parse_instances",
    "_parse_worker_log",
    "_select_cores",
    "_write_results_csv",
    "run_parallel_main",
]
