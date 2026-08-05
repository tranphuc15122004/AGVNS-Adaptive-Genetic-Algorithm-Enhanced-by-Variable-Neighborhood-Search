import sys
import time
import copy
import json
import os
import shutil
from typing import Dict, List, Optional
from algorithm.In_and_Out import *
from algorithm.engine import *
from algorithm.Test_algorithm.MOEAD_TS import MOEAD_TS
from algorithm.Test_algorithm.moead_objectives import (
    EvaluationContext, evaluate_solution, validate_solution,
)
import algorithm.algorithm_config as Config
from src.conf.configs import Configs
import time
from algorithm.Test_algorithm.new_engine import (
    Delaydispatch,
    write_destination_json_to_file_with_delay_timme,
    write_route_json_to_file_with_delay_time,
)
from algorithm.Object import Chromosome, Node


input_directory = Configs.algorithm_data_interaction_folder_path


def _read_json_file(path: str) -> Optional[dict]:
    """Read a JSON file defensively; return None on any failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        return None


def _write_json_file(path: str, payload: dict) -> None:
    """Write a JSON file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _copy_epoch_json_files(src_dir: str, dst_dir: str) -> None:
    """Copy every ``*.json`` snapshot of a data_interaction directory."""
    os.makedirs(dst_dir, exist_ok=True)
    if not os.path.isdir(src_dir):
        return
    for name in os.listdir(src_dir):
        if not name.endswith(".json"):
            continue
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(dst_dir, name))
            except OSError:
                continue


def _capture_tc_jump_snapshot(after_tc: float, before_tc: Optional[float]) -> None:
    """Snapshot epoch JSONs whenever the reported TC after optimization jumps.

    Diagnostics only: never alters the search or the output files.  Every
    epoch's data_interaction JSONs are copied into
    ``MOEAD_DEBUG_SNAPSHOT_DIR/last`` (rolling).  When ``after_tc`` exceeds the
    previous epoch's value by more than ``MOEAD_DEBUG_TC_JUMP_THRESHOLD``, the
    previous snapshot and the current epoch are copied into
    ``jump_<no>_<deltaT>/previous`` and ``.../current`` together with a
    ``jump_info.json`` so the cause of the fitness spike can be debugged.
    """
    try:
        if not Config.MOEAD_DEBUG_CAPTURE_TC_JUMP:
            return
        threshold = Config.MOEAD_DEBUG_TC_JUMP_THRESHOLD
        if threshold <= 0 or after_tc is None:
            return

        snapshot_root = Config.MOEAD_DEBUG_SNAPSHOT_DIR
        os.makedirs(snapshot_root, exist_ok=True)

        state = _read_json_file(os.path.join(snapshot_root, "state.json")) or {}
        previous_after_tc = state.get("previous_after_tc")
        previous_epoch = state.get("previous_epoch")

        # Epoch metadata comes from solution.json, which update_solution_json
        # has just written for the current dynamic interval.
        solution = _read_json_file(os.path.join(input_directory, "solution.json")) or {}
        try:
            current_epoch = int(solution.get("no.", solution.get("no", 0)))
        except (TypeError, ValueError):
            current_epoch = None
        current_delta_t = str(solution.get("deltaT", "????-????"))

        last_dir = os.path.join(snapshot_root, "last")

        # Cross-run guard: a fresh simulator run restarts at epoch 0, so the
        # first epoch of a new run must never be compared with a previous run.
        if (previous_after_tc is not None and current_epoch is not None and
                (previous_epoch is None or current_epoch > previous_epoch)):
            delta = float(after_tc) - float(previous_after_tc)
            if delta > float(threshold):
                jump_dir = os.path.join(
                    snapshot_root,
                    "jump_{:03d}_{}".format(
                        current_epoch, str(current_delta_t).replace("-", "_")
                    ),
                )
                _copy_epoch_json_files(last_dir, os.path.join(jump_dir, "previous"))
                _copy_epoch_json_files(input_directory, os.path.join(jump_dir, "current"))
                _write_json_file(os.path.join(jump_dir, "jump_info.json"), {
                    "epoch": current_epoch,
                    "deltaT": current_delta_t,
                    "previous_after_tc": float(previous_after_tc),
                    "current_after_tc": float(after_tc),
                    "current_before_tc": float(before_tc) if before_tc is not None else None,
                    "delta": float(delta),
                    "threshold": float(threshold),
                    "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                print("[MOEAD-TS] TC jump detected: {:.2f} -> {:.2f} (+{:.2f}) at epoch {} ({})".format(
                    float(previous_after_tc), float(after_tc), delta,
                    current_epoch, current_delta_t,
                ))
                print("[MOEAD-TS] snapshots saved to", jump_dir)

        # Rolling snapshot of the current epoch (kept even without a jump so
        # the previous epoch is always available for comparison).
        _copy_epoch_json_files(input_directory, last_dir)
        _write_json_file(os.path.join(snapshot_root, "state.json"), {
            "previous_after_tc": float(after_tc),
            "previous_epoch": current_epoch,
        })
    except Exception as exc:  # the debug hook must never break the pipeline
        print("[MOEAD-TS] tc-jump snapshot skipped: {}".format(exc))


def main():
    Config.set_random_seed()
    Config.set_begin_time()
    id_to_factory , route_map ,  id_to_vehicle , id_to_unlocated_items ,  id_to_ongoing_items , id_to_allorder = Input()
    deal_old_solution_file(id_to_vehicle)

    vehicleid_to_plan: Dict[str , List[Node]]= {}
    vehicleid_to_destination : Dict[str , Node] = {}

    new_order_itemIDs : List[str] = []
    new_order_itemIDs = restore_scene_with_single_node(vehicleid_to_plan , id_to_ongoing_items, id_to_unlocated_items  , id_to_vehicle , id_to_factory ,id_to_allorder)

    new_order_itemIDs = [item for item in new_order_itemIDs if item]
    
    
    # MOEA/D--TS starts from the restored dynamic scene and optimizes only
    # genuinely new, movable orders in the current dynamic interval.
    restored_vehicleid_to_plan = copy.deepcopy(vehicleid_to_plan)

    objective_context = EvaluationContext(
        route_map, id_to_vehicle, id_to_factory, id_to_allorder
    )
    initial_cost = evaluate_solution(
        restored_vehicleid_to_plan, objective_context, validate=False
    ).tc
    best_chromosome : Chromosome = MOEAD_TS(
        restored_vehicleid_to_plan,
        route_map,
        id_to_vehicle,
        id_to_factory,
        id_to_unlocated_items,
        new_order_itemIDs,
    )
    if best_chromosome is None:
        if new_order_itemIDs:
            raise RuntimeError(
                "MOEA/D-TS returned no candidate although new order items exist"
            )
        print('[MOEAD-TS] Khong co don hang moi - giu nguyen tuyen duong hien tai')
        best_chromosome : Chromosome = Chromosome(vehicleid_to_plan , route_map , id_to_vehicle)
        best_chromosome._moead_tc = initial_cost
        best_chromosome._moead_initial_population_mean_tc = initial_cost
        best_chromosome._moead_initial_population_size = Config.MOEAD_POPULATION_SIZE
    
    initial_population_mean_tc = getattr(
        best_chromosome, '_moead_initial_population_mean_tc', initial_cost
    )
    initial_population_size = getattr(
        best_chromosome, '_moead_initial_population_size', 1
    )
    print(
        '[MOEAD-TS] TC before optimization '
        '(mean initialized population, n={}): {:.2f}'.format(
            initial_population_size, initial_population_mean_tc
        )
    )

    # The evaluator uses this same canonical route representation.  Merge
    # before dispatch.  The committed-destination boundary is preserved by
    # ``merge_node`` so new same-factory actions cannot alter it.
    merge_node(id_to_vehicle, best_chromosome.solution)
    final_context = getattr(best_chromosome, '_moead_context', objective_context)
    if not validate_solution(best_chromosome.solution, final_context):
        raise RuntimeError(
            "MOEA/D-TS produced an invalid route after merge; output was not written"
        )
    final_cost = getattr(best_chromosome, '_moead_tc', best_chromosome.fitness)
    print(f'[MOEAD-TS] TC after optimization: {final_cost:.2f}')
    print('[MOEAD-TS] Route nodes after optimization:', sum(
        len(route or []) for route in best_chromosome.solution.values()
    ))

    # Publish the simulator-facing files first.  Keep an untouched full copy
    # for the next dynamic interval because ``get_output_solution`` removes
    # the destination prefix from the dispatch route in-place.
    archived_solution = copy.deepcopy(best_chromosome.solution)
    get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
    write_destination_json_to_file(vehicleid_to_destination   , input_directory)    
    write_route_json_to_file(best_chromosome.solution  , input_directory) 


    used_time = time.time() - Config.BEGIN_TIME
    print('Thoi gian thuc hien thuat toan: ' , used_time)
    update_solution_json(
        id_to_ongoing_items, id_to_unlocated_items, id_to_vehicle,
        archived_solution, {}, route_map, used_time,
    )

    # Debug hook: snapshot the epoch's JSONs when the after-optimization TC
    # jumps upward (see _capture_tc_jump_snapshot / MOEAD_DEBUG_* config).
    _capture_tc_jump_snapshot(final_cost, initial_population_mean_tc)

if __name__ == '__main__':
    main()
