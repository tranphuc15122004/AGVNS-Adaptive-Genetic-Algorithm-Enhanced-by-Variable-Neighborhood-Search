from typing import Dict , List , Tuple
from algorithm.Object import *
import algorithm.algorithm_config as config
import random
import time
from algorithm.engine import *
import copy
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
import contextlib
import math
from algorithm.Test_algorithm.adaptive_ratio import (
    AdaptiveRatioParams,
    compute_adaptive_ratio,
    params_from_config,
    compute_adaptive_ratio_erfc
)

def _copy_solution(sol: Dict[str, List[Node]]) -> Dict[str, List[Node]]:
    return {vid: route[:] for vid, route in sol.items()}

def adaptive_local_configs(num_order: int, num_vehicles: int):
    params = AdaptiveRatioParams(
        threshold_orders=80,
        kww_beta=3,
        kww_tau_factor=10.0,
        min_ratio=0.0,
        max_ratio=1.0,
        vehicle_influence=0.0,
        pivot_fraction=0.5,
        logistic_slope=10,
        early_shape=0.7,
    )
    #info = compute_adaptive_ratio(num_orders=num_order, num_vehicles=num_vehicles, p=params)
    info = compute_adaptive_ratio_erfc(num_orders= num_order , num_vehicles=num_vehicles , p = params , center= 0.5 , width= 0.2)
    config.CROSSOVER_TYPE_RATIO = info['ratio']
    # Return full diagnostics for logging if needed by caller
    return info


def GA(initial_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], 
            id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes: Dict[int, Dict[str, Node]], 
            Base_vehicleid_to_plan: Dict[str, List[Node]]) -> Chromosome:
    
    try:
        current_orders = max(0, len(Unongoing_super_nodes))
        applied_params = adaptive_local_configs(current_orders, num_vehicles=len(id_to_vehicle))
        print(f"Adaptive config applied: {applied_params}")
    except Exception as e:
        print(f"Adaptive config failed: {e}", file=sys.stderr)
    
    population, PDG_map = new_generate_random_chromosome(initial_vehicleid_to_plan, route_map, id_to_vehicle, Unongoing_super_nodes, Base_vehicleid_to_plan, config.POPULATION_SIZE)
    
    if population is None:
        print('Cant initialize the population')
        return None
    best_solution: Chromosome = None
    stagnant_generations = 0
    population.sort(key=lambda x: x.fitness)
    best_solution =  copy.deepcopy(population[0])
    
    begin_GA_time = time.time()
    for gen in range(config.NUMBER_OF_GENERATION):
        # Kiểm tra timeout
        begin_gen_time = time.time()
        if config.is_timeout():
            elapsed_time = time.time() - config.BEGIN_TIME
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
        
        # Tạo con (có giới hạn số lần thử để tránh vòng lặp vô hạn ở test nhỏ)
        target_size = config.POPULATION_SIZE * 2
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
            
            if random.uniform(0 , 1) < config.CROSSOVER_TYPE_RATIO:
                child = new_crossver2(parent1, parent2, Base_vehicleid_to_plan, PDG_map)
            else:                
                child = disturbance_opt(parent1.solution , id_to_vehicle , route_map , 0.5)
            
            if child is None:
                # If crossover repeatedly fails, use a safe fallback individual
                if attempts >= max_attempts:
                    # Fallback: clone a random elite and apply a light LS step to diversify
                    base = copy.deepcopy(random.choice(population)) if population else copy.deepcopy(population[0])
                    with contextlib.suppress(Exception):
                        randon_1_LS(base, True, 1)
                    population.append(base)
                    # Reset attempts for the next child
                    attempts = 0
                continue
            population.append(child)
        
        population.sort(key= lambda x: x.fitness)
        new_populution : List[Chromosome] = population[:config.POPULATION_SIZE]
        population = new_populution
        
        if config.is_timeout():
            break
        
        population.sort(key= lambda x: x.fitness)
        population = population[:config.POPULATION_SIZE]
        if population[0].fitness < best_solution.fitness: config.IMPROVED_IN_CROSS += 1
        
        mutate_count = 0
        for c in range (len(population)):
            if mutate_count > int(len(population) * config.MUTATION_RATE):
                break            
            randon_1_LS(population[c] , True , 1)
            mutate_count +=1
        
        population.sort(key=lambda x: x.fitness)
        if population[0].fitness < best_solution.fitness: config.IMPROVED_IN_MUTATION += 1
        
        
        # Cập nhật best solution
        if best_solution is None or population[0].fitness < int(best_solution.fitness):
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
        if stagnant_generations >= 5 or avg == population[0].fitness :
            print("Stopping early due to lack of improvement.")
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

