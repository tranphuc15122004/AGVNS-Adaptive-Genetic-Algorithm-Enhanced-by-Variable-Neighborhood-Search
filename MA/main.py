import argparse
import datetime
import os
import sys
import time
import traceback

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np

from runtime_stats import RuntimeStats
from src.conf.configs import Configs
from src.simulator.simulate_api import simulate
from src.utils.log_utils import ini_logger, remove_file_handler_of_logging
from src.utils.logging_engine import logger


def _parse_instances(raw_value: str):
    raw_value = raw_value.strip()
    if not raw_value:
        return []

    instances = []
    for part in raw_value.split(","):
        part = part.strip()
        if part:
            instances.append(int(part))
    return instances


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run the MA simulator for one or more benchmark instances."
    )
    parser.add_argument(
        "--instances",
        help="Comma-separated instance ids. Empty means using Configs.selected_instances or all instances.",
    )
    parser.add_argument(
        "--data-dir",
        help="Override the algorithm data_interaction directory for this process.",
    )
    parser.add_argument(
        "--cpu",
        type=int,
        help="Pin this process to a single CPU core on Linux.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed used by the MA algorithm subprocesses (default: 0).",
    )
    parser.add_argument(
        "--stats-file",
        help="CSV path for per-instance runtime statistics (default: <data-dir>/runtime_stats.csv).",
    )
    return parser.parse_args()


def _configure_runtime(args):
    os.environ["MA_RANDOM_SEED"] = str(args.seed)
    os.environ["DPDP_RANDOM_SEED"] = str(args.seed)
    Configs.RANDOM_SEED = args.seed
    if args.data_dir:
        os.environ["MA_DATA_INTERACTION_DIR"] = os.path.abspath(args.data_dir)
        Configs.configure_algorithm_data_dir(args.data_dir)

    if args.instances is not None:
        Configs.selected_instances = _parse_instances(args.instances)

    if args.cpu is not None and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {args.cpu})


def _get_test_instances():
    selected_instances = Configs.selected_instances
    if selected_instances:
        return selected_instances
    return list(Configs.all_test_instances)


if __name__ == "__main__":
    args = _parse_args()
    _configure_runtime(args)
    stats_file = args.stats_file or os.path.join(
        Configs.algorithm_data_interaction_folder_path,
        "runtime_stats.csv",
    )
    runtime_stats = RuntimeStats(stats_file, algorithm="MA", seed=args.seed)

    score_list = []
    failed_instances = []
    for idx in _get_test_instances():
        instance = f"instance_{idx}"
        log_file_name = (
            f"dpdp_{instance}_{os.getpid()}_{datetime.datetime.now().strftime('%y%m%d%H%M%S%f')}.log"
        )
        ini_logger(log_file_name)

        logger.info(f"Start to run {instance}")
        logger.info(f"data_interaction directory: {Configs.algorithm_data_interaction_folder_path}")
        if args.cpu is not None:
            logger.info(f"CPU affinity target: core {args.cpu}")

        started = time.monotonic()
        started_at_utc = runtime_stats.start_instance(instance)
        try:
            try:
                score = simulate(Configs.factory_info_file, Configs.route_info_file, instance)
            except Exception as exc:
                elapsed = time.monotonic() - started
                error = traceback.format_exc()
                runtime_stats.record(
                    instance,
                    status="FAILED",
                    runtime_seconds=elapsed,
                    started_at_utc=started_at_utc,
                    error=error,
                )
                logger.error("Failed to run simulator")
                logger.error(f"Error: {exc}, {error}")
                score_list.append(sys.maxsize)
                failed_instances.append(instance)
            else:
                elapsed = time.monotonic() - started
                runtime_stats.record(
                    instance,
                    status="SUCCESS",
                    score=score,
                    runtime_seconds=elapsed,
                    started_at_utc=started_at_utc,
                )
                score_list.append(score)
                logger.info(
                    "Score of %s: %s, runtime: %.6fs",
                    instance,
                    score,
                    elapsed,
                )
        finally:
            remove_file_handler_of_logging(log_file_name)

    logger.info("Runtime statistics saved to %s and %s", runtime_stats.csv_path, runtime_stats.json_path)

    avg_score = np.mean(score_list)
    print(score_list)
    print(avg_score)
    print("Happy Ending")
    if failed_instances:
        logger.error(f"Failed instances: {', '.join(failed_instances)}")
        sys.exit(1)
    print("SUCCESS")
