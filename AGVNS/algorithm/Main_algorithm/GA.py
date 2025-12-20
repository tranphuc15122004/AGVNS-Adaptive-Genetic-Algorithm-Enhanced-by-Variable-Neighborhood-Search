import time
from typing import Dict , List , Tuple 
from algorithm.Object import *
from algorithm.algorithm_config import *    
import random
from algorithm.engine import *
#from algorithm.Test_algorithm.GAVND2 import new_mutation

def GA(initial_vehicleid_to_plan : Dict[str , List[Node]] ,route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle] ,Unongoing_super_nodes : Dict[int , Dict[str, Node]] , Base_vehicleid_to_plan : Dict[str , List[Node]]) -> Chromosome:
    population : List[Chromosome] = []
    PDG_map : Dict[str , List[Node]] = {}
    population ,  PDG_map = generate_random_chromosome(initial_vehicleid_to_plan , route_map , id_to_vehicle , Unongoing_super_nodes , Base_vehicleid_to_plan  , POPULATION_SIZE)

    if population is None:
        print('Cant initialize the population')
        return None
    
    """ print()
    print(len(PDG_map))
    print(get_route_after(Base_vehicleid_to_plan , {})) """

    best_solution : Chromosome = None
    stagnant_generations = 0  # Biến đếm số thế hệ không cải thiện
    time_of_1_gen = 0
    population.sort(key= lambda x: x.fitness)
    best_solution = population[0]
    begintime = time.time()
    
    for gen in range(NUMBER_OF_GENERATION):
        new_population = []

        while len(new_population) < POPULATION_SIZE:
            parent1, parent2 = select_parents(population)
            child = parent1.crossover(parent2, PDG_map)
            new_population.append(child)
        # Sắp xếp lại quần thể và lấy 20 cá thể tốt nhất
        population.extend(new_population)
        population.sort(key=lambda x: x.fitness)
        population = population[:POPULATION_SIZE]

        """ for c in population:
            if random.uniform(0 , 1) <= MUTATION_RATE:
                c.mutate(True) """

        # Sắp xếp lại quần thể sau đột biến
        population.sort(key=lambda x: x.fitness)

        # Cập nhật giải pháp tốt nhất từ quần thể đã đột biến
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = population[0]
            stagnant_generations = 0
        else:
            stagnant_generations += 1

        # Điều kiện dừng sớm nếu không có cải thiện
        if stagnant_generations >= 10:
            print("Stopping early due to lack of improvement.")
            break

        endtime = time.time()
        if time_of_1_gen == 0:
            time_of_1_gen = endtime - begintime
        used_time = endtime - begintime + time_of_1_gen
        if used_time > 10 * 60:
            print("TimeOut!!")
            break
        
        for c in population:
            print(get_route_after(c.solution , {})  , file= sys.stderr)
        print(f'Generation {gen+1}: Best fittness = {best_solution.fitness} , Worst fittness = {population[-1].fitness} , Average = {sum([c.fitness for c in population]) / len(population)}')
            
    return best_solution      

def GA1LS(initial_vehicleid_to_plan : Dict[str , List[Node]] ,route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle] ,Unongoing_super_nodes : Dict[int , Dict[str, Node]] , Base_vehicleid_to_plan : Dict[str , List[Node]]) -> Chromosome:
    population : List[Chromosome] = []
    PDG_map : Dict[str , List[Node]] = {}
    population ,  PDG_map = generate_random_chromosome(initial_vehicleid_to_plan , route_map , id_to_vehicle , Unongoing_super_nodes , Base_vehicleid_to_plan  , POPULATION_SIZE)


    if population is None:
        print('Cant initialize the population')
        return None
    
    """ print()
    print(len(PDG_map))
    print(get_route_after(Base_vehicleid_to_plan , {})) """

    best_solution : Chromosome = None
    stagnant_generations = 0  # Biến đếm số thế hệ không cải thiện
    time_of_1_gen = 0
    population.sort(key= lambda x: x.fitness)
    best_solution = population[0]
    begintime = time.time()
    
    for gen in range(NUMBER_OF_GENERATION):
        new_population = []

        while len(new_population) < POPULATION_SIZE:
            parent1, parent2 = select_parents(population)
            child = parent1.crossover(parent2, PDG_map)
            new_population.append(child)
        # Sắp xếp lại quần thể và lấy 20 cá thể tốt nhất
        population.extend(new_population)
        population.sort(key=lambda x: x.fitness)
        population = population[:POPULATION_SIZE]

        for c in population:
            if random.uniform(0 , 1) <= MUTATION_RATE:
                c.mutate(True , True)

        # Sắp xếp lại quần thể sau đột biến
        population.sort(key=lambda x: x.fitness)

        # Cập nhật giải pháp tốt nhất từ quần thể đã đột biến
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = population[0]
            stagnant_generations = 0
        else:
            stagnant_generations += 1

        # Điều kiện dừng sớm nếu không có cải thiện
        if stagnant_generations >= 10:
            print("Stopping early due to lack of improvement.")
            break

        endtime = time.time()
        if time_of_1_gen == 0:
            time_of_1_gen = endtime - begintime
        used_time = endtime - begintime + time_of_1_gen
        if used_time > 10 * 60:
            print("TimeOut!!")
            break
        
        for c in population:
            print(get_route_after(c.solution , {})  , file= sys.stderr)
        #print(f'Generation {gen+1}: Best Fitness = {best_solution.fitness}')
        print(f'Generation {gen+1}: Best fittness = {best_solution.fitness} , Worst fittness = {population[-1].fitness} , Average = {sum([c.fitness for c in population]) / len(population)}')
        
    return best_solution


def GA5LS(initial_vehicleid_to_plan : Dict[str , List[Node]] ,route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle] ,Unongoing_super_nodes : Dict[int , Dict[str, Node]] , Base_vehicleid_to_plan : Dict[str , List[Node]]) -> Chromosome:
    population : List[Chromosome] = []
    PDG_map : Dict[str , List[Node]] = {}
    population ,  PDG_map = generate_random_chromosome(initial_vehicleid_to_plan , route_map , id_to_vehicle , Unongoing_super_nodes , Base_vehicleid_to_plan  , POPULATION_SIZE)

    if population is None:
        print('Cant initialize the population')
        return None

    best_solution : Chromosome = None
    stagnant_generations = 0  # Biến đếm số thế hệ không cải thiện
    time_of_1_gen = 0
    population.sort(key= lambda x: x.fitness)
    best_solution = population[0]
    begintime = time.time()

    for gen in range(NUMBER_OF_GENERATION):
        new_population = []

        while len(new_population) < POPULATION_SIZE:
            parent1, parent2 = select_parents(population)
            """ child = parent1.crossover(parent2, PDG_map)
            new_population.append(child) """
            child1 , child2 = new_crossover(parent1 , parent2 , PDG_map)
            if child1:
                new_population.append(child1)
            if child2:
                new_population.append(child2)
        # Sắp xếp lại quần thể và lấy 20 cá thể tốt nhất
        population.extend(new_population)
        population.sort(key=lambda x: x.fitness)
        population = population[:POPULATION_SIZE]

        """ for c in population:
            if random.uniform(0 , 1) <= MUTATION_RATE:
                c.mutate(True , False) """

        # Sắp xếp lại quần thể sau đột biến
        population.sort(key=lambda x: x.fitness)

        # Cập nhật giải pháp tốt nhất từ quần thể đã đột biến
        if best_solution is None or population[0].fitness < best_solution.fitness:
            best_solution = population[0]
            stagnant_generations = 0
        else:
            stagnant_generations += 1

        # Điều kiện dừng sớm nếu không có cải thiện
        if stagnant_generations >= 10:
            print("Stopping early due to lack of improvement.")
            break

        endtime = time.time()
        if time_of_1_gen == 0:
            time_of_1_gen = endtime - begintime
        used_time = endtime - begintime + time_of_1_gen
        if used_time > 9*60+30:
            print("TimeOut!!")
            break

        for c in population:
            print(get_route_after(c.solution , {})  , file= sys.stderr)
        #print(f'Generation {gen+1}: Best Fitness = {best_solution.fitness}')
        print(f'Generation {gen+1}: Best fittness = {best_solution.fitness} , Worst fittness = {population[-1].fitness} , Average = {sum([c.fitness for c in population]) / len(population)}')
    return best_solution

# Chọn lọc cha mẹ bằng phương pháp tournament selection
def select_parents(population: List[Chromosome]) -> Tuple[Chromosome, Chromosome]:
    def tournament_selection():
        tournament_size = max(2, len(population) // 10)
        candidates = random.sample(population, tournament_size)
        return min(candidates, key=lambda x: x.fitness)
    return tournament_selection(), tournament_selection()

def generate_random_chromosome(initial_vehicleid_to_plan : Dict[str , List[Node]],  route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes : Dict[int , Dict[str, Node]]  ,Base_vehicleid_to_plan : Dict[str , List[Node]] , quantity : int):
    ls_node_pair_num = len(Unongoing_super_nodes)
    if ls_node_pair_num == 0:
        return None , None

    #Quan the
    population : List[Chromosome] = []
    number_of_node = 0
    for plan in initial_vehicleid_to_plan.values():
        number_of_node += len(plan)
    
    pdg_Map : Dict[str , List[Node]] = {}
    
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
            pdg_Map[k] = node_list
    if len(pdg_Map) < 2:
        return None , None
    
    # Tao quan the
    while len(population) < quantity:
        temp_route: Dict[str , List[Node]] = {}
        for vehicleID , plan in Base_vehicleid_to_plan.items():
            temp_route[vehicleID] = []
            for node in plan:
                temp_route[vehicleID].append(node)
        
        # Chen ngau nhien cac super node vao cac lo trinh cua cac xe 
        for DPG in pdg_Map.values():
            # Khai bao cac bien lien quan
            # chen vao sau cac tuyen duong
            if random.uniform(0 , 1) <= 0.25:
                isExhausive = False
                route_node_list : List[Node] = []
                selected_vehicleID = random.choice(list(Base_vehicleid_to_plan.keys()))
                if DPG:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(DPG , id_to_vehicle , temp_route , route_map , selected_vehicleID)
                
                route_node_list = temp_route.get(bestInsertVehicleID , [])

                if isExhausive:
                    route_node_list = bestNodeList[:]
                else:
                    if route_node_list is None:
                        route_node_list = []
                    
                    new_order_pickup_node = DPG[0]
                    new_order_delivery_node = DPG[1]
                    
                    route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                    route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                temp_route[bestInsertVehicleID] = route_node_list
            else:
                if random.uniform(0 , 1) <= 0.5:
                    selected_vehicleID = random.choice(list(id_to_vehicle.keys()))
                    selected_vehicle = id_to_vehicle[selected_vehicleID]
                    
                    temp_route[selected_vehicleID].extend(DPG)
                else:
                    random_dispatch_nodePair(DPG , id_to_vehicle , temp_route)
                
        # Da tao xong mot ca the moi
        if len(temp_route) == len(id_to_vehicle):
            temp = 0
            for vehicle_route in temp_route.values():
                temp += len(vehicle_route)
            if temp == number_of_node:
                population.append(Chromosome(temp_route , route_map , id_to_vehicle ))
    population.append(Chromosome(initial_vehicleid_to_plan , route_map , id_to_vehicle))
    return population , pdg_Map 

def new_crossover(parent1: Chromosome , parent2: Chromosome , PDG_map : Dict[str , List[Node]]):
    
    # Cac super node
    new_PDG_map : Dict[str , List[Node]] = {}
    for key , value in PDG_map.items():
        key = f'{len(value[0].pickup_item_list)}_{value[0].pickup_item_list[0].id}'
        new_PDG_map[key] = value
    
    # Khởi tạo lời giải con là rỗng -> điều kiện dừng của vòng lặp sẽ là kiểm tra child đã được thêm tất cả các tuyền đường từ cha và mẹ
    child_solution_1 :Dict[str, List[Node]] = {vehicleID:[] for vehicleID in parent1.id_to_vehicle.keys()}
    child_solution_2 :Dict[str, List[Node]] = {vehicleID:[] for vehicleID in parent1.id_to_vehicle.keys()}
    
    check_valid_1 : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    check_valid_2 : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    
    # thêm các tuyến tuyến đường một cách ngẫu nhiên cho 2 lời giải con
    for vehicleID in parent1.id_to_vehicle.keys():
        if random.uniform(0 , 1) < 0.5:
            for node in parent1.solution[vehicleID]:
                child_solution_1[vehicleID].append(copy.deepcopy(node))
            for node in parent2.solution[vehicleID]:
                child_solution_2[vehicleID].append(copy.deepcopy(node))
        else:
            for node in parent2.solution[vehicleID]:
                child_solution_1[vehicleID].append(copy.deepcopy(node))
            for node in parent1.solution[vehicleID]:
                child_solution_2[vehicleID].append(copy.deepcopy(node))
    
    #Kiểm tra các cặp node còn thiếu
    # Lưu các nút thừa trong tuyến đường hiện tại
    for vehicleID in parent1.id_to_vehicle.keys():
        redundant = []
        del_index = []
        # Duyệt ngược danh sách để tìm và xóa nút thừa    
        for i in range(len(child_solution_1[vehicleID]) - 1, -1, -1):  
            node = child_solution_1[vehicleID][i]
            
            if node.pickup_item_list:
                if redundant and node.pickup_item_list[0].id == redundant[-1]:
                    redundant.pop()  # Loại bỏ phần tử tương ứng trong danh sách `redundant`
                    del_index.append(i)
            else:
                key = f'{len(node.delivery_item_list)}_{node.delivery_item_list[-1].id}'
                
                if key in new_PDG_map:
                    check_valid_1[key] += 1
                    
                    # nếu tìm được một super node thừa
                    if check_valid_1[key] > 1:
                        first_itemID_of_redundant_supernode = key.split('_')[-1]
                        redundant.append(first_itemID_of_redundant_supernode)
                        print(f"Redundant nodes: {redundant}" , file= sys.stderr)

                        # Xóa node giao của super node thừa
                        del_index.append(i)
                        print('Đã xóa 1 super node thừa' , file= sys.stderr)
        for i in del_index:
            child_solution_1[vehicleID].pop(i)
        
    #xóa các cặp node thừa cho xe 2
    for vehicleID in parent2.id_to_vehicle.keys():
        redundant = []
        del_index = []
        # Duyệt ngược danh sách để tìm và xóa nút thừa    
        for i in range(len(child_solution_2[vehicleID]) - 1, -1, -1):  
            node = child_solution_2[vehicleID][i]
            
            if node.pickup_item_list:
                if redundant and node.pickup_item_list[0].id == redundant[-1]:
                    redundant.pop()  # Loại bỏ phần tử tương ứng trong danh sách `redundant`
                    del_index.append(i)
            else:
                key = f'{len(node.delivery_item_list)}_{node.delivery_item_list[-1].id}'
                
                if key in new_PDG_map:
                    check_valid_2[key] += 1
                    
                    # nếu tìm được một super node thừa
                    if check_valid_2[key] > 1:
                        first_itemID_of_redundant_supernode = key.split('_')[-1]
                        redundant.append(first_itemID_of_redundant_supernode)
                        print(f"Redundant nodes: {redundant}" , file= sys.stderr)

                        # Xóa node giao của super node thừa
                        del_index.append(i)
                        print('Đã xóa 1 super node thừa' , file= sys.stderr)
        for i in del_index:
            child_solution_2[vehicleID].pop(i)
    
    #kiểm tra xem tổng số các node có bằng với số các node yêu cầu không
    node_num = 0
    for k, v in parent1.solution.items():
        node_num += len(v)
    child1_node_num = 0
    child2_node_num = 0
    for k, v in child_solution_1.items():
        child1_node_num += len(v)
    for key, value in check_valid_1.items():
        if value == 0:
            child1_node_num += 2
    
    for k, v in child_solution_2.items():
        child2_node_num += len(v)
    for key, value in check_valid_2.items():
        if value == 0:
            child2_node_num += 2    
    
    if child1_node_num != node_num or child2_node_num != node_num:
        return None , None
    
    #Tối ưu các lời giải relaxation con
    sorted_child_solution_1 = sorted(child_solution_1.items() ,  key=lambda x: int(x[0].split('_')[1]))
    child_solution_1.clear()
    child_solution_1.update(sorted_child_solution_1)
    child_1 = Chromosome(child_solution_1 , parent1.route_map , parent1.id_to_vehicle)
    
    sorted_child_solution_2 = sorted(child_solution_2.items() ,  key=lambda x: int(x[0].split('_')[1]))
    child_solution_2.clear()
    child_solution_2.update(sorted_child_solution_2)
    child_2 = Chromosome(child_solution_2 , parent2.route_map , parent2.id_to_vehicle)
    
    new_mutation(child_1 , False , 1)
    new_mutation(child_2 , False , 1)
    
    # Kiem tra lai và thêm các node còn thiếu solution 1        
    for key, value in check_valid_1.items():
        if value == 0:
            if random.uniform(0 , 1) < 0.5:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                node_list = new_PDG_map[key]
                isExhausive = False
                route_node_list : List[Node] = []
                
                if node_list:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(node_list , parent1.id_to_vehicle , child_solution_1 , parent1.route_map)
                    
                route_node_list = child_solution_1.get(bestInsertVehicleID , [])

                if isExhausive:
                    route_node_list = bestNodeList[:]
                else:
                    if route_node_list is None:
                        route_node_list = []
                    
                    new_order_pickup_node = node_list[0]
                    new_order_delivery_node = node_list[1]
                    
                    route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                    route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                child_solution_1[bestInsertVehicleID] = route_node_list
            else:
                node_list = new_PDG_map[key]
                if random.uniform(0 , 1) < 0.25:
                    # Random vehicle
                    selected_vehicleID = random.choice(list(parent1.id_to_vehicle.keys()))
                    child_solution_1[selected_vehicleID].extend(node_list)
                else:
                    # Random dispatch
                    random_dispatch_nodePair(node_list, parent1.id_to_vehicle, child_solution_1)
            
            print('Cập nhật super node còn thiếu' , file= sys.stderr)
            
    # Kiem tra lai và thêm các node còn thiếu solution 2      
    for key, value in check_valid_2.items():
        if value == 0:
            if random.uniform(0 , 1) < 0.5:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                node_list = new_PDG_map[key]
                isExhausive = False
                route_node_list : List[Node] = []
                
                if node_list:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(node_list , parent2.id_to_vehicle , child_solution_2 , parent2.route_map)
                    
                route_node_list = child_solution_2.get(bestInsertVehicleID , [])

                if isExhausive:
                    route_node_list = bestNodeList[:]
                else:
                    if route_node_list is None:
                        route_node_list = []
                    
                    new_order_pickup_node = node_list[0]
                    new_order_delivery_node = node_list[1]
                    
                    route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                    route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                child_solution_2[bestInsertVehicleID] = route_node_list
            else:
                node_list = new_PDG_map[key]
                if random.uniform(0 , 1) < 0.25:
                    # Random vehicle
                    selected_vehicleID = random.choice(list(parent2.id_to_vehicle.keys()))
                    child_solution_2[selected_vehicleID].extend(node_list)
                else:
                    # Random dispatch
                    random_dispatch_nodePair(node_list, parent2.id_to_vehicle, child_solution_2)
            
            print('Cập nhật super node còn thiếu' , file= sys.stderr)
    
    #child_1.fitness = child_1.evaluate_fitness()
    #child_2.fitness = child_2.evaluate_fitness()
    return child_1 , child_2