import sys
import time
import copy
import os
import json
from typing import Dict , List
from algorithm.In_and_Out import *
from algorithm.Object import Chromosome
from algorithm.engine import *
import algorithm.algorithm_config as Config
from src.conf.configs import Configs
import time


input_directory = Configs.algorithm_data_interaction_folder_path


def _runtime_clock(id_to_vehicle=None) -> tuple[int, int]:
    """Recover simulator epoch/time from solution metadata without aliases."""
    # ``gps_update_time`` is an absolute Unix timestamp and is the reliable
    # clock for projected cost/deadline features.  ``solution.json`` only
    # stores a relative delta interval and must remain the fallback.
    solution_path = os.path.join(input_directory, "solution.json")
    try:
        with open(solution_path, "r", encoding="utf-8") as handle:
            solution = json.load(handle)
        no = int(solution.get("no.", 0) or 0)
        delta = solution.get("deltaT", solution.get("delta_t", "0000-0010"))
        end_minutes = int(str(delta).split("-")[-1])
        timestamps = [int(getattr(vehicle, "gps_update_time", 0) or 0) for vehicle in (id_to_vehicle or {}).values()]
        absolute = max(timestamps, default=0)
        return max(0, no + 1), absolute if absolute > 100_000_000 else end_minutes * 60
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        timestamps = [int(getattr(vehicle, "gps_update_time", 0) or 0) for vehicle in (id_to_vehicle or {}).values()]
        absolute = max(timestamps, default=0)
        return 0, absolute if absolute > 100_000_000 else 0


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
    
    
    # ====================================================================
    # [THUẬT TOÁN MỚI - ĐIỂM CẮM VÀO]
    # --------------------------------------------------------------------
    # TODO: Cài thuật toán mới tại đây.
    #
    #   Đầu vào sẵn có:
    #     - vehicleid_to_plan     : kế hoạch các xe đã khôi phục (đơn đang chạy)
    #     - id_to_unlocated_items : toàn bộ đơn (order_item_id -> OrderItem)
    #     - new_order_itemIDs     : danh sách đơn MỚI cần xếp vào kế hoạch
    #     - route_map             : bản đồ khoảng cách/thời gian giữa các nhà máy
    #     - id_to_vehicle         : thông tin xe
    #     - id_to_factory         : thông tin nhà máy
    #
    #   Đầu ra cần có: best_chromosome (Chromosome) với .solution là kế hoạch
    #   hoàn chỉnh cho TẤT CẢ xe (đã bao gồm các đơn mới).
    # ====================================================================

    # --- Chi phí / route trước khi tối ưu (để đối chiếu) ---
    plan_before = copy.deepcopy(vehicleid_to_plan)
    try:
        cost_before = total_cost(id_to_vehicle, route_map, plan_before)
    except Exception:
        cost_before = 0.0
    try:
        from algorithm.evorl.legacy_adapter import build_epoch_state
        from algorithm.evorl.cost import projected_cost
        canonical_before = build_epoch_state(
            plan_before, id_to_vehicle, id_to_allorder, id_to_factory, route_map,
        )
        projected_before = projected_cost(
            {key: value.planned_route for key, value in canonical_before.vehicles.items()},
            canonical_before.vehicles, canonical_before.route_map, canonical_before.items,
            current_time=canonical_before.current_time,
        ).benchmark_cost
    except Exception:
        projected_before = cost_before

    # --- EvoRL canonical dispatcher ---
    # The dispatcher derives all mutable generated items from the restored
    # scene instead of relying on ``curr_unallocated - previous_unallocated``.
    # Legacy cheapest insertion remains an explicit emergency fallback so a
    # malformed historical solution cannot make the simulator lose a tick.
    dispatch_item_ids = []
    runtime_epoch, runtime_time = _runtime_clock(id_to_vehicle)
    try:
        if not Config.EVORL_ENABLE_CANONICAL_DISPATCH:
            raise RuntimeError("canonical dispatch disabled by EVORL_ENABLE_CANONICAL_DISPATCH")
        from algorithm.evorl.dispatch import dispatch_mutable_orders
        policy_checkpoint = os.environ.get("EVORL_CHECKPOINT") or None
        if os.environ.get("EVORL_REQUIRE_CHECKPOINT") == "1" and not policy_checkpoint:
            raise RuntimeError("strict EvoRL evaluation requires EVORL_CHECKPOINT")
        dispatch_item_ids = dispatch_mutable_orders(
            vehicleid_to_plan,
            id_to_vehicle,
            id_to_allorder,
            id_to_factory,
            route_map,
            generated_item_ids=list(id_to_unlocated_items),
            policy_checkpoint=policy_checkpoint,
            device=Config.EVORL_POLICY_DEVICE,
            epoch=runtime_epoch,
            current_time=runtime_time,
            time_budget_seconds=max(0.1, Config.get_remaining_time() - 1.0),
        )
        new_order_itemIDs = dispatch_item_ids
    except Exception as exc:
        if os.environ.get("EVORL_LEGACY_FALLBACK", "0") != "1":
            raise
        print(f"[EVORL] canonical dispatch failed; preserving legacy fallback: {exc}", file=sys.stderr)
        try:
            from algorithm.evorl.atomic import mutable_item_ids
            fallback_item_ids = mutable_item_ids(list(id_to_unlocated_items), id_to_vehicle, vehicleid_to_plan)
        except Exception:
            fallback_item_ids = new_order_itemIDs
        if fallback_item_ids:
            from algorithm.Test_algorithm.new_engine import new_dispatch_new_orders
            new_dispatch_new_orders(
                vehicleid_to_plan,
                id_to_factory,
                route_map,
                id_to_vehicle,
                id_to_unlocated_items,
                fallback_item_ids,
            )
    best_chromosome : Chromosome = Chromosome(vehicleid_to_plan , route_map , id_to_vehicle)
    try:
        canonical_after = build_epoch_state(
            vehicleid_to_plan, id_to_vehicle, id_to_allorder, id_to_factory, route_map,
        )
        projected_after = projected_cost(
            {key: value.planned_route for key, value in canonical_after.vehicles.items()},
            canonical_after.vehicles, canonical_after.route_map, canonical_after.items,
            current_time=canonical_after.current_time,
        ).benchmark_cost
    except Exception:
        projected_after = best_chromosome.fitness

    print()
    print('Route before:', get_route_after(plan_before , {}))
    print(f'[EVORL] Fitness before: {projected_before:.2f}')
    print()
    print('Route after:', get_route_after(best_chromosome.solution , {}))
    print(f'[EVORL] Fitness after: {projected_after:.2f}')
    print()
    # ====================================================================
    
    #Ket thuc thuat toan
    
    used_time = time.time() - Config.BEGIN_TIME
    print('Thoi gian thuc hien thuat toan: ' , used_time)
    
    update_solution_json(id_to_ongoing_items , id_to_unlocated_items , id_to_vehicle , best_chromosome.solution , vehicleid_to_destination , route_map , used_time)
    merge_node(id_to_vehicle , best_chromosome.solution)    
    
    if not Config.DELAY_DISPATCH:
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        
        write_destination_json_to_file(vehicleid_to_destination   , input_directory)    
        write_route_json_to_file(best_chromosome.solution  , input_directory) 
    else:
        emer_index =  Delaydispatch(id_to_vehicle , best_chromosome.solution , route_map)
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        
        
        write_destination_json_to_file_with_delay_timme(vehicleid_to_destination  ,emer_index , id_to_vehicle , input_directory)
        write_route_json_to_file_with_delay_time(best_chromosome.solution , emer_index , id_to_vehicle , input_directory)

if __name__ == '__main__':
    main()
