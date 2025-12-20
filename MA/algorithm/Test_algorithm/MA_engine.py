import copy
import sys
import math
import random
from algorithm.algorithm_config import *
from typing import Dict , List, Optional, Tuple
from algorithm.Object import *
from algorithm.engine import *
import algorithm.algorithm_config as config
from algorithm.local_search import *
from algorithm.Test_algorithm.new_LS import *



def overtime_cost(id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , vehicleid_to_plan: Dict[str , list[Node]]) -> float:
    driving_dis  : float = 0.0
    overtime_Sum : float = 0.0
    waiting_Sum  : float = 0.0
    objF : float  = 0.0
    dock_table: Dict[str, List[List[int]]] = {}
    n: int = 0
    vehicle_num: int = len(id_to_vehicle)
    curr_node: List[int] = [0] * vehicle_num
    curr_time: List[int] = [0] * vehicle_num
    leave_last_node_time: List[int] = [0] * vehicle_num

    n_node: List[int] = [0] * vehicle_num
    index = 0
    
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
                    overtime_Sum += max(0 , curr_time[minT2VehicleIndex] - commitCompleteTime)
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

        # Accumulate waiting time at this factory (queueing delay before service starts)
        if minT != math.inf and tTrue != math.inf:
            waiting_Sum += max(0, tTrue - minT)

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
                        overtime_Sum += max(0, curr_time[minT2VehicleIndex] - commit_complete_time)
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
    
    # Weight for waiting time; falls back to config.Delta if no dedicated setting is present
    waiting_weight = config.WAITING_WEIGHT
    objF = (config.Delta * overtime_Sum) + (driving_dis / float(len(id_to_vehicle))) + (waiting_weight * waiting_Sum)
    if objF < 0:
        print("the objective function less than 0" , file= sys.stderr)
    return overtime_Sum * config.Delta



def Pre_population_initialization(Base_vehicleid_to_plan : Dict[str , List[Node]] , UnongoingSuperNodes : Dict[int , Dict[str , Node]] , id_to_factory:Dict[str , Factory] , route_map: Dict[tuple , tuple] ,  id_to_vehicle: Dict[str , Vehicle] , id_to_unlocated_items:Dict[str , OrderItem], new_order_itemIDs: list[str]):
    if not new_order_itemIDs:
        return None

    # Gom nhóm các item theo order_id; bỏ qua ID không hợp lệ
    orderId_to_Item: Dict[str, list[OrderItem]] = {}
    for new_order_item_id in new_order_itemIDs:
        new_item = id_to_unlocated_items.get(new_order_item_id)
        if new_item is None:
            print(f"WARN: unknown order_item_id '{new_order_item_id}'", file=sys.stderr)
            continue
        order_id = new_item.order_id
        orderId_to_Item.setdefault(order_id, []).append(new_item)
    
    # Sắp xếp danh sách item trong mỗi đơn theo hậu tố số tăng dần (vd: 1420180055-1, -2, ...)
    def _suffix_from_id(iid: Optional[str], order_id: str) -> int:
        try:
            if not isinstance(iid, str):
                return 0
            prefix = f"{order_id}-"
            if iid.startswith(prefix):
                return int(iid[len(prefix):])
        except Exception:
            pass
        return 0

    for _oid, _items in orderId_to_Item.items():
        try:
            _items.sort(key=lambda it: _suffix_from_id(getattr(it, 'id', None), _oid))
        except Exception:
            # An toàn: nếu có item thiếu id, giữ nguyên thứ tự
            pass
    

    # Sử dụng ngưỡng dung lượng hợp lý (cực đại trong đội xe) để quyết định tách đơn sớm
    capacity_threshold = max((v.board_capacity for v in id_to_vehicle.values()), default=0)

    # Ánh xạ vehicleID -> các order có điểm nhận và giao trùng với vị trí hiện tại và điểm đến của xe
    considered_nodelist: Dict[str, List[str]] = {vk: [] for vk in id_to_vehicle.keys()}
    vehicle_curr_location: Dict[str, Optional[str]] = {vk: None for vk in id_to_vehicle.keys()}
    vehicle_des_location: Dict[str, Optional[str]] = {vk: None for vk in id_to_vehicle.keys()}

    for veh_ID, veh in id_to_vehicle.items():
        if getattr(veh, 'cur_factory_id', None):
            vehicle_curr_location[veh_ID] = veh.cur_factory_id
        if getattr(veh, 'des', None):
            # veh.des có thể là Node/Destination có id
            vehicle_des_location[veh_ID] = getattr(veh.des, 'id', None)

    # Ánh xạ từ id đơn hàng đến danh sách các cặp node (pickup, delivery)
    orderId_to_nodelist: Dict[str, List[List[Node]]] = {oid: [] for oid in orderId_to_Item.keys()}
    # Signature set to avoid duplicate PDG pairs per order
    orderId_to_sigset: Dict[str, set] = {oid: set() for oid in orderId_to_Item.keys()}

    def pdg_signature(pickup_node: Node, delivery_node: Node) -> tuple:
        def ids_from(items: List[OrderItem]):
            return tuple(sorted([getattr(it, 'id', None) for it in (items or []) if getattr(it, 'id', None) is not None]))
        return (
            pickup_node.id,
            ids_from(getattr(pickup_node, 'pickup_item_list', [])),
            delivery_node.id,
            ids_from(getattr(delivery_node, 'delivery_item_list', [])),
        )
    
    # Đếm số cặp từ lời giải trước để kiểm tra thống nhất sau khi thêm cặp mới
    pre_pdg_count = 0

    
    for temp_iter in UnongoingSuperNodes.values():
        if len(temp_iter) != 2: print('     ERROR: Co cap ko co 2 node')
        
        pickup_node = None
        delivery_node = None
        for node in temp_iter.values():
            if node.pickup_item_list and not node.delivery_item_list:
                pickup_node = node
            elif node.delivery_item_list and not node.pickup_item_list:
                delivery_node = node
        
        if pickup_node is None or delivery_node is None:
            print('     ERROR: UnongoingSuperNodes co node khong hop le (khong xac dinh duoc pickup/delivery)', file=sys.stderr)
            continue

        orid = pickup_node.pickup_item_list[0].order_id
        if orid != delivery_node.delivery_item_list[-1].order_id:
            print('   ERROR: co cap node khong trung orderid', file=sys.stderr)

        # Avoid duplicate PDG pair for this order
        if orid not in orderId_to_nodelist:
            orderId_to_nodelist[orid] = []
            orderId_to_sigset[orid] = set()
        sig = pdg_signature(pickup_node, delivery_node)
        if sig not in orderId_to_sigset[orid]:
            orderId_to_nodelist[orid].append([pickup_node , delivery_node])
            orderId_to_sigset[orid].add(sig)
            pre_pdg_count += 1

        # Đưa order này vào danh sách xem xét của các xe có (cur -> des) khớp (pickup -> delivery)
        for veh_ID in id_to_vehicle.keys():
            if (vehicle_curr_location.get(veh_ID) == pickup_node.id and
                vehicle_des_location.get(veh_ID) == delivery_node.id) and (vehicle_curr_location.get(veh_ID) != vehicle_des_location.get(veh_ID) == delivery_node.id):
                if orid not in considered_nodelist[veh_ID]:
                    considered_nodelist[veh_ID].append(orid)
                    print('     THEM 1 PHAN TU')
    
    
    true_PDG_number = 0

    for orderID, order_items in orderId_to_Item.items():
        # Tổng demand của order (giả định mỗi item là nguyên tử)
        order_demand = sum(item.demand for item in order_items)

        # Order đại diện để lấy pickup/delivery factory id
        temp = order_items[0]
        for veh_ID in id_to_vehicle.keys():
            if (temp.pickup_factory_id == vehicle_curr_location[veh_ID] and
                temp.delivery_factory_id == vehicle_des_location[veh_ID]):
                if temp.order_id not in considered_nodelist[veh_ID]:
                    considered_nodelist[veh_ID].append(temp.order_id)

        # Nếu tổng demand vượt ngưỡng, tách thành các PDG theo từng item
        if order_demand > capacity_threshold:
            for item in order_items:
                pdg_nodes: List[Node] = create_Pickup_Delivery_nodes([item], id_to_factory)
                if pdg_nodes and len(pdg_nodes) >= 2:
                    a, b = pdg_nodes[0], pdg_nodes[1]
                    is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                    is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                    pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)
                    sig = pdg_signature(pickup_node, delivery_node)
                    if sig not in orderId_to_sigset.setdefault(temp.order_id, set()):
                        orderId_to_nodelist.setdefault(temp.order_id, []).append([pickup_node, delivery_node])
                        orderId_to_sigset[temp.order_id].add(sig)
                        true_PDG_number += 1
        else:
            pdg_nodes: List[Node] = create_Pickup_Delivery_nodes(order_items, id_to_factory)
            if pdg_nodes and len(pdg_nodes) >= 2:
                a, b = pdg_nodes[0], pdg_nodes[1]
                is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)
                sig = pdg_signature(pickup_node, delivery_node)
                if sig not in orderId_to_sigset.setdefault(temp.order_id, set()):
                    orderId_to_nodelist.setdefault(temp.order_id, []).append([pickup_node, delivery_node])
                    orderId_to_sigset[temp.order_id].add(sig)
                    true_PDG_number += 1

    # Kiểm tra nhất quán số cặp đã gom (cặp cũ + cặp mới)
    total_pairs = sum(len(v) for v in orderId_to_nodelist.values())
    expected_total = pre_pdg_count + true_PDG_number
    
    if total_pairs != expected_total:
        print(f'     WARN: so luong cap node khong khop (thuc te={total_pairs}, mong doi={expected_total})', file=sys.stderr)

    # Gộp các PDG đã tách nếu tổng demand của đơn hàng hiện tại <= capacity_threshold
    # Đồng thời đảm bảo các cặp cùng (pickup_factory_id, delivery_factory_id).
    # Sau khi gộp, yêu cầu sắp xếp danh sách item:
    #  - pickup_item_list: thứ tự tăng dần theo hậu tố số (order_id-1, -2, -3, ...)
    #  - delivery_item_list: thứ tự giảm dần theo hậu tố số
    def _parse_seq_from_item_id(item: OrderItem, order_id: str) -> int:
        try:
            iid = getattr(item, 'id', None)
            if not isinstance(iid, str):
                return 0
            prefix = f"{order_id}-"
            if iid.startswith(prefix):
                tail = iid[len(prefix):]
                return int(tail)
            # Fallback: nếu không theo định dạng, trả 0 để ổn định
            return 0
        except Exception:
            return 0

    '''
    for orderID in list(orderId_to_nodelist.keys()):
        pdg_list = orderId_to_nodelist.get(orderID, [])
        if not pdg_list or len(pdg_list) <= 1:
            continue

        # Thu thập item và kiểm tra đồng nhất nhà máy
        unique_items: Dict[str, OrderItem] = {}
        pickup_ids = set()
        delivery_ids = set()

        for pair in pdg_list:
            if not pair or len(pair) < 2:
                continue
            a, b = pair[0], pair[1]
            is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
            is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
            pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)

            if pickup_node is None or delivery_node is None:
                continue

            pickup_ids.add(pickup_node.id)
            delivery_ids.add(delivery_node.id)

            for it in (pickup_node.pickup_item_list or []):
                it_id = getattr(it, 'id', None)
                if it_id is not None:
                    unique_items.setdefault(it_id, it)
            for it in (delivery_node.delivery_item_list or []):
                it_id = getattr(it, 'id', None)
                if it_id is not None:
                    unique_items.setdefault(it_id, it)

        # Chỉ tiến hành gộp nếu tất cả cặp có cùng factory pickup và delivery
        if len(pickup_ids) != 1 or len(delivery_ids) != 1:
            continue

        # Tính tổng demand hiện tại của đơn
        try:
            total_demand = sum(float(getattr(it, 'demand', 0.0) or 0.0) for it in unique_items.values())
        except Exception:
            total_demand = math.inf

        if total_demand <= capacity_threshold:
            combined_items = list(unique_items.values())
            # Tạo lại 1 cặp node duy nhất từ toàn bộ items
            try:
                merged_nodes: List[Node] = create_Pickup_Delivery_nodes(combined_items, id_to_factory)
            except Exception as e:
                print(f"     WARN: merge PDG for order '{orderID}' failed when creating nodes: {e}")
                merged_nodes = None

            if merged_nodes and len(merged_nodes) >= 2:
                a, b = merged_nodes[0], merged_nodes[1]
                is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)

                # Sắp xếp danh sách item theo yêu cầu: pickup tăng dần, delivery giảm dần
                try:
                    pick_items = list(pickup_node.pickup_item_list or [])
                    delv_items = list(delivery_node.delivery_item_list or [])

                    pick_items.sort(key=lambda it: _parse_seq_from_item_id(it, orderID))
                    delv_items.sort(key=lambda it: _parse_seq_from_item_id(it, orderID), reverse=True)

                    pickup_node.pickup_item_list = pick_items
                    delivery_node.delivery_item_list = delv_items
                except Exception as e:
                    print(f"     WARN: sort merged items for order '{orderID}' failed: {e}")

                # Thay thế toàn bộ danh sách PDG của order này bằng đúng 1 cặp đã gộp
                orderId_to_nodelist[orderID] = [[pickup_node, delivery_node]]
                # Cập nhật chữ ký để tránh trùng
                orderId_to_sigset.setdefault(orderID, set()).clear()
                orderId_to_sigset[orderID].add(pdg_signature(pickup_node, delivery_node))
                print(f"    DA GOP 1 DON HANG id : {orderID}")
            else:
                print(f"     WARN: merge PDG for order '{orderID}' created invalid node pair")
    '''
    # Chèn các đơn hàng trong considered_nodelist mà không vi phạm và không làm tăng delay time
    for vehicleID, orders_list in considered_nodelist.items():
        vehicle = id_to_vehicle[vehicleID]
        if not orders_list:
            continue

        route_node_list = Base_vehicleid_to_plan.get(vehicleID)
        if not route_node_list or len(route_node_list) < 2:
            # Không có lộ trình đủ dài để chèn giữa hai node liên tiếp
            continue

        # Dedupe orders list per vehicle to avoid processing same order multiple times
        unique_orders = []
        seen_orders = set()
        for oid in orders_list:
            if oid not in seen_orders:
                unique_orders.append(oid)
                seen_orders.add(oid)

        for orderID in unique_orders:
            pdg_list = orderId_to_nodelist.get(orderID, [])
            if not pdg_list:
                continue

            # Duyệt bằng chỉ số để có thể xoá phần tử khi đã chèn thành công
            j = 0
            while j < len(pdg_list):
                pdg_nodes = pdg_list[j]
                if not pdg_nodes or len(pdg_nodes) < 2:
                    j += 1
                    continue

                # Xác định pickup và delivery node đúng chiều
                a, b = pdg_nodes[0], pdg_nodes[1]
                is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                if is_a_pick and is_b_delv:
                    pickup_node, delivery_node = a, b
                else:
                    pickup_node, delivery_node = b, a

                inserted = False
                """ for i in range(len(route_node_list) - 1):
                    curr_node = route_node_list[i]
                    next_node = route_node_list[i + 1]

                    # Chỉ xem xét chèn giữa đoạn có cùng cặp nhà máy (đúng ý định "không tăng delay")
                    if curr_node.id == pickup_node.id and next_node.id == delivery_node.id:
                        before_cost = overtime_cost(id_to_vehicle, route_map, Base_vehicleid_to_plan)

                        # Chèn ngay sau curr_node để nằm giữa (pickup -> [pdg_nodes] -> delivery)
                        route_node_list[i + 1:i + 1] = pdg_nodes

                        after_cost = overtime_cost(id_to_vehicle, route_map, Base_vehicleid_to_plan)

                        carrying_items = vehicle.carrying_items if vehicle.des else []
                        if isFeasible(route_node_list, carrying_items, vehicle.board_capacity) and after_cost <= before_cost:
                            inserted = True
                            break
                        else:
                            # Hoàn tác nếu không thoả
                            del route_node_list[i + 1:i + 1 + len(pdg_nodes)] """
                tmp_nodelist = [pickup_node , delivery_node]
                isExhausive = False
                route_node_list : List[Node] = []

                bestInsertVehicleID = None
                bestInsertPosI = 0
                bestInsertPosJ = 1
                bestNodeList: List[Node] = []
                if tmp_nodelist:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = MA_dispatch_nodepair(
                        tmp_nodelist , id_to_vehicle , Base_vehicleid_to_plan , route_map , vehicleID)

                if not bestInsertVehicleID:
                    # Cannot place this PDG now; skip to next
                    inserted = False
                else:
                    route_node_list = Base_vehicleid_to_plan.get(bestInsertVehicleID , [])
                    if isExhausive and bestNodeList:
                        Base_vehicleid_to_plan[bestInsertVehicleID] = bestNodeList[:]
                        inserted = True
                    else:
                        if route_node_list is None:
                            route_node_list = []
                        new_order_pickup_node = tmp_nodelist[0]
                        new_order_delivery_node = tmp_nodelist[1]
                        # Insert ensuring delivery index adjusted if needed
                        route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                        route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                        Base_vehicleid_to_plan[bestInsertVehicleID] = route_node_list
                        inserted = True

                if inserted:
                    # Xoá cặp node vừa chèn ra khỏi orderId_to_nodelist để tránh lặp
                    pdg_list.pop(j)

                    # Nếu order này đã hết cặp node, dọn dẹp trong các dict liên quan
                    if len(pdg_list) == 0:
                        orderId_to_nodelist.pop(orderID, None)
                        # Bỏ orderID khỏi danh sách xem xét của tất cả các xe để tránh lặp
                        for _veh_id, _orders in considered_nodelist.items():
                            if _orders:
                                considered_nodelist[_veh_id] = [oid for oid in _orders if oid != orderID]
                    # Không tăng j vì danh sách đã rút ngắn; tiếp tục thử các PDG còn lại (nếu có)
                    continue
                else:
                    # Không chèn được PDG hiện tại, chuyển sang PDG tiếp theo
                    j += 1
    
    return orderId_to_nodelist



def Pre_population_initialization_2(Base_vehicleid_to_plan : Dict[str , List[Node]] , UnongoingSuperNodes : Dict[int , Dict[str , Node]] , id_to_factory:Dict[str , Factory] , route_map: Dict[tuple , tuple] ,  id_to_vehicle: Dict[str , Vehicle] , id_to_unlocated_items:Dict[str , OrderItem], new_order_itemIDs: list[str]):
    if not new_order_itemIDs:
        return None

    # Gom nhóm các item theo order_id; bỏ qua ID không hợp lệ
    orderId_to_Item: Dict[str, list[OrderItem]] = {}
    for new_order_item_id in new_order_itemIDs:
        new_item = id_to_unlocated_items.get(new_order_item_id)
        if new_item is None:
            print(f"WARN: unknown order_item_id '{new_order_item_id}'", file=sys.stderr)
            continue
        order_id = new_item.order_id
        orderId_to_Item.setdefault(order_id, []).append(new_item)
    
    
    # xử lý UnongoingSuperNodes
    # Bổ sung các order item đang “Unongoing” vào cùng cấu trúc xử lý với new_order_itemIDs.
    # UnongoingSuperNodes: Dict[int, Dict[str, Node]] mỗi giá trị là cặp 2 Node (pickup/delivery).
    # Ta lấy toàn bộ OrderItem trong pickup_item_list / delivery_item_list và đưa vào orderId_to_Item theo order_id.
    # Tránh trùng bằng bộ nhớ set theo (order_id, item.id)
    added_item_keys: set[ str] = set()
    for order_id, items in orderId_to_Item.items():
        for it in items:
            iid = getattr(it, 'id', None)
            if iid is not None:
                added_item_keys.add(iid)

    for pair_dict in (UnongoingSuperNodes or {}).values():
        if not pair_dict or len(pair_dict) < 2:
            continue
        # Xác định pickup / delivery node
        pickup_node: Optional[Node] = None
        delivery_node: Optional[Node] = None
        for node in pair_dict.values():
            if node.pickup_item_list and not node.delivery_item_list:
                pickup_node = node
            elif node.delivery_item_list and not node.pickup_item_list:
                delivery_node = node
        
        if pickup_node is None or delivery_node is None:
            # Không xác định đúng cặp, bỏ qua để an toàn
            continue
        
        # Gom items từ pickup và delivery (delivery có thể chứa các item cùng order đã ghép)
        candidate_lists: List[List[OrderItem]] = []
        if pickup_node.pickup_item_list:
            candidate_lists.append(pickup_node.pickup_item_list)
        
        for item_list in candidate_lists:
            for it in item_list:
                oid = it.order_id
                iid = it.id
                if oid is None or iid is None:
                    continue
                key =  iid
                if key in added_item_keys:
                    continue  # đã có
                
                tmp_item = id_to_unlocated_items.get(iid)
                if tmp_item is None:
                    print(f"WARN: unknown order_item_id '{iid}'", file=sys.stderr)
                    continue
                
                added_item_keys.add(key)
                orderId_to_Item.setdefault(oid, []).append(it)

    # Sau khi đã tổng hợp đầy đủ, sắp xếp item trong từng đơn theo hậu tố số tăng dần (order_id-1, -2, ...)
    def _suffix_from_id_2(iid: Optional[str], order_id: str) -> int:
        try:
            if not isinstance(iid, str):
                return 0
            prefix = f"{order_id}-"
            if iid.startswith(prefix):
                return int(iid[len(prefix):])
        except Exception:
            pass
        return 0

    for _oid, _items in orderId_to_Item.items():
        try:
            _items.sort(key=lambda it: _suffix_from_id_2(getattr(it, 'id', None), _oid))
        except Exception:
            pass

    

    # Sử dụng ngưỡng dung lượng hợp lý (cực đại trong đội xe) để quyết định tách đơn sớm
    capacity_threshold = max((v.board_capacity for v in id_to_vehicle.values()), default=0)

    # Ánh xạ vehicleID -> các order có điểm nhận và giao trùng với vị trí hiện tại và điểm đến của xe
    considered_nodelist: Dict[str, List[str]] = {vk: [] for vk in id_to_vehicle.keys()}
    vehicle_curr_location: Dict[str, Optional[str]] = {vk: None for vk in id_to_vehicle.keys()}
    vehicle_des_location: Dict[str, Optional[str]] = {vk: None for vk in id_to_vehicle.keys()}

    for veh_ID, veh in id_to_vehicle.items():
        if getattr(veh, 'cur_factory_id', None):
            vehicle_curr_location[veh_ID] = veh.cur_factory_id
        if getattr(veh, 'des', None):
            # veh.des có thể là Node/Destination có id
            vehicle_des_location[veh_ID] = getattr(veh.des, 'id', None)

    # Ánh xạ từ id đơn hàng đến danh sách các cặp node (pickup, delivery)
    orderId_to_nodelist: Dict[str, List[List[Node]]] = {oid: [] for oid in orderId_to_Item.keys()}
    # Signature set to avoid duplicate PDG pairs per order
    orderId_to_sigset: Dict[str, set] = {oid: set() for oid in orderId_to_Item.keys()}

    def pdg_signature(pickup_node: Node, delivery_node: Node) -> tuple:
        def ids_from(items: List[OrderItem]):
            return tuple(sorted([getattr(it, 'id', None) for it in (items or []) if getattr(it, 'id', None) is not None]))
        return (
            pickup_node.id,
            ids_from(getattr(pickup_node, 'pickup_item_list', [])),
            delivery_node.id,
            ids_from(getattr(delivery_node, 'delivery_item_list', [])),
        )
    

    # Khởi tạo biến đếm giống hàm gốc
    true_PDG_number = 0
    pre_pdg_count = 0  # (ở phiên bản này chưa dùng đến nhưng giữ cho nhất quán nếu mở rộng sau)

    for orderID, order_items in orderId_to_Item.items():
        # Tổng demand của order (giả định mỗi item là nguyên tử)
        order_demand = sum(item.demand for item in order_items)

        # Order đại diện để lấy pickup/delivery factory id
        temp = order_items[0]
        for veh_ID in id_to_vehicle.keys():
            if (temp.pickup_factory_id == vehicle_curr_location[veh_ID] and
                temp.delivery_factory_id == vehicle_des_location[veh_ID]):
                if temp.order_id not in considered_nodelist[veh_ID]:
                    considered_nodelist[veh_ID].append(temp.order_id)

        # Nếu tổng demand vượt ngưỡng, tách thành các PDG theo từng item
        if order_demand > capacity_threshold:
            for item in order_items:
                pdg_nodes: List[Node] = create_Pickup_Delivery_nodes([item], id_to_factory)
                if pdg_nodes and len(pdg_nodes) >= 2:
                    a, b = pdg_nodes[0], pdg_nodes[1]
                    is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                    is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                    pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)
                    sig = pdg_signature(pickup_node, delivery_node)
                    if sig not in orderId_to_sigset.setdefault(temp.order_id, set()):
                        orderId_to_nodelist.setdefault(temp.order_id, []).append([pickup_node, delivery_node])
                        orderId_to_sigset[temp.order_id].add(sig)
                        true_PDG_number += 1
        else:
            pdg_nodes: List[Node] = create_Pickup_Delivery_nodes(order_items, id_to_factory)
            if pdg_nodes and len(pdg_nodes) >= 2:
                a, b = pdg_nodes[0], pdg_nodes[1]
                is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)
                sig = pdg_signature(pickup_node, delivery_node)
                if sig not in orderId_to_sigset.setdefault(temp.order_id, set()):
                    orderId_to_nodelist.setdefault(temp.order_id, []).append([pickup_node, delivery_node])
                    orderId_to_sigset[temp.order_id].add(sig)
                    true_PDG_number += 1
    
    
    # Chèn các đơn hàng trong considered_nodelist mà không vi phạm và không làm tăng delay time
    for vehicleID, orders_list in considered_nodelist.items():
        vehicle = id_to_vehicle[vehicleID]
        if not orders_list:
            continue

        route_node_list = Base_vehicleid_to_plan.get(vehicleID)
        if not route_node_list or len(route_node_list) < 2:
            # Không có lộ trình đủ dài để chèn giữa hai node liên tiếp
            continue

        # Dedupe orders list per vehicle to avoid processing same order multiple times
        unique_orders = []
        seen_orders = set()
        for oid in orders_list:
            if oid not in seen_orders:
                unique_orders.append(oid)
                seen_orders.add(oid)

        for orderID in unique_orders:
            pdg_list = orderId_to_nodelist.get(orderID, [])
            if not pdg_list:
                continue

            # Duyệt bằng chỉ số để có thể xoá phần tử khi đã chèn thành công
            j = 0
            while j < len(pdg_list):
                pdg_nodes = pdg_list[j]
                if not pdg_nodes or len(pdg_nodes) < 2:
                    j += 1
                    continue

                # Xác định pickup và delivery node đúng chiều
                a, b = pdg_nodes[0], pdg_nodes[1]
                is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
                is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
                if is_a_pick and is_b_delv:
                    pickup_node, delivery_node = a, b
                else:
                    pickup_node, delivery_node = b, a

                inserted = False
                tmp_nodelist = [pickup_node , delivery_node]
                isExhausive = False
                route_node_list : List[Node] = []

                bestInsertVehicleID = None
                bestInsertPosI = 0
                bestInsertPosJ = 1
                bestNodeList: List[Node] = []
                if tmp_nodelist:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = MA_dispatch_nodepair(
                        tmp_nodelist , id_to_vehicle , Base_vehicleid_to_plan , route_map , vehicleID)

                if not bestInsertVehicleID:
                    # Cannot place this PDG now; skip to next
                    inserted = False
                else:
                    route_node_list = Base_vehicleid_to_plan.get(bestInsertVehicleID , [])
                    if isExhausive and bestNodeList:
                        Base_vehicleid_to_plan[bestInsertVehicleID] = bestNodeList[:]
                        inserted = True
                    else:
                        if route_node_list is None:
                            route_node_list = []
                        new_order_pickup_node = tmp_nodelist[0]
                        new_order_delivery_node = tmp_nodelist[1]
                        # Insert ensuring delivery index adjusted if needed
                        route_node_list.insert(bestInsertPosI, new_order_pickup_node)
                        route_node_list.insert(bestInsertPosJ, new_order_delivery_node)
                        Base_vehicleid_to_plan[bestInsertVehicleID] = route_node_list
                        inserted = True

                if inserted:
                    # Xoá cặp node vừa chèn ra khỏi orderId_to_nodelist để tránh lặp
                    pdg_list.pop(j)

                    # Nếu order này đã hết cặp node, dọn dẹp trong các dict liên quan
                    if len(pdg_list) == 0:
                        orderId_to_nodelist.pop(orderID, None)
                        # Bỏ orderID khỏi danh sách xem xét của tất cả các xe để tránh lặp
                        for _veh_id, _orders in considered_nodelist.items():
                            if _orders:
                                considered_nodelist[_veh_id] = [oid for oid in _orders if oid != orderID]
                    # Không tăng j vì danh sách đã rút ngắn; tiếp tục thử các PDG còn lại (nếu có)
                    continue
                else:
                    # Không chèn được PDG hiện tại, chuyển sang PDG tiếp theo
                    j += 1
    
    return orderId_to_nodelist


def build_chromosome_MA(Base_vehicleid_to_plan: Dict[str, List[Node]], id_to_vehicle: Dict[str, Vehicle], route_map: Dict[tuple, tuple], orderID_to_nodelist: Dict[str, List[List[Node]]]) -> Chromosome:
    
    new_vehicle_to_plan : Dict[str , List[Node]] = {}
    for VID , plan in Base_vehicleid_to_plan.items():
        new_vehicle_to_plan[VID] = []
        for node in plan:
            new_vehicle_to_plan[VID].append(copy.deepcopy(node))
    
    # Gom tất cả các cặp PDG rồi xáo trộn để thêm ngẫu nhiên
    all_pairs: List[List[Node]] = []
    for _orderID , order_nodelist in orderID_to_nodelist.items():
        for pdg_pair in order_nodelist:
            if not pdg_pair or len(pdg_pair) < 2:
                continue
            a, b = pdg_pair[0], pdg_pair[1]
            is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
            is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
            pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)
            # Dùng deepcopy để không làm thay đổi nguồn
            all_pairs.append([copy.deepcopy(pickup_node), copy.deepcopy(delivery_node)])

    random.shuffle(all_pairs)

    vehicle_ids = list(id_to_vehicle.keys())

    # Thêm từng cặp: chọn ngẫu nhiên 1 xe và thử gắn vào cuối tuyến của xe đó
    for pair in all_pairs:
        pickup_node, delivery_node = pair
        tried = vehicle_ids[:]
        random.shuffle(tried)

        placed = False
        for vid in tried:
            route = new_vehicle_to_plan.get(vid)
            if route is None:
                route = []
                new_vehicle_to_plan[vid] = route

            # Thử chèn vào cuối tuyến
            route.extend([pickup_node, delivery_node])
            vehicle = id_to_vehicle[vid]
            carrying_items = vehicle.carrying_items if getattr(vehicle, 'des', None) else []
            if isFeasible(route, carrying_items, vehicle.board_capacity):
                placed = True
                break
            else:
                # Hoàn tác nếu không khả thi
                route.pop(); route.pop()

        if not placed:
            # Dự phòng: thử chèn ngẫu nhiên theo hàm sẵn có
            random_dispatch_nodePair([pickup_node, delivery_node], id_to_vehicle, new_vehicle_to_plan)

    return Chromosome(new_vehicle_to_plan , route_map , id_to_vehicle)


def Population_initialization(Base_vehicleid_to_plan: Dict[str, List[Node]], route_map: Dict[tuple, tuple], id_to_vehicle: Dict[str, Vehicle], orderID_to_nodelist: Dict[str, List[List[Node]]], quantity: int) -> List[Chromosome]:
    
    if orderID_to_nodelist is None: return None
    if len(orderID_to_nodelist) == 0: return None
    
    population: List[Chromosome] = []
    
    while len(population) < quantity:
        new_individual = build_chromosome_MA(Base_vehicleid_to_plan, id_to_vehicle, route_map, orderID_to_nodelist)
        if new_individual:
            population.append(new_individual)
    
    return population


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
                        delaytime_to_node[minT2VehicleID][curr_node[minT2VehicleIndex]] += temp / 3600
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
                            delaytime_to_node[minT2VehicleID][curr_node[minT2VehicleIndex]] += temp / 3600
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

def Local_search_MA(individual: Chromosome, PDG_map: Dict[str, List[Node]]):
    """
    Triển khai theo yêu cầu:
    - Tính delaytime cho mỗi node bằng delaytime_for_each_node (delay chỉ nằm ở các node giao hàng)
    - Với mỗi cặp PDG, tìm vị trí node nhận và node giao tương ứng trong lời giải hiện tại,
      lấy delay tại node giao, và trả về vị trí (pickup_idx, delivery_idx) cùng delay.

    Trả về:
    - delaytime_to_node: Dict[vehicleID, List[float]]
    - pdg_index_delay_map: Dict[pdg_key, Tuple[vehicleID, pickup_idx, delivery_idx, delay_at_delivery_node]]
    """
    before_cost = individual.fitness
    # Invariant baseline: original multiset of node object identities across all routes
    original_node_id_multiset = sorted([id(node) for route in individual.solution.values() for node in route])
    # Destination invariants: map vehicleID -> expected destination factory id (if any)
    dest_factory_map = {vid: veh.des.id for vid, veh in individual.id_to_vehicle.items() if getattr(veh, 'des', None)}

    def check_invariants(candidate_solution: Dict[str, List[Node]]) -> bool:
        """Verify no node loss/duplication and destination unchanged for vehicles with a destination."""
        # Destination position invariant
        for vid, dest_id in dest_factory_map.items():
            route = candidate_solution.get(vid, [])
            if not route or route[0].id != dest_id:
                return False
        # Multiset of node identities invariant (same objects, just reordered)
        candidate_ids = sorted([id(node) for route in candidate_solution.values() for node in route])
        if candidate_ids != original_node_id_multiset:
            return False
        return True
    for i in range(config.LS_MAX):
        if config.is_timeout():
            break
        
        # 1) Độ trễ theo từng nút (node-level), delay chỉ gán tại các node giao
        delaytime_to_node = delaytime_for_each_node(
            individual.id_to_vehicle, individual.route_map, individual.solution
        )

        vehicleid_to_plan = individual.solution

        # 2) Duyệt mỗi PDG, tìm chỉ số node nhận và giao trong solution
        pdg_index_delay_map: Dict[str, Tuple[str, int, int, float]] = {}

        # Tiện ích: lấy tập id item từ danh sách item
        def item_ids(items: List[OrderItem]) -> set:
            ids = set()
            for it in items or []:
                # ưu tiên id duy nhất của item nếu có; fallback order_id
                ids.add(getattr(it, 'id', None) or getattr(it, 'order_id', None))
            ids.discard(None)
            return ids

        for key, pdg_nodes in PDG_map.items():
            if not pdg_nodes or len(pdg_nodes) < 2:
                continue

            a, b = pdg_nodes[0], pdg_nodes[1]
            is_a_pick = bool(a.pickup_item_list) and not bool(a.delivery_item_list)
            is_b_delv = bool(b.delivery_item_list) and not bool(b.pickup_item_list)
            pickup_node, delivery_node = (a, b) if is_a_pick and is_b_delv else (b, a)

            pick_factory = pickup_node.id
            delv_factory = delivery_node.id
            pick_items = item_ids(pickup_node.pickup_item_list)
            delv_items = item_ids(delivery_node.delivery_item_list)

            found = False
            for vehicleID, route in vehicleid_to_plan.items():
                # tìm index pickup và delivery trên cùng xe
                pick_idx = -1
                delv_idx = -1

                # chuẩn bị chữ ký items tại mỗi node route
                for idx, node in enumerate(route):
                    if pick_idx == -1 and node.id == pick_factory and node.pickup_item_list:
                        route_pick_ids = item_ids(node.pickup_item_list)
                        if pick_items.issubset(route_pick_ids):
                            pick_idx = idx
                    if delv_idx == -1 and node.id == delv_factory and node.delivery_item_list:
                        route_delv_ids = item_ids(node.delivery_item_list)
                        if delv_items.issubset(route_delv_ids):
                            delv_idx = idx
                    if pick_idx != -1 and delv_idx != -1:
                        break

                if pick_idx != -1 and delv_idx != -1:
                    # delay tại node giao lấy trực tiếp từ delaytime_to_node
                    per_node_delays = delaytime_to_node.get(vehicleID, [])
                    delay_val = 0.0
                    if 0 <= delv_idx < len(per_node_delays):
                        delay_val = float(per_node_delays[delv_idx] or 0.0)
                    pdg_index_delay_map[key] = (vehicleID, pick_idx, delv_idx, delay_val)
                    found = True
                    break

            if not found:
                # Không tìm thấy, trả về giá trị rỗng hợp lý
                pdg_index_delay_map[key] = ("", -1, -1, 0.0)
        
        
        vehicleid_to_plan = individual.solution
        
        chosen_key, chosen_val = None, None
        moved = False
        tries = 0
        while tries < 10 and not moved:
            tries += 1
            chosen_key, chosen_val = roulette_select_pdg_by_delay(pdg_index_delay_map)
            if not chosen_key or not chosen_val:
                continue

            orig_vid, orig_pick_idx, orig_delv_idx, _delay = chosen_val
            current_route = vehicleid_to_plan.get(orig_vid, [])
            if (orig_pick_idx < 0 or orig_delv_idx < 0 or
                orig_pick_idx >= len(current_route) or orig_delv_idx >= len(current_route)):
                # Indices stale; skip
                continue

            # Work on a temporary copy of the whole solution (structure only)
            temp_solution = {vid: list(r) for vid, r in vehicleid_to_plan.items()}
            temp_route = temp_solution[orig_vid]

            try:
                hi, lo = (orig_delv_idx, orig_pick_idx) if orig_delv_idx > orig_pick_idx else (orig_pick_idx, orig_delv_idx)
                node_hi = temp_route.pop(hi)
                node_lo = temp_route.pop(lo)
                if node_lo.pickup_item_list and not node_lo.delivery_item_list:
                    pickup_node = node_lo; delivery_node = node_hi
                elif node_hi.pickup_item_list and not node_hi.delivery_item_list:
                    pickup_node = node_hi; delivery_node = node_lo
                else:
                    pickup_node, delivery_node = node_lo, node_hi
            except Exception as e:
                print(f' WARN[Local search]: remove pair failed: {e}', file=sys.stderr)
                continue

            chosen_nodelist = [pickup_node, delivery_node]

            # Try insertion on temp_solution
            try:
                isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList = MA_dispatch_nodepair(
                    chosen_nodelist, individual.id_to_vehicle, temp_solution, individual.route_map
                )
            except Exception as e:
                print(f' WARN[Local search]: dispatch_nodePair error: {e}', file=sys.stderr)
                continue

            if not bestInsertVehicleID:
                continue

            target_route = temp_solution.get(bestInsertVehicleID)
            if target_route is None:
                target_route = []
                temp_solution[bestInsertVehicleID] = target_route

            if isExhausive:
                temp_solution[bestInsertVehicleID] = bestNodeList[:]
            else:
                target_route.insert(bestInsertPosI, pickup_node)
                # Adjust delivery insertion index if pickup inserted before original intended position
                adj_del_pos = bestInsertPosJ if bestInsertPosJ > bestInsertPosI else bestInsertPosJ + 1
                target_route.insert(adj_del_pos, delivery_node)

            # Invariant check; if failed skip this attempt
            if not check_invariants(temp_solution):
                # Optional: verbose diagnostic
                # print(' WARN[Local search]: invariant violation (node loss/duplication or destination shift)', file=sys.stderr)
                continue

            # Commit temp_solution
            individual.solution = temp_solution
            vehicleid_to_plan = individual.solution
            moved = True
            break

    is_improved = individual.fitness < before_cost
    return is_improved


def roulette_select_pdg_by_delay(
    pdg_index_delay_map: Dict[str, Tuple[str, int, int, float]]
) -> Optional[Tuple[str, Tuple[str, int, int, float]]]:
    """
    Chọn 1 cặp PDG theo Roulette Wheel dựa trên delay time tại node giao của từng cặp.

    - Input: pdg_index_delay_map: Dict[pdg_key, (vehicleID, pick_idx, delv_idx, delay_at_delivery)]
    - Trả về: (pdg_key, (vehicleID, pick_idx, delv_idx, delay)) hoặc None nếu không có cặp hợp lệ

    Quy tắc:
    - Trọng số = max(delay, 0). Nếu tổng trọng số = 0 -> chọn ngẫu nhiên đều giữa các cặp hợp lệ.
    - Cặp hợp lệ: có vehicleID khác rỗng và pick_idx, delv_idx >= 0.
    """
    if not pdg_index_delay_map:
        return None , None

    valid: List[Tuple[str, Tuple[str, int, int, float], float]] = []
    for key, info in pdg_index_delay_map.items():
        if not isinstance(info, tuple) or len(info) < 4:
            continue
        vehicleID, pick_idx, delv_idx, delay_val = info
        if not vehicleID or pick_idx < 0 or delv_idx < 0:
            continue
        try:
            w = float(delay_val)
        except Exception:
            w = 0.0
        if w < 0:
            w = 0.0
        valid.append((key, info, w))

    if not valid:
        return None , None

    total_w = sum(w for _, _, w in valid)
    if total_w <= 0:
        # Fallback: chọn đều ngẫu nhiên
        key, info, _ = random.choice(valid)
        return key, info

    r = random.uniform(0.0, total_w)
    acc = 0.0
    for key, info, w in valid:
        acc += w
        if acc >= r:
            return key, info

    # Trường hợp biên do sai số số học
    return None, None


# tinh nghi
def MA_dispatch_nodepair(node_list: list[Node], id_to_vehicle: Dict[str, Vehicle], vehicleid_to_plan: Dict[str, list[Node]], route_map: Dict[tuple, tuple], selected_vehicle: str = None, mode='total'):
    """Tìm vị trí chèn tốt nhất cho một cặp (pickup, delivery) vào các tuyến hiện có.

    Bổ sung cơ chế kiểm tra timeout toàn cục (config.is_timeout()) để tránh chạy quá
    lâu trong các trường hợp nhiều xe / tuyến dài. Nếu timeout xảy ra, hàm trả về
    kết quả tốt nhất thu thập được đến thời điểm đó (best-so-far) thay vì bỏ trống.
    """
    bestInsertVehicleID: str = ''
    bestInsertPosI: int = 0
    bestInsertPosJ: int = 1
    bestNodeList: list[Node] = []
    isExhausive = False
    timed_out = False

    # Guard input
    if not node_list or len(node_list) < 2:
        return isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList

    new_pickup_node = node_list[0]
    new_delivery_node = node_list[1]
    minCostDelta = math.inf

    # Early global timeout check
    if config.is_timeout():
        return isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList

    for vehicleID, vehicle in id_to_vehicle.items():
        if selected_vehicle is not None and vehicleID != selected_vehicle:
            continue

        # Periodic timeout check (outer loop)
        if config.is_timeout():
            timed_out = True
            break

        vehicle_plan = vehicleid_to_plan[vehicleID]
        node_list_size = len(vehicle_plan) if vehicle_plan else 0

        insert_pos = 0
        model_nodes_num = node_list_size + 2
        first_merge_node_num = 0

        if vehicle.des:
            if new_pickup_node.id != vehicle.des.id:
                insert_pos = 1
            if vehicle_plan:
                for node in vehicle_plan:
                    if vehicle.des.id != node.id:
                        break
                    first_merge_node_num += 1

        model_nodes_num -= first_merge_node_num

        modle_node_list: List[Node] = []  # thêm các cặp node gửi và nhận theo thứ tự mới (tuần tự)
        exhaustive_route_node_list: List[Node] = []  # Dùng để lưu giữ kế hoạch của một xe trong quá trình duyệt tham lam
        cp_route_node_list: List[Node] = []  # Một copy của một kế hoạch hiện có
        if vehicle_plan:
            for node in vehicle_plan:
                cp_route_node_list.append(node)

        empty_pos_num = 0

        # Exhaustive model build (nhánh này không sử dụng timeout sâu vì dữ liệu <=8)
        if model_nodes_num <= 8:
            if first_merge_node_num > 0:
                while first_merge_node_num > 0:
                    exhaustive_route_node_list.append(cp_route_node_list.pop(0))
                    first_merge_node_num -= 1

            count = 0
            i = 0
            while True:
                if config.is_timeout():  # Timeout guard trong quá trình phân rã cặp
                    timed_out = True
                    break
                if (not cp_route_node_list) or i >= len(cp_route_node_list):
                    break
                pickup_node = None
                delivery_node = None
                order_item_id = ''

                if cp_route_node_list[i].pickup_item_list and len(cp_route_node_list[i].pickup_item_list) > 0:
                    order_item_id = cp_route_node_list[i].pickup_item_list[0].id
                    pickup_node = cp_route_node_list[i]
                    del cp_route_node_list[i]
                    j = i
                    while j < len(cp_route_node_list):
                        if cp_route_node_list[j].delivery_item_list and len(cp_route_node_list[j].delivery_item_list) > 0:
                            item_id = cp_route_node_list[j].delivery_item_list[-1].id
                            if order_item_id == item_id:
                                delivery_node = cp_route_node_list[j]
                                del cp_route_node_list[j]
                                break
                        j += 1
                    modle_node_list.insert(count, pickup_node)
                    modle_node_list.insert(count + 1, delivery_node)
                    i -= 1
                    count += 1
                i += 1

            # Nếu timeout xảy ra trong lúc xây dựng, thoát sớm với best-so-far
            if timed_out:
                break

            modle_node_list.insert(count, new_pickup_node)
            count += 1
            modle_node_list.insert(count, new_delivery_node)
            empty_pos_num = len(cp_route_node_list) if cp_route_node_list else 0
            while cp_route_node_list:
                modle_node_list.append(cp_route_node_list.pop(0))
            model_nodes_num = len(modle_node_list) + empty_pos_num

        # Thử các vị trí chèn
        for i in range(insert_pos, node_list_size + 1):
            if config.is_timeout():
                timed_out = True
                break
            if vehicle_plan is not None:
                tempRouteNodeList: List[Node] = []
                for nnn in vehicle_plan:
                    tempRouteNodeList.append(nnn)
            else:
                tempRouteNodeList = []
            tempRouteNodeList.insert(i, new_pickup_node)
            for j in range(i + 1, node_list_size + 2):
                if config.is_timeout():
                    timed_out = True
                    break
                if j != i + 1 and tempRouteNodeList[j - 1].pickup_item_list:
                    for k in range(j, node_list_size + 2):
                        if config.is_timeout():
                            timed_out = True
                            break
                        if tempRouteNodeList[k].delivery_item_list:
                            if tempRouteNodeList[j - 1].pickup_item_list[0].id == tempRouteNodeList[k].delivery_item_list[-1].id:
                                j = k + 1
                                break
                    if timed_out:
                        break
                elif tempRouteNodeList[j - 1].delivery_item_list:
                    is_terminal = True
                    for k in range(j - 2, -1, -1):
                        if config.is_timeout():
                            timed_out = True
                            break
                        if tempRouteNodeList[k].pickup_item_list:
                            if tempRouteNodeList[j - 1].delivery_item_list[-1].id == tempRouteNodeList[k].pickup_item_list[0].id:
                                if k < i:
                                    is_terminal = True
                                    break
                                elif k > i:
                                    is_terminal = False
                                    break
                    if timed_out:
                        break
                    if is_terminal:
                        break
                if timed_out:
                    break
                tempRouteNodeList.insert(j, new_delivery_node)
                costValue = cost_of_a_route(tempRouteNodeList, vehicle, id_to_vehicle, route_map, vehicleid_to_plan, mode)
                if costValue < minCostDelta:
                    minCostDelta = costValue
                    bestInsertPosI = i
                    bestInsertPosJ = j
                    bestInsertVehicleID = vehicleID
                    isExhausive = False
                tempRouteNodeList.pop(j)
            if timed_out:
                break
        if timed_out:
            break

    # Có thể log nhẹ khi timeout (không làm nhiễu stderr quá mức)
    if timed_out and bestInsertVehicleID:
        print(f'[TIMEOUT][MA_dispatch_nodepair] returning best-so-far for vehicle {bestInsertVehicleID}', file=sys.stderr)
    elif timed_out:
        print('[TIMEOUT][MA_dispatch_nodepair] no feasible insertion found before timeout', file=sys.stderr)

    return isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList