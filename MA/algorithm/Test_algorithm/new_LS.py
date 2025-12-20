import sys
import math
import random
from typing import Dict , List
import copy
import time
from algorithm.Object import Node, Vehicle , Chromosome
import algorithm.algorithm_config as config
from algorithm.engine import *
from algorithm.local_search import * 

def new_get_UnongoingSuperNode (vehicleid_to_plan: Dict[str , List[Node]] , id_to_vehicle: Dict[str , Vehicle] ) -> Dict[int , Dict[str, Node]] :
    UnongoingSuperNodes : Dict[int , Dict[str , Node]] = {}
    
    NodePairNum = 0 
    # xet từng kế hoạch di chuyển của phương tiện
    for vehicleID , vehicle_plan in vehicleid_to_plan.items():
        vehicle = id_to_vehicle[vehicleID]
            
        if vehicle_plan and len(vehicle_plan) > 0:
            index = 1 if vehicle.des else 0
            
            # Để duy trì tính FILO 
            pickup_node_heap : List[Node] = []
            p_node_idx_heap : List[int] = []
            p_and_d_node_map : Dict[str , Node] = {}
            before_p_factory_id , before_d_factory_id = None , None
            before_p_node_idx , before_d_node_idx = 0 , 0
                        
            # đối với mỗi node của phương tiện
            for i in range (index , len(vehicle_plan)):
                curr = vehicle_plan[i]
                if curr.delivery_item_list  and curr.pickup_item_list :
                    print ("Exits combine node exception when Local search" , file= sys.stderr)
                
                heapTopOrderItemId = pickup_node_heap[0].pickup_item_list[0].id if pickup_node_heap else ""
                
                # Nếu node hiện tại là node giao
                if curr.delivery_item_list:
                    # Nó là node giao của node nhận đầu tiên trong heap
                    if curr.delivery_item_list[-1].id == heapTopOrderItemId:
                        pickup_node_key = f"{vehicleID},{p_node_idx_heap[0]}"
                        delivery_node_key = f"{vehicleID},{int(i)}"
                
                        if len(p_and_d_node_map) >= 2:
                            if ((pickup_node_heap[0].id != before_p_factory_id) or (p_node_idx_heap[0] + 1 != before_p_node_idx) or (curr.id != before_d_factory_id) or (i - 1 != before_d_node_idx)):
                                UnongoingSuperNodes[NodePairNum] = p_and_d_node_map
                                NodePairNum += 1
                                p_and_d_node_map : Dict[str , Node] = {}

                        p_and_d_node_map[pickup_node_key] = pickup_node_heap[0]
                        p_and_d_node_map[delivery_node_key] = curr

                        before_p_factory_id = pickup_node_heap[0].id
                        before_p_node_idx = p_node_idx_heap[0]
                        before_d_factory_id = curr.id
                        before_d_node_idx = i
                        pickup_node_heap.pop(0)
                        p_node_idx_heap.pop(0)
                
                # Nếu node hiện tại là node nhận
                if curr.pickup_item_list:
                    pickup_node_heap.insert(0 , curr)
                    p_node_idx_heap.insert(0 , i)
                    if p_and_d_node_map:
                        UnongoingSuperNodes[NodePairNum] = p_and_d_node_map
                        NodePairNum += 1
                        p_and_d_node_map : Dict[str , Node] = {}
            
            if len(p_and_d_node_map) >= 2:
                UnongoingSuperNodes[NodePairNum] = p_and_d_node_map
                NodePairNum += 1
                p_and_d_node_map : Dict[str , Node] = {}
                

    return UnongoingSuperNodes

def _route_node_coverage_signature(vehicleid_to_plan: Dict[str, List[Node]]) -> Dict[int, int]:
    """Build a multiset signature of Node object identities across all routes.
    Using object identity is robust for move-only LS operators to detect dup/miss.
    """
    from collections import Counter
    sig = Counter()
    for vid, route in vehicleid_to_plan.items():
        for node in route:
            sig[id(node)] += 1
    return dict(sig)

def delaytime_for_each_node(id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , vehicleid_to_plan: Dict[str , list[Node]]) -> Dict[str , List[float]]:
    driving_dis  : float = 0.0
    overtime_Sum : float = 0.0
    dock_table: Dict[str, List[List[int]]] = {}
    n: int = 0
    vehicle_num: int = len(id_to_vehicle)
    curr_node: List[int] = [0] * vehicle_num
    curr_time: List[int] = [0] * vehicle_num
    leave_last_node_time: List[int] = [0] * vehicle_num

    n_node: List[int] = [0] * vehicle_num
    index = 0
    
    #delay time cua moi cap node
    delaytime_to_node : Dict[str , List[float]] = {}
    for ID , route in vehicleid_to_plan.items():
        delaytime_to_node[ID] = [0] * len(route)
    
    for vehicleID , otherVehicle in id_to_vehicle.items():
        distance = 0
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
        
        if vehicleid_to_plan.get(vehicleID) and len(vehicleid_to_plan.get(vehicleID)) > 0:    
            curr_node[index] = 0
            n_node[index] = len(vehicleid_to_plan[vehicleID]) 
            
            if otherVehicle.des is None:
                if otherVehicle.cur_factory_id == vehicleid_to_plan[vehicleID][0].id:
                    curr_time[index] = otherVehicle.leave_time_at_current_factory
                else:
                    dis_and_time = route_map.get((otherVehicle.cur_factory_id , vehicleid_to_plan[vehicleID][0].id))
                    if dis_and_time is None:
                        print("no distance" , file= sys.stderr)
                    
                    distance = float(dis_and_time[0])
                    time = int(dis_and_time[1])
                    curr_time[index] = otherVehicle.leave_time_at_current_factory + time
                    driving_dis += distance
            else:
                if otherVehicle.cur_factory_id is not None and len(otherVehicle.cur_factory_id) > 0:
                    if otherVehicle.cur_factory_id == vehicleid_to_plan[vehicleID][0].id:
                        curr_time[index]  = otherVehicle.leave_time_at_current_factory
                    else:
                        curr_time[index] = otherVehicle.leave_time_at_current_factory
                        dis_and_time = route_map.get((otherVehicle.cur_factory_id , vehicleid_to_plan[vehicleID][0].id))
                        distance = float(dis_and_time[0])
                        time = int(dis_and_time[1])
                        curr_time[index] += time
                        driving_dis += distance
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
        minTNodeList = vehicleid_to_plan.get(minT2VehicleID)
        minTNode = minTNodeList[curr_node[minT2VehicleIndex]]
        
        if minTNode.delivery_item_list and len(minTNode.delivery_item_list) > 0:
            beforeOrderID = ""
            nextOrderID = ""
            for order_item in minTNode.delivery_item_list:
                nextOrderID = order_item.id
                if beforeOrderID != nextOrderID:
                    commitCompleteTime = order_item.committed_completion_time
                    
                    temp = curr_time[minT2VehicleIndex] - commitCompleteTime
                    overtime_Sum += max(0 , temp)
                    if temp > 0:
                        delaytime_to_node[minT2VehicleID][curr_node[minT2VehicleIndex]] += temp
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
                        
                        temp = curr_time[minT2VehicleIndex] - commit_complete_time
                        overtime_Sum += max(0, temp)
                        if temp > 0:
                            delaytime_to_node[minT2VehicleID][curr_node[minT2VehicleIndex]] += temp
                    before_order_id = next_order_id

            service_time += minTNodeList[curr_node[minT2VehicleIndex]].service_time
            curr_node[minT2VehicleIndex] += 1
            
        if curr_node[minT2VehicleIndex] >= n_node[minT2VehicleIndex]:
            n -= 1
            curr_node[minT2VehicleIndex] = math.inf
            curr_time[minT2VehicleIndex] = math.inf
            n_node[minT2VehicleIndex] = 0
        else:
            dis_and_time = route_map.get((cur_factory_id , minTNodeList[curr_node[minT2VehicleIndex]].id))
            if dis_and_time:
                distance = float(dis_and_time[0])
                time = int(dis_and_time[1])

                curr_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time + time
                leave_last_node_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time
                driving_dis += distance

        tw = [minT, tTrue + config.APPROACHING_DOCK_TIME + service_time]
        tw_list = dock_table.get(minTNode.id, [])

        tw_list.append(tw)
        dock_table[minTNode.id] = tw_list
    
    return delaytime_to_node

def disturbance_opt(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , relocate_rate = 0.3):
    begin = time.time()
    
    new_vehicle_to_plan : Dict[str , List[Node]] = {}
    for VID , plan in vehicleid_to_plan.items():
        new_vehicle_to_plan[VID] = []
        for node in plan:
            new_vehicle_to_plan[VID].append(copy.deepcopy(node))
            
    dis_order_super_node,  _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return None
    
    pdg_Map : Dict[str , List[Node]] = {}
    
    for idx, pdg in dis_order_super_node.items():
        pickup_node = None
        delivery_node = None
        node_list: List[Node] = []
        pos_i = 0
        pos_j = 0
        d_num = len(pdg) // 2
        index = 0

        if pdg:
            for v_and_pos_str, node in pdg.items():
                if index % 2 == 0:
                    vehicleID = v_and_pos_str.split(",")[0]
                    pos_i = int(v_and_pos_str.split(",")[1])
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    pos_j = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
                    pos_j = pos_j - d_num + 1

            k : str = f"{vehicleID},{int(pos_i)}+{int(pos_j)}"
            pdg_Map[k] = node_list
            
    if len(pdg_Map) < 2:
        return None

    num_pairs_to_relocate = max(1, int(len(pdg_Map) * relocate_rate))
    pairs_to_relocate = random.sample(list(pdg_Map.keys()), num_pairs_to_relocate)
    
    # Lưu trữ các cặp node sẽ được gán lại
    relocated_pairs : Dict[str, List[Node]] = {}
    
    # Nhóm các cặp node cần xóa theo xe
    vehicle_removal_info : Dict[str, List[tuple]] = {}
    
    for key in pairs_to_relocate:
        relocated_pairs[key] = pdg_Map[key]
        
        # Lấy thông tin vị trí và xe
        vehicle_pos_info = key.split(',')
        vehicle_id = vehicle_pos_info[0]
        positions = vehicle_pos_info[1].split('+')
        pos_i = int(positions[0])
        pos_j = int(positions[1])
        
        node_list = pdg_Map[key]
        d_num = len(node_list) // 2
        
        # Thêm thông tin xóa vào dictionary theo xe
        if vehicle_id not in vehicle_removal_info:
            vehicle_removal_info[vehicle_id] = []
        vehicle_removal_info[vehicle_id].append((pos_i, pos_i + d_num, pos_j, pos_j + d_num))
    
    # Xây dựng lời giải sau khi bỏ những cặp sẽ được gán lại
    for vehicle_id, removal_list in vehicle_removal_info.items():
        route_node_list = new_vehicle_to_plan.get(vehicle_id, [])
        
        # Thu thập tất cả các chỉ số cần xóa
        indices_to_remove = set()
        for pos_i_start, pos_i_end, pos_j_start, pos_j_end in removal_list:
            # Thêm chỉ số pickup nodes
            for idx in range(pos_i_start, pos_i_end):
                if idx < len(route_node_list):
                    indices_to_remove.add(idx)
            # Thêm chỉ số delivery nodes
            for idx in range(pos_j_start, pos_j_end):
                if idx < len(route_node_list):
                    indices_to_remove.add(idx)
        
        # Sắp xếp chỉ số theo thứ tự giảm dần để xóa từ cuối lên đầu
        sorted_indices = sorted(indices_to_remove, reverse=True)
        
        # Xóa các node theo thứ tự từ cuối lên đầu
        for idx in sorted_indices:
            if idx < len(route_node_list):
                del route_node_list[idx]
        
        new_vehicle_to_plan[vehicle_id] = route_node_list
    
    # Gán lại các cặp node đã đánh dấu một cách ngẫu nhiên vào tuyến đường
    for key, node_list in relocated_pairs.items():
        # Sử dụng random_dispatch_nodePair để gán ngẫu nhiên cặp node
        random_dispatch_nodePair(node_list, id_to_vehicle, new_vehicle_to_plan)
    
    
    #print(time.time() - begin)
    return Chromosome(new_vehicle_to_plan , route_map , id_to_vehicle)


def disturbance_2opt_blocks(
    vehicleid_to_plan: Dict[str, List[Node]],
    id_to_vehicle: Dict[str, Vehicle],
    route_map: Dict[tuple, tuple],
    max_attempts: int = 2,
    cross_rate: float = 0.3,
    accept_if_better: bool = True,
):
    """Very-fast 2-opt-like disturbance at super-node block level.

    - Build contiguous PD-group blocks per vehicle (start..end indices) from get_UnongoingSuperNode.
    - With probability `cross_rate`, try one inter-route swap of a single block (block exchange).
      Otherwise, do an intra-route 2-opt on block order: reverse a block segment [i..j] without
      reversing inside blocks (so pickup-before-delivery stays valid within each super node).
    - Accept only if feasible; if `accept_if_better` True, also require cost not worse.

    Designed to be O(route segment) and do just 1-2 attempts, so it's fast on large instances.
    Returns a new Chromosome (possibly unchanged if no move was accepted).
    """
    import random, copy, math, time, sys

    # Shallow copy plan (reuse Node objects)
    new_plan: Dict[str, List[Node]] = {vid: route[:] for vid, route in vehicleid_to_plan.items()}

    # Build block spans per vehicle
    dis_order_super_node, _ = get_UnongoingSuperNode(vehicleid_to_plan, id_to_vehicle)
    spans_by_vid: Dict[str, List[tuple]] = {}
    for idx, pdg in dis_order_super_node.items():
        if not pdg:
            continue
        positions: List[int] = []
        vid = None
        for vpos, node in pdg.items():
            parts = vpos.split(",")
            if vid is None:
                vid = parts[0]
            positions.append(int(parts[1]))
        if vid is None or not positions:
            continue
        start_idx = min(positions)
        end_idx = max(positions)
        lst = spans_by_vid.setdefault(vid, [])
        lst.append((start_idx, end_idx))
    for vid, spans in spans_by_vid.items():
        spans.sort(key=lambda ab: ab[0])

    def route_cost(vid: str, route_list: List[Node]) -> float:
        vehicle = id_to_vehicle[vid]
        return cost_of_a_route(route_list, vehicle, id_to_vehicle, route_map, new_plan)

    def feasible(vid: str, route_list: List[Node]) -> bool:
        vehicle = id_to_vehicle[vid]
        carry = vehicle.carrying_items if vehicle.des else []
        return isFeasible(route_list, carry, vehicle.board_capacity)

    def try_inter_swap() -> bool:
        vids = [v for v, spans in spans_by_vid.items() if spans]
        if len(vids) < 2:
            return False
        v1, v2 = random.sample(vids, 2)
        spans1 = spans_by_vid[v1]
        spans2 = spans_by_vid[v2]
        if not spans1 or not spans2:
            return False
        b1 = random.choice(spans1)
        b2 = random.choice(spans2)
        s1, e1 = b1
        s2, e2 = b2
        r1 = new_plan.get(v1, [])
        r2 = new_plan.get(v2, [])
        # Slices
        seg1 = r1[s1:e1 + 1]
        seg2 = r2[s2:e2 + 1]

        # Before cost (if needed)
        if accept_if_better:
            c1_before = route_cost(v1, r1)
            c2_before = route_cost(v2, r2)

        # Apply swap
        new_r1 = r1[:s1] + seg2 + r1[e1 + 1:]
        new_r2 = r2[:s2] + seg1 + r2[e2 + 1:]

        if not feasible(v1, new_r1) or not feasible(v2, new_r2):
            return False

        if accept_if_better:
            c1_after = route_cost(v1, new_r1)
            c2_after = route_cost(v2, new_r2)
            if c1_after + c2_after > c1_before + c2_before:
                return False

        # Commit
        new_plan[v1] = new_r1
        new_plan[v2] = new_r2
        return True

    def try_intra_2opt() -> bool:
        # choose a vehicle with >= 3 blocks
        candidates = [v for v, spans in spans_by_vid.items() if len(spans) >= 3]
        if not candidates:
            candidates = [v for v, spans in spans_by_vid.items() if len(spans) >= 2]
        if not candidates:
            return False
        vid = random.choice(candidates)
        spans = spans_by_vid[vid]
        r = new_plan.get(vid, [])
        # pick two block indices i<j
        i, j = sorted(random.sample(range(len(spans)), 2))
        s, _ = spans[i]
        _, e = spans[j]
        # build reversed by blocks: concatenate block slices in reversed block order
        blocks = spans[i:j + 1]
        segment_slices = [r[bs:be + 1] for (bs, be) in blocks]
        new_segment = []
        for sl in reversed(segment_slices):
            new_segment.extend(sl)
        new_r = r[:s] + new_segment + r[e + 1:]

        if not feasible(vid, new_r):
            return False
        if accept_if_better:
            if route_cost(vid, new_r) > route_cost(vid, r):
                return False

        new_plan[vid] = new_r
        return True

    # Try a few quick attempts
    for _ in range(max_attempts):
        do_cross = (random.random() < cross_rate)
        ok = try_inter_swap() if do_cross else try_intra_2opt()
        if ok:
            break

    return Chromosome(new_plan, route_map, id_to_vehicle)


def disturbance_2opt_blocks_plus(
    vehicleid_to_plan: Dict[str, List[Node]],
    id_to_vehicle: Dict[str, Vehicle],
    route_map: Dict[tuple, tuple],
    steps: int = 3,
    cross_rate: float = 0.4,
    shuffle_rate: float = 0.3,
    double_bridge_rate: float = 0.3,
    accept_if_better: bool = True,
    allow_worse_delta: float = 0.0,
):
    """Stronger but fast block-level perturbation combining:
    - Inter-route single block swap (like exchange)
    - Intra-route 2-opt on block order (reverse a block segment)
    - Intra-route block shuffle within a window
    - Intra-route double-bridge on block segments

    Performs up to `steps` accepted moves, each O(segment), with feasibility check and optional
    cost guard per affected route(s). Returns a new Chromosome (may be unchanged if no move accepted).
    """
    import random, math

    # Shallow copy plan (reuse Node objects)
    new_plan: Dict[str, List[Node]] = {vid: route[:] for vid, route in vehicleid_to_plan.items()}

    # Helper to build PDG block spans from the CURRENT plan
    def build_spans_from_plan(plan: Dict[str, List[Node]]) -> Dict[str, List[tuple]]:
        spans: Dict[str, List[tuple]] = {}
        dis_order_super_node, _ = get_UnongoingSuperNode(plan, id_to_vehicle)
        for _, pdg in dis_order_super_node.items():
            if not pdg:
                continue
            positions: List[int] = []
            vid = None
            for vpos, _node in pdg.items():
                parts = vpos.split(",")
                if vid is None:
                    vid = parts[0]
                positions.append(int(parts[1]))
            if vid is None or not positions:
                continue
            start_idx = min(positions)
            end_idx = max(positions)
            # Defensive clamp against out-of-range
            route = plan.get(vid, [])
            if not route:
                continue
            start_idx = max(0, min(start_idx, len(route) - 1))
            end_idx = max(0, min(end_idx, len(route) - 1))
            if start_idx > end_idx:
                continue
            spans.setdefault(vid, []).append((start_idx, end_idx))
        # Sort and filter
        for v in list(spans.keys()):
            spans[v].sort(key=lambda ab: ab[0])
            spans[v] = [(s, e) for (s, e) in spans[v] if 0 <= s <= e < len(new_plan.get(v, []))]
            if not spans[v]:
                spans.pop(v, None)
        return spans

    # Initial spans based on new_plan (not the original)
    spans_by_vid: Dict[str, List[tuple]] = build_spans_from_plan(new_plan)

    # Coverage signature before any mutation (for safety)
    pre_sig = _route_node_coverage_signature(new_plan)

    def route_cost(vid: str, route_list: List[Node]) -> float:
        vehicle = id_to_vehicle[vid]
        return cost_of_a_route(route_list, vehicle, id_to_vehicle, route_map, new_plan)

    def feasible(vid: str, route_list: List[Node]) -> bool:
        vehicle = id_to_vehicle[vid]
        carry = vehicle.carrying_items if vehicle.des else []
        return isFeasible(route_list, carry, vehicle.board_capacity)

    def accept_cost(before_list: list[tuple[str, float]], after_list: list[tuple[str, float]]) -> bool:
        if not accept_if_better:
            return True
        before_sum = sum(c for _, c in before_list)
        after_sum = sum(c for _, c in after_list)
        return after_sum <= before_sum + allow_worse_delta

    def try_inter_swap() -> bool:
        vids = [v for v, spans in spans_by_vid.items() if spans]
        if len(vids) < 2:
            return False
        v1, v2 = random.sample(vids, 2)
        spans1 = spans_by_vid[v1]
        spans2 = spans_by_vid[v2]
        if not spans1 or not spans2:
            return False
        s1, e1 = random.choice(spans1)
        s2, e2 = random.choice(spans2)
        r1 = new_plan.get(v1, [])
        r2 = new_plan.get(v2, [])
        seg1 = r1[s1:e1 + 1]
        seg2 = r2[s2:e2 + 1]
        before_costs = [(v1, route_cost(v1, r1)), (v2, route_cost(v2, r2))] if accept_if_better else []
        new_r1 = r1[:s1] + seg2 + r1[e1 + 1:]
        new_r2 = r2[:s2] + seg1 + r2[e2 + 1:]
        if not feasible(v1, new_r1) or not feasible(v2, new_r2):
            return False
        after_costs = [(v1, route_cost(v1, new_r1)), (v2, route_cost(v2, new_r2))] if accept_if_better else []
        if accept_cost(before_costs, after_costs):
            new_plan[v1] = new_r1
            new_plan[v2] = new_r2
            # Rebuild spans from current plan to avoid stale indices
            new_spans = build_spans_from_plan(new_plan)
            spans_by_vid.clear(); spans_by_vid.update(new_spans)
            return True
        return False

    def try_intra_2opt() -> bool:
        candidates = [v for v, spans in spans_by_vid.items() if len(spans) >= 2]
        if not candidates:
            return False
        vid = random.choice(candidates)
        spans = spans_by_vid[vid]
        r = new_plan.get(vid, [])
        # Require contiguous block coverage between i..j to preserve nodes
        def pick_contiguous_pair(max_tries: int = 6):
            for _ in range(max_tries):
                i, j = sorted(random.sample(range(len(spans)), 2))
                ok = True
                for k in range(i, j):
                    if spans[k][1] + 1 != spans[k + 1][0]:
                        ok = False
                        break
                if ok:
                    return i, j
            return None
        pair = pick_contiguous_pair()
        if pair is None:
            return False
        i, j = pair
        s = spans[i][0]
        e = spans[j][1]
        blocks = spans[i:j + 1]
        segment_slices = [r[bs:be + 1] for (bs, be) in blocks]
        new_segment = []
        for sl in reversed(segment_slices):
            new_segment.extend(sl)
        new_r = r[:s] + new_segment + r[e + 1:]
        if not feasible(vid, new_r):
            return False
        if accept_if_better:
            if route_cost(vid, new_r) > route_cost(vid, r) + allow_worse_delta:
                return False
        new_plan[vid] = new_r
        # Rebuild spans since block boundaries have changed
        new_spans = build_spans_from_plan(new_plan)
        spans_by_vid.clear(); spans_by_vid.update(new_spans)
        return True

    def try_intra_shuffle() -> bool:
        candidates = [v for v, spans in spans_by_vid.items() if len(spans) >= 3]
        if not candidates:
            return False
        vid = random.choice(candidates)
        spans = spans_by_vid[vid]
        r = new_plan.get(vid, [])
        # choose window size w in [3, min(6, len(spans))] but ensure contiguous blocks
        def pick_contiguous_window(max_tries: int = 8):
            w_max = min(6, len(spans))
            if w_max < 3:
                return None
            for _ in range(max_tries):
                w = random.randint(3, w_max)
                i = random.randint(0, len(spans) - w)
                j = i + w - 1
                ok = True
                for k in range(i, j):
                    if spans[k][1] + 1 != spans[k + 1][0]:
                        ok = False
                        break
                if ok:
                    return i, j
            return None
        win = pick_contiguous_window()
        if win is None:
            return False
        i, j = win
        s = spans[i][0]
        e = spans[j][1]
        block_spans = spans[i:j + 1]
        segs = [r[bs:be + 1] for (bs, be) in block_spans]
        random.shuffle(segs)
        new_segment = [node for seg in segs for node in seg]
        new_r = r[:s] + new_segment + r[e + 1:]
        if not feasible(vid, new_r):
            return False
        if accept_if_better:
            if route_cost(vid, new_r) > route_cost(vid, r) + allow_worse_delta:
                return False
        new_plan[vid] = new_r
        new_spans = build_spans_from_plan(new_plan)
        spans_by_vid.clear(); spans_by_vid.update(new_spans)
        return True

    def try_double_bridge() -> bool:
        candidates = [v for v, spans in spans_by_vid.items() if len(spans) >= 4]
        if not candidates:
            return False
        vid = random.choice(candidates)
        spans = spans_by_vid[vid]
        r = new_plan.get(vid, [])
        a, b, c, d = sorted(random.sample(range(len(spans)), 4))
        sA = spans[a][0]
        eA = spans[a][1]
        sB = spans[b][0]
        eB = spans[b][1]
        sC = spans[c][0]
        eC = spans[c][1]
        sD = spans[d][0]
        eD = spans[d][1]
        # segments by block boundaries
        A = r[:sA]
        S1 = r[sA:eA + 1]
        M = r[eA + 1:sB]
        S2 = r[sB:eB + 1]
        M2 = r[eB + 1:sC]
        S3 = r[sC:eC + 1]
        M3 = r[eC + 1:sD]
        S4 = r[sD:eD + 1]
        E = r[eD + 1:]
        # double-bridge style: A + S1 + M + S3 + M2 + S2 + M3 + S4 + E
        new_r = A + S1 + M + S3 + M2 + S2 + M3 + S4 + E
        if not feasible(vid, new_r):
            return False
        if accept_if_better:
            if route_cost(vid, new_r) > route_cost(vid, r) + allow_worse_delta:
                return False
        new_plan[vid] = new_r
        new_spans = build_spans_from_plan(new_plan)
        spans_by_vid.clear(); spans_by_vid.update(new_spans)
        return True

    # Attempt up to `steps` accepted moves
    accepted = 0

    """ while accepted < steps:
        # choose operator by multinomial
        r = random.random()
        op_done = False
        if r < cross_rate:
            op_done = try_inter_swap()
        elif r < cross_rate + shuffle_rate:
            op_done = try_intra_shuffle()
        elif r < cross_rate + shuffle_rate + double_bridge_rate:
            op_done = try_double_bridge()
        else:
            op_done = try_intra_2opt()
        if op_done:
            accepted += 1 """

    for _ in range(max(1, steps)):
        # choose operator by multinomial
        r = random.random()
        op_done = False
        if r < cross_rate:
            op_done = try_inter_swap()
        elif r < cross_rate + shuffle_rate:
            op_done = try_intra_shuffle()
        elif r < cross_rate + shuffle_rate + double_bridge_rate:
            op_done = try_double_bridge()
        else:
            op_done = try_intra_2opt()
        if op_done:
            accepted += 1

    # Safety: ensure we didn't lose/duplicate nodes
    post_sig = _route_node_coverage_signature(new_plan)
    if pre_sig != post_sig:
        print("[warn] coverage mismatch after disturbance_2opt_blocks_plus; returning original plan", file=sys.stderr)
        return Chromosome(vehicleid_to_plan, route_map, id_to_vehicle)
    return Chromosome(new_plan, route_map, id_to_vehicle)


def cheapest_insertion_for_block(node_block: List[Node],
                                id_to_vehicle: Dict[str, Vehicle],
                                vehicleid_to_plan: Dict[str, list[Node]],
                                route_map: Dict[tuple, tuple],
                                selected_vehicle: str = None):
    """Append-at-end heuristic with cost evaluation, optimized to avoid deep copies.

    We override only the target vehicle's route in the shared mapping temporarily when
    calling cost_of_a_route, then restore it. This avoids copying the whole plan map.
    """
    minCost = math.inf
    bestInsertPos = 0
    bestInsertVehicleID: Optional[str] = None

    for vehicleID, vehicle in id_to_vehicle.items():
        if selected_vehicle is not None and vehicleID != selected_vehicle:
            continue

        vehicle_plan = vehicleid_to_plan.get(vehicleID) or []
        tempRouteNodeList = vehicle_plan + node_block  # append at end
        carrying_items = vehicle.carrying_items if vehicle.des else []
        if not isFeasible(tempRouteNodeList, carrying_items, vehicle.board_capacity):
            continue
        # Temporarily override this vehicle's route
        tmp_cost = cost_of_a_route(tempRouteNodeList, vehicle, id_to_vehicle, route_map, vehicleid_to_plan)
        
        if tmp_cost < minCost:
            minCost = tmp_cost
            bestInsertPos = len(vehicle_plan)
            bestInsertVehicleID = vehicleID

    return bestInsertPos, bestInsertVehicleID

def disturbance_opt_insert_best(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , relocate_rate = 0.3):
    begin  = time.time()
    
    new_vehicle_to_plan : Dict[str , List[Node]] = {}
    for VID , plan in vehicleid_to_plan.items():
        new_vehicle_to_plan[VID] = []
        for node in plan:
            new_vehicle_to_plan[VID].append(copy.deepcopy(node))
            
    dis_order_super_node,  _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return None
    
    pdg_Map : Dict[str , List[Node]] = {}
    
    for idx, pdg in dis_order_super_node.items():
        pickup_node = None
        delivery_node = None
        node_list: List[Node] = []
        pos_i = 0
        pos_j = 0
        d_num = len(pdg) // 2
        index = 0

        if pdg:
            for v_and_pos_str, node in pdg.items():
                if index % 2 == 0:
                    vehicleID = v_and_pos_str.split(",")[0]
                    pos_i = int(v_and_pos_str.split(",")[1])
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    pos_j = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
                    pos_j = pos_j - d_num + 1

            k : str = f"{vehicleID},{int(pos_i)}+{int(pos_j)}"
            pdg_Map[k] = node_list
            
    if len(pdg_Map) < 2:
        return None

    num_pairs_to_relocate = max(1, int(len(pdg_Map) * relocate_rate))
    pairs_to_relocate = random.sample(list(pdg_Map.keys()), num_pairs_to_relocate)
    
    # Lưu trữ các cặp node sẽ được gán lại
    relocated_pairs : Dict[str, List[Node]] = {}
    
    # Nhóm các cặp node cần xóa theo xe
    vehicle_removal_info : Dict[str, List[tuple]] = {}
    
    for key in pairs_to_relocate:
        relocated_pairs[key] = pdg_Map[key]
        
        # Lấy thông tin vị trí và xe
        vehicle_pos_info = key.split(',')
        vehicle_id = vehicle_pos_info[0]
        positions = vehicle_pos_info[1].split('+')
        pos_i = int(positions[0])
        pos_j = int(positions[1])
        
        node_list = pdg_Map[key]
        d_num = len(node_list) // 2
        
        # Thêm thông tin xóa vào dictionary theo xe
        if vehicle_id not in vehicle_removal_info:
            vehicle_removal_info[vehicle_id] = []
        vehicle_removal_info[vehicle_id].append((pos_i, pos_i + d_num, pos_j, pos_j + d_num))
    
    # Xây dựng lời giải sau khi bỏ những cặp sẽ được gán lại
    for vehicle_id, removal_list in vehicle_removal_info.items():
        route_node_list = new_vehicle_to_plan.get(vehicle_id, [])
        
        # Thu thập tất cả các chỉ số cần xóa
        indices_to_remove = set()
        for pos_i_start, pos_i_end, pos_j_start, pos_j_end in removal_list:
            # Thêm chỉ số pickup nodes
            for idx in range(pos_i_start, pos_i_end):
                if idx < len(route_node_list):
                    indices_to_remove.add(idx)
            # Thêm chỉ số delivery nodes
            for idx in range(pos_j_start, pos_j_end):
                if idx < len(route_node_list):
                    indices_to_remove.add(idx)
        
        # Sắp xếp chỉ số theo thứ tự giảm dần để xóa từ cuối lên đầu
        sorted_indices = sorted(indices_to_remove, reverse=True)
        
        # Xóa các node theo thứ tự từ cuối lên đầu
        for idx in sorted_indices:
            if idx < len(route_node_list):
                del route_node_list[idx]
        
        new_vehicle_to_plan[vehicle_id] = route_node_list
    
    # Gán lại các cặp node đã đánh dấu một cách ngẫu nhiên vào tuyến đường
    for key, node_list in relocated_pairs.items():
        if random.random() < 0.25:
            if node_list:
                bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(node_list, id_to_vehicle, new_vehicle_to_plan, route_map)
                
            if bestInsertVehicle is None:
                print(f"[fix error] reinsert abandon block | insertion failed -> stopping")
                continue
            target_route = new_vehicle_to_plan[bestInsertVehicle]
            target_route[bestInsertPos: bestInsertPos] = node_list
        
        else:
            random_dispatch_nodePair(node_list, id_to_vehicle, new_vehicle_to_plan)
        
    
    #print(time.time() - begin)
    return Chromosome(new_vehicle_to_plan , route_map , id_to_vehicle)


def new_inter_couple_exchange(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , limit_time : float , is_limited : bool = False ):    
    # Kiểm tra timeout toàn cục và khởi tạo thời gian bắt đầu cho giới hạn cục bộ
    if config.is_timeout():
        return False
    
    op_start_time = time.time()
    
    is_improved = False

    dis_order_super_node = {}
    if config.USE_ADAPTIVE_ORDER_DISCRIMINATE:
        if config.CROSSOVER_TYPE_RATIO <= 0:
            dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        else:
            dis_order_super_node , _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        
    else:
        dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    
    
    ls_node_pair_num = len(dis_order_super_node)
    
    if ls_node_pair_num == 0:
        return False
    vehicleID = ""
    pdg_Map : Dict[str , List[Node]] = {}
    
    for idx, pdg in dis_order_super_node.items():
        pickup_node = None
        delivery_node = None
        node_list: List[Node] = []
        pos_i = 0
        pos_j = 0
        d_num = len(pdg) // 2
        index = 0

        if pdg:
            for v_and_pos_str, node in pdg.items():
                if index % 2 == 0:
                    vehicleID = v_and_pos_str.split(",")[0]
                    pos_i = int(v_and_pos_str.split(",")[1])
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    pos_j = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
                    pos_j = pos_j - d_num + 1

            k : str = f"{vehicleID},{int(pos_i)}+{int(pos_j)}"
            pdg_Map[k] = node_list
    
    if len(pdg_Map) < 2:
        return False
    
    cost0 = total_cost(id_to_vehicle , route_map, vehicleid_to_plan)
    min_cost = cost0

    min_cost_pdg1_key_str : str = None
    min_cost_pdg2_key_str :str = None
    min_cost_pdg1 : List[Node]= None
    min_cost_pdg2 : List[Node]= None
    
    

    # Shuffle PDG iteration order to diversify search without changing internal PDG structure
    shuffled_keys = list(pdg_Map.keys())
    random.shuffle(shuffled_keys)

    idx_i = 0
    for before_key in shuffled_keys:
        before_DPG = pdg_Map[before_key]
        # Kiểm tra timeout trong vòng lặp ngoài
        if config.is_timeout() or (time.time() - op_start_time) > limit_time:
            break
            
        before_vehicle = id_to_vehicle.get(before_key.split(",")[0])
        before_posI = int(before_key.split(",")[1].split("+")[0])
        before_posJ = int(before_key.split(",")[1].split("+")[1])
        d1num = len(before_DPG) // 2
        
        # Iterate following keys in randomized order ensuring unique pairs (i < j)
        for idx_j in range(idx_i + 1, len(shuffled_keys)):
            # Kiểm tra timeout trong vòng lặp trong (mỗi 10 iterations để tránh overhead)
            if idx_j % 10 == 0 and (config.is_timeout() or (time.time() - op_start_time) > limit_time):
                break

            next_key = shuffled_keys[idx_j]
            next_DPG = pdg_Map[next_key]
            
            next_vehicle = id_to_vehicle.get(next_key.split(",")[0])
            next_posI = int(next_key.split(",")[1].split("+")[0])
            next_posJ = int(next_key.split(",")[1].split("+")[1])
            d2num = len(next_DPG) // 2
            if before_vehicle is next_vehicle:
                continue
            
            route_node_list1 = vehicleid_to_plan.get(before_vehicle.id , [])
            route_node_list2 = vehicleid_to_plan.get(next_vehicle.id , [])
            
            temp1 = route_node_list1[before_posI: before_posI + d1num]
            temp11 = route_node_list1[before_posJ: before_posJ + d1num]
            temp2 = route_node_list2[next_posI: next_posI + d2num]
            temp22 = route_node_list2[next_posJ: next_posJ + d2num]
            
            del route_node_list1[before_posI: before_posI + d1num]
            del route_node_list2[next_posI: next_posI + d2num]
            route_node_list1[before_posI:before_posI] = temp2
            route_node_list2[next_posI:next_posI] = temp1
            
            real_before_post_j = before_posJ + (d2num - d1num)
            real_next_post_j = next_posJ + (d1num - d2num)
            
            del route_node_list1[real_before_post_j: real_before_post_j + d1num]
            if len(route_node_list2) < real_next_post_j + d2num:
                print(222 , file= sys.stderr)
            del route_node_list2[real_next_post_j: real_next_post_j + d2num]
            
            route_node_list1[real_before_post_j:real_before_post_j] = temp22
            route_node_list2[real_next_post_j:real_next_post_j] = temp11
            
            carry1 = before_vehicle.carrying_items if before_vehicle.des else []
            carry2 = next_vehicle.carrying_items if next_vehicle.des else []
            feasible = (isFeasible(route_node_list1, carry1, before_vehicle.board_capacity) and
                        isFeasible(route_node_list2, carry2, next_vehicle.board_capacity))

            if feasible:
                test_vehicleid_to_plan = vehicleid_to_plan.copy()
                # Sao mỏng 2 tuyến thay đổi để tránh side-effect
                test_vehicleid_to_plan[before_vehicle.id] = route_node_list1[:] 
                test_vehicleid_to_plan[next_vehicle.id]   = route_node_list2[:]
                
                cost1 = total_cost(id_to_vehicle , route_map , test_vehicleid_to_plan)
                
                if cost1 < min_cost:
                    min_cost = cost1
                    is_improved = True
                    min_cost_pdg1_key_str = before_key
                    min_cost_pdg2_key_str = next_key
                    min_cost_pdg1 = before_DPG[:]
                    min_cost_pdg2 = next_DPG[:]
            
            del route_node_list1[real_before_post_j: real_before_post_j + d2num]
            del route_node_list2[real_next_post_j: real_next_post_j + d1num]
            route_node_list1[real_before_post_j:real_before_post_j] = temp11
            route_node_list2[real_next_post_j:real_next_post_j] = temp22
            
            del route_node_list1[before_posI: before_posI + d2num]
            del route_node_list2[next_posI: next_posI + d1num]
            route_node_list1[before_posI:before_posI] = temp1
            route_node_list2[next_posI:next_posI] = temp2
            
            if is_improved and is_limited:
                break
        
        # Kiểm tra timeout và early exit
        if config.is_timeout() or (is_improved and is_limited) or (time.time() - op_start_time) > limit_time:
            break    
        
        idx_i += 1
    
    if is_improved:
        before_DPG = min_cost_pdg1
        before_key = min_cost_pdg1_key_str
        before_vehicle = id_to_vehicle.get(before_key.split(",")[0])
        before_posI = int(before_key.split(",")[1].split("+")[0])
        before_posJ = int(before_key.split(",")[1].split("+")[1])
        d1num = len(before_DPG) // 2
        
        next_key = min_cost_pdg2_key_str
        next_DPG = min_cost_pdg2
        next_vehicle = id_to_vehicle.get(next_key.split(",")[0])
        next_posI = int(next_key.split(",")[1].split("+")[0])
        next_posJ = int(next_key.split(",")[1].split("+")[1])
        d2num = len(next_DPG) // 2
        
        route_node_list1 = vehicleid_to_plan.get(before_vehicle.id , [])
        route_node_list2 = vehicleid_to_plan.get(next_vehicle.id , [])
        
        temp1 = route_node_list1[before_posI: before_posI + d1num]
        temp11 = route_node_list1[before_posJ: before_posJ + d1num]
        temp2 = route_node_list2[next_posI: next_posI + d2num]
        temp22 = route_node_list2[next_posJ: next_posJ + d2num]
        
        del route_node_list1[before_posI: before_posI + d1num]
        del route_node_list2[next_posI: next_posI + d2num]
        
        route_node_list1[before_posI:before_posI] = temp2
        route_node_list2[next_posI:next_posI] = temp1
        
        real_before_post_j = before_posJ + (d2num - d1num)
        real_next_post_j = next_posJ + (d1num - d2num)
        
        del route_node_list1[real_before_post_j: real_before_post_j + d1num]
        del route_node_list2[real_next_post_j: real_next_post_j + d2num]
        
        route_node_list1[real_before_post_j:real_before_post_j] = temp22
        route_node_list2[real_next_post_j:real_next_post_j] = temp11
        
        vehicleid_to_plan[before_vehicle.id] = route_node_list1
        vehicleid_to_plan[next_vehicle.id] = route_node_list2

    return is_improved

def new_block_exchange(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , limit_time: float , is_limited : bool = False):
    if config.is_timeout():
        return False
    op_start_time = time.time()
    
    is_improved = False

    dis_order_super_node = {}
    if config.USE_ADAPTIVE_ORDER_DISCRIMINATE:
        if config.CROSSOVER_TYPE_RATIO <= 0:
            dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        else:
            dis_order_super_node , _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        
    else:
        dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    
    
    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return False
    
    vehicleID = None
    block_map : Dict[str , List[Node]] = {}
    for idx , pdg in dis_order_super_node.items():
        if not pdg:
            continue
        # Determine vehicle and collect all positions of this super node
        positions: List[int] = []
        vehicleID = None
        for v_and_pos_str, node in pdg.items():
            parts = v_and_pos_str.split(",")
            if vehicleID is None:
                vehicleID = parts[0]
            pos = int(parts[1])
            positions.append(pos)

        if vehicleID is None or not positions:
            continue

        start_idx = min(positions)
        end_idx = max(positions)

        vehicle_node_route: List[Node] = vehicleid_to_plan.get(vehicleID, [])
        # Defensive clamp (in case of stale indices)
        start_idx = max(0, min(start_idx, len(vehicle_node_route)))
        end_idx = max(0, min(end_idx, len(vehicle_node_route) - 1))
        if start_idx > end_idx:
            continue

        # Build block by slicing the actual route to avoid mismatches
        block_nodes: List[Node] = vehicle_node_route[start_idx:end_idx + 1]

        k: str = f"{vehicleID},{start_idx}+{end_idx}"
        block_map[k] = block_nodes
    if len(block_map)  <2:
        return False
    
    origin_cost = total_cost(id_to_vehicle , route_map , vehicleid_to_plan)
    
    min_cost = origin_cost
    min_cost_block1_key_str : str = None
    min_cost_block2_key_str :str = None
    min_cost_block1 : List[Node] = None
    min_cost_block2 : List[Node] = None
    # Shuffle block_map iteration order for diversification
    shuffled_block_keys = list(block_map.keys())
    random.shuffle(shuffled_block_keys)

    idxI = 0
    for before_key in shuffled_block_keys:
        before_block = block_map[before_key]
        # Kiểm tra timeout trong vòng lặp ngoài
        if config.is_timeout() or (time.time() - op_start_time) > limit_time:
            break
        
        before_vehicle = id_to_vehicle.get(before_key.split(",")[0])
        before_posI = int(before_key.split(",")[1].split("+")[0])
        before_posJ = int(before_key.split(",")[1].split("+")[1])
        block1_len = len(before_block)
        
        # Iterate following keys in randomized order ensuring unique pairs (i < j)
        for idxJ in range(idxI + 1, len(shuffled_block_keys)):
            # Kiểm tra timeout trong vòng lặp trong (mỗi 10 iterations)
            if idxJ % 10 == 0 and ((config.is_timeout() or (time.time() - op_start_time) > limit_time)):
                break

            next_key = shuffled_block_keys[idxJ]
            next_block = block_map[next_key]
            
            next_vehicle = id_to_vehicle.get(next_key.split(",")[0])
            next_posI = int(next_key.split(",")[1].split("+")[0])
            next_posJ = int(next_key.split(",")[1].split("+")[1])
            block2_len = len(next_block) 
            
            route_node_list1 = vehicleid_to_plan.get(before_vehicle.id , [])
            route_node_list2 = vehicleid_to_plan.get(next_vehicle.id , [])
            
            if before_vehicle is not next_vehicle: 
                temp1 : List[Node]= route_node_list1[before_posI : before_posI + block1_len]
                temp2 : List[Node]= route_node_list2[next_posI : next_posI + block2_len]
                
                del route_node_list1[before_posI : before_posI + block1_len]
                del route_node_list2[next_posI : next_posI + block2_len]
                
                route_node_list1[before_posI: before_posI] = temp2
                route_node_list2[next_posI: next_posI] = temp1

                carry1 = before_vehicle.carrying_items if before_vehicle.des else []
                carry2 = next_vehicle.carrying_items if next_vehicle.des else []
                feasible = (isFeasible(route_node_list1, carry1, before_vehicle.board_capacity) and
                            isFeasible(route_node_list2, carry2, next_vehicle.board_capacity))
                if feasible:
                    test_vehicleid_to_plan = vehicleid_to_plan.copy()
                    # Sao mỏng 2 tuyến thay đổi để tránh side-effect
                    test_vehicleid_to_plan[before_vehicle.id] = route_node_list1[:] 
                    test_vehicleid_to_plan[next_vehicle.id]   = route_node_list2[:]
                    
                    cost1 = total_cost(id_to_vehicle , route_map , test_vehicleid_to_plan)
                    
                    if cost1 < min_cost:
                        is_improved = True
                        min_cost = cost1
                        min_cost_block1_key_str = before_key
                        min_cost_block2_key_str = next_key
                        min_cost_block1  = before_block[:]
                        min_cost_block2 = next_block[:]

                del route_node_list1[before_posI : before_posI + block2_len]
                del route_node_list2[next_posI : next_posI + block1_len]
                route_node_list1 [before_posI: before_posI] = temp1
                route_node_list2 [next_posI: next_posI] = temp2
            else:
                if before_posJ < next_posI or next_posJ < before_posI:
                    if next_posJ < before_posI:
                        before_posI, next_posI = next_posI, before_posI
                        before_posJ, next_posJ = next_posJ, before_posJ
                        block1_len, block2_len = block2_len, block1_len

                    temp1 = route_node_list1[before_posI: before_posI + block1_len]
                    temp2 = route_node_list1[next_posI: next_posI + block2_len]

                    del route_node_list1[next_posI: next_posI + block2_len]
                    del route_node_list1[before_posI: before_posI + block1_len]

                    route_node_list1[before_posI:before_posI] = temp2
                    real_next_post_i = next_posI + (block2_len - block1_len)
                    route_node_list1[real_next_post_i:real_next_post_i] = temp1

                    carry1 = before_vehicle.carrying_items if before_vehicle.des else []
                    feasible = isFeasible(route_node_list1, carry1, before_vehicle.board_capacity) 
                    if feasible:
                        cost1 = cost_of_a_route(route_node_list1, before_vehicle , id_to_vehicle , route_map , vehicleid_to_plan )
                    else :
                        cost1 = math.inf
                    if cost1 < min_cost:
                        is_improved = True
                        min_cost = cost1
                        min_cost_block1_key_str = before_key
                        min_cost_block2_key_str = next_key
                        min_cost_block1 = before_block[:]
                        min_cost_block2 = next_block[:]

                    del route_node_list1[real_next_post_i: real_next_post_i + block1_len]
                    del route_node_list1[before_posI: before_posI + block2_len]
                    route_node_list1[before_posI:before_posI] = temp1
                    route_node_list1[next_posI:next_posI] = temp2
            
            if is_improved and is_limited:
                break
        # Kiểm tra timeout và early exit
        if config.is_timeout() or (is_improved and is_limited) or (time.time() - op_start_time) > limit_time:
            break
        idxI +=1
    
    if is_improved:
        # Defensive: snapshot routes and coverage signature to prevent duplicates/missing nodes
        pre_state = {vid: route[:] for vid, route in vehicleid_to_plan.items()}
        pre_sig = _route_node_coverage_signature(vehicleid_to_plan)
        before_key = min_cost_block1_key_str
        before_vid, before_positions = before_key.split(",")
        before_post_i, before_post_j = map(int, before_positions.split("+"))
        before_block = min_cost_block1[:]
        block1_len = len(before_block)

        next_key = min_cost_block2_key_str
        next_vid, next_positions = next_key.split(",")
        next_post_i, next_post_j = map(int, next_positions.split("+"))
        next_dpg = min_cost_block2[:]
        block2_len = len(next_dpg)

        route_node_list1 = vehicleid_to_plan.get(before_vid, [])
        if before_vid != next_vid:
            route_node_list2 = vehicleid_to_plan.get(next_vid, [])
            temp1 = route_node_list1[before_post_i:before_post_j + 1]
            temp2 = route_node_list2[next_post_i:next_post_j + 1]

            del route_node_list1[before_post_i:before_post_i + block1_len]
            del route_node_list2[next_post_i:next_post_i + block2_len]
            
            route_node_list1[before_post_i:before_post_i] = temp2
            route_node_list2[next_post_i:next_post_i] = temp1
            
            vehicleid_to_plan[before_vid] = route_node_list1
            vehicleid_to_plan[next_vid] = route_node_list2
        else:
            temp1 = route_node_list1[before_post_i:before_post_i + block1_len]
            temp2 = route_node_list1[next_post_i:next_post_i + block2_len]

            del route_node_list1[next_post_i:next_post_i + block2_len]
            del route_node_list1[before_post_i:before_post_i + block1_len]

            route_node_list1[before_post_i:before_post_i] = temp2
            real_next_post_i = next_post_i + (block2_len - block1_len)
            route_node_list1[real_next_post_i:real_next_post_i] = temp1
            
            vehicleid_to_plan[before_vid] = route_node_list1

        # Validate coverage after mutation
        post_sig = _route_node_coverage_signature(vehicleid_to_plan)
        if pre_sig != post_sig:
            # Revert changes if coverage mismatch
            for vid in list(vehicleid_to_plan.keys()):
                vehicleid_to_plan[vid] = pre_state.get(vid, [])[:]
            return False

    return is_improved

def new_block_relocate(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , limit_time: float , is_limited: bool = False ):
    if config.is_timeout():
        return False
    op_start_time = time.time()
    
    is_improved = False
    
    dis_order_super_node = {}
    if config.USE_ADAPTIVE_ORDER_DISCRIMINATE:
        if config.CROSSOVER_TYPE_RATIO <= 0:
            dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        else:
            dis_order_super_node , _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        
    else:
        dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    
    
    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return False
    
    vehicleID = None
    block_map : Dict[str , List[Node]] = {}

    for idx, pdg in dis_order_super_node.items():
        if not pdg:
            continue
        positions: List[int] = []
        vehicleID = None
        for v_and_pos_str, node in pdg.items():
            parts = v_and_pos_str.split(",")
            if vehicleID is None:
                vehicleID = parts[0]
            positions.append(int(parts[1]))
        if vehicleID is None or not positions:
            continue
        start_idx = min(positions)
        end_idx = max(positions)
        vehicle_node_route: List[Node] = vehicleid_to_plan.get(vehicleID, [])
        start_idx = max(0, min(start_idx, len(vehicle_node_route)))
        end_idx = max(0, min(end_idx, len(vehicle_node_route) - 1))
        if start_idx > end_idx:
            continue
        block_nodes: List[Node] = vehicle_node_route[start_idx:end_idx + 1]
        k: str = f"{vehicleID},{start_idx}+{end_idx}"
        block_map[k] = block_nodes
    
    if len(block_map)  <2:
        return False
    
    
    origin_cost = total_cost(id_to_vehicle , route_map , vehicleid_to_plan)

    min_cost = origin_cost
    best_relocate_vehicleID : str = None
    best_relocate_pos : int = 0
    min_cost_block1_key_str:  str = None
    best_relocate_block : List[Node] = None
    # Randomize order of blocks to try as the moving source
    shuffled_block_keys = list(block_map.keys())
    random.shuffle(shuffled_block_keys)

    for before_key in shuffled_block_keys:
        before_block = block_map[before_key]
        # Kiểm tra timeout trong vòng lặp ngoài
        if config.is_timeout() or (time.time() - op_start_time) > limit_time:
            break
            
        before_vid, before_pos = before_key.split(",")
        before_post_i, before_post_j = map(int, before_pos.split("+"))
        before_vehicle = id_to_vehicle.get(before_vid)
        block1_len = len(before_block)
        route_node_list1 = vehicleid_to_plan.get(before_vid, [])
        
        del route_node_list1[before_post_i: before_post_i + block1_len]
        
        # Lặp qua danh sách vehicle id thực tế (được xáo trộn) để đảm bảo đồng bộ vehicle <-> route
        target_vids = list(vehicleid_to_plan.keys())
        random.shuffle(target_vids)
        for iter_idx, target_vid in enumerate(target_vids, start=1):
            # Kiểm tra timeout trong vòng lặp trong (mỗi 5 iterations)
            if iter_idx % 5 == 0 and (config.is_timeout() or (time.time() - op_start_time) > limit_time):
                break

            target_vehicle = id_to_vehicle.get(target_vid)
            if target_vehicle is None:
                continue

            route_node_list = vehicleid_to_plan.get(target_vid, [])
            node_list_size = len(route_node_list)
            insert_pos = 1 if target_vehicle.des else 0

            # Chuẩn bị trạng thái chở hiện tại để kiểm tra khả thi
            carry = target_vehicle.carrying_items if target_vehicle.des else []

            for i in range(insert_pos, node_list_size + 1):
                # Thử chèn block
                route_node_list[i:i] = before_block

                # Kiểm tra khả thi trước khi tính chi phí để tránh sinh phương án lỗi
                feasible = isFeasible(route_node_list, carry, target_vehicle.board_capacity)
                if feasible:
                    current_cost = cost_of_a_route(route_node_list, target_vehicle, id_to_vehicle, route_map, vehicleid_to_plan)

                    if current_cost < min_cost:
                        min_cost = current_cost
                        is_improved = True
                        min_cost_block1_key_str = before_key
                        best_relocate_block = list(before_block)
                        best_relocate_vehicleID = target_vid
                        best_relocate_pos = i

                # Xóa block sau khi kiểm tra
                del route_node_list[i:i + block1_len]
                if is_improved and is_limited:
                    break
        
        route_node_list1[before_post_i:before_post_i] = before_block  # Khôi phục dữ liệu ban đầu
        if config.is_timeout() or (is_improved and is_limited) or (time.time() - op_start_time) > limit_time: 
            break

    if is_improved:
        # Snapshot & signature before apply
        pre_state = {vid: route[:] for vid, route in vehicleid_to_plan.items()}
        pre_sig = _route_node_coverage_signature(vehicleid_to_plan)

        before_vid, before_pos = min_cost_block1_key_str.split(",")
        before_post_i, before_post_j = map(int, before_pos.split("+"))
        origin_route_node_list = vehicleid_to_plan.get(before_vid, [])
        del origin_route_node_list[before_post_i: before_post_i + len(best_relocate_block)]
        vehicleid_to_plan[before_vid] = origin_route_node_list

        best_relocate_route = vehicleid_to_plan.get(best_relocate_vehicleID, [])
        best_relocate_route[best_relocate_pos:best_relocate_pos] = best_relocate_block
        vehicleid_to_plan[best_relocate_vehicleID] = best_relocate_route

        post_sig = _route_node_coverage_signature(vehicleid_to_plan)
        if pre_sig != post_sig:
            # rollback
            for vid in list(vehicleid_to_plan.keys()):
                vehicleid_to_plan[vid] = pre_state.get(vid, [])[:]
            return False
    
    return is_improved

def new_multi_pd_group_relocate(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , limit_time: float , is_limited : bool = False):
    if config.is_timeout():
        return False
    op_start_time = time.time()
    
    is_improved = False
    cp_vehicle_id2_planned_route : Dict [str , List [Node]]= {}
    for key , value in vehicleid_to_plan.items():
        cp_vehicle_id2_planned_route[key] = []
        for node in value:
            cp_vehicle_id2_planned_route[key].append(node)

    dis_order_super_node = {}
    if config.USE_ADAPTIVE_ORDER_DISCRIMINATE:
        if config.CROSSOVER_TYPE_RATIO <= 0:
            dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        else:
            dis_order_super_node , _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
        
    else:
        dis_order_super_node = new_get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)

    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return False
    formal_super_node : Dict[int, Dict[str , List[Node]]]= {}
    new_formal_super_node : Dict[int, Dict[str , List[Node]]]= {}
    new_cost_delta = [math.inf] * ls_node_pair_num
    
    for idx, pdg in dis_order_super_node.items():
        # Kiểm tra timeout trong quá trình xây dựng solution
        if config.is_timeout() or (time.time() - op_start_time) > limit_time:
            break
            
        if not pdg or len(pdg) == 0:
            continue
        
        pickup_node : Node = None ; delivery_node : Node = None
        node_list = []
        index = 0
        d_num = len(pdg) // 2
        vehicle_id = None
        pos_i, pos_j = 0, 0
        
        if pdg: 
            # Them toan cac super node vao nodelist
            for v_and_pos_str , node in pdg.items():
                if index % 2 == 0:
                    vehicle_id, pos_i = v_and_pos_str.split(",")
                    pos_i = int(pos_i)
                    pickup_node =  node
                    node_list.insert(0, pickup_node)
                else:
                    pos_j = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    pos_j = pos_j - d_num + 1
                index += 1
            
            k = f"{vehicle_id},{pos_i}+{pos_j}"
            pdg_hash_map : Dict[str , List[Node]] = {k: node_list}
            formal_super_node[idx] = pdg_hash_map
            new_formal_super_node[idx] = pdg_hash_map
        
        route_node_list : List[Node] = cp_vehicle_id2_planned_route.get(vehicle_id , [])
        vehicle = id_to_vehicle.get(vehicle_id)
        
        cost_after_insertion = single_vehicle_cost(route_node_list , vehicle , route_map )
        
        del route_node_list[pos_i : pos_i + d_num]
        del route_node_list[pos_j - d_num : pos_j]
        cp_vehicle_id2_planned_route[vehicle_id] = route_node_list
        
        cost_before_insertion = single_vehicle_cost(route_node_list , vehicle , route_map )
        curr_cost_detal = cost_after_insertion - cost_before_insertion
        
        min_cost_delta, best_insert_pos_i, best_insert_pos_j, best_insert_vehicle_id = dispatch_order_to_best(node_list , cp_vehicle_id2_planned_route , id_to_vehicle , route_map)
        
        if min_cost_delta < curr_cost_detal:
            new_cost_delta[idx] = min_cost_delta
            pdg_hash_map : Dict[str , List[Node]] = {}
            k = f"{best_insert_vehicle_id},{best_insert_pos_i}+{best_insert_pos_j}"
            pdg_hash_map[k] = node_list
            new_formal_super_node[idx] = pdg_hash_map
        
        route_node_list[pos_i:pos_i] = node_list[0 : len(node_list) // 2]
        route_node_list[pos_j:pos_j] = node_list[len(node_list) // 2 : len(node_list)]

    cost_delta_temp : List[float] = new_cost_delta[:]
    sort_index = sorted(range(ls_node_pair_num), key=lambda k: cost_delta_temp[k])
    mask = [False] * len(id_to_vehicle)
    orgin_cost = -1.0
    final_cost = -1.0
    is_improved = False
    for i in range(ls_node_pair_num):
        # Kiểm tra timeout trong vòng lặp optimization
        if config.is_timeout() or (time.time() - op_start_time) > limit_time:
            break
            
        if new_cost_delta[i] != math.inf:
            before_super_node_map = formal_super_node[sort_index[i]]
            new_super_node_map = new_formal_super_node[sort_index[i]]

            before_key = next(iter(before_super_node_map))
            before_vid, before_pos = before_key.split(',')
            before_post_i, before_post_j = map(int, before_pos.split('+'))
            before_dpg = before_super_node_map[before_key]
            d_num = len(before_dpg) // 2
            before_vehicle_idx = int(before_vid.split('_')[1]) - 1

            new_key = next(iter(new_super_node_map))
            new_vid, new_pos = new_key.split(',')
            new_post_i, new_post_j = map(int, new_pos.split('+'))
            new_dpg = new_super_node_map[new_key]
            new_vehicle_idx = int(new_vid.split('_')[1]) - 1

            if not mask[before_vehicle_idx] and not mask[new_vehicle_idx]:
                before_route_node_list = copy.deepcopy(vehicleid_to_plan.get(before_vid, []))
                before_vehicle = id_to_vehicle[before_vid]
                cost0 = cost_of_a_route(before_route_node_list, before_vehicle , id_to_vehicle , route_map , vehicleid_to_plan )
                if orgin_cost < 0:
                    orgin_cost = cost0

                del before_route_node_list[before_post_i:before_post_i + d_num]
                del before_route_node_list[before_post_j - d_num:before_post_j]
                vehicleid_to_plan[before_vid] = before_route_node_list

                new_route_node_list = copy.deepcopy(vehicleid_to_plan.get(new_vid, []))
                new_vehicle = id_to_vehicle[new_vid]

                new_route_node_list[new_post_i:new_post_i] = new_dpg[:d_num]
                new_route_node_list[new_post_j:new_post_j] = new_dpg[d_num:]
                cost1 = cost_of_a_route(new_route_node_list, new_vehicle , id_to_vehicle , route_map , vehicleid_to_plan)

                if cost0 <= cost1:
                    before_route_node_list[before_post_i:before_post_i] = before_dpg[:d_num]
                    before_route_node_list[before_post_j:before_post_j] = before_dpg[d_num:]
                    vehicleid_to_plan[before_vid] = before_route_node_list
                else:
                    final_cost = cost1
                    mask[before_vehicle_idx] = True
                    mask[new_vehicle_idx] = True
                    is_improved = True
                    vehicleid_to_plan[new_vid] = new_route_node_list
                    
                    if is_limited:
                        break
    return is_improved