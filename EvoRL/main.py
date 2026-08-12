import argparse
import datetime
import os
import sys
import traceback

import numpy as np

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
        description="Run the EvoRL simulator for one or more benchmark instances."
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
        help="Seed used by the algorithm subprocesses (default: 0).",
    )
    parser.add_argument(
        "--checkpoint",
        help=(
            "RPPO checkpoint used for inference.  The simulator refuses to "
            "run without it unless --allow-heuristic is explicitly supplied."
        ),
    )
    parser.add_argument(
        "--allow-heuristic",
        action="store_true",
        help="Explicitly allow the legacy heuristic path (debug/compatibility only).",
    )
    return parser.parse_args()


def _configure_runtime(args):
    # The simulator calls main_algorithm.py in a fresh subprocess on every
    # dispatch tick.  Environment propagation keeps that child deterministic.
    os.environ["EVORL_RANDOM_SEED"] = str(args.seed)

    # A baseline run must be an actual EvoRL policy run.  Requiring the
    # checkpoint here prevents a missing environment variable from silently
    # turning an evaluation into the legacy heuristic implementation.
    if args.checkpoint:
        checkpoint = os.path.abspath(args.checkpoint)
        if not os.path.isfile(checkpoint):
            raise FileNotFoundError("EvoRL checkpoint does not exist: %s" % checkpoint)
        os.environ["EVORL_CHECKPOINT"] = checkpoint
        os.environ["EVORL_REQUIRE_CHECKPOINT"] = "1"
        os.environ["EVORL_LEGACY_FALLBACK"] = "0"
    elif args.allow_heuristic:
        os.environ.pop("EVORL_CHECKPOINT", None)
        os.environ["EVORL_REQUIRE_CHECKPOINT"] = "0"
        os.environ["EVORL_LEGACY_FALLBACK"] = "1"
    else:
        raise ValueError(
            "EvoRL inference requires --checkpoint; use --allow-heuristic "
            "only for an explicit compatibility/debug run."
        )

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
        logger.info(f"Algorithm random seed: {args.seed}")

        try:
            score, elapsed = simulate(Configs.factory_info_file, Configs.route_info_file, instance)
            score_list.append(score)
            logger.info(f"Score of {instance}: {score}, runtime: {elapsed:.6f}s")
        except Exception as exc:
            logger.error("Failed to run simulator")
            logger.error(f"Error: {exc}, {traceback.format_exc()}")
            score_list.append(sys.maxsize)
            failed_instances.append(instance)

        remove_file_handler_of_logging(log_file_name)

    avg_score = np.mean(score_list)
    print(score_list)
    print(avg_score)
    print("Happy Ending")
    if failed_instances:
        logger.error(f"Failed instances: {', '.join(failed_instances)}")
        sys.exit(1)
