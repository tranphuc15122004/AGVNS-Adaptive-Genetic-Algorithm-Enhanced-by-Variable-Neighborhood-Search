"""Parallel MA experiment adapter."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parallel_runner import (  # noqa: E402
    _available_cores,
    _build_jobs,
    _build_summary,
    _job_seed,
    _parse_instances,
    _parse_worker_log,
    _write_results_csv,
    run_parallel_main,
)


def _select_cores(args):
    available = _available_cores()
    cores = [int(value.strip()) for value in args.cores.split(",")] if args.cores else available
    if not cores:
        raise ValueError("No CPU cores were selected.")
    if args.workers is not None and args.workers <= 0:
        raise ValueError("--workers must be positive.")
    worker_count = args.workers or len(cores)
    if worker_count > len(cores):
        raise ValueError("--workers exceeds the number of selected cores.")
    return cores[:worker_count]


if __name__ == "__main__":
    run_parallel_main(
        os.path.dirname(os.path.abspath(__file__)),
        "MA",
        seed_env="MA_RANDOM_SEED",
    )
