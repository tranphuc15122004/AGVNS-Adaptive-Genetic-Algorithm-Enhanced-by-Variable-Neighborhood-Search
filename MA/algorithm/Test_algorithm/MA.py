from typing import Dict , List , Tuple
from algorithm.Object import *
import algorithm.algorithm_config as config
import random
import time
from algorithm.engine import *
import copy
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.MA_engine import *
import contextlib
import math


def _copy_solution(sol: Dict[str, List[Node]]) -> Dict[str, List[Node]]:
    return {vid: route[:] for vid, route in sol.items()}



def Memetic_algorithm(Base_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle], orderID_to_nodelist : Dict[str , List[List[Node]]]) -> Chromosome:
    
    population = Population_initialization(Base_vehicleid_to_plan , route_map , id_to_vehicle , orderID_to_nodelist , 20)
    if population is None:
        print('Cant initialize the population')
        return None
    
    if len(population) != 20: 
        print(' ERROR: Quan the dc khoi tao khong du 20 ca the')
        return None
    
    population.sort(key= lambda x: x.fitness)
    
    avg = sum(c.fitness for c in population) / len(population)
        
    print(f'Pre GA Generation : Best = {population[0].fitness:.2f}, '
            f'Worst = {population[-1].fitness:.2f}, '
            f'Avg = {avg:.2f}, ')
    
    
    stagnant_generations = 0
    population.sort(key=lambda x: x.fitness)
    best_solution: Chromosome = copy.deepcopy(population[0])
    
    Unongoing_super_nodes , _ = get_UnongoingSuperNode(population[0].solution , id_to_vehicle)
    PDG_map : Dict[str , List[Node]] = {}
    
    # tao Dict cac super node
    for idx, pdg in Unongoing_super_nodes.items():
        pickup_node = None
        delivery_node = None
        node_list: List[Node] = []
        pos_i = 0
        pos_j = 0
        d_num = len(pdg) // 2
        index = 0

        if pdg:
            vehicleID = ''
            for v_and_pos_str, node in (pdg.items()):
                vehicleID = v_and_pos_str.split(",")[0]
                if index % 2 == 0:
                    pos_i = int(v_and_pos_str.split(",")[1])
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    pos_j = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
                    pos_j = int(pos_j - d_num + 1)
            
            k : str = f"{vehicleID},{int(pos_i)}+{int(pos_j)}"
            PDG_map[k] = node_list
    if len(PDG_map) < 2:
        return population[0]
    
    
    begin_GA_time = time.time()
    for gen in range(config.NUMBER_OF_GENERATION):
        # Kiểm tra timeout
        begin_gen_time = time.time()
        if config.is_timeout():
            elapsed_time = time.time() - config.BEGIN_TIME
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
        
        # Tạo con (có giới hạn số lần thử để tránh vòng lặp vô hạn ở test nhỏ)
        target_size = 20 * 2
        max_attempts = (getattr(config, 'OFFSPRING_ATTEMPTS_FACTOR', 10) or 10) * max(1, target_size - len(population))
        attempts = 0
        while len(population) < target_size and not config.is_timeout():
            attempts += 1
            parent1, parent2 = select_parents(population)
            if not parent1 or not parent2:
                # Fall back to cloning best if parent selection fails (very small population)
                candidate = copy.deepcopy(random.choice(population)) if population else None
                if candidate:
                    population.append(candidate)
                continue
            
            child = parent1.crossover(parent2 , PDG_map)
            
            if child is None:
                continue
            
            Local_search_MA(child , PDG_map)
            
            population.append(child)
        
        population.sort(key= lambda x: x.fitness)
        new_populution : List[Chromosome] = population[:config.POPULATION_SIZE]
        population = new_populution
        
        population.sort(key= lambda x: x.fitness)
        population = population[:config.POPULATION_SIZE]
        if population[0].fitness < best_solution.fitness: config.IMPROVED_IN_CROSS += 1
        
        
        # Cập nhật best solution
        if best_solution is None or population[0].fitness < (best_solution.fitness):
            new_best_solution = _copy_solution(population[0].solution)
            best_solution = Chromosome(new_best_solution , route_map , id_to_vehicle)
            stagnant_generations = 0
        else:
            stagnant_generations += 1
        
        avg = sum(c.fitness for c in population) / len(population)
        
        print(f'Generation {gen+1}: Best = {population[0].fitness:.2f}, '
                f'Worst = {population[-1].fitness:.2f}, '
                f'Avg = {avg:.2f}, '
                f'Time: {time.time() - begin_gen_time}')

        # Điều kiện dừng
        #  
        if stagnant_generations >= 10 :
            print("Stopping early due to lack of improvement.")
            break
        
        if config.is_timeout():
            break
        
        gen_end_time = time.time()
        
        elapsed_time = gen_end_time - config.BEGIN_TIME
        
        # Kiểm tra timeout
        if elapsed_time  > config.ALGO_TIME_LIMIT:
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
    final_time = time.time()
    total_runtime = final_time - config.BEGIN_TIME
    print(f"Total runtime: {total_runtime:.2f}s ({total_runtime/60:.1f} minutes)" )
    print(f"Total GA runtime: {final_time - begin_GA_time:.2f}s ({(final_time - begin_GA_time)/60:.1f} minutes)" )
    
    return best_solution



def select_parents(population: List[Chromosome]) -> Tuple[Chromosome, Chromosome]:
    if config.is_timeout():
        return None , None
    # Safeguards for very small active population
    if not population:
        return None, None
    if len(population) == 1:
        # Only one individual available; return it twice (degenerate crossover)
        return population[0], population[0]
    
    def tournament_selection():
        # Adaptive tournament size with upper bound = len(population)
        # and lower bound = 2 (but not exceeding population size)
        raw_size = max(2, len(population) // 5)  # more selective than //10
        tournament_size = min(len(population), raw_size)
        # Fallback to 1 if population ==1 already handled above
        if tournament_size <= 1:
            return population[0]
        candidates = random.sample(population, tournament_size)
        return min(candidates, key=lambda x: x.fitness)
    
    # Kết hợp cả 2 phương pháp
    # If population extremely small, allow duplicates gracefully
    p1 = tournament_selection()
    p2 = tournament_selection()
    return p1, p2