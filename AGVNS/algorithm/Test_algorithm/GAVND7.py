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


def GAVND_7(initial_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], 
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
            randon_1_LS(population[c] , PDG_map , True , 1)
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
        if stagnant_generations >= 4 or avg == population[0].fitness :
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
    
    
    # Giai doan 2
    unique_population = remove_similar_individuals(population, threshold=0.0)
    unique_population.sort(key=lambda x: x.fitness)
    print(len(unique_population))
    
    unique_population = [ini for ini in unique_population if ini.fitness < best_solution.fitness  + config.addDelta]
    print(len(unique_population))
    
    mutate_count = 0
    while not config.is_timeout():
        
        if mutate_count > int(len(population) * config.MUTATION_RATE) or mutate_count >= len(unique_population):
            break
        
        if unique_population[mutate_count % len(unique_population)].fitness > unique_population[0].fitness + config.addDelta: break
        
        adaptive_LS_stategy(unique_population[mutate_count] , PDG_map , False )
        
        mutate_count += 1
    
    unique_population.sort(key=lambda x: x.fitness)
    if unique_population[0].fitness < best_solution.fitness: config.IMPROVED_IN_DIVER += 1
    best_solution = unique_population[0]
    
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


def adaptive_LS_stategy(indivisual: Chromosome, PDG_map : Dict[str , List[Node]],  is_limited=True ):
    if config.is_timeout():
        return False
    
    i = 0
    
    # Dictionary các phương pháp Local Search
    methods = {
        'PDPairExchange': lambda: new_inter_couple_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf,  is_limited),
        'BlockExchange': lambda: new_block_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited),
        'BlockRelocate': lambda: new_block_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited),
        'mPDG': lambda: new_multi_pd_group_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited),
    }
    
    # Counter cho từng phương pháp
    counters = {name: 0 for name in methods}
    
    # Lấy thứ tự adaptive
    method_names = get_adaptive_order(indivisual , methods )
    
    #  Track local search timings per method
    ls_timings = {
        'PDPairExchange': 0.0,
        'BlockExchange': 0.0,
        'BlockRelocate': 0.0,
        'mPDG': 0.0,
    }

    # Best snapshot latch to ensure we commit the best solution found during LS
    
    best_cost = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
    best_snapshot = _copy_solution(indivisual.solution)
    
    while not config.is_timeout():
        
        ls_start = time.time()
        if methods[method_names[0]]():
            ls_timings[method_names[0]] += time.time() - ls_start
            i += 1
            counters[method_names[0]] += 1
            # Latch best if improved
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[1]]():
            ls_timings[method_names[1]] += time.time() - ls_start
            i += 1
            counters[method_names[1]] += 1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue

        ls_timings[method_names[1]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[2]]():
            ls_timings[method_names[2]] += time.time() - ls_start
            i += 1
            counters[method_names[2]] += 1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue

        ls_timings[method_names[2]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[3]]():
            ls_timings[method_names[3]] += time.time() - ls_start
            i += 1
            counters[method_names[3]] += 1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue

        ls_timings[method_names[3]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        break

    # Commit the best snapshot found during LS
    indivisual.solution = best_snapshot

    for method_name in methods:
        indivisual.improved_LS_map[method_name] += counters[method_name]
    
    #  Enhanced logging with detailed timing information
    total_ls_time = sum(ls_timings.values())
    timing_details = " | ".join([f"{name}:{counters[name]}({ls_timings[name]:.3f}s)" for name in method_names])
    print(f"LS: {timing_details} | TotalTime:{total_ls_time:.3f}s | Cost:{total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution):.2f}")

