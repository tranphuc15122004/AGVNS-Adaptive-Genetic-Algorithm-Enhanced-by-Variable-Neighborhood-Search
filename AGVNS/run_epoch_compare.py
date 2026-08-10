# -*- coding: utf-8 -*-
"""Run the AGVNS pipeline on a given dynamic scene and emit ONLY comparison data.

Launched as an isolated subprocess by MOEA/D--TS (see
``MOEAD-TS/algorithm/main.py``, function ``_launch_agvns_compare``) on a sandbox
copy of the exact scene that MOEA/D--TS is about to optimise, so both algorithms
are compared on identical inputs.

It replicates the exact AGVNS ``algorithm/main.py`` dispatch pipeline
(``new_dispatch_new_orders`` -> ``get_UnongoingSuperNode`` -> ``GAVND_7`` ->
``gold_algorithm_LS``), then writes ``--out-file`` with ``{tc, route_after}``
where ``route_after`` uses the SAME canonical JSON format as MOEA/D--TS
(``[[vehicle_id, [[factory_id, [pickups], [deliveries]]...]]]``) so the two
plans are directly diffable.

Nothing simulator-facing is ever written outside the sandbox:
  * ``--data-dir`` only receives the inputs copied by MOEA/D--TS;
  * the per-epoch plan log is disabled (``DPDP_EPOCH_PLAN_LOG=0``);
  * the only real output is ``--out-file``.

Usage (from the AGVNS/ directory):
    python run_epoch_compare.py --data-dir <sandbox> --out-file <result.json>
"""

import argparse
import copy
import json
import os
import sys
import time


def _normalize_for_agvns(vehicleid_to_plan) -> None:
    """Split multi-item nodes into single-item nodes (AGVNS-compatible).

    AGVNS natively plans single-item factory nodes: its legacy ``solution.json``
    format stores one item per ``p1_x``/``d1_x`` token, and ``dispatch_nodePair``
    matches pickup/delivery pairs through ``delivery_item_list[-1]`` which only
    works for single-item nodes.  A restored MOEA/D--TS canonical plan may carry
    several items per node, so such a node makes ``dispatch_nodePair`` insert a
    ``None`` into the candidate route and crash.

    Splitting preserves the exact route semantics: same factory, same
    unload-then-load order, same LIFO stack order (delivery list order is the
    unload order, pickup list order is the load order).
    """
    from algorithm.Object import Node

    for vehicle_id, route in vehicleid_to_plan.items():
        if not route:
            continue
        new_route = []
        for node in route:
            deliveries = node.delivery_item_list or []
            pickups = node.pickup_item_list or []
            # Deliveries unload before pickups load at the same factory.
            for item in deliveries:
                new_route.append(Node(
                    node.id, [item], [], None, None, node.lng, node.lat))
            for item in pickups:
                new_route.append(Node(
                    node.id, [], [item], None, None, node.lng, node.lat))
        vehicleid_to_plan[vehicle_id] = new_route


# ``import *`` is only legal at module level, and ``algorithm.engine`` binds
# ``input_directory`` from Configs at import time — so parse the CLI args and
# redirect Configs BEFORE importing any ``algorithm.*`` module.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True,
                        help="sandbox dir with the raw simulator inputs + inherited solution.json")
    parser.add_argument("--out-file", required=True,
                        help="where to write the {tc, route_after} comparison result")
    args = parser.parse_args()

    # Diagnostics only: never pollute the per-epoch plan log.
    os.environ["DPDP_EPOCH_PLAN_LOG"] = "0"

    from src.conf.configs import Configs

    Configs.algorithm_data_interaction_folder_path = os.path.abspath(args.data_dir)
    Configs.algorithm_vehicle_input_info_path = os.path.join(
        args.data_dir, "vehicle_info.json")
    Configs.algorithm_unallocated_order_items_input_path = os.path.join(
        args.data_dir, "unallocated_order_items.json")
    Configs.algorithm_ongoing_order_items_input_path = os.path.join(
        args.data_dir, "ongoing_order_items.json")
    Configs.algorithm_output_destination_path = os.path.join(
        args.data_dir, "output_destination.json")
    Configs.algorithm_output_planned_route_path = os.path.join(
        args.data_dir, "output_route.json")

    import algorithm.algorithm_config as Config
    from algorithm.In_and_Out import *
    from algorithm.Object import Chromosome
    from algorithm.engine import *
    from algorithm.Test_algorithm.new_engine import *
    from algorithm.Test_algorithm.new_LS import *
    from algorithm.Test_algorithm.GAVND7 import GAVND_7

    Config.set_begin_time()
    id_to_factory, route_map, id_to_vehicle, id_to_unlocated_items, \
        id_to_ongoing_items, id_to_allorder = Input()
    deal_old_solution_file(id_to_vehicle)

    vehicleid_to_plan = {}
    vehicleid_to_destination = {}
    new_order_item_ids = restore_scene_with_single_node(
        vehicleid_to_plan, id_to_ongoing_items, id_to_unlocated_items,
        id_to_vehicle, id_to_factory, id_to_allorder,
    )
    new_order_item_ids = [item for item in new_order_item_ids if item]

    # The inherited plan is a MOEA/D--TS canonical route which may carry
    # several items per node; AGVNS dispatch expects single-item nodes.
    _normalize_for_agvns(vehicleid_to_plan)

    # Exact AGVNS dispatch pipeline (mirrors AGVNS/algorithm/main.py).
    new_dispatch_new_orders(
        vehicleid_to_plan, id_to_factory, route_map, id_to_vehicle,
        id_to_unlocated_items, new_order_item_ids,
    )
    unongoing_super_nodes, base_vehicleid_to_plan = get_UnongoingSuperNode(
        vehicleid_to_plan, id_to_vehicle)

    copy_vehicleid_to_plan = copy.deepcopy(vehicleid_to_plan)
    best_chromosome = GAVND_7(
        copy_vehicleid_to_plan, route_map, id_to_vehicle,
        unongoing_super_nodes, base_vehicleid_to_plan,
    )

    copy_vehicleid_to_plan = copy.deepcopy(vehicleid_to_plan)
    best_chromosome = Chromosome(copy_vehicleid_to_plan, route_map, id_to_vehicle)
    gold_algorithm_LS(best_chromosome, False)

    merge_node(id_to_vehicle, best_chromosome.solution)
    route_after = json.dumps(
        [
            [
                vehicle_id,
                [
                    [
                        node.id,
                        [item.id for item in (node.pickup_item_list or [])],
                        [item.id for item in (node.delivery_item_list or [])],
                    ]
                    for node in (nodes or [])
                ],
            ]
            for vehicle_id, nodes in sorted(best_chromosome.solution.items())
        ],
        ensure_ascii=False, separators=(",", ":"),
    )
    tc = float(best_chromosome.fitness)

    result = {
        "tc": tc,
        "route_after": route_after,
        "num_vehicles": len(id_to_vehicle),
        "wall_time": time.time() - Config.BEGIN_TIME,
    }
    os.makedirs(os.path.dirname(args.out_file), exist_ok=True)
    with open(args.out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("[AGVNS-compare] TC={:.2f}".format(tc))
