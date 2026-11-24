import sys
import time
import copy
import math
import os
from typing import Dict , List
from algorithm.In_and_Out import *
from algorithm.epoch_plan_log import append_current_solution
from algorithm.Object import Chromosome
from algorithm.engine import *
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.GAVND7 import GAVND_7
import algorithm.algorithm_config as Config
from src.conf.configs import Configs


input_directory = Configs.algorithm_data_interaction_folder_path


def _assert_valid_dispatch_plan(vehicleid_to_plan, id_to_vehicle, required_item_ids, id_to_factory):
    errors = validate_dispatch_plan(
        vehicleid_to_plan, id_to_vehicle, required_item_ids, id_to_factory
    )
    if errors:
        raise RuntimeError("Invalid dispatch plan: %s" % "; ".join(errors))



def _assert_valid_output_plan(
        vehicleid_to_plan: Dict[str, List[Node]],
        vehicleid_to_destination: Dict[str, Node],
        id_to_vehicle: Dict[str, Vehicle],
        required_item_ids: List[str],
        id_to_factory: Dict[str, Factory],
) -> None:
    simulator_plan = {}
    for vehicle_id in id_to_vehicle:
        destination = vehicleid_to_destination.get(vehicle_id)
        route = list(vehicleid_to_plan.get(vehicle_id) or [])
        simulator_plan[vehicle_id] = (
            ([destination] if destination is not None else []) + route
        )
    _assert_valid_dispatch_plan(
        simulator_plan, id_to_vehicle, required_item_ids, id_to_factory
    )



def _fitness_display(value: float) -> str:
    if math.isfinite(value):
        return str(value)
    if Config.is_timeout():
        return "unavailable (algorithm budget exhausted)"
    return "unavailable (non-finite objective)"


def main():
    Config.set_begin_time()
    id_to_factory , route_map ,  id_to_vehicle , id_to_unlocated_items ,  id_to_ongoing_items , id_to_allorder = Input()
    deal_old_solution_file(id_to_vehicle)

    vehicleid_to_plan: Dict[str , List[Node]]= {}
    vehicleid_to_destination : Dict[str , Node] = {}

    new_order_itemIDs : List[str] = []
    new_order_itemIDs = restore_scene_with_single_node(vehicleid_to_plan , id_to_ongoing_items, id_to_unlocated_items  , id_to_vehicle , id_to_factory ,id_to_allorder)

    new_order_itemIDs = [item for item in new_order_itemIDs if item]
    
    #Thuat toan
    print()
    
    """ if over24hours(id_to_vehicle , new_order_itemIDs):
        redispatch_process(id_to_vehicle , route_map , vehicleid_to_plan , id_to_factory , id_to_unlocated_items)
    else:
        dispatch_new_orders(vehicleid_to_plan , id_to_factory , route_map , id_to_vehicle , id_to_unlocated_items , new_order_itemIDs)
    """
    #worse_dispatch_new_orders(vehicleid_to_plan , id_to_factory , route_map , id_to_vehicle , id_to_unlocated_items , new_order_itemIDs)
    new_dispatch_new_orders(
        vehicleid_to_plan, id_to_factory, route_map, id_to_vehicle,
        id_to_unlocated_items, new_order_itemIDs, strict=True,
    )

    ci_vehicleid_to_plan = copy.deepcopy(vehicleid_to_plan)
    _assert_valid_dispatch_plan(
        ci_vehicleid_to_plan, id_to_vehicle, new_order_itemIDs, id_to_factory
    )
    
    Unongoing_super_nodes , Base_vehicleid_to_plan = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    
    best_chromosome = Chromosome(copy.deepcopy(ci_vehicleid_to_plan), route_map, id_to_vehicle)
    initial_fitness = best_chromosome.fitness
    ga_chromosome = None
    try:
        ga_chromosome = GAVND_7(
            copy.deepcopy(ci_vehicleid_to_plan), route_map, id_to_vehicle,
            Unongoing_super_nodes, copy.deepcopy(Base_vehicleid_to_plan),
        )
    except Exception as exc:
        print(
            "GA solution rejected (%s); using validated Cheapest Insertion fallback"
            % exc,
            file=sys.stderr,
        )
    finally:
        # Search is over. The simulator's larger timeout is now only available
        # for scoring, validation, and writing the best incumbent.
        Config.begin_finalization()

    if not math.isfinite(initial_fitness):
        initial_fitness = best_chromosome.fitness
    selected_fitness = initial_fitness

    if ga_chromosome is not None:
        try:
            _assert_valid_dispatch_plan(
                ga_chromosome.solution, id_to_vehicle, new_order_itemIDs, id_to_factory
            )
            ga_fitness = getattr(ga_chromosome, "_fitness_at_timeout", math.inf)
            if not math.isfinite(ga_fitness):
                try:
                    ga_fitness = ga_chromosome.fitness
                except Exception:
                    ga_fitness = math.inf
            if math.isfinite(ga_fitness) and ga_fitness <= initial_fitness:
                best_chromosome = ga_chromosome
                selected_fitness = ga_fitness
                print("Selected feasible GA solution")
            else:
                print(
                    "GA solution did not match or improve Cheapest Insertion; "
                    "using validated Cheapest Insertion fallback",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                "GA solution rejected (%s); using validated Cheapest Insertion fallback"
                % exc,
                file=sys.stderr,
            )
    #gold_algorithm_LS(best_chromosome , False)
    
    print()
    final_fitness = selected_fitness
    print('The solution initialized by Cheapest Insertion:')
    print(get_route_after(vehicleid_to_plan , {}))
    print(f'The fitness value before EA: {_fitness_display(initial_fitness)}')
    
    print(get_route_after(best_chromosome.solution , {}))
    print(f'The fitness value after EA: {_fitness_display(final_fitness)}')
    print()
    
    #Ket thuc thuat toan

    _assert_valid_dispatch_plan(
        best_chromosome.solution, id_to_vehicle, new_order_itemIDs, id_to_factory
    )
    
    used_time = time.time() - Config.BEGIN_TIME
    print('Thoi gian thuc hien thuat toan: ' , used_time)
    
    update_solution_json(id_to_ongoing_items , id_to_unlocated_items , id_to_vehicle , best_chromosome.solution , vehicleid_to_destination , route_map , used_time)
    merge_node(id_to_vehicle , best_chromosome.solution)    
    
    if not Config.DELAY_DISPATCH:
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        _assert_valid_output_plan(
            best_chromosome.solution, vehicleid_to_destination, id_to_vehicle,
            new_order_itemIDs, id_to_factory,
        )
        
        write_destination_json_to_file(vehicleid_to_destination   , input_directory)    
        write_route_json_to_file(best_chromosome.solution  , input_directory) 
    else:
        emer_index =  Delaydispatch(id_to_vehicle , best_chromosome.solution , route_map)
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        _assert_valid_output_plan(
            best_chromosome.solution, vehicleid_to_destination, id_to_vehicle,
            new_order_itemIDs, id_to_factory,
        )
        
        
        write_destination_json_to_file_with_delay_timme(vehicleid_to_destination  ,emer_index , id_to_vehicle , input_directory)
        write_route_json_to_file_with_delay_time(best_chromosome.solution , emer_index , id_to_vehicle , input_directory)

    # Archive the final plan (route_after) of this epoch for cross-variant
    # comparison (diagnostics only; see algorithm/epoch_plan_log.py).
    append_current_solution(
        final_fitness if math.isfinite(final_fitness) else None,
        os.path.join(input_directory, "solution.json"),
    )

if __name__ == '__main__':
    main()
