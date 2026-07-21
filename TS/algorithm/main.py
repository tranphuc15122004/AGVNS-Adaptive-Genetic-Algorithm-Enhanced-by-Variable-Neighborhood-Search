import sys
import time
from typing import Dict , List
from algorithm.In_and_Out import *
from algorithm.Object import Chromosome
from algorithm.engine import *
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.MA import Memetic_algorithm
from algorithm.Test_algorithm.MA_engine import *
from algorithm.Test_algorithm.tabu_search import Tabu_Search
import algorithm.algorithm_config as Config
from src.conf.configs import Configs
import time


input_directory = Configs.algorithm_data_interaction_folder_path


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
    
    
    Pre_Unongoing_super_nodes , Base_vehicleid_to_plan = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    base_plan_before_preinitialization = copy.deepcopy(Base_vehicleid_to_plan)
    
    orderId_to_nodelist =  Pre_population_initialization_2(Base_vehicleid_to_plan , Pre_Unongoing_super_nodes , id_to_factory , route_map , id_to_vehicle , id_to_unlocated_items , new_order_itemIDs)
    
    copy_base_vehicleid_to_plan = base_plan_before_preinitialization
    best_chromosome : Chromosome = Tabu_Search(
        copy_base_vehicleid_to_plan,
        route_map,
        id_to_vehicle,
        orderId_to_nodelist,
        id_to_factory,
        id_to_unlocated_items,
        new_order_itemIDs,
    )
    if best_chromosome is None:
        print('[TS] Khong co don hang moi - giu nguyen tuyen duong hien tai')
        best_chromosome : Chromosome = Chromosome(vehicleid_to_plan , route_map , id_to_vehicle)
    
    print()
    print('Route before:', get_route_after(base_plan_before_preinitialization , {}))
    
    print()
    print('Route after:', get_route_after(best_chromosome.solution , {}))
    print(f'[TS] Fitness after MA: {best_chromosome.fitness:.2f}')
    print()
    
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
