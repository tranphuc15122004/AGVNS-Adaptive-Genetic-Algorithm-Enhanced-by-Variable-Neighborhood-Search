from typing import Dict , List , Tuple 
from algorithm.Object import *
import algorithm.algorithm_config as config 
import random
import time
from algorithm.engine import *
from collections import deque
import hashlib
import copy
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
import contextlib


def GAVND_5(initial_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], 
            id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes: Dict[int, Dict[str, Node]], 
            Base_vehicleid_to_plan: Dict[str, List[Node]]) -> Chromosome:
    
    try:
        current_orders = max(0, len(Unongoing_super_nodes))
        applied_params = config.adaptive_config(current_orders, num_vehicles=len(id_to_vehicle))
        print(f"Adaptive config applied: {applied_params}")
    except Exception as e:
        print(f"Adaptive config failed: {e}", file=sys.stderr)
    

    population, PDG_map = new_generate_random_chromosome(initial_vehicleid_to_plan, route_map, id_to_vehicle, Unongoing_super_nodes, Base_vehicleid_to_plan, 1)
    
    if population is None:
        print('Cant initialize the population')
        return None
    best_solution: Chromosome = None
    stagnant_generations = 0
    population.sort(key=lambda x: x.fitness)
    best_solution = population[0]
    # Elite size
    
        
    for gen in range(config.NUMBER_OF_GENERATION):
        # Kiểm tra timeout
        begin_gen_time = time.time()
        if config.is_timeout():
            elapsed_time = time.time() - config.BEGIN_TIME
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
        
        elite_count = min(len(population), max(1, int(config.POPULATION_SIZE * 0.2)))
        new_population = population[:elite_count]
        
        # Tạo con (có giới hạn số lần thử để tránh vòng lặp vô hạn ở test nhỏ)
        target_size = config.POPULATION_SIZE
        max_attempts = (getattr(config, 'OFFSPRING_ATTEMPTS_FACTOR', 10) or 10) * max(1, target_size - len(new_population))
        attempts = 0
        while len(new_population) < target_size and not config.is_timeout():
            attempts += 1
            parent1, parent2 = select_parents(population)
            if not parent1 or not parent2:
                # Fall back to cloning best if parent selection fails (very small population)
                candidate = copy.deepcopy(population[0]) if population else None
                if candidate:
                    new_population.append(candidate)
                continue
            child = new_crossver2(parent1, parent2, Base_vehicleid_to_plan, PDG_map)
            
            if child is None:
                # If crossover repeatedly fails, use a safe fallback individual
                if attempts >= max_attempts:
                    # Fallback: clone a random elite and apply a light LS step to diversify
                    base = copy.deepcopy(random.choice(new_population)) if new_population else copy.deepcopy(population[0])
                    with contextlib.suppress(Exception):
                        randon_1_LS(base, True, 1)
                    new_population.append(base)
                    # Reset attempts for the next child
                    attempts = 0
                continue
            new_population.append(child)
            
        population : List[Chromosome] = new_population[:config.POPULATION_SIZE]
        
        if config.is_timeout():
            break
        
        population.sort(key= lambda x: x.fitness)
        population = population[:config.POPULATION_SIZE]
        if population[0].fitness < best_solution.fitness: config.IMPROVED_IN_CROSS += 1
        
        mutate_count = 0
        for c in range (len(population)):
            if mutate_count > int(len(population) * 0.25):
                break            
            randon_1_LS(population[c] , True , 1)
            mutate_count +=1
        
        population.sort(key=lambda x: x.fitness)
        if population[0].fitness < best_solution.fitness: config.IMPROVED_IN_MUTATION += 1
        
        
        # Cập nhật best solution
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = copy.deepcopy(population[0])
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
        if stagnant_generations >= 5 or avg == population[0].fitness:
            print("Stopping early due to lack of improvement.")
            break

        # Time check - Điều chỉnh
        gen_end_time = time.time()
        
        # Tính tổng thời gian đã sử dụng
        elapsed_time = gen_end_time - config.BEGIN_TIME
        
        # Ước tính thời gian cần cho generation tiếp theo
        avg_gen_time = elapsed_time / (gen + 1)
        estimated_next_gen_time = avg_gen_time
        
        # Kiểm tra timeout
        if elapsed_time  > config.ALGO_TIME_LIMIT:
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s, Estimated next gen: {estimated_next_gen_time:.1f}s")
            break
    final_time = time.time()
    total_runtime = final_time - config.BEGIN_TIME
    print(f"Total runtime: {total_runtime:.2f}s ({total_runtime/60:.1f} minutes)" )
    
    # Giai doan 2
    unique_population = remove_similar_individuals(population, threshold=0.0)
    
    mutate_count = 0
    for c in range (len(unique_population)):
        if mutate_count > int(len(population) * config.MUTATION_RATE) or mutate_count >= len(unique_population):
            break            
        adaptive_LS_stategy(unique_population[c] , True , 1)
        
        mutate_count +=1
    
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


def adaptive_LS_stategy(indivisual: Chromosome, is_limited=True , mode = 1 ):
    if config.is_timeout():
        return False
    
    i = 1
    
    # Dictionary các phương pháp Local Search
    methods = {
        'PDPairExchange': lambda: new_inter_couple_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf,  is_limited),
        'BlockExchange': lambda: new_block_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited),
        'BlockRelocate': lambda: new_block_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited),
        'mPDG': lambda: new_multi_pd_group_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, math.inf, is_limited)
    }
    
    # Counter cho từng phương pháp
    counters = {name: 0 for name in methods}
    
    # Lấy thứ tự adaptive
    method_names = get_adaptive_order(indivisual , methods , mode=mode)
    
    #  Track local search timings per method
    ls_timings = {
        'PDPairExchange': 0.0,
        'BlockExchange': 0.0,
        'BlockRelocate': 0.0,
        'mPDG': 0.0,
    }
    
    while i < config.LS_MAX and not config.is_timeout():
        
        ls_start = time.time()
        if methods[method_names[0]]():
            ls_timings[method_names[0]] += time.time() - ls_start
            i += 1
            counters[method_names[0]] += 1
            continue
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[1]]():
            ls_timings[method_names[1]] += time.time() - ls_start
            i += 1
            counters[method_names[1]] += 1
            continue

        ls_timings[method_names[1]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[2]]():
            ls_timings[method_names[2]] += time.time() - ls_start
            i += 1
            counters[method_names[2]] += 1
            continue

        ls_timings[method_names[2]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        ls_start = time.time()
        if methods[method_names[3]]():
            ls_timings[method_names[3]] += time.time() - ls_start
            i += 1
            counters[method_names[3]] += 1
            continue

        ls_timings[method_names[3]] += time.time() - ls_start
        
        if config.is_timeout():
            break
        
        indivisual.cant_improved = True
        break

    for method_name in methods:
        indivisual.improved_LS_map[method_name] += counters[method_name]
    
    #  Enhanced logging with detailed timing information
    total_ls_time = sum(ls_timings.values())
    timing_details = " | ".join([f"{name}:{counters[name]}({ls_timings[name]:.3f}s)" for name in method_names])
    print(f"LS: {timing_details} | TotalTime:{total_ls_time:.3f}s | Cost:{total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution):.2f}")

