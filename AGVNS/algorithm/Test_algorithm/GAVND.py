from typing import Dict , List , Tuple 
from algorithm.Object import *
import algorithm.algorithm_config as config 
import random
from algorithm.engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.new_engine import *
import multiprocessing

def GAVND_1(initial_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], 
            id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes: Dict[int, Dict[str, Node]], 
            Base_vehicleid_to_plan: Dict[str, List[Node]]) -> Chromosome:
    
    population, PDG_map = generate_random_chromosome(initial_vehicleid_to_plan, route_map, id_to_vehicle, Unongoing_super_nodes, Base_vehicleid_to_plan, config.POPULATION_SIZE)

    if population is None:
        print('Cant initialize the population')
        return None
    best_solution: Chromosome = None
    stagnant_generations = 0
    population.sort(key=lambda x: x.fitness)
    best_solution = population[0]
    min_diversity = 0.15
    # Elite size
    elite_size = max(2, config.POPULATION_SIZE // 5)
    
    for gen in range(config.NUMBER_OF_GENERATION):
        # Kiểm tra timeout
        if config.is_timeout():
            elapsed_time = time.time() - config.BEGIN_TIME
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s")
            break
        
        gen_start_time = time.time()  # Bắt đầu generation
        
        diversity = calculate_diversity(population)
        if diversity < min_diversity:
            population = maintain_diversity(population, id_to_vehicle, route_map, Base_vehicleid_to_plan, PDG_map , min_diversity)
        else:
            new_population = []
            
            # Elitism - giữ lại elite
            population.sort(key=lambda x: x.fitness)
            new_population = population[:elite_size]

            # Tạo con
            while len(new_population) < config.POPULATION_SIZE:
                parent1, parent2 = select_parents(population)
                child = parent1.crossover(parent2, PDG_map)
                new_population.append(child)
            population = new_population

            for c in population:
                if random.random() < 1: 
                    new_mutation(c , False , 1)
        
        # Sắp xếp lại quần thể
        population.sort(key=lambda x: x.fitness)
        population = population[:config.POPULATION_SIZE]
        new_mutation(best_solution , False , 1)

        # Cập nhật best solution
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = copy.deepcopy(population[0])
            stagnant_generations = 0
        else:
            stagnant_generations += 1
        
        diversity = calculate_diversity(population)
        fitness_diversity = calculate_fitness_diversity(population)
        
        print(f'Generation {gen+1}: Best = {best_solution.fitness:.2f}, '
            f'Worst = {population[-1].fitness:.2f}, '
            f'Avg = {sum([c.fitness for c in population]) / len(population):.2f}, '
            f'Diversity = {diversity:.3f}, '
            f'FitDiv = {fitness_diversity:.3f}')

        # Điều kiện dừng
        if stagnant_generations >= 10:
            print("Stopping early due to lack of improvement.")
            break

        # Time check - Điều chỉnh
        gen_end_time = time.time()
        current_gen_duration = gen_end_time - gen_start_time
        
        # Tính thời gian của generation đầu tiên
        if gen == 0:
            first_gen_time = current_gen_duration
        
        # Tính tổng thời gian đã sử dụng
        elapsed_time = gen_end_time - config.BEGIN_TIME
        
        # Ước tính thời gian cần cho generation tiếp theo
        avg_gen_time = elapsed_time / (gen + 1)
        estimated_next_gen_time = avg_gen_time
        
        # Kiểm tra timeout
        if elapsed_time + estimated_next_gen_time > config.ALGO_TIME_LIMIT:
            print(f"TimeOut!! Elapsed: {elapsed_time:.1f}s, Estimated next gen: {estimated_next_gen_time:.1f}s")
            break

    final_time = time.time()
    total_runtime = final_time - config.BEGIN_TIME
    print(f"Total runtime: {total_runtime:.2f}s ({total_runtime/60:.1f} minutes)" )
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
    if random.random() < 0.75:
        return tournament_selection(), tournament_selection()
    else:
        return roulette_wheel_selection(), roulette_wheel_selection()


def new_mutation(indivisual: Chromosome, is_limited=True , mode = 1):
    if config.is_timeout():
        return copy.deepcopy(indivisual)
    
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
    return copy.deepcopy(indivisual)
    
def maintain_diversity(population: List[Chromosome], 
                    id_to_vehicle: Dict[str, Vehicle],
                    route_map: Dict[Tuple, Tuple],
                    Base_vehicleid_to_plan: Dict[str, List[Node]],
                    PDG_map: Dict[str, List[Node]],
                    min_diversity: float = 0.15 ) -> List[Chromosome]:
    """Duy trì độ đa dạng của quần thể"""
    if config.is_timeout():
        print("Timeout detected in maintain_diversity", file=sys.stderr)
        return population  # ✅ Return population hiện tại
    
    diversity = calculate_diversity(population)
    fitness_diversity = calculate_fitness_diversity(population)
    
    # Nếu độ đa dạng quá thấp
    if diversity < min_diversity or fitness_diversity < min_diversity:
        print("Low diversity detected, applying diversity maintenance...")
        
        # Sắp xếp theo fitness
        population.sort(key=lambda x: x.fitness)
        
        # Giữ lại elite (30% tốt nhất)
        elite_size = max(2, len(population) // 2)
        elite = population[:elite_size]
        
        # Loại bỏ các cá thể quá giống nhau
        unique_population = remove_similar_individuals(elite, threshold=0.1)
        
        # Tạo cá thể mới để bù đắp
        new_individuals = []
        needed = config.POPULATION_SIZE - len(unique_population)
        
        for i in range(needed):
            if config.is_timeout():
                print(f"Timeout during creating new individuals, created {i}/{needed}", file=sys.stderr)
                break
            
            # Tạo cá thể mới bằng nhiều phương pháp khác nhau
            if random.random() < 0.5:
                # Tạo hoàn toàn ngẫu nhiên
                new_individual = generate_single_random_chromosome(Base_vehicleid_to_plan, route_map, id_to_vehicle, PDG_map)
            else:
                # Random crossover từ elite
                if random.random() < 0.5 and len(unique_population) > 2:
                    parent1, parent2 = random.sample(elite, 2)
                    new_individual = parent1.crossover(parent2, PDG_map)
                else:
                    parent1 = random.sample(population , 1)[0]
                    new_individual = copy.deepcopy(parent1)
                
            new_individuals.append(new_individual)
        
        res_population = unique_population + new_individuals
        for c in res_population:
            if random.random() < config.MUTATION_RATE:
                new_mutation(c , False , 2)
        return res_population
    return population
