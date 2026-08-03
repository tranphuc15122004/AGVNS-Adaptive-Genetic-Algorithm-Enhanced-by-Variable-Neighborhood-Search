import sys
import time
import copy
from typing import Dict , List
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
    
    print(f'[MOEAD-TS] TC before optimization: {initial_cost:.2f}')

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
    if not Config.DELAY_DISPATCH:
        archived_solution = copy.deepcopy(best_chromosome.solution)
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        write_destination_json_to_file(vehicleid_to_destination   , input_directory)    
        write_route_json_to_file(best_chromosome.solution  , input_directory) 
    else:
        emer_index =  Delaydispatch(id_to_vehicle , best_chromosome.solution , route_map)
        archived_solution = copy.deepcopy(best_chromosome.solution)
        get_output_solution(id_to_vehicle , best_chromosome.solution , vehicleid_to_destination)
        write_destination_json_to_file_with_delay_timme(vehicleid_to_destination  ,emer_index , id_to_vehicle , input_directory)
        write_route_json_to_file_with_delay_time(best_chromosome.solution , emer_index , id_to_vehicle , input_directory)

    used_time = time.time() - Config.BEGIN_TIME
    print('Thoi gian thuc hien thuat toan: ' , used_time)
    update_solution_json(
        id_to_ongoing_items, id_to_unlocated_items, id_to_vehicle,
        archived_solution, {}, route_map, used_time,
    )

if __name__ == '__main__':
    main()
