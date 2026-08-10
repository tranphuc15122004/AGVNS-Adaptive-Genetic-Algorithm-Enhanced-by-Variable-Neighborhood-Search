# -*- coding: utf-8 -*-
"""Replay a captured MOEA/D--TS epoch snapshot with the AGVNS algorithm.

Usage (from the AGVNS/ directory):
    python replay_saved_epoch.py ../MOEAD-TS/algorithm/data_interaction_tc_jump/jump_041_0420_0430

Why this exists
---------------
The TC-jump snapshots live under ``MOEAD-TS/algorithm/data_interaction_tc_jump/``
as ``jump_<no>_<deltaT>/previous`` (epoch N-1) and ``.../current`` (epoch N).
This script feeds the SAME dynamic scene (same vehicle state, same ongoing and
unallocated orders, same inherited plan) into the AGVNS pipeline so you can
compare how AGVNS handles the epoch that made MOEA/D--TS spike.

How it works
------------
AGVNS hardcodes its ``data_interaction`` path in ``Configs`` (no environment
override), so this script:

  1. builds a fresh sandbox under ``AGVNS/algorithm/data_interaction_replay/``
     with ``solution.json`` (from previous/) plus the three simulator inputs
     (from current/);
  2. points every ``Configs.algorithm_*_input/output_path`` at that sandbox
     *before* ``algorithm.main`` is imported (its module-level ``input_directory``
     is read at import time);
  3. runs the real ``algorithm.main.main()`` pipeline.

The original snapshot is never modified; all AGVNS outputs land in the sandbox.
"""

import argparse
import os
import shutil
import sys

EPOCH_INPUT_FILES = (
    "unallocated_order_items.json",
    "ongoing_order_items.json",
    "vehicle_info.json",
)
INHERITED_PLAN_FILE = "solution.json"
STALE_OUTPUT_FILES = ("output_route.json", "output_destination.json")


def build_sandbox(snapshot_dir: str, sandbox_dir: str) -> None:
    """Assemble the replayable data_interaction files into ``sandbox_dir``."""
    prev_dir = os.path.join(snapshot_dir, "previous")
    cur_dir = os.path.join(snapshot_dir, "current")
    for sub in (prev_dir, cur_dir):
        if not os.path.isdir(sub):
            print("ERROR: missing snapshot sub-directory: {}".format(sub))
            sys.exit(2)

    os.makedirs(sandbox_dir, exist_ok=True)

    shutil.copy2(
        os.path.join(prev_dir, INHERITED_PLAN_FILE),
        os.path.join(sandbox_dir, INHERITED_PLAN_FILE),
    )
    for name in EPOCH_INPUT_FILES:
        src = os.path.join(cur_dir, name)
        if not os.path.exists(src):
            print("WARNING: missing input file {}".format(src))
            continue
        shutil.copy2(src, os.path.join(sandbox_dir, name))

    for name in STALE_OUTPUT_FILES:
        path = os.path.join(sandbox_dir, name)
        if os.path.exists(path):
            os.remove(path)

    print("Sandbox ready: {}".format(sandbox_dir))
    print("  solution.json (inherit)      <- previous/{}".format(INHERITED_PLAN_FILE))
    for name in EPOCH_INPUT_FILES:
        print("  {:<28} <- current/{}".format(name, name))


def point_configs_at(sandbox_dir: str) -> None:
    """Redirect every Configs data_interaction path to the sandbox.

    Must run BEFORE ``algorithm.main`` is imported: both ``algorithm.main`` and
    ``algorithm.engine`` bind ``input_directory`` from Configs at import time.
    """
    from src.conf.configs import Configs

    Configs.algorithm_data_interaction_folder_path = os.path.abspath(sandbox_dir)
    Configs.algorithm_vehicle_input_info_path = os.path.join(sandbox_dir, "vehicle_info.json")
    Configs.algorithm_unallocated_order_items_input_path = os.path.join(
        sandbox_dir, "unallocated_order_items.json")
    Configs.algorithm_ongoing_order_items_input_path = os.path.join(
        sandbox_dir, "ongoing_order_items.json")
    Configs.algorithm_output_destination_path = os.path.join(
        sandbox_dir, "output_destination.json")
    Configs.algorithm_output_planned_route_path = os.path.join(
        sandbox_dir, "output_route.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot_dir",
        help="path to a captured epoch, e.g. "
             "../MOEAD-TS/algorithm/data_interaction_tc_jump/jump_041_0420_0430",
    )
    parser.add_argument(
        "--out", default=None,
        help="sandbox directory (default: "
             "algorithm/data_interaction_replay/<snapshot_name>)",
    )
    args = parser.parse_args()

    snapshot_dir = os.path.abspath(args.snapshot_dir)
    if not os.path.isdir(snapshot_dir):
        print("ERROR: snapshot directory not found: {}".format(snapshot_dir))
        sys.exit(2)

    variant_root = os.path.dirname(os.path.abspath(__file__))
    if args.out:
        sandbox_dir = os.path.abspath(args.out)
    else:
        snapshot_name = os.path.basename(snapshot_dir.rstrip(os.sep))
        sandbox_dir = os.path.join(
            variant_root, "algorithm", "data_interaction_replay", snapshot_name,
        )

    build_sandbox(snapshot_dir, sandbox_dir)
    point_configs_at(sandbox_dir)

    # A replay is a diagnostics run: never pollute the real per-epoch plan log.
    os.environ["DPDP_EPOCH_PLAN_LOG"] = "0"

    print("Replaying epoch with AGVNS from {} ...".format(sandbox_dir))
    from algorithm.main import main  # noqa: E402  (import after Configs redirect)
    main()
    print("AGVNS replay finished. Outputs written to {}".format(sandbox_dir))


if __name__ == "__main__":
    main()
