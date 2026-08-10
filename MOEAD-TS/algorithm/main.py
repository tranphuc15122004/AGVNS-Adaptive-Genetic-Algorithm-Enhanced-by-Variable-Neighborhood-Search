import sys
import time
import copy
import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional
from algorithm.In_and_Out import *
from algorithm.engine import *
from algorithm.epoch_plan_log import append_current_solution
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


_COMPARE_STATE_FILE = os.path.join(Config.MOEAD_DUAL_RUN_DIR, "_run_state.json")


def _compare_run_id(current_epoch: Optional[int]) -> str:
    """Return the dual-run id, restarting whenever the epoch goes backwards."""
    try:
        os.makedirs(Config.MOEAD_DUAL_RUN_DIR, exist_ok=True)
        state = _read_json_file(_COMPARE_STATE_FILE) or {}
        run_id = state.get("run_id")
        last_epoch = state.get("last_epoch")
        if (run_id is None or
                (last_epoch is not None and current_epoch is not None and
                 current_epoch <= last_epoch)):
            run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + os.urandom(4).hex()
        _write_json_file(_COMPARE_STATE_FILE, {
            "run_id": run_id, "last_epoch": current_epoch,
        })
        return run_id
    except Exception:
        return "run_" + time.strftime("%Y%m%d_%H%M%S")


def _launch_agvns_compare():
    """Copy the restored scene and start the AGVNS worker in parallel.

    Diagnostics only: MOEA/D--TS keeps publishing the simulator-facing files.
    The AGVNS worker (AGVNS/run_epoch_compare.py) runs on a sandbox copy of the
    exact scene and never writes outside it.  Returns ``(proc, out_file,
    epoch_dir, meta)`` or ``(None, None, None, None)`` when disabled/failed.
    """
    if not Config.MOEAD_DUAL_RUN_AGVNS:
        return None, None, None, None
    try:
        prev_solution = _read_json_file(
            os.path.join(input_directory, "solution.json")) or {}
        try:
            prev_no = int(prev_solution.get("no.", prev_solution.get("no", 0)))
        except (TypeError, ValueError):
            prev_no = 0
        current_epoch = prev_no + 1
        delta_t = "{:04d}-{:04d}".format(current_epoch * 10, current_epoch * 10 + 10)

        run_id = _compare_run_id(current_epoch)
        epoch_dir = os.path.join(
            Config.MOEAD_DUAL_RUN_DIR, run_id,
            "epoch_{:03d}_{}".format(current_epoch, delta_t.replace("-", "_")),
        )
        input_dir = os.path.join(epoch_dir, "input")
        os.makedirs(input_dir, exist_ok=True)

        for name in (
                "vehicle_info.json", "unallocated_order_items.json",
                "ongoing_order_items.json", "solution.json"):
            src = os.path.join(input_directory, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(input_dir, name))

        out_file = os.path.join(epoch_dir, "agvns_result.json")
        agvns_script = os.path.join(Config.MOEAD_AGVNS_DIR, "run_epoch_compare.py")
        stdout_log = open(os.path.join(epoch_dir, "agvns_stdout.log"), "w")
        proc = subprocess.Popen(
            [sys.executable, agvns_script,
             "--data-dir", input_dir, "--out-file", out_file],
            cwd=Config.MOEAD_AGVNS_DIR,
            stdout=stdout_log, stderr=subprocess.STDOUT, text=True,
        )
        return proc, out_file, epoch_dir, (current_epoch, delta_t, run_id, stdout_log)
    except Exception as exc:
        print("[MOEAD-TS] AGVNS compare launch skipped: {}".format(exc))
        return None, None, None, None


def _collect_agvns_compare(proc, out_file, epoch_dir, meta,
                           moead_tc, moead_route_after) -> None:
    """Wait for the AGVNS worker and archive the side-by-side comparison."""
    if proc is None:
        return
    _, _, run_id, stdout_log = meta
    try:
        try:
            proc.wait(timeout=Config.MOEAD_DUAL_RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            print("[MOEAD-TS] AGVNS compare timed out for {}".format(epoch_dir))
            return
        finally:
            try:
                stdout_log.close()
            except Exception:
                pass
        if proc.returncode != 0:
            print("[MOEAD-TS] AGVNS compare failed (rc={}) for {}".format(
                proc.returncode, epoch_dir))
            return

        agvns = _read_json_file(out_file) or {}
        agvns_tc = agvns.get("tc")

        # Prefer the authoritative epoch metadata written by update_solution_json.
        current_solution = _read_json_file(
            os.path.join(input_directory, "solution.json")) or {}
        try:
            epoch = int(current_solution.get("no.", current_solution.get("no", 0)))
        except (TypeError, ValueError):
            epoch = meta[0]
        delta_t = current_solution.get("deltaT", meta[1])

        if agvns_tc is None:
            print("[MOEAD-TS] AGVNS compare produced no TC at epoch {} ({})".format(
                epoch, delta_t))
            return

        agvns_tc = float(agvns_tc)
        moead_tc = float(moead_tc) if moead_tc is not None else None
        delta = (moead_tc - agvns_tc) if moead_tc is not None else None
        print("[DUAL-RUN] epoch {} ({}): MOEAD TC={} | AGVNS TC={:.2f} | "
              "diff(MOEAD-AGVNS)={}".format(
                  epoch, delta_t,
                  "{:.2f}".format(moead_tc) if moead_tc is not None else "n/a",
                  agvns_tc,
                  "{:.2f}".format(delta) if delta is not None else "n/a"))

        record = {
            "epoch": epoch,
            "deltaT": delta_t,
            "moead_tc": moead_tc,
            "agvns_tc": agvns_tc,
            "delta": delta,
            "moead_route_after": moead_route_after,
            "agvns_route_after": agvns.get("route_after"),
            "agvns_wall_time": agvns.get("wall_time"),
        }
        log_path = os.path.join(Config.MOEAD_DUAL_RUN_DIR, run_id, "comparison.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print("[MOEAD-TS] AGVNS compare collect skipped: {}".format(exc))


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

    # Dual-run diagnostics: snapshot the restored scene and start AGVNS on the
    # identical input in parallel (only MOEA/D--TS results go to the simulator).
    _agvns_proc, _agvns_out_file, _agvns_epoch_dir, _agvns_meta = _launch_agvns_compare()

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

    # Archive the final plan (route_after) of this epoch for cross-variant
    # comparison (diagnostics only; see algorithm/epoch_plan_log.py).
    append_current_solution(final_cost, os.path.join(input_directory, "solution.json"))

    # Collect the parallel AGVNS comparison (see _launch_agvns_compare above).
    _solution_meta = _read_json_file(os.path.join(input_directory, "solution.json")) or {}
    _collect_agvns_compare(
        _agvns_proc, _agvns_out_file, _agvns_epoch_dir, _agvns_meta,
        final_cost, _solution_meta.get("route_after", ""),
    )

if __name__ == '__main__':
    main()
