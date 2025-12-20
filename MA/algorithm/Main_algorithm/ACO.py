import time
from typing import Dict , List , Tuple 
from algorithm.Object import *
from algorithm.algorithm_config import *    
import random
from algorithm.engine import *

def ACO(initial_vehicleid_to_plan : Dict[str , List[Node]] ,route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle] ,Unongoing_super_nodes : Dict[int , Dict[str, Node]] , Base_vehicleid_to_plan : Dict[str , List[Node]]) -> Chromosome:
    # --- Khởi tạo ---
    super_node_map : List[List[Node]] = Build_supernodes_map(Unongoing_super_nodes)
    if not super_node_map: 
        return None
    
    pheromone_map: Dict[Tuple[str, str], float] = initialize_pheromone(super_node_map , Base_vehicleid_to_plan , id_to_vehicle)

    heuristic_map: Dict[Tuple[str, str], float] = calculate_heuristic(pheromone_map , route_map )
    
    best_solution: Chromosome = None
    best_fitness = float('inf')
    stagnant_generations = 0
    time_of_1_iter = 0
    begintime = time.time()

    for iteration in range(NUMBER_OF_GENERATION_ACO):  # Tương tự số thế hệ trong GA
        ants: List[Chromosome] = []

        # --- Mỗi "ant" tạo một lời giải ---
        #for _ in range(POPULATION_SIZE):
        while len(ants) < POPULATION_SIZE_ACO:
            solution = construct_solution(Base_vehicleid_to_plan , super_node_map , pheromone_map , heuristic_map , route_map , id_to_vehicle)
            if solution:
                ants.append(solution)
                print(len(ants) , file= sys.stderr)

        # --- Cập nhật pheromone ---
        update_pheromone(pheromone_map, ants  , id_to_vehicle)

        # --- Tìm giải pháp tốt nhất ---
        ants.sort(key=lambda x: x.fitness)
        if best_solution is None or ants[0].fitness < best_fitness:
            best_solution = ants[0]
            best_fitness = ants[0].fitness
            stagnant_generations = 0
        else:
            stagnant_generations += 1

        # --- In kết quả ---
        """ for a in ants:
            print(get_route_after(a.solution, {}), file=sys.stderr) """

        print(f'Iteration {iteration + 1}: Best fittness = {best_fitness} , Worst fittness = {ants[-1].fitness} , Average = {sum(a.fitness for a in ants) / len(ants)}')

        # --- Điều kiện dừng ---
        if stagnant_generations >= 200:
            print("Stopping early due to stagnation.")
            break

        endtime = time.time()
        if time_of_1_iter == 0:
            time_of_1_iter = endtime - begintime
        used_time = endtime - begintime + time_of_1_iter
        if used_time > 10 * 60:
            print("TimeOut!!")
            break

    return best_solution

# Hoàn thiện
def Build_supernodes_map(Unongoing_super_nodes : Dict[int , Dict[str, Node]] ) -> List[List[Node]]:
    pdg_Map : List[List[Node]] = []
    
    # tao Dict cac super node
    for idx, pdg in Unongoing_super_nodes.items():
        pickup_node = None
        delivery_node = None
        node_list: List[Node] = []
        index = 0

        if pdg:
            vehicleID = ''
            for v_and_pos_str, node in (pdg.items()):
                vehicleID = v_and_pos_str.split(",")[0]
                if index % 2 == 0:
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
            pdg_Map.append(node_list)
    
    if len(pdg_Map) < 2:
        return None
    return pdg_Map

def initialize_pheromone( super_node_map: List[List[Node]]  ,  Base_vehicleid_to_plan : Dict[str , List[Node]] , id_to_vehicle: Dict[str, Vehicle]) -> Dict[Tuple[str, str], float]:
    pheromone_map = {}
    
    # Nếu không có super_node_map hoặc trống
    if not super_node_map:
        return pheromone_map
    
    # Trích xuất tất cả các node từ super_node_map
    all_nodes : List[Node] = []
    unique_id = set()
    
    # Thêm các node trong lời giải cố định mà không phải đích đến hiện tại của xe
    # Do các đơn hàng đó vẫn có thể được đảo ngẫu nhiên trong tuyến đường
    for plan in Base_vehicleid_to_plan.values():
        for node in plan:
            all_nodes.append(node)
    
    # Thu thập tất cả các node và tạo ánh xạ node đón -> node trả
    for node_pair in super_node_map:
        if len(node_pair) >= 2:
            pickup_node = node_pair[0]
            delivery_node = node_pair[1]
            all_nodes.extend([pickup_node, delivery_node])
    
    # Thêm vị trí hiện tại của các xe vào ma trận
    for vehicleID , vehicle in id_to_vehicle.items():
        temp_node = Node(vehicle.cur_factory_id , [] , [])
        all_nodes.append(temp_node)
    
    # Khởi tạo pheromone cho mọi cặp node có thể
    for node1 in all_nodes:
        for node2 in all_nodes:
            # Chuyển đổi ID thành chuỗi để dùng làm key
            node1_id = str(node1.id)
            node2_id = str(node2.id)
            unique_id.add(node1_id)
            unique_id.add(node2_id)
            
            # Giá trị pheromone mặc định
            pheromone_value = BASE_PHEROMONE
            
            # Lưu vào ma trận pheromone
            pheromone_map[(node1_id, node2_id)] = pheromone_value
    #print(len(unique_id))
    return pheromone_map

# Không bị ảnh hưởng nếu thay đổi cấu trúc của ma trận pheromone
def calculate_heuristic(pheromone_map: Dict[Tuple[str, str], float] , route_map: Dict[Tuple, Tuple] ) -> Dict[Tuple[str, str], float]:
    """
    Tính toán và chuẩn hóa giá trị heuristic cho các cặp node.
    Sử dụng giá trị trung bình làm giá trị mặc định.
    """
    heuristic_raw = {}
    heuristic_map = {}
    
    # Bước 1: Tính giá trị heuristic thô cho các cặp có trong route_map
    valid_values = []  # Để tính giá trị trung bình sau này
    
    for (node1_id, node2_id) in pheromone_map.keys():
        key = (node1_id, node2_id)
        if key in route_map:
            distance, time = route_map[key]
            check = False
            # Xử lý trường hợp đặc biệt để tránh chia cho 0
            if distance <= 0:
                check = True
                distance = 0.4
            
            if time <= 0:
                check = True
                time = 0.4
                
            # Tính giá trị heuristic (tỷ lệ nghịch với khoảng cách và thời gian)
            distance_heuristic = 1.0 / distance
            time_heuristic = 1.0 / (time / 3600)
            value = (distance_heuristic +  time_heuristic) 
            if not check:
                valid_values.append(value)
            heuristic_raw[key] = value
    
    # Tính giá trị mặc định là trung bình của các giá trị đã tính
    DEFAULT_HEURISTIC = 0.01  # Giá trị mặc định ban đầu
    if valid_values:
        DEFAULT_HEURISTIC = sum(valid_values) / len(valid_values)
    
    # Bước 2: Áp dụng giá trị mặc định cho các cặp không có trong route_map
    for (node1_id, node2_id) in pheromone_map.keys():
        key = (node1_id, node2_id)
        if key not in heuristic_raw:
            heuristic_raw[key] = DEFAULT_HEURISTIC
    
    # Bước 3: Chuẩn hóa giá trị heuristic
    if heuristic_raw:
        # Tìm giá trị min và max
        min_value = min(heuristic_raw.values())
        max_value = max(heuristic_raw.values())
        
        # Tránh chia cho 0 nếu tất cả các giá trị bằng nhau
        range_value = max_value - min_value
        if range_value == 0:
            # Nếu tất cả giá trị bằng nhau, đặt mọi giá trị heuristic = 1
            for key in heuristic_raw:
                heuristic_map[key] = 1.0
        else:
            # Chuẩn hóa về khoảng [0.1, 1.0]
            for key, value in heuristic_raw.items():
                normalized = 0.1 + 0.9 * ((value - min_value) / range_value)
                heuristic_map[key] = normalized
    
    return heuristic_map

def update_pheromone(pheromone_map: Dict[Tuple[str, str], float], ants: List[Chromosome] , id_to_vehicle: Dict[str, Vehicle]):
    if not ants:
        return
    
    # Tham số điều chỉnh
    MIN_PHEROMONE = 0.1     # Giá trị pheromone tối thiểu
    MAX_PHEROMONE = 1.0     # Giá trị pheromone tối đa
    ELITE_ANT_FACTOR = 2.0  # Hệ số tăng cường cho kiến tốt nhất
    
    # Bước 1: Bay hơi pheromone trên tất cả các cạnh
    for key in pheromone_map:
        pheromone_map[key] = max(MIN_PHEROMONE, pheromone_map[key] * (1 - EVAPORATION_RATE))
    
    # Bước 2: Tăng cường pheromone trên các cạnh thuộc lời giải tốt
    # Sắp xếp kiến theo chất lượng (fitness thấp là tốt hơn)
    sorted_ants = sorted(ants, key=lambda x: x.fitness)
    
    # Xác định số lượng kiến ưu tú để tăng cường pheromone
    num_best_ants = max(1, min(1, len(sorted_ants) // 3))
    
    # Tăng cường pheromone cho những kiến tốt nhất
    for i in range(num_best_ants):
        ant = sorted_ants[i]
        # Trọng số giảm dần theo thứ hạng (kiến tốt hơn có trọng số cao hơn)
        weight = 1.0 / (i + 1)
        
        # Hệ số đặc biệt cho kiến tốt nhất
        if i == 0:
            weight *= ELITE_ANT_FACTOR
        
        # Duyệt qua từng phương tiện và tuyến đường của nó
        for vehicle_id, nodes in ant.solution.items():
            """ len_fixed_nodes = len(Base_vehicleid_to_plan[vehicle_id])
            if len(nodes) == len_fixed_nodes:
                continue """
            # Cập nhật tuyến đường từ điểm đầu tiên với những xe không có DES
            vehicle = id_to_vehicle[vehicle_id]
            if not vehicle.des and nodes:
                key = (vehicle.cur_factory_id  , nodes[0].id)
                if key in pheromone_map:
                    # Lượng pheromone thêm vào tỷ lệ nghịch với fitness
                    # và tỷ lệ thuận với trọng số của kiến
                    delta_pheromone = weight / max(0.05, ant.fitness / 1000.0)
                    pheromone_map[key] = min(MAX_PHEROMONE, pheromone_map[key] + delta_pheromone)
            
            # Duyệt qua các cặp node liên tiếp
            for j in range(len(nodes) - 1):
                node1_id = str(nodes[j].id)
                node2_id = str(nodes[j + 1].id)
                
                # Tạo key để truy cập pheromone_map
                key = (node1_id, node2_id)
                
                if key in pheromone_map:
                    # Lượng pheromone thêm vào tỷ lệ nghịch với fitness
                    # và tỷ lệ thuận với trọng số của kiến
                    delta_pheromone = weight / max(0.05, ant.fitness / 1000.0)
                    pheromone_map[key] = min(MAX_PHEROMONE, pheromone_map[key] + delta_pheromone)
    
    # Bước 3 (tùy chọn): Chuẩn hóa lại nếu cần
    # Đảm bảo tất cả các giá trị pheromone nằm trong khoảng [MIN_PHEROMONE, MAX_PHEROMONE]
    for key in pheromone_map:
        pheromone_map[key] = max(MIN_PHEROMONE, min(MAX_PHEROMONE, pheromone_map[key]))

def construct_solution(Base_vehicleid_to_plan: Dict[str, List[Node]], super_node_map : List[List[Node]],
                    pheromone_map: Dict[Tuple[str, str], float], 
                    heuristic_map: Dict[Tuple[str, str], float], 
                    route_map: Dict[Tuple, Tuple], 
                    id_to_vehicle: Dict[str, Vehicle]) -> Chromosome:    
    # Tạo bản sao của kế hoạch cơ sở để tránh thay đổi bản gốc
    solution : Dict[str ,List[Node]] = {}
    is_fesible_solution = True
    # Lưu trữ các node có thể đổi chỗ trong base soluion
    # Mỗi phần mảng được coi như là một Stack các node nhận háng với node ở trên đầu là node cần được chèn vào để đảm bảo tính FILO
    fixed_nodes_in_vehicle :Dict[str , List[Node]] = {}
    
    for vehicle_id, fixed_nodes in Base_vehicleid_to_plan.items():
        solution[vehicle_id] = []
        fixed_nodes_in_vehicle[vehicle_id] = []
        vehicle = id_to_vehicle[vehicle_id]
        
        start_idx = 1 if vehicle.des else 0
        
        if vehicle.des and len(fixed_nodes) != 0:
            solution[vehicle_id].append(fixed_nodes[0])
        
        if len(fixed_nodes) >= 2: 
            fixed_nodes_in_vehicle[vehicle_id].extend(reversed(fixed_nodes[start_idx:]))
            #fixed_nodes_in_vehicle[vehicle_id].extend(fixed_nodes[start_idx:])
    
    # Xáo trộn các cặp điểm để tăng tính ngẫu nhiên
    unassigned_pairs: List[List[Node]] = list(super_node_map)
    random.shuffle(unassigned_pairs)

    while True:
        # Biến kiểm tra điều kiện dừng
        check_terminate = True
        if unassigned_pairs:
            check_terminate = False
        for v in fixed_nodes_in_vehicle.values():
            if len(v) != 0:
                check_terminate = False
                break
        if check_terminate: 
            #print ('end loop' , file= sys.stderr)
            break
        
        # --- tính toán giá trị hấp dẫn của tất cả các tuyến đường ---
        attraction_dict : Dict[str , List[Tuple[Node , float]]]= {vID:[] for vID in id_to_vehicle}
        # Xét từng xe để tính toán giá trị hấp dẫn tại tất cả các xe
        for vehicleID , plan in solution.items():
            vehicle = id_to_vehicle[vehicleID]
            
            # Xây dựng các node có thể gán trong 
            considered_nodes : List[Node]= []
            # Thêm các node pickup của các cặp chưa được gán 
            considered_nodes.extend(item[0] for item in unassigned_pairs if len(item) == 2)
            # Thêm các node cố định không thể gán vào xe khác
            if len(fixed_nodes_in_vehicle[vehicleID]) != 0:
                considered_nodes.append(fixed_nodes_in_vehicle[vehicleID][-1])

            # Tính toán độ hấp dẫn của tất cả các node
            for node in considered_nodes:
                # Tính độ hấp dẫn dựa trên pheromone và heuristic
                attraction = calculate_node_attraction(plan, node, pheromone_map, heuristic_map, vehicle , route_map)
                
                # Thêm vào danh sách độ hấp dẫn
                attraction_dict[vehicleID].append((node, attraction))
        # Tính toán xem node nào sẽ được gán vào xe nào:
        # Chuyển sang phương pháp lựa chọn có xác suất (Roulette Wheel Selection)
        all_candidates = []  # [(vehicle_id, node, attraction_value), ...]
        total_attraction = 0
        
        # Thu thập tất cả các ứng viên và tính tổng độ hấp dẫn
        for vehicle_id, attractions in attraction_dict.items():
            for node, attraction_value in attractions:
                if attraction_value > 0:  # Chỉ xét các node khả thi
                    all_candidates.append((vehicle_id, node, attraction_value))
                    total_attraction += attraction_value
        # Nếu không có ứng viên nào khả thi
        if not all_candidates or len(all_candidates) == 0 or total_attraction <= 0:
            #print('error 1' , file= sys.stderr)
            is_fesible_solution = False
        
        # Tính xác suất chọn cho mỗi ứng viên
        probabilities = [attr / total_attraction for _, _, attr in all_candidates]
        
        # Lựa chọn dựa trên xác suất (Roulette wheel)
        r = random.random()
        cumulative_prob = 0
        selected_idx = -1
        
        for i, prob in enumerate(probabilities):
            cumulative_prob += prob
            if r <= cumulative_prob:
                selected_idx = i
                break
        
        # Nếu có vấn đề với quá trình lựa chọn, lấy ứng viên cuối cùng
        if selected_idx == -1:
            selected_idx = len(all_candidates) - 1
        
        # Lấy thông tin node và vehicle được chọn
        best_vehicle_id, best_node, _ = all_candidates[selected_idx]
        
        # Thêm node được chọn vào tuyến đường
        solution[best_vehicle_id].append(best_node)
        
        # Loại bỏ node đã gán khỏi danh sách cần gán và lặp lại quá trình gán node tiếp theo
        # Nếu là node từ unassigned_pairs (node pickup)
        if best_node.pickup_item_list and not best_node.delivery_item_list:
            is_pickup = True
        else: 
            is_pickup = False

        # Nếu không phải node pickup, tức là node từ fixed_nodes_in_vehicle
        if not is_pickup:
            # Loại bỏ node khỏi fixed_nodes_in_vehicle
            fixed_nodes = fixed_nodes_in_vehicle[best_vehicle_id]
            for i, node in enumerate(fixed_nodes):
                if node.id == best_node.id and node.delivery_item_list[-1].id == best_node.delivery_item_list[-1].id :
                    fixed_nodes.pop(i)
                    break
        else:
            for i, pair in enumerate(unassigned_pairs):
                if len(pair) >= 2 and pair[0].id == best_node.id and pair[0].pickup_item_list[0].id == best_node.pickup_item_list[0].id :
                    # Thêm delivery node vào fixed_nodes_in_vehicle
                    delivery_node = pair[1]
                    fixed_nodes_in_vehicle[best_vehicle_id].append(delivery_node)
                    # Loại bỏ cặp node khỏi unassigned_pairs
                    unassigned_pairs.pop(i)
                    break
    
    
    for vehicleID ,  plan in solution.items():
        vehicle = id_to_vehicle[vehicleID]
        carrying_items = vehicle.carrying_items if vehicle.des else []
        if not isFeasible(plan ,carrying_items , vehicle.board_capacity):
            #print('error 2' , file= sys.stderr)
            is_fesible_solution = False
            
    if is_fesible_solution is False:
        solution = repair_solution(solution , Base_vehicleid_to_plan , id_to_vehicle , route_map)
        if solution is None:
            #print('error 3' , file= sys.stderr)
            return None
    chromosome = Chromosome(solution, route_map , id_to_vehicle)
    return chromosome

def repair_solution(solution: Dict[str, List[Node]], Base_vehicleid_to_plan: Dict[str, List[Node]], 
                    id_to_vehicle: Dict[str, Vehicle], route_map: Dict[Tuple, Tuple]) -> Dict[str, List[Node]]:
    """Sửa chữa các lời giải không khả thi bằng cách làm việc với cặp pickup-delivery."""
    
    # Phát hiện các xe có tuyến đường không khả thi
    error_vehicles = []
    for vehicleID, plan in solution.items():
        vehicle = id_to_vehicle[vehicleID]
        carrying_items = vehicle.carrying_items.copy() if vehicle.des else []

        if not isFeasible(plan, carrying_items, vehicle.board_capacity):
            error_vehicles.append(vehicleID)

    if not error_vehicles:
        return solution  # Lời giải đã khả thi

    # Step 1: Xây dựng dictionary ánh xạ vehicleID -> các số đánh dấu các cặp trong tuyến đường
    pair_idx_in_vehicle = {vID: [] for vID in id_to_vehicle.keys()} 

    for vehicleID in error_vehicles:
        plan = solution[vehicleID]
        vehicle = id_to_vehicle[vehicleID]
        
        pair_idx_in_vehicle[vehicleID] = [0] * len(plan)
        start_idx = 1 if vehicle.des else 0
        count = 1
        st = []
        for i in range(start_idx, len(plan)):
            if plan[i].pickup_item_list:
                pair_idx_in_vehicle[vehicleID][i] = count
                st.append((plan[i].pickup_item_list[0].id , count))
                count += 1
            else:
                if st:
                    item_id, idx = st.pop()
                    if item_id == plan[i].delivery_item_list[-1].id:
                        pair_idx_in_vehicle[vehicleID][i] = idx
                else:
                    pair_idx_in_vehicle[vehicleID][i] = 0
                    

    # Step 2: Tạo danh sách các cặp node từ xe có tuyến đường không khả thi
    problematic_pairs : List[List[Node]] = []  
    
    repaired_solution = {vehicleID: [] for vehicleID in solution.keys()}
    for vehicleID in solution.keys():
        repaired_solution[vehicleID] = []
        repaired_solution[vehicleID].extend(solution[vehicleID])
    
    for vehicleID in error_vehicles:
        plan : List[Node] = []
        for node in solution[vehicleID]: plan.append(node)
        vehicle = id_to_vehicle[vehicleID]
        carrying_items = vehicle.carrying_items.copy() if vehicle.des else []
        
        pair_num = []
        for i in pair_idx_in_vehicle[vehicleID]:
            if i not in pair_num:
                pair_num.append(i)
        if 0 in pair_num:
            pair_num.remove(0)
        if not pair_num:
            continue
        
        # Tạo danh sách các cặp node có vấn đề
        while True:
            if not pair_num: break
            
            chosen_pair = random.choice(pair_num)
            pair_num.remove(chosen_pair)
            pickup_node = None
            delivery_node = None
            
            delete_idx = []
            for i in range(len(plan)):
                if pair_idx_in_vehicle[vehicleID][i] == chosen_pair:
                    if plan[i].pickup_item_list:
                        pickup_node = plan[i]
                        delete_idx.append(i)
                    elif plan[i].delivery_item_list:
                        delivery_node = plan[i]
                        delete_idx.append(i)
                    if pickup_node and delivery_node:
                        break
            
            
            plan = [node for i , node in enumerate(plan) if i not in delete_idx]
            pair_idx_in_vehicle[vehicleID] = [i for i in pair_idx_in_vehicle[vehicleID] if i != chosen_pair]
            problematic_pairs.append([pickup_node , delivery_node])
            
            if isFeasible(plan , carrying_items , vehicle.board_capacity):
                repaired_solution[vehicleID] = plan
                break
    
    # Step 3: Xáo trộn các cặp node có vấn đề
    random.shuffle(problematic_pairs)
    # Step 4: Gán lại các cặp node vào các xe
    # Chen ngau nhien cac super node vao cac lo trinh cua cac xe 
    for DPG in problematic_pairs:
        # Khai bao cac bien lien quan
        # chen theo cách tốt nhất
        isExhausive = False
        route_node_list : List[Node] = []
        selected_vehicleID = random.choice(list(Base_vehicleid_to_plan.keys()))
        if DPG:
            isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(DPG , id_to_vehicle , repaired_solution , route_map , selected_vehicleID)
        
        route_node_list = repaired_solution.get(bestInsertVehicleID , [])

        if isExhausive:
            route_node_list = bestNodeList[:]
        else:
            if route_node_list is None:
                route_node_list = []
            
            new_order_pickup_node = DPG[0]
            new_order_delivery_node = DPG[1]
            
            route_node_list.insert(bestInsertPosI, new_order_pickup_node)
            route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
        repaired_solution[bestInsertVehicleID] = route_node_list


    # Step 5: Kiểm tra cuối cùng
    all_feasible = True
    
    temp1 , tmep2 = 0 , 0
    for vehicleID, plan in repaired_solution.items():
        temp1 += len(plan)
    for vehicleID, plan in solution.items():
        tmep2 += len(plan)
    if temp1 != tmep2:
        all_feasible = False
    
    for vehicleID, plan in repaired_solution.items():
        vehicle = id_to_vehicle[vehicleID]
        carrying_items = vehicle.carrying_items.copy() if vehicle.des else []
        if not isFeasible(plan, carrying_items, vehicle.board_capacity):
            all_feasible = False
            break
    return repaired_solution if all_feasible else None

def calculate_node_attraction(route: List[Node], node: Node, pheromone_map: Dict[Tuple[str, str], float],heuristic_map: Dict[Tuple[str, str], float],vehicle: Vehicle , route_map) -> float:
    """
    Tính điểm hấp dẫn của việc thêm một node vào cuối tuyến đường.
    """
    
    temp_route :List[Node]= []
    temp_route.extend(route)
    last_node = temp_route[-1].id if temp_route else vehicle.cur_factory_id
    
    # Tính pheromone và heuristic từ node cuối cùng đến node mới
    key = (str(last_node), str(node.id))
    
    temp_route.append(node)
    """ carrying_items = vehicle.carrying_items if vehicle.des else []
    if not isFeasible(temp_route , carrying_items, vehicle.board_capacity):
        return 0.0 """
    
    
    # Tính độ hấp dẫn dựa trên công thức ACO tiêu chuẩn
    if key in pheromone_map and key in heuristic_map:
        pheromone = pheromone_map[key]
        heuristic = heuristic_map[key]
        if node.pickup_item_list:
            TW_heuristic = node.pickup_item_list[0].committed_completion_time
        else:
            TW_heuristic = node.delivery_item_list[0].committed_completion_time
        
        currT = 0
        if not vehicle.des:
            if vehicle.cur_factory_id == temp_route[0].id:
                currT = vehicle.leave_time_at_current_factory
            else:
                dis_and_time = route_map.get((vehicle.cur_factory_id , temp_route[0].id))
                time = int(dis_and_time[1])
                currT = vehicle.leave_time_at_current_factory + time
        else:    
            currT = vehicle.des.arrive_time
        
        # thoi gian con lai de hoan thanh don
        TW_heuristic = (TW_heuristic - currT)
        # neu cai tren cang nho -> cai duoi cang to
        TW_heuristic = (4 * 3600) / (4* 3600 +  TW_heuristic)
        
        return pow(pheromone, ALPHA) * pow(heuristic, BETA) * pow(TW_heuristic , BETA)
    
    # Giá trị mặc định nếu không tìm thấy thông tin
    return 0.1
