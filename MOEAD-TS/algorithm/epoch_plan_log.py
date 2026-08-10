# -*- coding: utf-8 -*-
"""Append each epoch's final solution (route_after + TC) to a per-run JSONL log.

Diagnostics only - never alters the search.  Purpose: compare the final plan of
MOEAD-TS vs AGVNS epoch by epoch (e.g. find the first epoch where the two
algorithms diverge, then diff their routes).

The log is one file per simulator run:
    <variant>/algorithm/data_interaction_epoch_log/epoch_plans_<run_id>.jsonl
Each line is one JSON record: ``{"epoch", "deltaT", "tc", "route_after", "t"}``.
A new run starts whenever the epoch number goes backwards (the simulator
restarts at epoch 0), so separate runs never mix in one file.

Disable with the environment variable ``DPDP_EPOCH_PLAN_LOG=0`` (used by the
replay tools so they never pollute the real run logs).
"""

import json
import os
import time

_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "algorithm", "data_interaction_epoch_log",
)
_STATE_FILE = os.path.join(_LOG_DIR, "_run_state.json")


def append_epoch_solution(epoch, delta_t, tc, route_after) -> None:
    """Append one epoch's final plan record to the active run's log file."""
    try:
        if os.environ.get("DPDP_EPOCH_PLAN_LOG", "1") == "0":
            return
        os.makedirs(_LOG_DIR, exist_ok=True)

        state = {}
        try:
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError, TypeError):
            state = {}

        run_id = state.get("run_id")
        last_epoch = state.get("last_epoch")
        if (run_id is None or
                (last_epoch is not None and epoch is not None and epoch <= last_epoch)):
            run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + os.urandom(4).hex()
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"run_id": run_id, "last_epoch": epoch}, f)

        record = {
            "epoch": epoch,
            "deltaT": delta_t,
            "tc": tc,
            "route_after": route_after,
            "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        log_path = os.path.join(_LOG_DIR, "epoch_plans_{}.jsonl".format(run_id))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Diagnostics only: never break the pipeline.
        pass


def append_current_solution(tc, solution_json_path) -> None:
    """Read solution.json and append the current epoch's final plan."""
    try:
        meta = {}
        try:
            with open(solution_json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError, TypeError):
            meta = {}
        try:
            epoch = int(meta.get("no.", meta.get("no", 0)))
        except (TypeError, ValueError):
            epoch = None
        append_epoch_solution(epoch, meta.get("deltaT"), tc, meta.get("route_after"))
    except Exception:
        pass
