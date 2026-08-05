# -*- coding: utf-8 -*-
"""Replay a saved MOEA/D--TS epoch snapshot offline.

Usage:
    python replay_saved_epoch.py algorithm/data_interaction_tc_jump/jump_041_0420_0430

What it does
------------
Every captured jump epoch lives under ``algorithm/data_interaction_tc_jump/``
as ``jump_<no>_<deltaT>/previous`` (epoch N-1 files) and ``.../current``
(epoch N files).  To reproduce epoch N exactly, the algorithm needs:

    solution.json                  <- from previous/  (plan the restore rebuilds)
    unallocated_order_items.json   <- from current/  (epoch N simulator input)
    ongoing_order_items.json       <- from current/  (epoch N simulator input)
    vehicle_info.json              <- from current/  (epoch N simulator input)

This script assembles those files in a fresh sandbox directory and runs the
real ``algorithm.main`` pipeline against it via the ``MOEAD_DATA_INTERACTION_DIR``
environment override.  Outputs are written into the sandbox so the original
snapshot stays untouched.  With the fixed MOEA/D--TS seed the replay should
reproduce the same "TC after optimization" as the captured ``jump_info.json``.
"""

import argparse
import os
import shutil
import sys

# Input files that belong to the simulated epoch itself (epoch N) and the one
# file that describes the plan inherited from the previous epoch (epoch N-1).
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

    # Fresh outputs: never inherit stale plan/output files from the sandbox.
    for name in STALE_OUTPUT_FILES:
        path = os.path.join(sandbox_dir, name)
        if os.path.exists(path):
            os.remove(path)

    print("Sandbox ready: {}".format(sandbox_dir))
    print("  solution.json (inherit)      <- previous/{}".format(INHERITED_PLAN_FILE))
    for name in EPOCH_INPUT_FILES:
        print("  {:<28} <- current/{}".format(name, name))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot_dir",
        help="path to a captured epoch, e.g. "
             "algorithm/data_interaction_tc_jump/jump_041_0420_0430",
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

    # Must be set before ``algorithm.main`` (and therefore Configs) is imported:
    # Configs reads the data_interaction path at module load time.
    os.environ["MOEAD_DATA_INTERACTION_DIR"] = sandbox_dir

    # A replay is a diagnostics run: never let it touch the real TC-jump
    # snapshot/state machinery under ``data_interaction_tc_jump``.
    os.environ["MOEAD_DEBUG_CAPTURE_TC_JUMP"] = "0"

    print("Replaying epoch from {} ...".format(sandbox_dir))
    from algorithm.main import main  # noqa: E402  (import after env override)
    main()
    print("SUCCESS")


if __name__ == "__main__":
    main()
