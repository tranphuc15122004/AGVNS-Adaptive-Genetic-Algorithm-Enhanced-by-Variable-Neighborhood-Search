from typing import Dict , List , Tuple 
from algorithm.Object import *
import algorithm.algorithm_config as config 
import random
import time
from algorithm.engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.new_engine import *


def GAVND_2(initial_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], 
            id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes: Dict[int, Dict[str, Node]], 
            Base_vehicleid_to_plan: Dict[str, List[Node]]) -> Chromosome:
    
    #  Initialize timing tracking
    timing_stats = {
        'initialization': 0.0,
        'diversity_calculation': 0.0,
        'diversity_maintenance': 0.0,
        'parent_selection': 0.0,
        'crossover': 0.0,
        'mutation': 0.0,
        'population_sorting': 0.0,
        'fitness_evaluation': 0.0,
        'total_generations': 0.0
    }
    
    #  Start timing initialization
    init_start = time.time()
    
    population, PDG_map = generate_random_chromosome(initial_vehicleid_to_plan, route_map, id_to_vehicle, Unongoing_super_nodes, Base_vehicleid_to_plan, config.POPULATION_SIZE)

    if population is None:
        print('Cant initialize the population')
        return None
    
    best_solution: Chromosome = initial_vehicleid_to_plan
    stagnant_generations = 0
    population.sort(key=lambda x: x.fitness)
    best_solution = population[0]
    min_diversity = 0.15
    # Elite size
    elite_size = max(2, config.POPULATION_SIZE // 5)
    
    timing_stats['initialization'] = time.time() - init_start
    print(f" Initialization completed in {timing_stats['initialization']:.3f}s", file=sys.stderr)
    
    for gen in range(config.NUMBER_OF_GENERATION):
        #  Start timing total generation
        gen_start = time.time()
        
        # Kiểm tra timeout
        elapsed_time = time.time() - config.BEGIN_TIME
        if config.is_timeout():
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
        
        #  Start timing diversity calculation
        diversity_start = time.time()
        diversity = calculate_diversity(population)
        timing_stats['diversity_calculation'] += time.time() - diversity_start
        
        #  Start timing diversity maintenance
        maintain_start = time.time()
        if diversity < min_diversity :
            population = maintain_diversity(population, id_to_vehicle, route_map, Base_vehicleid_to_plan, PDG_map)
            timing_stats['diversity_maintenance'] += time.time() - maintain_start
        else:
            timing_stats['diversity_maintenance'] += time.time() - maintain_start
            
            #  Start timing crossover operations
            crossover_start = time.time()
            new_population = []
            
            # Elitism - giữ lại elite
            population.sort(key=lambda x: x.fitness)
            new_population = population[:elite_size]

            # Tạo con
            while len(new_population) < config.POPULATION_SIZE:
                parent1, parent2 = select_parents(population)
                child1 , child2 = new_crossover(parent1 , parent2 , PDG_map)
                if child1:
                    new_population.append(child1)
                if child2:
                    new_population.append(child2)

            population = new_population
            timing_stats['crossover'] += time.time() - crossover_start
            population.sort(key=lambda x: x.fitness)
            
            #  Start timing mutation operations
            mutation_start = time.time()
            """ for c in population:
                if random.random() < config.MUTATION_RATE:
                    new_mutation(c ,True , 1) """
            for i in range (0 , 5):
                new_mutation(population[i] , True , 1)
            timing_stats['mutation'] += time.time() - mutation_start
        
        #  Start timing population sorting
        sort_start = time.time()
        # Sắp xếp lại quần thể
        population.sort(key=lambda x: x.fitness)
        timing_stats['population_sorting'] += time.time() - sort_start

        #  Start timing fitness evaluation
        fitness_start = time.time()
        # Cập nhật best solution
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = population[0]
            stagnant_generations = 0
        else:
            stagnant_generations += 1
        
        diversity = calculate_diversity(population)
        fitness_diversity = calculate_fitness_diversity(population)
        timing_stats['fitness_evaluation'] += time.time() - fitness_start
        
        #  Record generation timing
        gen_time = time.time() - gen_start
        timing_stats['total_generations'] += gen_time
        
        print(f'Generation {gen+1}: Best = {best_solution.fitness:.2f}, '
            f'Worst = {population[-1].fitness:.2f}, '
            f'Avg = {sum([c.fitness for c in population]) / len(population):.2f}, '
            f'Diversity = {diversity:.3f}, '
            f'FitDiv = {fitness_diversity:.3f}, '
            f'GenTime = {gen_time:.3f}s')

        # Điều kiện dừng
        if stagnant_generations >= 7:
            print("Stopping early due to lack of improvement.")
            break

        # Kiểm tra timeout
        elapsed_time = time.time() - config.BEGIN_TIME
        if elapsed_time > config.ALGO_TIME_LIMIT:
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break

    #  Print comprehensive timing summary
    total_runtime = time.time() - config.BEGIN_TIME
    print(f"\n{'='*60}")
    print(f"PERFORMANCE TIMING SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Runtime: {total_runtime:.3f}s ({total_runtime/60:.2f} minutes)")
    print(f"Initialization: {timing_stats['initialization']:.3f}s ({timing_stats['initialization']/total_runtime*100:.1f}%)")
    print(f"Diversity Calculation: {timing_stats['diversity_calculation']:.3f}s ({timing_stats['diversity_calculation']/total_runtime*100:.1f}%)")
    print(f"Diversity Maintenance: {timing_stats['diversity_maintenance']:.3f}s ({timing_stats['diversity_maintenance']/total_runtime*100:.1f}%)")
    print(f"Crossover Operations: {timing_stats['crossover']:.3f}s ({timing_stats['crossover']/total_runtime*100:.1f}%)")
    print(f"Mutation Operations: {timing_stats['mutation']:.3f}s ({timing_stats['mutation']/total_runtime*100:.1f}%)")
    print(f"Population Sorting: {timing_stats['population_sorting']:.3f}s ({timing_stats['population_sorting']/total_runtime*100:.1f}%)")
    print(f"Fitness Evaluation: {timing_stats['fitness_evaluation']:.3f}s ({timing_stats['fitness_evaluation']/total_runtime*100:.1f}%)")
    print(f"All Generations: {timing_stats['total_generations']:.3f}s ({timing_stats['total_generations']/total_runtime*100:.1f}%)")
    
    # Calculate unaccounted time
    accounted_time = sum(timing_stats.values())
    unaccounted = total_runtime - accounted_time
    print(f"Other Operations: {unaccounted:.3f}s ({unaccounted/total_runtime*100:.1f}%)")
    print(f"{'='*60}")
    
    return best_solution


def select_parents(population: List[Chromosome]) -> Tuple[Chromosome, Chromosome]:
    if config.is_timeout():
        return None , None
    
    def tournament_selection():
        # Tăng tournament size để tăng selective pressure
        tournament_size = max(3, len(population) // 5)  # Tăng từ //10 lên //5
        candidates = random.sample(population, tournament_size)
        return min(candidates, key=lambda x: x.fitness)
    
    def roulette_wheel_selection():
        # Thêm roulette wheel selection để tăng đa dạng
        fitness_values = [1 / (c.fitness + 1) for c in population]  # Inverse fitness
        total_fitness = sum(fitness_values)
        r = random.uniform(0, total_fitness)
        cumulative = 0
        for i, fitness in enumerate(fitness_values):
            cumulative += fitness
            if cumulative >= r:
                return population[i]
        return population[-1]
    
    # Kết hợp cả 2 phương pháp
    if random.random() < 1:
        return tournament_selection(), tournament_selection()
    else:
        return roulette_wheel_selection(), roulette_wheel_selection()


def new_mutation(indivisual: Chromosome, is_limited=True , mode = 1):
    if config.is_timeout():
        return False
    
    i = 1
    
    # Dictionary các phương pháp Local Search
    methods = {
        'PDPairExchange': lambda: inter_couple_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, is_limited),
        'BlockExchange': lambda: block_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, is_limited),
        'BlockRelocate': lambda: block_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, is_limited),
        'mPDG': lambda: multi_pd_group_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, is_limited),
        '2opt': lambda: improve_ci_path_by_2_opt(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map, is_limited)
    }
    
    # Counter cho từng phương pháp
    counters = {name: 0 for name in methods.keys()}
    
    # Lấy thứ tự adaptive
    method_names = get_adaptive_order(indivisual , methods , mode=mode)
    
    #  Track local search timings per method
    ls_timings = {
        'PDPairExchange': 0.0,
        'BlockExchange': 0.0,
        'BlockRelocate': 0.0,
        'mPDG': 0.0,
        '2opt': 0.0
    }
    
    while i < config.LS_MAX:
        if config.is_timeout():
            break
        
        #  Time each local search method execution
        ls_start = time.time()
        if methods[method_names[0]]():
            ls_timings[method_names[0]] += time.time() - ls_start
            i += 1
            counters[method_names[0]] += 1
            continue
        ls_timings[method_names[0]] += time.time() - ls_start
        
        ls_start = time.time()
        if methods[method_names[1]]():
            ls_timings[method_names[1]] += time.time() - ls_start
            i += 1
            counters[method_names[1]] += 1
            continue
        ls_timings[method_names[1]] += time.time() - ls_start
        
        ls_start = time.time()
        if methods[method_names[2]]():
            ls_timings[method_names[2]] += time.time() - ls_start
            i += 1
            counters[method_names[2]] += 1
            continue
        ls_timings[method_names[2]] += time.time() - ls_start
        
        ls_start = time.time()
        if methods[method_names[3]]():
            ls_timings[method_names[3]] += time.time() - ls_start
            i += 1
            counters[method_names[3]] += 1
            continue
        ls_timings[method_names[3]] += time.time() - ls_start
        
        ls_start = time.time()
        if methods[method_names[4]]():
            ls_timings[method_names[4]] += time.time() - ls_start
            i += 1
            counters[method_names[4]] += 1
            continue
        ls_timings[method_names[4]] += time.time() - ls_start
        
        # No improvement found
        break
    #indivisual.fitness = indivisual.evaluate_fitness()
    for method_name in methods.keys():
        indivisual.improved_LS_map[method_name] += counters[method_name]
    
    #  Enhanced logging with detailed timing information
    total_ls_time = sum(ls_timings.values())
    timing_details = " | ".join([f"{name}:{counters[name]}({ls_timings[name]:.3f}s)" for name in method_names])
    print(f"LS: {timing_details} | TotalTime:{total_ls_time:.3f}s | Cost:{total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution):.2f}", file=sys.stderr)

def maintain_diversity(population: List[Chromosome], 
                    id_to_vehicle: Dict[str, Vehicle],
                    route_map: Dict[Tuple, Tuple],
                    Base_vehicleid_to_plan: Dict[str, List[Node]],
                    PDG_map: Dict[str, List[Node]],) -> List[Chromosome]:
    # Kiểm tra timeout ngay từ đầu
    if config.is_timeout():
        print("Timeout detected in maintain_diversity", file=sys.stderr)
        return population  #  Return population hiện tại

    print("Low diversity detected, applying diversity maintenance...")
    
    # Sắp xếp theo fitness
    population.sort(key=lambda x: x.fitness)
    
    # Giữ lại elite (30% tốt nhất)
    elite_size = max(2, len(population))
    elite = population[:elite_size]
    
    # Loại bỏ các cá thể quá giống nhau
    unique_population = remove_similar_individuals(elite, threshold=0.1)
    for c in unique_population:
        new_mutation(c , True , 1)
    
    # Tạo cá thể mới để bù đắp
    new_individuals = []
    needed = config.POPULATION_SIZE - len(unique_population)
    
    for i in range(needed):
        if config.is_timeout():
            print(f"Timeout during creating new individuals, created {i}/{needed}", file=sys.stderr)
            break
        
        # Tạo cá thể mới bằng nhiều phương pháp khác nhau
        if random.random() < 0.5:
            # Tạo tương đối tốt
            new_individual = generate_single_random_chromosome(Base_vehicleid_to_plan, route_map, id_to_vehicle, PDG_map)
        else:
            # Random crossover từ elite
            if random.random() < 0.5 and len(unique_population) > 2:
                parent1, parent2 = random.sample(elite, 2)
                new_individual = parent1.crossover(parent2, PDG_map)
                child1 , child2 = new_crossover(parent1 , parent2 , PDG_map)
                if child1 and child2:
                    new_individual = child1 if child1.fitness < child2.fitness else child2
                else:
                    new_individual = random.choice([parent1, parent2])
            else:
                new_individual =  copy.deepcopy(random.choice(unique_population))
            new_mutation(new_individual, is_limited=True , mode= 2)
        
        new_individuals.append(new_individual)
    
    return unique_population + new_individuals


