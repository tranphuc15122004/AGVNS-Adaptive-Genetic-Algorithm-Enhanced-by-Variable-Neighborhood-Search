"""One-epoch official in-process/subprocess parity harness.

The competition simulator normally invokes ``main_algorithm.py`` as a child
process.  This module drives the same first decision epoch in-process and in a
real child process, then compares the canonical destination/suffix boundary.
It is intentionally small enough for a daily integration smoke while the
full 64-instance campaign remains a separate benchmark job.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional

from algorithm.evorl.dispatch import dispatch_mutable_orders
from src.simulator.simulate_api import initialize_environment
from src.utils.json_tools import convert_input_info_to_json_files, get_output_of_algorithm
from src.conf.configs import Configs

from algorithm.evorl.legacy_adapter import build_epoch_state
from .runtime import ParityResult
from .trace import stable_digest


def _node_snapshot(node: Any):
    if node is None:
        return None
    # Canonical DTO nodes expose ``factory_id``/``*_item_ids`` while the
    # competition simulator nodes expose ``id``/``*_items``.  Do not use
    # ``hasattr(factory_id)`` as the discriminator: legacy nodes can expose
    # only ``id`` and would otherwise be treated as an empty DTO node.
    if hasattr(node, "factory_id") and hasattr(node, "pickup_item_ids"):
        return {
            "factory_id": str(node.factory_id),
            "pickup_item_ids": tuple(str(value) for value in node.pickup_item_ids),
            "delivery_item_ids": tuple(str(value) for value in node.delivery_item_ids),
        }
    pickups = getattr(node, "pickup_item_list", None)
    deliveries = getattr(node, "delivery_item_list", None)
    if pickups is None:
        pickups = getattr(node, "pickup_items", ()) or ()
    if deliveries is None:
        deliveries = getattr(node, "delivery_items", ()) or ()
    return {
        "factory_id": str(getattr(node, "id", "")),
        "pickup_item_ids": tuple(str(getattr(value, "id", value)) for value in pickups),
        "delivery_item_ids": tuple(str(getattr(value, "id", value)) for value in deliveries),
    }


def _boundary_snapshot(plans: Mapping[str, Any], vehicles: Mapping[str, Any],
                       destinations: Optional[Mapping[str, Any]] = None):
    """Normalize legacy output into immutable destination + suffix fields."""

    result = {}
    destinations = destinations or {}
    for vehicle_id in sorted(vehicles):
        vehicle = vehicles[vehicle_id]
        route = list(plans.get(vehicle_id) or ())
        destination = destinations.get(vehicle_id)
        if destination is None:
            destination = getattr(vehicle, "des", None)
        if destination is None and route:
            destination, route = route[0], route[1:]
        carrying = getattr(vehicle, "carrying_items", ()) or ()
        if hasattr(vehicle, "carrying_item_ids"):
            carrying = getattr(vehicle, "carrying_item_ids") or ()
        if hasattr(carrying, "items"):
            carrying = carrying.items
        result[str(vehicle_id)] = {
            "destination": _node_snapshot(destination),
            "route": tuple(_node_snapshot(node) for node in route),
            "carrying": tuple(str(getattr(item, "id", item)) for item in carrying),
        }
    return result


def run_one_epoch_parity(*, checkpoint: str, instance_id: int = 1,
                         simulator_seed: int = 0,
                         work_dir: str | None = None,
                         timeout_seconds: float = 60.0,
                         execution_mode: str = "EvoRL-paper-repro") -> ParityResult:
    """Compare one real official epoch in-process with ``main_algorithm.py``."""

    temporary = tempfile.TemporaryDirectory(prefix="evorl_parity_") if work_dir is None else None
    root = Path(work_dir or temporary.name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    old_data_dir = Configs.algorithm_data_interaction_folder_path
    old_execution_mode = os.environ.get("EVORL_EXECUTION_MODE")
    try:
        Configs.configure_algorithm_data_dir(str(root))
        os.environ["EVORL_EXECUTION_MODE"] = str(execution_mode)
        simulator = initialize_environment(
            Configs.factory_info_file, Configs.route_info_file,
            f"instance_{int(instance_id)}", simulator_seed=int(simulator_seed),
        )
        if simulator is None:
            raise RuntimeError("official simulator initialization failed")
        simulator.cur_time = simulator.pre_time + simulator.time_interval
        input_info = simulator.update_input()
        all_items = {}
        all_items.update(input_info.id_to_unallocated_order_item)
        all_items.update(input_info.id_to_ongoing_order_item)
        generated_ids = list(input_info.id_to_unallocated_order_item)

        # In-process canonical dispatcher.
        in_process_plans = {
            vehicle_id: list(getattr(vehicle, "planned_route", ()) or ())
            for vehicle_id, vehicle in simulator.id_to_vehicle.items()
        }
        dispatch_mutable_orders(
            in_process_plans, simulator.id_to_vehicle, all_items,
            simulator.id_to_factory, simulator.route_map,
            generated_item_ids=generated_ids, policy_checkpoint=checkpoint,
            epoch=0, current_time=int(simulator.cur_time), time_budget_seconds=timeout_seconds,
        )
        left = _boundary_snapshot(in_process_plans, simulator.id_to_vehicle)

        # Real subprocess boundary.  The simulator's own JSON writer is used,
        # rather than hand-built payloads, so serialization is part of the test.
        convert_input_info_to_json_files(input_info)
        environment = dict(os.environ)
        environment.update({
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "MA_DATA_INTERACTION_DIR": str(root),
            "EVORL_CHECKPOINT": str(Path(checkpoint).resolve()),
            "EVORL_REQUIRE_CHECKPOINT": "1",
            "EVORL_LEGACY_FALLBACK": "0",
            "EVORL_PROTOCOL": "benchmark_heldout",
            "EVORL_EXECUTION_MODE": str(execution_mode),
            "EVORL_EPISODE_ID": f"parity-instance-{instance_id}-seed-{simulator_seed}",
            "EVORL_HIDDEN_SIDECAR": str(root / "hidden.json"),
        })
        completed = subprocess.run(
            [sys.executable, "main_algorithm.py"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=environment, capture_output=True, text=True,
            timeout=float(timeout_seconds), check=False,
        )
        if completed.returncode != 0 or "SUCCESS" not in completed.stdout:
            return ParityResult(False, (0,), {
                "subprocess_returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            })
        destinations, routes = get_output_of_algorithm(simulator.id_to_order_item)
        right = _boundary_snapshot(routes, simulator.id_to_vehicle, destinations)
        equal = left == right
        details = {
            "in_process_hash": stable_digest(left),
            "subprocess_hash": stable_digest(right),
            "in_process": left,
            "subprocess": right,
        }
        return ParityResult(equal, () if equal else (0,), details)
    finally:
        Configs.configure_algorithm_data_dir(old_data_dir)
        if old_execution_mode is None:
            os.environ.pop("EVORL_EXECUTION_MODE", None)
        else:
            os.environ["EVORL_EXECUTION_MODE"] = old_execution_mode
        if temporary is not None:
            temporary.cleanup()
