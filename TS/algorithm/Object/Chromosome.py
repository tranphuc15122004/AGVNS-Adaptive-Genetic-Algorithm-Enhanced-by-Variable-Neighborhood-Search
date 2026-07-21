import math
import random
import sys
import time
from typing import Dict, List, Optional, Tuple
from algorithm.Object import *
import algorithm.algorithm_config as config
from algorithm.engine import dispatch_nodePair, total_cost
from algorithm.local_search import *

class Chromosome:
    def __init__(self, vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle]):
        self.solution = vehicleid_to_plan
        self.route_map = route_map
        self.id_to_vehicle = id_to_vehicle
        self.improved_LS_map = {method: 0 for method in config.LS_METHODS}
        self.cant_improved = False


    @property
    def fitness(self) -> float:
        return total_cost(self.id_to_vehicle, self.route_map, self.solution)

    def mutate(self  ,is_limited = False , is_1LS : bool = False):
        mutate_solution(self , is_limited  , is_1LS)


    def crossover(self, other: 'Chromosome' , PDG_map : Dict[str , List[Node]]) -> 'Chromosome':
        if config.is_timeout():
            return None
        child_solution = crossover_solutions(self, other  , PDG_map)
        return child_solution

    def __repr__(self):
        return f'Chromosome(Fitness: {self.fitness}, Solution: {get_route_after(self.solution , {})})'

def mutate_solution(indivisual : Chromosome , is_limited = False , is_1LS : bool = False):
    if is_1LS:
        n1 = 0
        i  = 1
        while i < config.LS_MAX:
            is_improved = False
            if inter_couple_exchange(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                n1 +=1
                is_improved = True
            if is_improved:
                i += 1
            else:
                break
            print(f"PDPairExchange:{n1}; cost:{total_cost(indivisual.id_to_vehicle , indivisual.route_map , indivisual.solution ):.2f}" , file= sys.stderr  )
    else:
        n1 , n2 , n3 , n4, n5 = 0 ,0 ,0 ,0 ,0
        i  = 1
        while i < config.LS_MAX:
            if config.is_timeout():
                break
            
            is_improved = False
            if inter_couple_exchange(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                n1 +=1
                is_improved = True
            if block_exchange(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                n2 +=1
                is_improved = True
                
            if block_relocate(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                is_improved = True
                n3 +=1
            
            if multi_pd_group_relocate(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                n4 +=1
                is_improved = True
            
            if improve_ci_path_by_2_opt(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map  , is_limited):
                n5 +=1
                is_improved = True
            
            if is_improved:
                i += 1
            else:
                break
        print(f"PDPairExchange:{n1}; BlockExchange:{n2}; BlockRelocate:{n3}; mPDG:{n4}; 2opt:{n5}; cost:{total_cost(indivisual.id_to_vehicle , indivisual.route_map , indivisual.solution ):.2f}" , file= sys.stderr  )


def crossover_solutions(parent1: Chromosome , parent2: Chromosome , PDG_map : Dict[str , List[Node]]):
    # Early timeout guard: return the better parent to keep GA stable
    if config.is_timeout():
        try:
            return parent1 if parent1.fitness <= parent2.fitness else parent2
        except Exception:
            return parent1

    Overtime1 = calculate_delaytime_each_vehicle(parent1)
    Overtime2 = calculate_delaytime_each_vehicle(parent2)

    Overtime = {f"{s}P1": item for s, item in Overtime1.items()}
    Overtime.update({f"{s}P2": item for s, item in Overtime2.items()})
    
    # Chuyển thành danh sách tuple
    Overtime_list = list(Overtime.items())
    random.shuffle(Overtime_list)
    Overtime = sorted(Overtime_list, key=lambda item: item[1])
    
    # Cac super node
    new_PDG_map : Dict[str , List[Node]] = {}
    for key , value in PDG_map.items():
        key = f'{len(value[0].pickup_item_list)}_{value[0].pickup_item_list[0].id}'
        new_PDG_map[key] = value
    
    # Khởi tạo lời giải con là rỗng -> điều kiện dừng của vòng lặp sẽ là kiểm tra child đã được thêm tất cả các tuyền đường từ cha và mẹ
    child_solution :Dict[str, List[Node]] = {vehicleID:[] for vehicleID in parent1.id_to_vehicle.keys()}
    check_valid : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    added_route_check : set[str] = set()
    
    # Thêm đầy đủ các tuyến đường vào lời giải con (có thể gây thừa hoặc thiếu các unongoing super node)
    while len(added_route_check) != len(parent1.id_to_vehicle):
        if config.is_timeout():
            try:
                return parent1 if parent1.fitness <= parent2.fitness else parent2
            except Exception:
                return parent1
        Topitem =  Overtime[0]
        del Overtime[0]
        vehicleID = Topitem[0].split('P')[0]
        ParentIndex = int(Topitem[0].split('P')[1])
        
        # Kiem tra da lay duoc dung va du tuyen duong cuar cac xe chuaw
        if vehicleID in added_route_check: 
            continue
        else:
            added_route_check.add(vehicleID)
        
        if ParentIndex == 1:
            for node in parent1.solution[vehicleID]:
                child_solution[vehicleID].append(node)
        else:
            for node in parent2.solution[vehicleID]:
                child_solution[vehicleID].append(node)

        # Lưu các nút thừa trong tuyến đường hiện tại
        redundant = []
        del_index = []
        # Duyệt ngược danh sách để tìm và xóa nút thừa    
        for i in range(len(child_solution[vehicleID]) - 1, -1, -1):  
            node = child_solution[vehicleID][i]
            
            if node.pickup_item_list:
                if redundant and node.pickup_item_list[0].id == redundant[-1]:
                    redundant.pop()  # Loại bỏ phần tử tương ứng trong danh sách `redundant`
                    del_index.append(i)
            else:
                key = f'{len(node.delivery_item_list)}_{node.delivery_item_list[-1].id}'
                
                if key in new_PDG_map:
                    check_valid[key] += 1
                    
                    # nếu tìm được một super node thừa
                    if check_valid[key] > 1:
                        first_itemID_of_redundant_supernode = key.split('_')[-1]
                        redundant.append(first_itemID_of_redundant_supernode)
                        #print(f"Redundant nodes: {redundant}" , file= sys.stderr)

                        # Xóa node giao của super node thừa
                        del_index.append(i)
                        #print('Đã xóa 1 super node thừa' , file= sys.stderr)
        for i in del_index:
            child_solution[vehicleID].pop(i)

    # Kiem tra lai solution        
    for key, value in check_valid.items():
        if config.is_timeout():
            try:
                return parent1 if parent1.fitness <= parent2.fitness else parent2
            except Exception:
                return parent1
        if value == 0:
            if random.uniform(0 , 1) < 0:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                node_list = new_PDG_map[key]
                isExhausive = False
                route_node_list : List[Node] = []
                
                if node_list:
                    if config.is_timeout():
                        try:
                            return parent1 if parent1.fitness <= parent2.fitness else parent2
                        except Exception:
                            return parent1
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(node_list , parent1.id_to_vehicle , child_solution , parent1.route_map)
                    
                route_node_list = child_solution.get(bestInsertVehicleID , [])

                if isExhausive:
                    route_node_list = bestNodeList[:]
                else:
                    if route_node_list is None:
                        route_node_list = []
                    
                    new_order_pickup_node = node_list[0]
                    new_order_delivery_node = node_list[1]
                    
                    route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                    route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                child_solution[bestInsertVehicleID] = route_node_list
            else:
                node_list = new_PDG_map[key]
                if random.uniform(0 , 1) < 0.5:
                    # Random vehicle
                    selected_vehicleID = random.choice(list(parent1.id_to_vehicle.keys()))
                    child_solution[selected_vehicleID].extend(node_list)
                else:
                    # Random dispatch
                    if config.is_timeout():
                        try:
                            return parent1 if parent1.fitness <= parent2.fitness else parent2
                        except Exception:
                            return parent1
                    random_dispatch_nodePair(node_list, parent1.id_to_vehicle, child_solution)
            
            #print('Cập nhật super node còn thiếu' , file= sys.stderr)
    
    if config.is_timeout():
        try:
            return parent1 if parent1.fitness <= parent2.fitness else parent2
        except Exception:
            return parent1
    sorted_child_solution = sorted(child_solution.items() ,  key=lambda x: int(x[0].split('_')[1]))
    child_solution.clear()
    child_solution.update(sorted_child_solution)
    child = Chromosome(child_solution , parent1.route_map , parent1.id_to_vehicle)
    return child

def calculate_delaytime_each_vehicle(chromosome: Chromosome) -> Dict[str , int]:
    dock_table: Dict[str, List[List[int]]] = {}
    n: int = 0
    vehicle_num: int = len(chromosome.id_to_vehicle)
    # asdfasdfasdfasdfasdfasd
    overtime_per_vehicle : Dict[str , int] = {}
    for vehicleID in chromosome.id_to_vehicle.keys():
        overtime_per_vehicle[vehicleID] = 0

    curr_node: List[int] = [0] * vehicle_num
    curr_time: List[int] = [0] * vehicle_num
    leave_last_node_time: List[int] = [0] * vehicle_num

    n_node: List[int] = [0] * vehicle_num
    index = 0
    
    for vehicleID , otherVehicle in chromosome.id_to_vehicle.items():
        time  = 0
        
        if otherVehicle.cur_factory_id :
            if otherVehicle.leave_time_at_current_factory > otherVehicle.gps_update_time:
                tw: List[int] = [
                    otherVehicle.arrive_time_at_current_factory,
                    otherVehicle.leave_time_at_current_factory
                ]
                tw_list: Optional[List[List[int]]] = dock_table.get(otherVehicle.cur_factory_id)
                if tw_list is None:
                    tw_list = []
                tw_list.append(tw)
                dock_table[otherVehicle.cur_factory_id] = tw_list
            leave_last_node_time[index] = otherVehicle.leave_time_at_current_factory
        else:
            leave_last_node_time[index] = otherVehicle.gps_update_time
        
        if chromosome.solution.get(vehicleID) and len(chromosome.solution.get(vehicleID)) > 0:    
            curr_node[index] = 0
            n_node[index] = len(chromosome.solution[vehicleID]) 
            
            if otherVehicle.des is None:
                if otherVehicle.cur_factory_id == chromosome.solution[vehicleID][0].id:
                    curr_time[index] = otherVehicle.leave_time_at_current_factory
                else:
                    dis_and_time = chromosome.route_map.get((otherVehicle.cur_factory_id , chromosome.solution[vehicleID][0].id))
                    if dis_and_time is None:
                        print("no distance" , file= sys.stderr)
                    
                    time = int(dis_and_time[1])
                    curr_time[index] = otherVehicle.leave_time_at_current_factory + time
            else:
                if otherVehicle.cur_factory_id is not None and len(otherVehicle.cur_factory_id) > 0:
                    if otherVehicle.cur_factory_id == chromosome.solution[vehicleID][0].id:
                        curr_time[index]  = otherVehicle.leave_time_at_current_factory
                    else:
                        curr_time[index] = otherVehicle.leave_time_at_current_factory
                        dis_and_time = chromosome.route_map.get((otherVehicle.cur_factory_id , chromosome.solution[vehicleID][0].id))
                        time = int(dis_and_time[1])
                        curr_time[index] += time
                else: 
                    curr_time[index] = otherVehicle.des.arrive_time
            n+=1
        else:
            curr_time[index] = math.inf
            curr_time[index] = math.inf
            n_node[index] = 0
        index += 1
        
    while n > 0:
        minT = math.inf
        minT2VehicleIndex = 0
        tTrue = minT
        idx = 0
        
        for i in range (vehicle_num):
            if curr_time[i] < minT:
                minT = curr_time[i]
                minT2VehicleIndex = i
        
        minT2VehicleIndex += 1
        minT2VehicleID = "V_" + str(minT2VehicleIndex)
        minT2VehicleIndex -= 1
        
        minTNodeList: List[Node] = []
        minTNodeList = chromosome.solution.get(minT2VehicleID)
        minTNode = minTNodeList[curr_node[minT2VehicleIndex]]
        
        if minTNode.delivery_item_list and len(minTNode.delivery_item_list) > 0:
            beforeOrderID = ""
            nextOrderID = ""
            for order_item in minTNode.delivery_item_list:
                nextOrderID = order_item.id
                if beforeOrderID != nextOrderID:
                    commitCompleteTime = order_item.committed_completion_time
                    overtime_per_vehicle[minT2VehicleID] += max(0 , curr_time[minT2VehicleIndex] - commitCompleteTime)
                beforeOrderID = nextOrderID
        
        usedEndTime : List[int] = []
        timeSlots : List[List[int]] =  dock_table.get(minTNode.id, [])
        if timeSlots:
            i = 0
            while i < len(timeSlots):
                time_slot = timeSlots[i]
                if time_slot[1] <= minT:
                    timeSlots.pop(i)  # Xóa phần tử nếu end_time <= minT
                elif time_slot[0] <= minT < time_slot[1]:
                    usedEndTime.append(time_slot[1])
                    i += 1
                else:
                    print("------------ timeslot.start > minT --------------", file = sys.stderr)
                    i += 1

        if len(usedEndTime) < 6:
            tTrue = minT
        else:
            idx = len(usedEndTime) - 6
            usedEndTime.sort()
            tTrue = usedEndTime[idx]
            
        service_time = minTNodeList[curr_node[minT2VehicleIndex]].service_time
        cur_factory_id = minTNodeList[curr_node[minT2VehicleIndex]].id
        curr_node[minT2VehicleIndex] += 1

        while (curr_node[minT2VehicleIndex] < n_node[minT2VehicleIndex] and
            cur_factory_id == minTNodeList[curr_node[minT2VehicleIndex]].id):

            delivery_item_list = minTNodeList[curr_node[minT2VehicleIndex]].delivery_item_list
            
            if delivery_item_list and len(delivery_item_list) > 0:
                before_order_id = ""
                next_order_id = ""

                for order_item in delivery_item_list:
                    next_order_id = order_item.order_id
                    if before_order_id != next_order_id:
                        commit_complete_time = order_item.committed_completion_time
                        overtime_per_vehicle[minT2VehicleID] += max(0, curr_time[minT2VehicleIndex] - commit_complete_time)
                    before_order_id = next_order_id

            service_time += minTNodeList[curr_node[minT2VehicleIndex]].service_time
            curr_node[minT2VehicleIndex] += 1
            
        if curr_node[minT2VehicleIndex] >= n_node[minT2VehicleIndex]:
            n -= 1
            curr_node[minT2VehicleIndex] = math.inf
            curr_time[minT2VehicleIndex] = math.inf
            n_node[minT2VehicleIndex] = 0
        else:
            dis_and_time = chromosome.route_map.get((cur_factory_id , minTNodeList[curr_node[minT2VehicleIndex]].id))
            if dis_and_time:
                time = int(dis_and_time[1])

                curr_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time + time
                leave_last_node_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time

        tw = [minT, tTrue + config.APPROACHING_DOCK_TIME + service_time]
        tw_list = dock_table.get(minTNode.id, [])

        tw_list.append(tw)
        dock_table[minTNode.id] = tw_list
    
    return overtime_per_vehicle