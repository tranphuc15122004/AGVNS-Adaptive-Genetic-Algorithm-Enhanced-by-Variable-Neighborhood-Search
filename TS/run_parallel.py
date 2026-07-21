import argparse
import collections
import datetime
import os
import subprocess
import sys
import time

from src.conf.configs import Configs


def _parse_instances(raw_value: str):
    instances = []
    for part in raw_value.split(","):
        part = part.strip()
        if part:
            instances.append(int(part))
    return instances


def _parse_cores(raw_value: str):
    cores = []
    for part in raw_value.split(","):
        part = part.strip()
        if part:
            cores.append(int(part))
    return cores


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run multiple MA instances in parallel with isolated data_interaction directories."
    )
    parser.add_argument(
        "instance_ids",
        nargs="*",
        help="Instance ids to run in parallel, for example: 1 2 5 8",
    )
    parser.add_argument(
        "--instances",
        help="Comma-separated instance ids. Defaults to Configs.selected_instances, or all if that list is empty.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmark instances.",
    )
    parser.add_argument(
        "--cores",
        help="Comma-separated CPU core ids. Defaults to 0..cpu_count-1.",
    )
    parser.add_argument(
        "--run-root",
        default=os.path.join("algorithm", "data_interaction_runs"),
        help="Directory where per-instance workspaces and logs will be created.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to launch each worker.",
    )
    return parser.parse_args()


def _select_instances(args):
    if args.instance_ids:
        return [int(instance_id) for instance_id in args.instance_ids]
    if args.all:
        return list(Configs.all_test_instances)
    if args.instances:
        return _parse_instances(args.instances)
    if Configs.selected_instances:
        return list(Configs.selected_instances)
    return list(Configs.all_test_instances)


def _select_cores(args):
    if args.cores:
        cores = _parse_cores(args.cores)
    else:
        cpu_count = os.cpu_count() or 1
        cores = list(range(cpu_count))

    if not cores:
        raise ValueError("No CPU cores were selected.")
    return cores


def _build_worker_env(data_dir: str):
    env = os.environ.copy()
    env["MA_DATA_INTERACTION_DIR"] = os.path.abspath(data_dir)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    return env


def _launch_instance(ma_root: str, python_exec: str, run_dir: str, instance: int, core: int):
    os.makedirs(run_dir, exist_ok=True)
    log_path = os.path.join(run_dir, "worker.log")
    log_handle = open(log_path, "w", encoding="utf-8")
    cmd = [
        python_exec,
        "main.py",
        "--instances",
        str(instance),
        "--data-dir",
        run_dir,
        "--cpu",
        str(core),
    ]
    process = subprocess.Popen(
        cmd,
        cwd=ma_root,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=_build_worker_env(run_dir),
        text=True,
    )
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(process.pid, {core})
    return {
        "instance": instance,
        "core": core,
        "process": process,
        "log_handle": log_handle,
        "log_path": log_path,
        "run_dir": run_dir,
        "started_at": time.time(),
    }


def main():
    args = _parse_args()
    ma_root = os.path.dirname(os.path.abspath(__file__))
    run_root = os.path.abspath(os.path.join(ma_root, args.run_root))
    run_id = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    batch_root = os.path.join(run_root, run_id)
    os.makedirs(batch_root, exist_ok=True)

    instances = _select_instances(args)
    cores = collections.deque(_select_cores(args))
    pending = collections.deque(instances)
    active = []
    finished = []

    print(f"Batch root: {batch_root}")
    print(f"Instances: {instances}")
    print(f"Cores: {list(cores)}")

    while pending or active:
        while pending and cores:
            instance = pending.popleft()
            core = cores.popleft()
            run_dir = os.path.join(batch_root, f"instance_{instance}")
            worker = _launch_instance(ma_root, args.python, run_dir, instance, core)
            active.append(worker)
            print(
                f"Started instance_{instance} on core {core} "
                f"with workspace {run_dir}"
            )

        time.sleep(1)
        still_active = []
        for worker in active:
            return_code = worker["process"].poll()
            if return_code is None:
                still_active.append(worker)
                continue

            worker["log_handle"].close()
            worker["return_code"] = return_code
            worker["elapsed_seconds"] = time.time() - worker["started_at"]
            finished.append(worker)
            cores.append(worker["core"])
            print(
                f"Finished instance_{worker['instance']} on core {worker['core']} "
                f"with code {return_code} in {worker['elapsed_seconds']:.1f}s"
            )
            print(f"Log: {worker['log_path']}")

        active = still_active

    failed = [worker for worker in finished if worker["return_code"] != 0]
    print(f"Completed {len(finished)} instance(s). Failed: {len(failed)}")
    if failed:
        for worker in failed:
            print(
                f"instance_{worker['instance']} failed on core {worker['core']} "
                f"with log {worker['log_path']}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
