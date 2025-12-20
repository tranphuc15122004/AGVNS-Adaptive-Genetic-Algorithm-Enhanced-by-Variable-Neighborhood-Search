import copy
from datetime import datetime
import json
import math
import os
import random
import re
import sys
from algorithm.algorithm_config import *
from typing import Dict , List, Optional, Tuple
from algorithm.Object import *
from algorithm.engine import *
import algorithm.algorithm_config as config
from algorithm.local_search import *
from algorithm.Test_algorithm.new_LS import *

def new_dispatch_new_orders(vehicleid_to_plan: Dict[str, List[Node]],
                            id_to_factory: Dict[str, Factory],
                            route_map: Dict[tuple, tuple],
                            id_to_vehicle: Dict[str, Vehicle],
                            id_to_unlocated_items: Dict[str, OrderItem],
                            new_order_itemIDs: List[str],
                            strict: bool = False):
    """Dispatch new orders with CI before timeout, random after timeout.

    - Trước khi timeout: dùng `dispatch_nodePair` (cheapest insertion) để chèn.
    - Sau khi timeout (config.is_timeout() == True): mọi block mới được gán
      nhanh bằng `random_dispatch_nodePair`, không cần đếm đơn tồn đọng.
    """
    all_exhaustive = True

    if not new_order_itemIDs:
        return all_exhaustive

    # Gom các order item theo order_id
    # Đồng thời lưu lại tập ID item đầu vào để sau này validate đã được gán hết chưa
    orderId_to_Item: Dict[str, List[OrderItem]] = {}
    requested_item_ids: set[str] = set()
    missing_item_ids: List[str] = []
    for new_order_item in new_order_itemIDs:
        requested_item_ids.add(new_order_item)
        new_item = id_to_unlocated_items.get(new_order_item)
        if new_item is None:
            # Ghi nhận nhưng không làm hỏng luồng chèn; có thể in log để debug
            missing_item_ids.append(new_order_item)
            continue
        orderID = new_item.order_id
        orderId_to_Item.setdefault(orderID, []).append(new_item)

    # Lấy sức chứa (giả sử tất cả xe cùng capacity như cũ)
    capacity = None
    for vehicle in id_to_vehicle.values():
        capacity = vehicle.board_capacity
        break

    # Helper: chèn 1 block node_list theo CI hoặc random tùy trạng thái timeout
    # YÊU CẦU: node_list phải chứa đủ các item tương ứng trong tmp_itemList/order_items;
    # không được bỏ block nào nếu create_Pickup_Delivery_nodes trả về rỗng.
    def _insert_block(node_list: List[Node]) -> None:
        nonlocal all_exhaustive
        if not node_list:
            # Nếu node_list rỗng nhưng về logic lẽ ra phải có item, đây là tình huống lỗi;
            # với strict=True ta raise để lộ bug sớm, còn không thì chỉ log.
            msg = "[new_dispatch_new_orders] ERROR: _insert_block được gọi với node_list rỗng"
            if strict:
                raise RuntimeError(msg)
            print(msg, file=sys.stderr)
            all_exhaustive = False
            return

        # Đếm tổng node trước khi chèn để chắc chắn sau đó tăng đúng +2
        before_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
        # Nếu đã timeout tại thời điểm này -> random
        if config.is_timeout():
            random_dispatch_nodePair(node_list, id_to_vehicle, vehicleid_to_plan)
            after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
            if after_nodes != before_nodes + 2:
                msg = f"[new_dispatch_new_orders] WARNING: random_dispatch_nodePair không tăng đúng 2 node (before={before_nodes}, after={after_nodes})"
                print(msg, file=sys.stderr)
                all_exhaustive = False
                if strict:
                    raise RuntimeError(msg)
            return

        isExhaustive = False
        bestVID = ''
        bestI = 0
        bestJ = 1
        bestList: List[Node] = []

        isExhaustive, bestVID, bestI, bestJ, bestList = dispatch_nodePair(
            node_list, id_to_vehicle, vehicleid_to_plan, route_map
        )

        # Nếu sau khi chạy CI mà timeout thì coi như đã trễ, block này dùng random
        if config.is_timeout():
            random_dispatch_nodePair(node_list, id_to_vehicle, vehicleid_to_plan)
            after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
            if after_nodes != before_nodes + 2:
                msg = f"[new_dispatch_new_orders] WARNING: random_dispatch_nodePair (sau CI timeout) không tăng đúng 2 node (before={before_nodes}, after={after_nodes})"
                print(msg, file=sys.stderr)
                all_exhaustive = False
                if strict:
                    raise RuntimeError(msg)
            return

        # Kiểm tra kết quả CI hợp lệ
        if not bestVID or bestVID not in id_to_vehicle:
            random_dispatch_nodePair(node_list, id_to_vehicle, vehicleid_to_plan)
            after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
            if after_nodes != before_nodes + 2:
                msg = f"[new_dispatch_new_orders] WARNING: CI trả về bestVID không hợp lệ, random fallback cũng không tăng đúng 2 node (before={before_nodes}, after={after_nodes})"
                print(msg, file=sys.stderr)
                all_exhaustive = False
                if strict:
                    raise RuntimeError(msg)
            return

        route_node_list = vehicleid_to_plan.get(bestVID, []) or []

        if isExhaustive and bestList:
            vehicleid_to_plan[bestVID] = bestList[:]
        else:
            all_exhaustive = False
            # Bảo vệ chỉ số chèn
            if bestI < 0:
                bestI = 0
            if bestJ < bestI + 1:
                bestJ = bestI + 1
            if bestI > len(route_node_list):
                bestI = len(route_node_list)
            if bestJ > len(route_node_list) + 1:
                bestJ = len(route_node_list) + 1

            new_pickup = node_list[0]
            new_delivery = node_list[1]
            route_node_list.insert(bestI, new_pickup)
            route_node_list.insert(bestJ, new_delivery)
            vehicleid_to_plan[bestVID] = route_node_list

        # Kiểm tra lại: sau khi chèn bằng CI, tổng số node phải tăng đúng 2
        after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
        if after_nodes != before_nodes + 2:
            msg = f"[new_dispatch_new_orders] WARNING: dispatch_nodePair/CI không làm tăng đúng 2 node (before={before_nodes}, after={after_nodes})"
            print(msg, file=sys.stderr)
            all_exhaustive = False
            if strict:
                raise RuntimeError(msg)

    # Duyệt từng order; tại mọi thời điểm, chỉ check timeout để quyết định
    for orderID, order_items in orderId_to_Item.items():
        order_demand = sum(item.demand for item in order_items)

        # Nếu timeout xảy ra ở thời điểm bắt đầu xử lý order này -> toàn bộ order dùng random
        if config.is_timeout():
            node_list = create_Pickup_Delivery_nodes(order_items, id_to_factory)
            if node_list:
                random_dispatch_nodePair(node_list, id_to_vehicle, vehicleid_to_plan)
            continue

        # Đơn vượt sức chứa: tách thành nhiều block
        if capacity is not None and order_demand > capacity:
            tmp_demand = 0
            tmp_itemList: List[OrderItem] = []

            for item in order_items:
                # Nếu tại đây đã timeout thì phần block hiện tại và phần về sau
                # đều sẽ được xử lý bằng random qua _insert_block (vì _insert_block
                # kiểm tra timeout ở đầu).
                if (tmp_demand + item.demand) > capacity:
                    node_list = create_Pickup_Delivery_nodes(tmp_itemList, id_to_factory)
                    _insert_block(node_list)
                    tmp_itemList = []
                    tmp_demand = 0

                tmp_itemList.append(item)
                tmp_demand += item.demand

            if tmp_itemList:
                node_list = create_Pickup_Delivery_nodes(tmp_itemList, id_to_factory)
                _insert_block(node_list)
        else:
            # Đơn không vượt capacity
            node_list = create_Pickup_Delivery_nodes(order_items, id_to_factory)
            _insert_block(node_list)

    # ===================== HẬU KIỂM: đảm bảo tất cả item mới đã được gán =====================
    # Thu thập các item id đã xuất hiện trong mọi route sau khi chèn
    assigned_item_ids: set[str] = set()

    def _collect_items_from_node(nd: Node) -> None:
        if nd is None:
            return
        if getattr(nd, 'pickup_item_list', None):
            for it in nd.pickup_item_list:
                if hasattr(it, 'id'):
                    assigned_item_ids.add(it.id)
        if getattr(nd, 'delivery_item_list', None):
            for it in nd.delivery_item_list:
                if hasattr(it, 'id'):
                    assigned_item_ids.add(it.id)

    for route in vehicleid_to_plan.values():
        for nd in route or []:
            _collect_items_from_node(nd)

    # Những item mới mà không xuất hiện trong bất kỳ route nào
    unassigned_items = [iid for iid in requested_item_ids if iid not in assigned_item_ids]

    # ===================== BƯỚC CỨU HỘ: cố gắng gán lại các item chưa được gán =====================
    if unassigned_items:
        rescue_failed: List[str] = []

        for iid in unassigned_items:
            item = id_to_unlocated_items.get(iid)
            if not item:
                rescue_failed.append(iid)
                continue

            node_list = create_Pickup_Delivery_nodes([item], id_to_factory)
            if not node_list:
                rescue_failed.append(iid)
                continue

            # Thử random_dispatch_nodePair trước
            before_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
            random_dispatch_nodePair(node_list, id_to_vehicle, vehicleid_to_plan)
            after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
            if after_nodes == before_nodes + 2:
                continue

            # Nếu random thất bại, thử append cuối một xe bất kỳ (đơn giản, ưu tiên khả thi hơn tối ưu)
            assigned = False
            for vehicleID, vehicle in id_to_vehicle.items():
                route = vehicleid_to_plan.get(vehicleID) or []
                tempRouteNodeList = route + node_list
                # Lấy carrying_items robust như trong fast_cheapest_insertion_for_block
                def _carrying_list(v: Vehicle) -> List[OrderItem]:
                    ci = getattr(v, 'carrying_items', None)
                    try:
                        ci_copy = copy.deepcopy(ci)
                    except Exception:
                        ci_copy = ci
                    try:
                        items_top_first: List[OrderItem] = []
                        while ci_copy is not None and hasattr(ci_copy, 'is_empty') and not ci_copy.is_empty():
                            items_top_first.append(ci_copy.pop())
                        return list(reversed(items_top_first)) if items_top_first else (list(ci_copy) if isinstance(ci_copy, list) else [])
                    except Exception:
                        try:
                            return list(ci_copy) if ci_copy is not None else []
                        except Exception:
                            return []

                carrying_items = _carrying_list(vehicle)
                if not isFeasible(tempRouteNodeList, carrying_items, vehicle.board_capacity):
                    continue

                vehicleid_to_plan[vehicleID] = tempRouteNodeList
                assigned = True
                break

            if not assigned:
                rescue_failed.append(iid)

        if missing_item_ids or rescue_failed:
            if missing_item_ids:
                print(f"[new_dispatch_new_orders] WARNING: {len(missing_item_ids)} new_order_itemIDs không tìm thấy trong id_to_unlocated_items: {missing_item_ids}", file=sys.stderr)
            if rescue_failed:
                print(f"[new_dispatch_new_orders] ERROR: {len(rescue_failed)} items không thể gán ngay cả sau bước cứu hộ: {rescue_failed}", file=sys.stderr)
            all_exhaustive = False
            if strict and rescue_failed:
                raise RuntimeError(f"new_dispatch_new_orders strict mode: không thể gán {len(rescue_failed)} items: {rescue_failed}")

    return all_exhaustive



def worse_dispatch_new_orders(vehicleid_to_plan: Dict[str , list[Node]] ,  id_to_factory:Dict[str , Factory] , route_map: Dict[tuple , tuple] ,  id_to_vehicle: Dict[str , Vehicle] , id_to_unlocated_items:Dict[str , OrderItem], new_order_itemIDs: list[str]):
    # Keep a safe backup of the original plans so we can revert on infeasible changes
    try:
        original_plans = copy.deepcopy(vehicleid_to_plan)
    except Exception:
        original_plans = {k: list(v) for k, v in vehicleid_to_plan.items()}
    
    if new_order_itemIDs:
        orderId_to_Item : Dict[str , list[OrderItem]] = {}
        for new_order_item in new_order_itemIDs:
            new_item = id_to_unlocated_items.get(new_order_item)
            orderID  = new_item.order_id
            if orderID not in orderId_to_Item:
                orderId_to_Item[orderID] = []
            orderId_to_Item.get(orderID).append(new_item)
        
        for vehicle in id_to_vehicle.values():
            capacity = vehicle.board_capacity
            break
        
        for orderID , orderID_items in orderId_to_Item.items():
            order_demand = 0
            for item in orderID_items:
                order_demand += item.demand
            
            if order_demand > capacity:
                tmp_demand = 0
                tmp_itemList: list[OrderItem] = []
                
                for item in orderID_items:
                    if (tmp_demand + item.demand) > capacity:
                        for plan in vehicleid_to_plan.values():
                            if len(plan) >= 6: all_exhautive = False
                        
                        
                        node_list: list[Node] = create_Pickup_Delivery_nodes(tmp_itemList , id_to_factory)
                        
                        """ if node_list:
                            bestInsertPos, bestInsertVehicle = fast_cheapest_insertion_for_block(
                                node_list, id_to_vehicle, vehicleid_to_plan, route_map
                            )
                            
                        if bestInsertVehicle is None:
                            print(f"[new_crossver2] reinsert abandon block | insertion failed -> stopping", file=sys.stderr)
                            break
                        target_route = vehicleid_to_plan[bestInsertVehicle]
                        target_route[bestInsertPos: bestInsertPos] = node_list """
                        
                        if node_list:
                            # Try random insertion first
                            before_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                            random_dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan)
                            after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                            if after_nodes != before_nodes + 2:
                                # Immediate fallback: cheapest insertion by cost
                                isExhausiveFB = False
                                bestVID = ''
                                bestI = 0
                                bestJ = 1
                                bestList: List[Node] = []
                                isExhausiveFB , bestVID, bestI, bestJ , bestList = dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan , route_map)
                                tgt_route : List[Node] = vehicleid_to_plan.get(bestVID , [])
                                if isExhausiveFB:
                                    vehicleid_to_plan[bestVID] = bestList[:]
                                else:
                                    if tgt_route is None: tgt_route = []
                                    tgt_route.insert(bestI , node_list[0])
                                    tgt_route.insert(bestJ , node_list[1])
                                    vehicleid_to_plan[bestVID] = tgt_route
                        
                        tmp_itemList.clear()
                        tmp_demand = 0
                    tmp_itemList.append(item)
                    tmp_demand += item.demand 

                if len(tmp_itemList) > 0:
                    for plan in vehicleid_to_plan.values():
                        if len(plan) >= 6: all_exhautive = False
                    
                    node_list: list[Node] = create_Pickup_Delivery_nodes(tmp_itemList , id_to_factory)
                    """ if node_list:
                        bestInsertPos, bestInsertVehicle = fast_cheapest_insertion_for_block(
                            node_list, id_to_vehicle, vehicleid_to_plan, route_map
                        )
                        
                    if bestInsertVehicle is None:
                        print(f"[new_crossver2] reinsert abandon block | insertion failed -> stopping", file=sys.stderr)
                        break
                    target_route = vehicleid_to_plan[bestInsertVehicle]
                    target_route[bestInsertPos: bestInsertPos] = node_list """
                    if node_list:
                        before_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                        random_dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan)
                        after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                        if after_nodes != before_nodes + 2:
                            isExhausiveFB , bestVID, bestI, bestJ , bestList = dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan , route_map)
                            tgt_route : List[Node] = vehicleid_to_plan.get(bestVID , [])
                            if isExhausiveFB:
                                vehicleid_to_plan[bestVID] = bestList[:]
                            else:
                                if tgt_route is None: tgt_route = []
                                tgt_route.insert(bestI , node_list[0])
                                tgt_route.insert(bestJ , node_list[1])
                                vehicleid_to_plan[bestVID] = tgt_route
            else:
                for plan in vehicleid_to_plan.values():
                    if len(plan) >= 6: all_exhautive = False
                
                node_list: list[Node] = create_Pickup_Delivery_nodes(orderID_items , id_to_factory)
                """ if node_list:
                    bestInsertPos, bestInsertVehicle = fast_cheapest_insertion_for_block(
                        node_list, id_to_vehicle, vehicleid_to_plan, route_map
                    )
                    
                if bestInsertVehicle is None:
                    print(f"[new_crossver2] reinsert abandon block | insertion failed -> stopping", file=sys.stderr)
                    break
                target_route = vehicleid_to_plan[bestInsertVehicle]
                target_route[bestInsertPos: bestInsertPos] = node_list """
                if node_list:
                    before_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                    random_dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan)
                    after_nodes = sum(len(r or []) for r in vehicleid_to_plan.values())
                    if after_nodes != before_nodes + 2:
                        isExhausiveFB , bestVID, bestI, bestJ , bestList = dispatch_nodePair(node_list , id_to_vehicle , vehicleid_to_plan , route_map)
                        tgt_route : List[Node] = vehicleid_to_plan.get(bestVID , [])
                        if isExhausiveFB:
                            vehicleid_to_plan[bestVID] = bestList[:]
                        else:
                            if tgt_route is None: tgt_route = []
                            tgt_route.insert(bestI , node_list[0])
                            tgt_route.insert(bestJ , node_list[1])
                            vehicleid_to_plan[bestVID] = tgt_route
    
    # Post-insertion sanity check: validate feasibility for each vehicle; if any violation
    # found, log a detailed capacity trace and revert to the original plans.
    for vehicleID, vehicle in id_to_vehicle.items():
        route = vehicleid_to_plan.get(vehicleID, [])
        carrying = vehicle.carrying_items if vehicle.des else []
        if not isFeasible(route, carrying, vehicle.board_capacity):
            # produce a left_capacity trace for debugging
            left_capacity = vehicle.board_capacity
            trace = []
            try:
                if carrying:
                    for ci in (carrying if isinstance(carrying, list) else list(carrying)):
                        left_capacity -= getattr(ci, 'demand', 0)
                        trace.append(f"init carrying -{getattr(ci,'demand',0)} -> {left_capacity}")
            except Exception:
                pass

            for idx, nd in enumerate(route):
                # delivery nodes increase capacity
                dlist = getattr(nd, 'delivery_item_list', None) or getattr(nd, 'delivery_items', None) or []
                if dlist:
                    for it in dlist:
                        left_capacity += getattr(it, 'demand', 0)
                        trace.append(f"node{idx} delivery +{getattr(it,'demand',0)} -> {left_capacity}")

                plist = getattr(nd, 'pickup_item_list', None) or getattr(nd, 'pickup_items', None) or []
                if plist:
                    for it in plist:
                        left_capacity -= getattr(it, 'demand', 0)
                        trace.append(f"node{idx} pickup -{getattr(it,'demand',0)} -> {left_capacity}")
                        if left_capacity < 0:
                            print(f"ERROR: vehicle {vehicleID} left capacity {left_capacity} < 0 at node idx {idx} (item {getattr(it,'id',None)}). Trace: {trace}", file=sys.stderr)
                            break

            print("Reverting to original plans due to infeasible insertion in worse_dispatch_new_orders", file=sys.stderr)
            vehicleid_to_plan.clear()
            vehicleid_to_plan.update(original_plans)
            return 



def fast_cheapest_insertion_for_block(node_block: List[Node],
                                     id_to_vehicle: Dict[str, Vehicle],
                                     vehicleid_to_plan: Dict[str, list[Node]],
                                     route_map: Dict[tuple, tuple],
                                     selected_vehicle: str = None,
                                     prefilter_k: int = 4):
    """Fast append-at-end heuristic with prefiltering.

    Steps:
    - Compute a cheap distance heuristic from each vehicle's tail (last planned node or current factory)
      to the block's first node; keep top-K vehicles.
    - For these candidates only, check feasibility and evaluate full route cost using cost_of_a_route.

    Returns: (bestInsertPos, bestInsertVehicleID)
    """
    if not node_block:
        return 0, None

    first_node_id = node_block[0].id if node_block[0] else None
    if first_node_id is None:
        return 0, None

    # Build candidate list with distances
    candidates: List[Tuple[float, str]] = []  # (distance_heuristic, vehicleID)

    def dist(a: Optional[str], b: Optional[str]) -> float:
        if not a or not b:
            return math.inf
        v = route_map.get((a, b))
        if v is None:
            v = route_map.get((b, a))
        try:
            return float(v[0]) if v is not None else math.inf
        except Exception:
            return math.inf

    for vehicleID, vehicle in id_to_vehicle.items():
        if selected_vehicle is not None and vehicleID != selected_vehicle:
            continue

        plan = vehicleid_to_plan.get(vehicleID) or []
        tail_id: Optional[str] = None
        if plan:
            tail_id = plan[-1].id
        else:
            # If no planned route, use current factory as tail; fallback to destination header
            tail_id = vehicle.cur_factory_id or (vehicle.des.id if vehicle.des else None)

        d = dist(tail_id, first_node_id)
        candidates.append((d, vehicleID))

    # Sort and take top-K
    candidates.sort(key=lambda x: x[0])
    if prefilter_k > 0:
        candidates = candidates[:prefilter_k]

    minCost = math.inf
    bestInsertPos = 0
    bestInsertVehicleID: Optional[str] = None

    for _, vehicleID in candidates:
        vehicle = id_to_vehicle[vehicleID]
        vehicle_plan = vehicleid_to_plan.get(vehicleID) or []
        tempRouteNodeList = vehicle_plan + node_block  # append at end
        # Build carrying list robustly (bottom -> top)
        def _carrying_list(v: Vehicle) -> List[OrderItem]:
            ci = getattr(v, 'carrying_items', None)
            try:
                ci_copy = copy.deepcopy(ci)
            except Exception:
                ci_copy = ci
            try:
                items_top_first: List[OrderItem] = []
                while ci_copy is not None and hasattr(ci_copy, 'is_empty') and not ci_copy.is_empty():
                    items_top_first.append(ci_copy.pop())
                return list(reversed(items_top_first)) if items_top_first else (list(ci_copy) if isinstance(ci_copy, list) else [])
            except Exception:
                try:
                    return list(ci_copy) if ci_copy is not None else []
                except Exception:
                    return []
        carrying_items = _carrying_list(vehicle)

        # Feasibility precheck for this candidate only
        if not isFeasible(tempRouteNodeList, carrying_items, vehicle.board_capacity):
            continue

        # Full cost evaluation (heavy) only for filtered candidates
        tmp_cost = cost_of_a_route(tempRouteNodeList, vehicle, id_to_vehicle, route_map, vehicleid_to_plan)
        if tmp_cost < minCost:
            minCost = tmp_cost
            bestInsertPos = len(vehicle_plan)
            bestInsertVehicleID = vehicleID

    return bestInsertPos, bestInsertVehicleID


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


def new_generate_random_chromosome(initial_vehicleid_to_plan : Dict[str , List[Node]],  route_map: Dict[Tuple, Tuple], id_to_vehicle: Dict[str, Vehicle], Unongoing_super_nodes : Dict[int , Dict[str, Node]]  ,Base_vehicleid_to_plan : Dict[str , List[Node]] , quantity : int):
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
    
    while len(population) < quantity:
        new_individual = disturbance_opt(initial_vehicleid_to_plan , id_to_vehicle , route_map , 0.5)
        
        if new_individual:
            population.append(new_individual)
    
    population.append(Chromosome(initial_vehicleid_to_plan , route_map , id_to_vehicle))
    return population , pdg_Map 

def calculate_diversity(population: List[Chromosome]) -> float:
    """Tính độ đa dạng của quần thể dựa trên sự khác biệt về route"""
    if len(population) < 2:
        return 1.0
    
    total_distance = 0
    count = 0
    
    for i in range(len(population)):
        for j in range(i + 1, len(population)):
            distance = calculate_chromosome_distance(population[i], population[j])
            total_distance += distance
            count += 1
    
    return total_distance / count if count > 0 else 0.0

def calculate_chromosome_distance(c1: Chromosome, c2: Chromosome) -> float:
    """Tính khoảng cách giữa 2 chromosome dựa trên route structure"""
    distance = 0
    total_positions = 0
    
    # So sánh route của từng vehicle
    for vehicle_id in c1.solution.keys():
        route1 = c1.solution.get(vehicle_id, [])
        route2 = c2.solution.get(vehicle_id, [])
        
        max_len = max(len(route1), len(route2))
        total_positions += max_len
        
        # Đếm số vị trí khác nhau
        for i in range(max_len):
            node1_id = None
            if i < len(route1):
                node1_id = route1[i].pickup_item_list[0].id if route1[i].pickup_item_list else route1[i].delivery_item_list[0].id
            node2_id =  None
            if i < len(route2):
                node2_id = route2[i].pickup_item_list[0].id if route2[i].pickup_item_list else route2[i].delivery_item_list[0].id
            
            if node1_id != node2_id:
                distance += 1
    
    # Normalize distance
    return distance / total_positions if total_positions > 0 else 0.0

def calculate_fitness_diversity(population: List[Chromosome]) -> float:
    """Tính độ đa dạng dựa trên fitness values"""
    if len(population) < 2:
        return 1.0
    
    fitness_values = [c.fitness for c in population]
    avg_fitness = sum(fitness_values) / len(fitness_values)
    
    # Tính độ lệch chuẩn
    variance = sum((f - avg_fitness) ** 2 for f in fitness_values) / len(fitness_values)
    std_dev = math.sqrt(variance)
    
    # Normalize bằng average fitness
    return std_dev / avg_fitness if avg_fitness > 0 else 0.0

def generate_single_random_chromosome(Base_vehicleid_to_plan: Dict[str, List[Node]], 
                                    route_map: Dict[Tuple, Tuple],
                                    id_to_vehicle: Dict[str, Vehicle],
                                    PDG_map: Dict[str, List[Node]]) -> Chromosome:
    """Tạo một cá thể ngẫu nhiên"""
    temp_route: Dict[str, List[Node]] = {}
    
    # Copy base route
    for vehicleID, plan in Base_vehicleid_to_plan.items():
        temp_route[vehicleID] = [node for node in plan]
    
    # Random dispatch các PDG
    for DPG in PDG_map.values():
        if random.uniform(0 , 1) < 0.5:
            isExhausive = False
            route_node_list : List[Node] = []
            if DPG:
                isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = dispatch_nodePair(DPG , id_to_vehicle , temp_route , route_map)
            
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
            if random.uniform(0 , 1) < 0.5:
                # Random vehicle
                selected_vehicleID = random.choice(list(id_to_vehicle.keys()))
                temp_route[selected_vehicleID].extend(DPG)
            else:
                # Random dispatch
                random_dispatch_nodePair(DPG, id_to_vehicle, temp_route)
        
    return Chromosome(temp_route, route_map, id_to_vehicle)

def remove_similar_individuals(population: List[Chromosome], threshold: float = 0.1) -> List[Chromosome]:
    """Loại bỏ các cá thể quá giống nhau"""
    unique_population = []
    
    for individual in population:
        is_unique = True
        
        for unique_individual in unique_population:
            distance = calculate_chromosome_distance(individual, unique_individual)
            if distance <= threshold:
                # Giữ cá thể có fitness tốt hơn
                if individual.fitness < unique_individual.fitness:
                    unique_population.remove(unique_individual)
                    unique_population.append(individual)
                is_unique = False
                break
        
        if is_unique:
            unique_population.append(individual)
    
    return unique_population


def get_adaptive_order(indivisual: Chromosome ,methods : Dict , mode= 1) -> List[str]:
    """Tạo thứ tự adaptive dựa trên improved_LS_map của cá thể"""
    
    # Lấy lịch sử cải thiện từ cá thể
    improvement_history = indivisual.improved_LS_map.copy()
    
    # Tính score cho từng phương pháp (với một chút randomness)
    method_scores = {}
    total_improvements = sum(improvement_history.values())
    
    for method_name in methods.keys():
        # Base score từ lịch sử cải thiện
        improvement_count = improvement_history.get(method_name, 0)
        
        if total_improvements > 0:
            # Success rate của method này
            success_rate = improvement_count / total_improvements
            method_scores[method_name] = success_rate * random.uniform(0.8 , 1.2)
        else:
            # Nếu chưa có lịch sử, dùng random weights
            method_scores[method_name] = random.uniform(0.5, 1.0)
    
    # Sắp xếp theo score giảm dần (method tốt nhất trước)
    if mode == 1:
        sorted_methods = sorted(method_scores.items(), key=lambda x: x[1], reverse=True)
    else:
        sorted_methods = sorted(method_scores.items(), key=lambda x: x[1])
        
    # Trả về danh sách tên methods theo thứ tự ưu tiên
    ordered_methods = [method[0] for method in sorted_methods]
    return ordered_methods

def randon_1_LS(indivisual: Chromosome  , PDG_map: Dict[str, List[Node]], is_limited = False , mode = 0):
    if config.is_timeout():
        return False
    
    i = 1
    
    # Dictionary các phương pháp Local Search
    methods = {
        'PDPairExchange': lambda: new_inter_couple_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map , config.LS_MAX_TIME_IN_SINGLE , is_limited),
        'BlockExchange': lambda: new_block_exchange(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map , config.LS_MAX_TIME_IN_SINGLE, is_limited),
        'BlockRelocate': lambda: new_block_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map , config.LS_MAX_TIME_IN_SINGLE, is_limited),
        'mPDG': lambda: new_multi_pd_group_relocate(indivisual.solution, indivisual.id_to_vehicle, indivisual.route_map , config.LS_MAX_TIME_IN_SINGLE, is_limited)
    }
    
    # Counter cho từng phương pháp
    counters = {name: 0 for name in methods.keys()}
    
    # Lấy thứ tự adaptive
    if mode == 0:
        chosen_method = random.choices(list(methods.keys()))[0]
    else:
        improvement_history = indivisual.improved_LS_map.copy()
        for k in methods.keys():
            improvement_history.setdefault(k, 0)
        
        # Roulette wheel: weight = (improved_count + 1); nếu mode != 0 có thể nhấn mạnh thêm
        weights = []
        for k in methods.keys():
            base = improvement_history[k] + 1
            
            weights.append(base)
        total_w = sum(weights)
        r = random.uniform(0, total_w)
        acc = 0.0
        chosen_method = None
        for k, w in zip(methods.keys(), weights):
            acc += w
            if r <= acc:
                chosen_method = k
                break
        if chosen_method is None:
            chosen_method = next(iter(methods.keys()))
    
    i = 0
    begin_LS_time = time.time()
    while i < 1:
        if config.is_timeout():
            break
        op_begin = time.time()
        improved = methods[chosen_method]()
        op_elapsed = time.time() - op_begin
        if op_elapsed > config.LS_MAX_TIME_PER_OP:
            print(f"LS: {chosen_method} aborted (per-op time {op_elapsed:.3f}s > {config.LS_MAX_TIME_PER_OP}s)", file=sys.stderr)
        if improved:
            i +=1 
            counters[chosen_method] += 1
            continue
        else: 
            break
    #indivisual.fitness = indivisual.evaluate_fitness()
    for method_name in methods.keys():
        indivisual.improved_LS_map[method_name] += counters[method_name]
    total_ls_time = time.time() - begin_LS_time
    print(f"LS: {chosen_method} | Count: {i} | TotalTime:{total_ls_time:.3f}s | Cost:{total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution):.2f}")


def new_crossover(parent1: Chromosome , parent2: Chromosome , PDG_map : Dict[str , List[Node]] , is_limited = False):
    begin_func_time = time.time()
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
                child_solution_1[vehicleID].append(node)
            for node in parent2.solution[vehicleID]:
                child_solution_2[vehicleID].append(node)
        else:
            for node in parent2.solution[vehicleID]:
                child_solution_1[vehicleID].append(node)
            for node in parent1.solution[vehicleID]:
                child_solution_2[vehicleID].append(node)
    
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
                        #print(f"Redundant nodes: {redundant}" , file= sys.stderr)
                        # Xóa node giao của super node thừa
                        del_index.append(i)
                        #print('Đã xóa 1 super node thừa' , file= sys.stderr)
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
                        #print(f"Redundant nodes: {redundant}" , file= sys.stderr)

                        # Xóa node giao của super node thừa
                        del_index.append(i)
                        #print('Đã xóa 1 super node thừa' , file= sys.stderr)
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
    
    print('Thoi gian thuc hien crossover: ' , time.time() - begin_func_time  , file=sys.stderr)
    
    #Tối ưu các lời giải relaxation con
    sorted_child_solution_1 = sorted(child_solution_1.items() ,  key=lambda x: int(x[0].split('_')[1]))
    child_solution_1.clear()
    child_solution_1.update(sorted_child_solution_1)
    child_1 = Chromosome(child_solution_1 , parent1.route_map , parent1.id_to_vehicle)
    
    sorted_child_solution_2 = sorted(child_solution_2.items() ,  key=lambda x: int(x[0].split('_')[1]))
    child_solution_2.clear()
    child_solution_2.update(sorted_child_solution_2)
    child_2 = Chromosome(child_solution_2 , parent2.route_map , parent2.id_to_vehicle)
    
    """ randon_1_LS(child_1 , is_limited , 0)
    randon_1_LS(child_2 , is_limited , 0) """
    
    # Kiem tra lai và thêm các node còn thiếu solution 1        
    for key, value in check_valid_1.items():
        if value == 0:
            if random.uniform(0 , 1) < 1:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                selected_vehicleID = random.choice(list(parent1.id_to_vehicle.keys()))
                node_list = new_PDG_map[key]
                isExhausive = False
                route_node_list : List[Node] = []
                
                if node_list:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = new_dispatch_nodePair(node_list , parent1.id_to_vehicle , child_solution_1 , parent1.route_map ,selected_vehicleID)
                    
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
                random_dispatch_nodePair(node_list, parent1.id_to_vehicle, child_solution_1)
    
    
    # Kiem tra lai và thêm các node còn thiếu solution 2      
    for key, value in check_valid_2.items():
        if value == 0:
            if random.uniform(0 , 1) < 1:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                selected_vehicleID = random.choice(list(parent1.id_to_vehicle.keys()))
                
                node_list = new_PDG_map[key]
                isExhausive = False
                route_node_list : List[Node] = []
                
                if node_list:
                    isExhausive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList = new_dispatch_nodePair(node_list , parent2.id_to_vehicle , child_solution_2 , parent2.route_map , selected_vehicleID )
                    
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
                random_dispatch_nodePair(node_list, parent2.id_to_vehicle, child_solution_2)
    
    print('Thoi gian thuc hien crossover: ' , time.time() - begin_func_time  , file=sys.stderr)
    print(child_1.fitness , file=sys.stderr)
    print(child_2.fitness , file=sys.stderr)
    return child_1 , child_2


# chen lại node list theo chiến lược cheapest insertion
def new_dispatch_nodePair(node_list: list[Node]  , id_to_vehicle: Dict[str , Vehicle] , vehicleid_to_plan: Dict[str, list[Node]], route_map: Dict[tuple , tuple]  , selected_vehicle: str= None , mode = 'total' ):
    """Cheapest insertion of a PD pair with speed optimizations:
    - Prefilter vehicles by a cheap distance heuristic to pickup.
    - For each candidate vehicle, rank (i, j) by local delta distance and only
      evaluate top few with full cost_of_a_route.
    """
    bestInsertVehicleID: str = ''
    bestInsertPosI: int = 0
    bestInsertPosJ: int = 1
    bestNodeList : list[Node] = []
    # Flag: whether exhaustive search was used (kept for API compatibility)
    isExhautive  = False
    new_pickup_node = node_list[0]
    new_delivery_node = node_list[1]
    minCostValue = math.inf

    # Tunables
    PREFILTER_VEH_K = min(5, len(id_to_vehicle)//2)
    TOP_CAND_PER_VEH = 10
    
    def dist_ids(a: Optional[str], b: Optional[str]) -> float:
        if not a or not b:
            return math.inf
        v = route_map.get((a, b))
        if v is None:
            v = route_map.get((b, a))
        try:
            return float(v[0]) if v is not None else math.inf
        except Exception:
            return math.inf

    # Build vehicle prefilter by distance from a coarse anchor to pickup
    veh_candidates: List[Tuple[float, str]] = []
    for vehicleID, vehicle in id_to_vehicle.items():
        if selected_vehicle is not None and vehicleID != selected_vehicle:
            continue
        plan = vehicleid_to_plan.get(vehicleID) or []
        anchor_ids: List[Optional[str]] = []
        if plan:
            anchor_ids.extend([plan[0].id, plan[-1].id])
        anchor_ids.append(vehicle.cur_factory_id if vehicle.cur_factory_id else (vehicle.des.id if vehicle.des else None))
        dmin = min((dist_ids(aid, new_pickup_node.id) for aid in anchor_ids if aid), default=math.inf)
        veh_candidates.append((dmin, vehicleID))

    veh_candidates.sort(key=lambda x: x[0])
    if PREFILTER_VEH_K > 0:
        veh_candidates = veh_candidates[:PREFILTER_VEH_K]

    # Get ranking mode from config if available (default: 'single').
    # Options: 'single' (single_vehicle_cost delta), 'neighbor' (distance-based local delta)
    ranking_mode = 'neighbor'

    for _, vehicleID in veh_candidates:
        vehicle = id_to_vehicle[vehicleID]
        vehicle_plan = vehicleid_to_plan.get(vehicleID) or []
        node_list_size = len(vehicle_plan)

        insert_pos = 0
        first_merge_node_num = 0
        if vehicle.des:
            if new_pickup_node.id != vehicle.des.id:
                insert_pos = 1
            if vehicle_plan:
                for node in vehicle_plan:
                    if vehicle.des.id != node.id:
                        break
                    first_merge_node_num += 1

        # Collect candidates ranked by the chosen strategy
        candidates_ij: List[Tuple[float, int, int]] = []

        # Precompute original neighbor distances to reuse in delta
        def route_id_at(idx: int) -> Optional[str]:
            if idx < 0 or idx >= len(vehicle_plan):
                return None
            return vehicle_plan[idx].id

        # Baseline per-vehicle cost for delta computation (needed only for 'single')
        baseline_single = None
        if ranking_mode == 'single':
            baseline_single = single_vehicle_cost(vehicle_plan, vehicle, route_map)
            # If baseline is not finite (unexpected), skip this vehicle to avoid misleading deltas
            if not math.isfinite(baseline_single):
                continue

        for i in range(insert_pos, node_list_size + 1):

            # Build a lightweight view of plan with pickup inserted positions for neighbor lookups
            # We won't copy the full list for each j; we just need neighbor ids
            def base_i_id_at(idx: int) -> Optional[str]:
                # sequence with pickup at position i
                if idx < i:
                    return route_id_at(idx)
                if idx == i:
                    return new_pickup_node.id
                return route_id_at(idx - 1)

            for j in range(i + 1, node_list_size + 2):
                # precedence quick checks (reuse original logic)
                prev_id_node = base_i_id_at(j - 1)
                # Need to inspect node type at j-1 in the hypothetical list
                prev_is_pickup = False
                prev_is_delivery = False
                if j - 1 == i:
                    prev_is_pickup = True
                else:
                    # map back to original index
                    orig_idx = j - 1 if (j - 1) < i else (j - 2)
                    if 0 <= orig_idx < len(vehicle_plan):
                        nd = vehicle_plan[orig_idx]
                        prev_is_pickup = bool(nd.pickup_item_list)
                        prev_is_delivery = bool(nd.delivery_item_list)

                if prev_is_pickup and j != i + 1:
                    # find its matching delivery after j-1 and skip ahead
                    found_k = None
                    for k in range(j, node_list_size + 2):
                        # delivery candidate at base_i_id_at(k)
                        if k == i:
                            continue
                        orig_k = k if k < i else (k - 1)
                        if 0 <= orig_k < len(vehicle_plan):
                            ndk = vehicle_plan[orig_k]
                            if ndk.delivery_item_list and ndk.delivery_item_list[-1].id == (vehicle_plan[orig_idx].pickup_item_list[0].id if vehicle_plan[orig_idx].pickup_item_list else None):
                                found_k = k
                                break
                    if found_k is not None:
                        j = found_k + 1
                        # continue with updated j
                elif prev_is_delivery:
                    # ensure its pickup is not before i
                    is_terminal = True
                    # search backwards in base seq
                    scan_limit = j - 2
                    while scan_limit >= 0:
                        if scan_limit == i:
                            # pickup is the inserted new pickup at i (different id), ok to continue
                            pass
                        orig_k = scan_limit if scan_limit < i else (scan_limit - 1)
                        if 0 <= orig_k < len(vehicle_plan):
                            ndk = vehicle_plan[orig_k]
                            if ndk.pickup_item_list and prev_id_node and ndk.pickup_item_list[0].id == (vehicle_plan[orig_k].pickup_item_list[0].id if ndk.pickup_item_list else None):
                                if orig_k < i:
                                    is_terminal = True
                                    break
                                elif orig_k > i:
                                    is_terminal = False
                                    break
                        scan_limit -= 1
                    if is_terminal:
                        break

                # Build candidate route once
                tempRouteNodeList: List[Node] = [n for n in vehicle_plan]
                tempRouteNodeList.insert(i, new_pickup_node)
                tempRouteNodeList.insert(j, new_delivery_node)

                if ranking_mode == 'single':
                    cand_single = single_vehicle_cost(tempRouteNodeList, vehicle, route_map)
                    delta_single = (cand_single - baseline_single) if math.isfinite(cand_single) else math.inf
                    candidates_ij.append((delta_single, i, j))
                else:
                    # Neighbor-based delta ranking
                    pre_i_id = route_id_at(i - 1)
                    next_i_id = route_id_at(i)
                    base_break = 0.0
                    base_add = 0.0
                    if pre_i_id and next_i_id:
                        base_break += dist_ids(pre_i_id, next_i_id)
                    if pre_i_id:
                        base_add += dist_ids(pre_i_id, new_pickup_node.id)
                    if next_i_id:
                        base_add += dist_ids(new_pickup_node.id, next_i_id)
                    delta_i = base_add - base_break

                    pre_j_id = base_i_id_at(j - 1)
                    next_j_id = base_i_id_at(j)
                    base_break_j = 0.0
                    base_add_j = 0.0
                    if pre_j_id and next_j_id:
                        base_break_j += dist_ids(pre_j_id, next_j_id)
                    if pre_j_id:
                        base_add_j += dist_ids(pre_j_id, new_delivery_node.id)
                    if next_j_id:
                        base_add_j += dist_ids(new_delivery_node.id, next_j_id)
                    delta_neighbor = delta_i + (base_add_j - base_break_j)
                    candidates_ij.append((delta_neighbor, i, j))

        # choose top candidates by delta estimate for the chosen ranking
        candidates_ij.sort(key=lambda x: x[0])
        if TOP_CAND_PER_VEH > 0:
            candidates_ij = candidates_ij[:TOP_CAND_PER_VEH]


        # Evaluate with full global cost for selected candidates
        for _, i, j in candidates_ij:
            tempRouteNodeList: List[Node] = [n for n in vehicle_plan]
            tempRouteNodeList.insert(i, new_pickup_node)
            tempRouteNodeList.insert(j, new_delivery_node)
            costValue = cost_of_a_route(tempRouteNodeList, vehicle, id_to_vehicle, route_map, vehicleid_to_plan, mode)
            if costValue < minCostValue:
                minCostValue = costValue
                bestInsertPosI = i
                bestInsertPosJ = j
                bestInsertVehicleID = vehicleID
                isExhautive = False

    return isExhautive , bestInsertVehicleID, bestInsertPosI, bestInsertPosJ , bestNodeList


#Trì hoãn việc triển khai các cặp node mà thời gian hoàn thành còn dư giả
def delay_dispatch_orders(id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , vehicleid_to_plan: Dict[str , list[Node]]) :
    dock_table: Dict[str, List[List[int]]] = {}
    n: int = 0
    vehicle_num: int = len(id_to_vehicle)
    curr_node: List[int] = [0] * vehicle_num
    curr_time: List[int] = [0] * vehicle_num
    leave_last_node_time: List[int] = [0] * vehicle_num

    n_node: List[int] = [0] * vehicle_num
    index = 0
    
    processed_vehicleid_to_plan : Dict[str , List[Node]] = copy.deepcopy(vehicleid_to_plan)
    emergency_dict : Dict[str , List[int]] = {k : [-1] * len(va) for k , va in processed_vehicleid_to_plan.items()}
    
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
                    # travel time from current factory to the first planned node
                    dis_and_time = route_map.get((otherVehicle.cur_factory_id , vehicleid_to_plan[vehicleID][0].id))
                    if dis_and_time is None:
                        dis_and_time = route_map.get((vehicleid_to_plan[vehicleID][0].id, otherVehicle.cur_factory_id))
                    time = int(dis_and_time[1]) if dis_and_time is not None else 0
                    curr_time[index] = otherVehicle.leave_time_at_current_factory + time
            else:
                if otherVehicle.cur_factory_id is not None and len(otherVehicle.cur_factory_id) > 0:
                    if otherVehicle.cur_factory_id == vehicleid_to_plan[vehicleID][0].id:
                        curr_time[index]  = otherVehicle.leave_time_at_current_factory
                    else:
                        curr_time[index] = otherVehicle.leave_time_at_current_factory
                        dis_and_time = route_map.get((otherVehicle.cur_factory_id , vehicleid_to_plan[vehicleID][0].id))
                        if dis_and_time is None:
                            dis_and_time = route_map.get((vehicleid_to_plan[vehicleID][0].id, otherVehicle.cur_factory_id))
                        time = int(dis_and_time[1]) if dis_and_time is not None else 0
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
        minTNodeList = vehicleid_to_plan.get(minT2VehicleID)
        minTNode = minTNodeList[curr_node[minT2VehicleIndex]]
        
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
            
        # Determine emergency for the first node at this factory using predicted start time at dock
        predicted_start_time = tTrue + config.APPROACHING_DOCK_TIME
        if minTNode.delivery_item_list and len(minTNode.delivery_item_list) > 0:
            for order_item in minTNode.delivery_item_list:
                commit_complete_time = order_item.committed_completion_time
                slack_time = commit_complete_time - predicted_start_time
                if slack_time < SLACK_TIME_THRESHOLD:
                    emergency_dict[minT2VehicleID][curr_node[minT2VehicleIndex]] = 1
                    break

        service_time = minTNodeList[curr_node[minT2VehicleIndex]].service_time
        cur_factory_id = minTNodeList[curr_node[minT2VehicleIndex]].id
        curr_node[minT2VehicleIndex] += 1

        while (curr_node[minT2VehicleIndex] < n_node[minT2VehicleIndex] and
            cur_factory_id == minTNodeList[curr_node[minT2VehicleIndex]].id):

            delivery_item_list = minTNodeList[curr_node[minT2VehicleIndex]].delivery_item_list
            
            if delivery_item_list and len(delivery_item_list) > 0:
                # predicted start time for this subsequent node accounts for prior service at this factory
                predicted_start_time = tTrue + config.APPROACHING_DOCK_TIME + service_time
                for order_item in delivery_item_list:
                    commit_complete_time = order_item.committed_completion_time
                    slack_time = commit_complete_time - predicted_start_time
                    if slack_time < SLACK_TIME_THRESHOLD:
                        emergency_dict["V_" + str(minT2VehicleIndex + 1)][curr_node[minT2VehicleIndex]] = 1
                        break

            service_time += minTNodeList[curr_node[minT2VehicleIndex]].service_time
            curr_node[minT2VehicleIndex] += 1
        
        if curr_node[minT2VehicleIndex] >= n_node[minT2VehicleIndex]:
            n -= 1
            curr_node[minT2VehicleIndex] = math.inf
            curr_time[minT2VehicleIndex] = math.inf
            n_node[minT2VehicleIndex] = 0
        else:
            dis_and_time = route_map.get((cur_factory_id , minTNodeList[curr_node[minT2VehicleIndex]].id))
            if dis_and_time is None:
                dis_and_time = route_map.get((minTNodeList[curr_node[minT2VehicleIndex]].id, cur_factory_id))
            if dis_and_time:
                time = int(dis_and_time[1])
            else:
                time = 0

            curr_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time + time
            leave_last_node_time[minT2VehicleIndex] = tTrue + config.APPROACHING_DOCK_TIME + service_time

        tw = [minT, tTrue + config.APPROACHING_DOCK_TIME + service_time]
        tw_list = dock_table.get(minTNode.id, [])

        tw_list.append(tw)
        dock_table[minTNode.id] = tw_list
    
    for vehicleID , node_list in processed_vehicleid_to_plan.items():
        vehicle = id_to_vehicle[vehicleID]
        # If vehicle is currently carrying items, keep full route to satisfy LIFO/feasibility
        has_carrying = False
        try:
            has_carrying = (vehicle.carrying_items is not None) and (not vehicle.carrying_items.is_empty())
        except Exception:
            try:
                has_carrying = (vehicle.carrying_items is not None) and (len(vehicle.carrying_items) > 0)
            except Exception:
                has_carrying = False
        if has_carrying:
            # keep original plan for this vehicle
            processed_vehicleid_to_plan[vehicleID] = node_list
            continue
        start_idx =0
        # Only keep a delivery if its matching pickup exists; then keep both
        keep_indices: set[int] = set()
        # Always keep destination header if present and matches vehicle.des
        header_kept = False
        if node_list and vehicle.des and node_list[0].id == vehicle.des.id:
            keep_indices.add(0)
            header_kept = True
            start_idx = 1
        for idx in range(start_idx, len(node_list)):
            if emergency_dict[vehicleID][idx] == 1 and node_list[idx].delivery_item_list:
                target_id = node_list[idx].delivery_item_list[-1].id
                p_idx = idx - 1
                found_pickup = False
                while p_idx >= start_idx:
                    nd = node_list[p_idx]
                    if nd.pickup_item_list and nd.pickup_item_list[0].id == target_id:
                        found_pickup = True
                        break
                    p_idx -= 1
                if found_pickup:
                    keep_indices.add(p_idx)
                    keep_indices.add(idx)

        # Closure: for any kept pickup, also keep its matching delivery later in the plan
        # Especially important for header that contains a pickup
        def find_matching_delivery(after_idx: int, item_id: str) -> Optional[int]:
            for j in range(max(after_idx, start_idx), len(node_list)):
                nd = node_list[j]
                if nd.delivery_item_list and nd.delivery_item_list[-1].id == item_id:
                    return j
            return None

        # Track if we fail to close header pickup -> fallback to original plan
        need_fallback_to_full_plan = False

        # Ensure deliveries for kept pickups
        for i in sorted(list(keep_indices)):
            nd = node_list[i]
            if nd.pickup_item_list:
                pid = nd.pickup_item_list[0].id
                j = find_matching_delivery(i + 1, pid)
                if j is not None:
                    keep_indices.add(j)
                else:
                    # If header has pickup but no delivery found, safer to return full plan
                    if header_kept and i == 0:
                        need_fallback_to_full_plan = True
                        break

        # filter only kept indices (urgent deliveries and their pickups), preserving order
        if need_fallback_to_full_plan:
            filtered = node_list
        else:
            filtered = [node for i , node in enumerate(processed_vehicleid_to_plan[vehicleID]) if i in keep_indices]

        # Final LIFO validation against current carrying stack; if fails, drop non-header nodes
        def lifo_ok(route_nodes: List[Node], veh: Vehicle) -> bool:
            try:
                ci = copy.deepcopy(veh.carrying_items)
            except Exception:
                return True  # if cannot copy, skip strict check
            # simulate header node (first) then the rest
            for nd in route_nodes:
                if nd.delivery_item_list:
                    for it in nd.delivery_item_list:
                        # pop from either Stack-like or list
                        top = ci.pop()
                        if top is None or getattr(top, 'id', None) != getattr(it, 'id', None):
                            return False
                if nd.pickup_item_list:
                    for it in nd.pickup_item_list:
                        if hasattr(ci, 'push'):
                            ci.push(it)
                        else:
                            ci.append(it)
            # do not require empty at end; we only ensure no violation during sequence
            return True

        if filtered and not lifo_ok(filtered, vehicle):
            # Keep only header if present to ensure feasibility
            filtered = filtered[:1] if (filtered and vehicle.des and filtered[0].id == vehicle.des.id) else []
        processed_vehicleid_to_plan[vehicleID] = filtered
    
    return processed_vehicleid_to_plan

#====================================================================================================================================================================


def extract_block_from_solution (vehicleid_to_plan : Dict[str , List[Node]] , id_to_vehicle : Dict[str , Vehicle]) -> Dict[str , List[Node]]:
    dis_order_super_node , _ = get_UnongoingSuperNode(vehicleid_to_plan , id_to_vehicle)
    
    ls_node_pair_num = len(dis_order_super_node)
    if ls_node_pair_num == 0:
        return False
    
    vehicleID = None
    block_map : Dict[str , List[Node]] = {}
    for idx , pdg in dis_order_super_node.items():
        pickup_node : Node = None
        delivery_node : Node = None
        node_list :List[Node] = []
        posI :int =0 ; posJ : int= 0
        dNum : int= len(pdg) // 2
        index :int= 0
        if pdg:
            for v_and_pos_str, node in pdg.items():
                if index % 2 == 0:
                    vehicleID = v_and_pos_str.split(",")[0]
                    posI = int(v_and_pos_str.split(",")[1])
                    pickup_node = node
                    node_list.insert(0, pickup_node)
                    index += 1
                else:
                    posJ = int(v_and_pos_str.split(",")[1])
                    delivery_node = node
                    node_list.append(delivery_node)
                    index += 1
                    posJ = posJ - dNum + 1
            
            vehicle_node_route : List[Node] = vehicleid_to_plan.get(vehicleID , [])
            
            for i in range(posI + dNum , posJ):
                node_list.insert(i - posI , vehicle_node_route[i])

            k : str = f"{vehicleID},{posI}+{posJ + dNum - 1}"    
            block_map[k] = node_list
    
    return block_map

# chấm điểm cho dựa trên cấu trúc của block
def block_scoring_func(blockmap: Dict[str, List[Node]],
                      vehicleid_to_plan1: Dict[str, List[Node]],
                      vehicleid_to_plan2: Dict[str, List[Node]],
                      route_map: Dict[Tuple[str, str], Tuple[float, float]]) -> Dict[str, Tuple[float, float, float]]:
    """Tính điểm cho từng block và trả về 3 chỉ số:
    (avg_distance, avg_time, avg_demand)

    - avg_distance: trung bình quãng đường giữa các cặp node liên tiếp.
    - avg_time: trung bình thời gian di chuyển giữa các cặp node liên tiếp.
    - avg_demand: trung bình demand của tất cả item (pickup + delivery) xuất hiện trong block.

    Các block không hợp lệ (số node < 2 hoặc số node lẻ) trả về (inf, inf, inf).
    Nếu không có cạnh hợp lệ (edge_count == 0) thì avg_distance = avg_time = 0.0 nhưng vẫn tính avg_demand.
    """
    block_scores: Dict[str, Tuple[float, float, float]] = {}

    if not blockmap:
        return block_scores

    for block_key, node_list in blockmap.items():
        if not node_list or len(node_list) % 2 != 0 or len(node_list) < 2:
            block_scores[block_key] = (math.inf, math.inf, math.inf)
            continue

        total_distance = 0.0
        total_time = 0.0
        edge_count = 0
        total_demand = 0.0
        item_count = 0

        # Tính demand trung bình trước (không phụ thuộc vào cạnh hợp lệ)
        for nd in node_list:
            if nd.pickup_item_list:
                for it in nd.pickup_item_list:
                    if hasattr(it, 'demand'):
                        total_demand += it.demand
                        item_count += 1
            if nd.delivery_item_list:
                for it in nd.delivery_item_list:
                    if hasattr(it, 'demand'):
                        total_demand += it.demand
                        item_count += 1
        avg_demand = (total_demand / item_count) if item_count > 0 else 0.0

        # Duyệt các cặp node liên tiếp để lấy distance/time
        for i in range(len(node_list) - 1):
            n1 = node_list[i]
            n2 = node_list[i + 1]
            if not n1 or not n2:
                continue
            key = (n1.id, n2.id)
            dis_time = route_map.get(key)
            if dis_time is None:
                dis_time = route_map.get((n2.id, n1.id))
            if dis_time is None:
                continue
            try:
                distance_val = float(dis_time[0])
                time_val = float(dis_time[1])
            except (ValueError, TypeError, IndexError):
                continue
            total_distance += distance_val
            total_time += time_val
            edge_count += 1

        if edge_count == 0:
            avg_distance = 0.0
            avg_time = 0.0
        else:
            avg_distance = total_distance / edge_count
            avg_time = total_time / edge_count

        block_scores[block_key] = (avg_distance, avg_time, avg_demand)

    return block_scores

# Incremental scoring with cache to avoid recomputing unchanged blocks each iteration
def compute_block_scores_incremental(blockmap: Optional[Dict[str, List[Node]]],
                                     route_map: Dict[Tuple[str, str], Tuple[float, float]],
                                     score_cache: Dict[str, Tuple[float, float, float]]) -> Dict[str, Tuple[float, float, float]]:
    """Compute block scores using a cache.

    - blockmap: key -> node_list
    - route_map: distance/time matrix
    - score_cache: persisted across iterations, stores key -> (avg_distance, avg_time, avg_demand)

    Returns a dict of scores for keys present in blockmap. For any key not in cache, compute and store it.
    This mirrors block_scoring_func per-block logic but avoids recomputing existing keys.
    """
    if not blockmap:
        return {}

    result: Dict[str, Tuple[float, float, float]] = {}

    for block_key, node_list in blockmap.items():
        if block_key in score_cache:
            result[block_key] = score_cache[block_key]
            continue

        # Compute score for this block (same logic as block_scoring_func for a single block)
        if not node_list or len(node_list) % 2 != 0 or len(node_list) < 2:
            score_cache[block_key] = (math.inf, math.inf, math.inf)
            result[block_key] = score_cache[block_key]
            continue

        total_distance = 0.0
        total_time = 0.0
        edge_count = 0
        total_demand = 0.0
        item_count = 0

        for nd in node_list:
            if nd.pickup_item_list:
                for it in nd.pickup_item_list:
                    if hasattr(it, 'demand'):
                        total_demand += it.demand
                        item_count += 1
            if nd.delivery_item_list:
                for it in nd.delivery_item_list:
                    if hasattr(it, 'demand'):
                        total_demand += it.demand
                        item_count += 1
        avg_demand = (total_demand / item_count) if item_count > 0 else 0.0

        for i in range(len(node_list) - 1):
            n1 = node_list[i]
            n2 = node_list[i + 1]
            if not n1 or not n2:
                continue
            key = (n1.id, n2.id)
            dis_time = route_map.get(key)
            if dis_time is None:
                dis_time = route_map.get((n2.id, n1.id))
            if dis_time is None:
                continue
            try:
                distance_val = float(dis_time[0])
                time_val = float(dis_time[1])
            except (ValueError, TypeError, IndexError):
                continue
            total_distance += distance_val
            total_time += time_val
            edge_count += 1

        if edge_count == 0:
            avg_distance = 0.0
            avg_time = 0.0
        else:
            avg_distance = total_distance / edge_count
            avg_time = total_time / edge_count

        score = (avg_distance, avg_time, avg_demand)
        score_cache[block_key] = score
        result[block_key] = score

    return result

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
        def _carrying_list2(v: Vehicle) -> List[OrderItem]:
            ci = getattr(v, 'carrying_items', None)
            try:
                ci_copy = copy.deepcopy(ci)
            except Exception:
                ci_copy = ci
            try:
                items_top_first: List[OrderItem] = []
                while ci_copy is not None and hasattr(ci_copy, 'is_empty') and not ci_copy.is_empty():
                    items_top_first.append(ci_copy.pop())
                return list(reversed(items_top_first)) if items_top_first else (list(ci_copy) if isinstance(ci_copy, list) else [])
            except Exception:
                try:
                    return list(ci_copy) if ci_copy is not None else []
                except Exception:
                    return []
        carrying_items = _carrying_list2(vehicle)
        if not isFeasible(tempRouteNodeList, carrying_items, vehicle.board_capacity):
            continue
        # Temporarily override this vehicle's route
        tmp_cost = cost_of_a_route(tempRouteNodeList, vehicle, id_to_vehicle, route_map, vehicleid_to_plan)
        
        if tmp_cost < minCost:
            minCost = tmp_cost
            bestInsertPos = len(vehicle_plan)
            bestInsertVehicleID = vehicleID

    return bestInsertPos, bestInsertVehicleID

# ================== Block map update with overlap removal & optional salvage (LIFO assumption) ==================
# Thay vì lưu toàn bộ item id, chỉ lưu chữ ký nhóm pickup-delivery: "{count}_{anchor_item_id}"
# anchor_item_id: pickup -> first item id; delivery -> last item id (theo quy ước new_PDG_map)
def update_blockmap(blockmap1 : Dict[str, List[Node]] , blockmap2 : Dict[str , List[Node]] , used_block_nodes: List[Node] , used_signatures : set[str]):
    """Cập nhật blockmap sau khi chèn một block.

    Tối ưu hiệu năng: chỉ đánh dấu các nhóm PD bằng chữ ký (len_pick_list + '_' + first_pick_id)
    tương thích với key của new_PDG_map. Delivery node có chữ ký (len_delivery_list + '_' + last_delivery_id) và
    giả định first pickup id == last delivery id cho cùng nhóm -> hai chữ ký trùng nhau.

    Các bước:
    1. Thu thập chữ ký pickup trong block vừa dùng -> thêm vào used_signatures.
    2. Với mỗi block còn lại: nếu giao chữ ký mới -> tách salvage (trái/phải) bỏ phần giao.
    3. Chỉ giữ segment hợp lệ (balanced LIFO, số nút chẵn >=2, không chứa chữ ký đã dùng).
    4. Xóa block gốc trùng/giao; thêm các segment mới (tối đa 2).
    5. Dọn dẹp block nào vẫn chứa chữ ký đã dùng.
    """
    if not used_block_nodes:
        return
    
    def pickup_signature(nd: Node) -> Optional[str]:
        if nd.pickup_item_list:
            return f"{len(nd.pickup_item_list)}_{nd.pickup_item_list[0].id}"
        return None

    def delivery_signature(nd: Node) -> Optional[str]:
        if nd.delivery_item_list:
            return f"{len(nd.delivery_item_list)}_{nd.delivery_item_list[-1].id}"
        return None

    # Tạo tập chữ ký mới từ block vừa dùng (dùng pickup đủ, nhưng thêm delivery để chắc chắn)
    new_used_set : set[str] = set()
    for nd in used_block_nodes:
        sig_p = pickup_signature(nd)
        if sig_p: new_used_set.add(sig_p)
        sig_d = delivery_signature(nd)
        if sig_d: new_used_set.add(sig_d)
    used_signatures.update(new_used_set)

    # Kiểm tra LIFO balanced nhanh dựa trên chữ ký (stack chữ ký pickup, delivery phải trùng)
    def is_lifo_balanced(nodes: List[Node]) -> bool:
        stack : List[str] = []
        for nd in nodes:
            sig_p = pickup_signature(nd)
            if sig_p:
                stack.append(sig_p)
            sig_d = delivery_signature(nd)
            if sig_d:
                if not stack or stack[-1] != sig_d:
                    return False
                stack.pop()
        return len(stack) == 0

    salvage_min_pairs = 1           # keep residual only if at least this many pickup-delivery pairs
    salvage_min_ratio = 0.0         # set >0 (e.g. 0.5) to enforce size ratio vs original, 0 disables
    max_new_segments_per_block = 2  # with LIFO we expect at most 2

    def process_blockmap(bmap: Dict[str, List[Node]]):
        if not bmap:
            return
        to_delete : List[str] = []
        to_add : List[Tuple[str, List[Node]]] = []
        # iterate over snapshot because we will modify after
        
        for key, nodes in list(bmap.items()):
            if not nodes:
                to_delete.append(key)
                continue
            # Thu thập chữ ký pickup của block
            block_pick_sigs : List[str] = []
            block_all_sigs : set[str] = set()
            for nd in nodes:
                sp = pickup_signature(nd)
                if sp:
                    block_pick_sigs.append(sp)
                    block_all_sigs.add(sp)
                sd = delivery_signature(nd)
                if sd:
                    block_all_sigs.add(sd)

            # Nếu không giao với chữ ký mới nhưng đã dùng trước đó -> xóa; nếu không thì giữ nguyên
            if block_all_sigs.isdisjoint(new_used_set):
                if not block_all_sigs.isdisjoint(used_signatures - new_used_set):
                    to_delete.append(key)
                continue

            # If this block is exactly the inserted block (same length & node identity/order) -> remove directly
            if len(nodes) == len(used_block_nodes) and all(a is b for a,b in zip(nodes, used_block_nodes)):
                to_delete.append(key)
                continue
            
            # Attempt salvage: split into contiguous segments whose nodes do NOT contain any newly used item ids
            segments : List[List[Node]] = []
            current : List[Node] = []
            def node_has_new_sig(nd: Node) -> bool:
                sp = pickup_signature(nd)
                if sp and sp in new_used_set: return True
                sd = delivery_signature(nd)
                if sd and sd in new_used_set: return True
                return False
            for nd in nodes:
                if node_has_new_sig(nd):
                    if current:
                        segments.append(current)
                        current = []
                else:
                    current.append(nd)
            if current:
                segments.append(current)

            # Evaluate & keep valid segments
            added_segments = 0
            for idx, seg in enumerate(segments):
                if added_segments >= max_new_segments_per_block:
                    break
                if len(seg) < 2 or len(seg) % 2 != 0:
                    continue
                if not is_lifo_balanced(seg):
                    continue
                # Tính số cặp = số pickup signature trong segment
                seg_pick_sigs = []
                seg_all_sigs : set[str] = set()
                for nd in seg:
                    sp = pickup_signature(nd)
                    if sp:
                        seg_pick_sigs.append(sp)
                        seg_all_sigs.add(sp)
                    sd = delivery_signature(nd)
                    if sd:
                        seg_all_sigs.add(sd)
                # Loại nếu có chữ ký đã dùng
                if not seg_all_sigs.isdisjoint(used_signatures):
                    continue
                pair_count = len(seg_pick_sigs)
                pair_count = len(seg) // 2
                if pair_count < salvage_min_pairs:
                    continue
                if salvage_min_ratio > 0 and (len(seg)/len(nodes)) < salvage_min_ratio:
                    continue
                # create new key
                new_key = f"{key}|r{idx}"
                # avoid key collision
                suffix = 0
                base_new_key = new_key
                while new_key in bmap or any(k == new_key for k,_ in to_add):
                    suffix += 1
                    new_key = f"{base_new_key}_{suffix}"
                
                to_add.append((new_key, seg))
                added_segments += 1

            # original block removed regardless once processed (overlapped)
            to_delete.append(key)

        # apply deletions
        for k in to_delete:
            bmap.pop(k, None)
        # add salvage blocks
        for k, seg in to_add:
            bmap[k] = seg

        # final safety: remove any block accidentally containing used signatures
        purge_keys = []
        for k, nodes in bmap.items():
            has_used = False
            for nd in nodes:
                sp = pickup_signature(nd)
                if sp and sp in used_signatures:
                    has_used = True
                    break
                sd = delivery_signature(nd)
                if sd and sd in used_signatures:
                    has_used = True
                    break
            if has_used:
                purge_keys.append(k)
        for k in purge_keys:
            bmap.pop(k, None)

    process_blockmap(blockmap1)
    process_blockmap(blockmap2)


# ================== Simple block map update (NO salvage) ==================
def update_blockmap_drop_overlap(blockmap1: Dict[str, List[Node]],
                                 blockmap2: Dict[str, List[Node]],
                                 used_block_nodes: List[Node],
                                 used_signatures: set[str]):
    """Cập nhật blockmap nhưng KHÔNG tái sử dụng (salvage) phần còn lại của các block overlap.

    Khác với `update_blockmap` (có salvage segment), hàm này chỉ đơn giản:
    1. Thu thập chữ ký (signature) của toàn bộ pickup & delivery trong block vừa dùng.
    2. Thêm các chữ ký đó vào `used_signatures` (tập toàn cục các nhóm đã chọn).
    3. Xóa mọi block chứa bất kỳ chữ ký nào đã dùng (bao gồm mới và cũ).
       => Loại bỏ triệt để overlap, không giữ lại phần còn lại để tránh rủi ro nhiễu cấu trúc.

    Ưu điểm:
    - Nhanh, đơn giản, tránh tạo nhiều block nhỏ gây phân mảnh.
    - Hữu ích nếu heuristic salvage làm giảm chất lượng hoặc gây quá nhiều block nhỏ.

    Nhược điểm:
    - Có thể bỏ lỡ cơ hội tái sử dụng phần “sạch” còn lại của block lớn.

    Tham số:
    - blockmap1, blockmap2: hai dict block của 2 parent.
    - used_block_nodes: list node của block vừa chèn (có thể None / rỗng nếu vòng đầu tiên).
    - used_signatures: set lưu chữ ký đã chọn qua các vòng trước (sẽ được cập nhật tại chỗ).
    """
    if not used_block_nodes:
        return

    def pickup_signature(nd: Node) -> Optional[str]:
        if nd.pickup_item_list:
            return f"{len(nd.pickup_item_list)}_{nd.pickup_item_list[0].id}"
        return None

    def delivery_signature(nd: Node) -> Optional[str]:
        if nd.delivery_item_list:
            return f"{len(nd.delivery_item_list)}_{nd.delivery_item_list[-1].id}"
        return None

    # 1. Thu thập chữ ký mới
    new_used_set: set[str] = set()
    for nd in used_block_nodes:
        sp = pickup_signature(nd)
        if sp:
            new_used_set.add(sp)
        sd = delivery_signature(nd)
        if sd:
            new_used_set.add(sd)
    used_signatures.update(new_used_set)

    def purge(bmap: Dict[str, List[Node]]):
        if not bmap:
            return
        to_delete: List[str] = []
        for key, nodes in bmap.items():
            if not nodes:
                to_delete.append(key)
                continue
            remove_block = False
            if len(nodes) == len(used_block_nodes) and all(a is b for a, b in zip(nodes, used_block_nodes)):
                # Chính là block vừa dùng
                remove_block = True
            else:
                for nd in nodes:
                    sp = pickup_signature(nd)
                    if sp and sp in used_signatures:
                        remove_block = True
                        break
                    sd = delivery_signature(nd)
                    if sd and sd in used_signatures:
                        remove_block = True
                        break
            if remove_block:
                to_delete.append(key)
        for k in to_delete:
            bmap.pop(k, None)

    purge(blockmap1)
    purge(blockmap2)



# ================= Helper functions for validation ==================
def pickup_signature_of(nd: Node) -> Optional[str]:
    if nd and nd.pickup_item_list:
        return f"{len(nd.pickup_item_list)}_{nd.pickup_item_list[0].id}"
    return None

def delivery_signature_of(nd: Node) -> Optional[str]:
    if nd and nd.delivery_item_list:
        return f"{len(nd.delivery_item_list)}_{nd.delivery_item_list[-1].id}"
    return None

def extract_pickup_signatures(nodes: List[Node]) -> set[str]:
    sigs = set()
    for nd in nodes:
        ps = pickup_signature_of(nd)
        if ps:
            sigs.add(ps)
    return sigs


def build_block_vehicle_map(blockmap: Dict[str, List[Node]], node2veh: Dict[int, str]) -> Dict[str, Optional[str]]:
    res: Dict[str, Optional[str]] = {}
    for k, nodes in (blockmap or {}).items():
        vid: Optional[str] = None
        # Pick the first node that matches a vehicle; blocks should be contiguous from one route
        for nd in (nodes or []):
            vid = node2veh.get(id(nd))
            if vid is not None:
                break
        res[k] = vid
    return res

# Map each node (by identity) to its vehicle in each parent, then map blocks -> source vehicle
def build_node_to_vehicle(solution: Dict[str, List[Node]]) -> Dict[int, str]:
    m: Dict[int, str] = {}
    for vid, route in (solution or {}).items():
        if not route:
            continue
        for nd in route:
            m[id(nd)] = vid
    return m

# Hàm tính chữ ký block
def block_signatures(nodes: List[Node]) -> set[str]:
    sigs: set[str] = set()
    for nd in nodes:
        if nd.pickup_item_list:
            sigs.add(f"{len(nd.pickup_item_list)}_{nd.pickup_item_list[0].id}")
        if nd.delivery_item_list:
            sigs.add(f"{len(nd.delivery_item_list)}_{nd.delivery_item_list[-1].id}")
    return sigs
            

PREFILTER_K = 1200

def find_best_block(blockmap1: Dict[str, List[Node]],
                    blockmap2: Dict[str, List[Node]],
                    blockscore1: Dict[str, Tuple[float, float, float]],
                    blockscore2: Dict[str, Tuple[float, float, float]]):
    """Chọn block tốt nhất với skyline O(B log B) thay vì O(B^2):
    1) Hợp nhất ứng viên từ cả hai parent: (key, nodes, avg_dis, avg_time, avg_demand).
    2) Lọc non-dominated bằng thuật toán skyline 2D (dis, time): sort theo dis tăng dần, giữ các điểm có time < best_time_so_far.
    3) Trong front, ưu tiên demand lớn (giữ hiệu quả) rồi tie-break bằng (dis+time) nhỏ.
    """
    candidates = []  # (key, nodes, avg_dis, avg_time, avg_demand)

    # Gom ứng viên từ parent 1
    for k, nodes in (blockmap1 or {}).items():
        if not nodes:
            continue
        score = blockscore1.get(k)
        if not score:
            continue
        avg_dis, avg_time, avg_demand = score
        if math.isinf(avg_dis) or math.isinf(avg_time) or math.isinf(avg_demand):
            continue
        candidates.append((k, nodes, avg_dis, avg_time, avg_demand))
    # Gom ứng viên từ parent 2
    for k, nodes in (blockmap2 or {}).items():
        if not nodes:
            continue
        score = blockscore2.get(k)
        if not score:
            continue
        avg_dis, avg_time, avg_demand = score
        if math.isinf(avg_dis) or math.isinf(avg_time) or math.isinf(avg_demand):
            continue
        candidates.append((k, nodes, avg_dis, avg_time, avg_demand))

    if not candidates:
        return None

    # Prefilter top-K by demand desc then (dis+time) asc to reduce set size
    if len(candidates) > PREFILTER_K:
        candidates.sort(key=lambda x: (-x[4], (x[2] + x[3])))
        candidates = candidates[:PREFILTER_K]

    # Skyline: O(B log B)
    candidates.sort(key=lambda x: (x[2], x[3]))  # sort by distance asc, time asc
    front = []
    best_time = math.inf
    for item in candidates:
        _, _, dis, tim, _ = item
        # Since sorted by (dis asc, time asc), any item with time < best_time is non-dominated
        if tim < best_time:
            front.append(item)
            best_time = tim

    if not front:
        return None

    # Ưu tiên demand lớn, tie-break theo (dis+time) nhỏ
    front.sort(key=lambda x: (-x[4], (x[2] + x[3])))
    best = front[0]
    return best[1]

def new_crossver2(parent1: Chromosome , parent2: Chromosome , Base_vehicleid_to_plan : Dict[str , List[Node]] , PDG_map: Dict[str , List[Node]] , static_single_pass: bool = False):
    begin = time.time()
    
    # Cac super node
    new_PDG_map : Dict[str , List[Node]] = {}
    for key , value in PDG_map.items():
        if len(value )!= 2: print("ERROR 1")
        first_node = value[0]
        if first_node.pickup_item_list and first_node.delivery_item_list:
            print ("ERROR 2")
        if first_node.pickup_item_list:
            key = f'{len(first_node.pickup_item_list)}_{first_node.pickup_item_list[0].id}'
        elif first_node.delivery_item_list:
            key = f'{len(first_node.delivery_item_list)}_{first_node.delivery_item_list[-1].id}'
        
        
        new_PDG_map[key] = value
        
    check_valid : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    
    blockmap_parent1 = extract_block_from_solution(parent1.solution , parent1.id_to_vehicle)
    blockmap_parent2 = extract_block_from_solution(parent2.solution , parent2.id_to_vehicle)


    # ========= Khởi tạo biến điều khiển vòng lặp =========
    DEBUG = False  # set True to enable verbose logging
    start_time = time.time()
    iteration = 0
    stagnation = 0  # số vòng không thu thêm signature mới
    total_blocks_target = len(new_PDG_map) if new_PDG_map else 0
    # Tham số dừng (có thể điều chỉnh / đưa ra ngoài nếu cần tinh chỉnh sau)
    MAX_ITER = max(5, 2 * total_blocks_target) if total_blocks_target > 0 else 20
    MAX_NO_GAIN = 5          # số vòng liên tiếp không có gain mới thì dừng
    TIME_BUDGET_SEC = 15   # ngân sách thời gian cho riêng crossover này
    MIN_GAIN_PER_BLOCK = 1   # yêu cầu tối thiểu signature mới / vòng

    # Ghi lại lý do dừng cuối cùng (debug)
    last_stop_reason = None

    def is_finished() -> bool:
        """Điều kiện dừng tổng hợp cho vòng lặp chọn block.

        Các tiêu chí:
        1. Timeout toàn cục (config.is_timeout()).
        2. Hết block (cả hai map rỗng hoặc None).
        3. Đủ coverage (số signature đã dùng >= tổng số super nhóm ban đầu).
        4. Quá số vòng lặp tối đa.
        5. Vượt ngân sách thời gian cục bộ.
        6. Stagnation (không có gain mới quá MAX_NO_GAIN).
        """
        nonlocal last_stop_reason
        # 1. Timeout toàn cục
        if hasattr(config, 'is_timeout') and config.is_timeout():
            last_stop_reason = 'global-timeout'
            return True
        # 2. Hết block
        empty1 = (not blockmap_parent1) or (len(blockmap_parent1) == 0)
        empty2 = (not blockmap_parent2) or (len(blockmap_parent2) == 0)
        if empty1 and empty2:
            last_stop_reason = 'no-blocks-left'
            return True
        # 3. Coverage đủ
        if total_blocks_target > 0 and len(used_signatures) >= total_blocks_target:
            last_stop_reason = 'coverage-complete'
            return True
        # 4. Quá số vòng
        if iteration >= MAX_ITER:
            last_stop_reason = 'max-iter'
            return True
        # 5. Hết ngân sách thời gian cục bộ
        if (time.time() - start_time) >= TIME_BUDGET_SEC:
            last_stop_reason = 'time-budget'
            return True
        # 6. Stagnation
        if stagnation >= MAX_NO_GAIN:
            last_stop_reason = 'stagnation'
            return True
        return False
    
    
    used_signatures : set[str] = set()

    child_vehicleid_to_plan : Dict[str , List[Node]] = copy.deepcopy(Base_vehicleid_to_plan)

    # Seed used_signatures from any existing nodes in base plan (avoid re-adding groups already present)
    for v_nodes in child_vehicleid_to_plan.values():
        used_signatures.update(extract_pickup_signatures(v_nodes))
    if DEBUG and used_signatures:
        print(f"[new_crossver2] Seeded {len(used_signatures)} signatures from base plan", file=sys.stderr)
    
    prev_block = None
    if DEBUG:
        print(f"[new_crossver2] START | total_target_blocks={len(new_PDG_map)}", file=sys.stderr)

    # Optional FAST PATH: compute scores once and insert in a single ordered pass
    if static_single_pass:
        # 1) Compute scores once
        score_map_p1 = block_scoring_func(blockmap_parent1, parent1.solution, parent2.solution, parent1.route_map)
        score_map_p2 = block_scoring_func(blockmap_parent2, parent1.solution, parent2.solution, parent1.route_map)

        # 2) Build candidate list
        candidates = []  # (origin, key, nodes, dis, time, demand)
        if blockmap_parent1:
            for k, nodes in blockmap_parent1.items():
                sc = score_map_p1.get(k)
                if not sc:
                    continue
                d, t, dem = sc
                if math.isinf(d) or math.isinf(t) or math.isinf(dem):
                    continue
                candidates.append(("P1", k, nodes, d, t, dem))
        if blockmap_parent2:
            for k, nodes in blockmap_parent2.items():
                sc = score_map_p2.get(k)
                if not sc:
                    continue
                d, t, dem = sc
                if math.isinf(d) or math.isinf(t) or math.isinf(dem):
                    continue
                candidates.append(("P2", k, nodes, d, t, dem))

        # Prefilter by demand desc then (d+t) asc to shrink candidate set
        if len(candidates) > PREFILTER_K:
            candidates.sort(key=lambda x: (-x[5], (x[3] + x[4])))
            candidates = candidates[:PREFILTER_K]

        # 3) Compute skyline front once
        def skyline_front(items):
            items_sorted = sorted(items, key=lambda x: (x[3], x[4]))  # by (distance, time)
            best_time = math.inf
            # Use (origin,key) as identity to avoid unhashable list in tuple
            front_identities = set()
            for it in items_sorted:
                if it[4] < best_time:
                    best_time = it[4]
                    front_identities.add((it[0], it[1]))  # (origin, key)
            return front_identities

        front_set = skyline_front(candidates)
        # 4) Static ranking: prefer skyline members, then demand desc, then (d+t)
        candidates.sort(key=lambda x: (0 if (x[0], x[1]) in front_set else 1, -x[5], (x[3] + x[4])))

        # 5) Single pass insertion
        for origin, key, nodes, d, t, dem in candidates:
            # If already fully covered all PD groups, stop
            if total_blocks_target > 0 and len(used_signatures) >= total_blocks_target:
                break

            # Skip if any of its pickup signatures already used
            def block_pickup_sigs(ns: List[Node]) -> set[str]:
                s = set()
                for nd in ns:
                    if nd.pickup_item_list:
                        s.add(f"{len(nd.pickup_item_list)}_{nd.pickup_item_list[0].id}")
                return s
            pick_sigs = block_pickup_sigs(nodes)
            if any(sig in used_signatures for sig in pick_sigs):
                continue

            # Determine target vehicle (currently not enforcing source vehicle mapping)
            selected_vehicle: Optional[str] = None

            # Try insertion at best position (append-based CI currently)
            bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(
                nodes,
                parent1.id_to_vehicle,
                child_vehicleid_to_plan,
                parent1.route_map,
                selected_vehicle=None,
            )
            if bestInsertVehicle is None:
                # Strict mode: if enforcing source vehicle and no feasible insertion, skip this block
                continue
            target_route = child_vehicleid_to_plan[bestInsertVehicle]
            target_route[bestInsertPos: bestInsertPos] = nodes
            target_vehicle = parent1.id_to_vehicle[bestInsertVehicle] 
            
            if not isFeasible(target_route , target_vehicle.carrying_items , target_vehicle.board_capacity):
                # rollback
                del target_route[bestInsertPos: bestInsertPos + len(nodes)]
                continue

            # Update signatures and drop overlaps in blockmaps (no salvage)
            used_signatures.update(pick_sigs)
            update_blockmap_drop_overlap(blockmap_parent1, blockmap_parent2, nodes, used_signatures)

    # Caches for block scores to avoid recomputation across iterations (dynamic mode)
    score_cache_p1: Dict[str, Tuple[float, float, float]] = {}
    score_cache_p2: Dict[str, Tuple[float, float, float]] = {}
    
    while not static_single_pass:
        begin  = time.time()
        if is_finished():
            if DEBUG:
                print(f"[new_crossver2] STOP before-iter reason={last_stop_reason} iter={iteration}", file=sys.stderr)
            break
        try:
            # Log trạng thái đầu vòng lặp (coverage hiện tại trước khi chọn block mới)
            if DEBUG:
                print(
                    f"[new_crossver2] Iter {iteration} | blocks_p1={len(blockmap_parent1) if blockmap_parent1 else 0} | "
                    f"blocks_p2={len(blockmap_parent2) if blockmap_parent2 else 0} | used_sig={len(used_signatures)}/{total_blocks_target} | "
                    f"stagn={stagnation}",
                    file=sys.stderr
                )

            # Cập nhật block map với block trước đó
            update_blockmap(blockmap_parent1, blockmap_parent2, prev_block, used_signatures)
            
            # Điểm các block
            block_score_parent1 = compute_block_scores_incremental(blockmap_parent1, parent1.route_map, score_cache_p1)
            block_score_parent2 = compute_block_scores_incremental(blockmap_parent2, parent1.route_map, score_cache_p2)
            candidate_count = (len(block_score_parent1) if block_score_parent1 else 0) + (len(block_score_parent2) if block_score_parent2 else 0)
            if DEBUG:
                print(f"[new_crossver2] Iter {iteration} | candidate_blocks={candidate_count}", file=sys.stderr)

            best_block = find_best_block(blockmap_parent1, blockmap_parent2, block_score_parent1, block_score_parent2)
            if not best_block:
                last_stop_reason = 'no-candidate'
                if DEBUG:
                    print(f"[new_crossver2] Iter {iteration} | no candidates -> stopping", file=sys.stderr)
                break

            # Lấy key block (nếu xác định được) để log
            found_key = None
            for k, v in (blockmap_parent1 or {}).items():
                if v is best_block:
                    found_key = f"P1:{k}"
                    break
            if not found_key:
                for k, v in (blockmap_parent2 or {}).items():
                    if v is best_block:
                        found_key = f"P2:{k}"
                        break
            
            new_sigs = block_signatures(best_block)
            # Skip block if any of its pickup signatures already used (to avoid duplicates & LIFO conflicts)
            pickup_sigs = {s for s in new_sigs if '_' in s}  # all are pickup style already
            if any(sig in used_signatures for sig in pickup_sigs):
                # Remove this exact block from its map to prevent reselection
                removed_from = None
                if blockmap_parent1:
                    for k, v in list(blockmap_parent1.items()):
                        if v is best_block:
                            blockmap_parent1.pop(k, None)
                            removed_from = 'P1'
                            break
                if removed_from is None and blockmap_parent2:
                    for k, v in list(blockmap_parent2.items()):
                        if v is best_block:
                            blockmap_parent2.pop(k, None)
                            removed_from = 'P2'
                            break
                if DEBUG:
                    print(f"[new_crossver2] Iter {iteration} | skip duplicate-signature block {found_key}", file=sys.stderr)
                stagnation += 1
                continue

            gain = len(pickup_sigs - used_signatures)
            if DEBUG:
                print(
                    f"[new_crossver2] Iter {iteration} | chosen_block_key={found_key} | block_len={len(best_block)} | "
                    f"new_pick_sig_gain={gain}",
                    file=sys.stderr
                )
            if gain < MIN_GAIN_PER_BLOCK:
                stagnation += 1
            else:
                stagnation = 0

            bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(
                best_block,
                parent1.id_to_vehicle,
                child_vehicleid_to_plan,
                parent1.route_map
            )
            if bestInsertVehicle is None:
                last_stop_reason = 'no-insertion-position'
                if DEBUG:
                    print(f"[new_crossver2] Iter {iteration} | insertion failed -> stopping", file=sys.stderr)
                break
            target_route = child_vehicleid_to_plan[bestInsertVehicle]
            target_route[bestInsertPos: bestInsertPos] = best_block
            target_vehicle = parent1.id_to_vehicle[bestInsertVehicle]

            # Validate only the modified vehicle route for LIFO + uniqueness
            if not isFeasible(target_route , target_vehicle.carrying_items , target_vehicle.board_capacity):
                # Rollback insertion
                del target_route[bestInsertPos: bestInsertPos + len(best_block)]
                # Remove this block from future consideration
                removed_from = None
                if blockmap_parent1:
                    for k, v in list(blockmap_parent1.items()):
                        if v is best_block:
                            blockmap_parent1.pop(k, None)
                            removed_from = 'P1'
                            break
                if removed_from is None and blockmap_parent2:
                    for k, v in list(blockmap_parent2.items()):
                        if v is best_block:
                            blockmap_parent2.pop(k, None)
                if DEBUG:
                    print(f"[new_crossver2] Iter {iteration} | rollback block {found_key} (violates LIFO/dup)", file=sys.stderr)
                stagnation += 1
                continue

            # Update coverage after successful insertion
            used_signatures.update(pickup_sigs)
            if DEBUG:
                print(
                    f"[new_crossver2] Iter {iteration} | inserted at vehicle={bestInsertVehicle} pos={bestInsertPos} | "
                    f"coverage={len(used_signatures)}/{total_blocks_target}",
                    file=sys.stderr
                )

            prev_block = best_block
            iteration += 1
        except Exception as e:
            last_stop_reason = 'exception'
            if DEBUG:
                print(f"[new_crossver2] Iter {iteration} | EXCEPTION: {e}", file=sys.stderr)
            import traceback
            if DEBUG:
                traceback.print_exc(file=sys.stderr)
            break
        #print(time.time() - begin)
    
    
    if DEBUG:
        print(
            f"[new_crossver2] END | iterations={iteration} | coverage={len(used_signatures)}/{total_blocks_target} | "
            f"used_signatures={len(used_signatures)} | final_reason={last_stop_reason}",
            file=sys.stderr
        )
    
    # kiểm tra lại lời giải con và xử lý các node thừa hoặc thiếu
    for vehicleID in parent1.id_to_vehicle.keys():
        redundant = []
        del_index = []
        # Duyệt ngược danh sách để tìm và xóa nút thừa    
        for i in range(len(child_vehicleid_to_plan[vehicleID]) - 1, -1, -1):  
            node = child_vehicleid_to_plan[vehicleID][i]
            
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
            child_vehicleid_to_plan[vehicleID].pop(i)
    
    
    # Kiem tra lai và thêm các node còn thiếu vào con   
    for key, value in check_valid.items():
        if value == 0:
            
            # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
            node_list = new_PDG_map[key]
            
            if node_list:
                bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(node_list, parent1.id_to_vehicle, child_vehicleid_to_plan, parent1.route_map)
            
            if bestInsertVehicle is None:
                last_stop_reason = 'no-insertion-position'
                print(f"[new_crossver2] reinsert abandon block | insertion failed -> stopping", file=sys.stderr)
                break
            target_route = child_vehicleid_to_plan[bestInsertVehicle]
            target_route[bestInsertPos: bestInsertPos] = node_list
    
    #print (time.time() - begin)
    return Chromosome(child_vehicleid_to_plan , parent1.route_map , parent1.id_to_vehicle)


def fix_duppication_nodes (inidividual : Chromosome , PDG_map: Dict[str , List[Node]] ):
    # Cac super node
    new_PDG_map : Dict[str , List[Node]] = {}
    for key , value in PDG_map.items():
        if len(value )!= 2: print("ERROR 1 _ fix ")
        first_node = value[0]
        if first_node.pickup_item_list and first_node.delivery_item_list:
            print ("ERROR 2 _ fix")
        if first_node.pickup_item_list:
            key = f'{len(first_node.pickup_item_list)}_{first_node.pickup_item_list[0].id}'
        elif first_node.delivery_item_list:
            key = f'{len(first_node.delivery_item_list)}_{first_node.delivery_item_list[-1].id}'
        
        
        new_PDG_map[key] = value
        
    check_valid : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    
    for vID, plan in inidividual.solution.items():
        veh = inidividual.id_to_vehicle[vID]
        carry = veh.carrying_items
        if plan:
            if isFeasible(plan ,carry ,veh.board_capacity) == False:
                print("Solution trien vao bi loi !!!!")
    
    # kiểm tra lại lời giải con và xử lý các node thừa hoặc thiếu
    for vehicleID in inidividual.id_to_vehicle.keys():
        redundant = []
        del_index = []
        # Duyệt ngược danh sách để tìm và xóa nút thừa    
        for i in range(len(inidividual.solution[vehicleID]) - 1, -1, -1):  
            node = inidividual.solution[vehicleID][i]
            
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
            inidividual.solution[vehicleID].pop(i)
    
    
    # Kiem tra lai và thêm các node còn thiếu vào con   
    for key, value in check_valid.items():
        if value == 0:
            
            # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
            node_list = new_PDG_map[key]
            
            if node_list:
                bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(node_list, inidividual.id_to_vehicle, inidividual.solution, inidividual.route_map)
                
            if bestInsertVehicle is None:
                last_stop_reason = 'no-insertion-position'
                print(f"[new_crossver2] reinsert abandon block | insertion failed -> stopping", file=sys.stderr)
                break
            target_route = inidividual.solution[bestInsertVehicle]
            target_route[bestInsertPos: bestInsertPos] = node_list


def fix_duppication_nodes2 (inidividual : Chromosome ,   PDG_map: Dict[str , List[Node]] , Base_vehicleid_to_plan: Dict[str, List[Node]] , root_vehicleid_to_plan: Dict[str, List[Node]] ):
    # Cac super node
    new_PDG_map : Dict[str , List[Node]] = {}
    for key , value in PDG_map.items():
        if len(value)!= 2: print("ERROR 1 _ fix ")
        first_node = value[0]
        if first_node.pickup_item_list and first_node.delivery_item_list:
            print ("ERROR 2 _ fix")
        
        if first_node.pickup_item_list:
            key = f'{len(first_node.pickup_item_list)}_{first_node.pickup_item_list[0].id}'
        elif first_node.delivery_item_list:
            key = f'{len(first_node.delivery_item_list)}_{first_node.delivery_item_list[-1].id}'
            print("ERROR 3_Node delivery dat truoc")
        
        new_PDG_map[key] = value
    
    check_valid : Dict[str , int]= {key : 0 for key in new_PDG_map.keys()}
    
    for vID, plan in inidividual.solution.items():
        veh = inidividual.id_to_vehicle[vID]
        carry = veh.carrying_items
        if plan:
            if isFeasible(plan ,carry ,veh.board_capacity) == False:
                print("ERROR 4_Solution trien vao bi loi !!!!")
                
    temp = 0
    for vid, plan in inidividual.solution.items():
        temp += len(plan)
    
    
    for vid, plan in root_vehicleid_to_plan.items():
        temp -= len(plan)
        
    
    if temp == 0:
        return True
    else:
        
        # kiểm tra lại lời giải con và xử lý các node thừa hoặc thiếu
        for vehicleID in inidividual.id_to_vehicle.keys():
            redundant = []
            del_index = []
            # Duyệt ngược danh sách để tìm và xóa nút thừa    
            for i in range(len(inidividual.solution[vehicleID]) - 1, -1, -1):  
                node = inidividual.solution[vehicleID][i]
                
                if node.pickup_item_list and node.delivery_item_list:
                    if redundant and node.pickup_item_list[0].id == redundant[-1]:
                        redundant.pop()  # Loại bỏ phần tử tương ứng trong danh sách `redundant`
                        del_index.append(i)
                elif node.delivery_item_list and node.pickup_item_list:
                    key = f'{len(node.delivery_item_list)}_{node.delivery_item_list[-1].id}'
                    
                    if key in new_PDG_map:
                        check_valid[key] += 1
                        
                        # nếu tìm được một super node thừa
                        if check_valid[key] > 1:
                            first_itemID_of_redundant_supernode = key.split('_')[-1]
                            redundant.append(first_itemID_of_redundant_supernode)
                            # Xóa node giao của super node thừa
                            del_index.append(i)
                            #print('Đã xóa 1 super node thừa' , file= sys.stderr)
            for i in del_index:
                inidividual.solution[vehicleID].pop(i)
        
        
        # Kiem tra lai và thêm các node còn thiếu vào con   
        for key, value in check_valid.items():
            if value == 0:
                # truong hop bi thieu 1 super node thi gan theo chien luoc CI vao solution hien tai
                node_list = new_PDG_map[key]
                
                if node_list:
                    bestInsertPos, bestInsertVehicle = cheapest_insertion_for_block(node_list, inidividual.id_to_vehicle, inidividual.solution, inidividual.route_map)
                    
                if bestInsertVehicle is None:
                    print(f"[fix error] reinsert abandon block | insertion failed -> stopping")
                    continue
                target_route = inidividual.solution[bestInsertVehicle]
                target_route[bestInsertPos: bestInsertPos] = node_list

        return False
    
    

def decrease_node_num(vehicleid_to_plan: Dict[str , List[Node]], id_to_vehicle: Dict[str , Vehicle] , route_map: Dict[tuple , tuple] , num_nodes = 0):
    
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

    num_pairs_to_relocate = max(1, int(len(pdg_Map) - (num_nodes )))
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
    
    #print(time.time() - begin)
    return new_vehicle_to_plan


def gold_algorithm_LS(indivisual : Chromosome , is_limited = False):
    n1 , n2 , n3 , n4, n5 = 0 ,0 ,0 ,0 ,0

    # Keep best snapshot to ensure final committed solution reflects best improvements
    def _copy_solution(sol: Dict[str, List[Node]]) -> Dict[str, List[Node]]:
        return {vid: route[:] for vid, route in sol.items()}
    best_cost = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
    best_snapshot = _copy_solution(indivisual.solution)

    while True:
        if config.is_timeout():
            break
        
        begin = time.time()
        if new_inter_couple_exchange(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , math.inf , is_limited):
            n1 +=1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue
        print(time.time() - begin)
        
        if config.is_timeout():
            break
        
        begin = time.time()
        if new_block_exchange(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map, math.inf , is_limited):
            n2 +=1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue
        print(time.time() - begin)

        if config.is_timeout():
            break

        begin  = time.time()
        if new_block_relocate(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map, math.inf , is_limited):
            n3 +=1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            continue
        print(time.time() - begin)
        

        if config.is_timeout():
            break

        begin  = time.time()
        
        if new_multi_pd_group_relocate(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map, math.inf , is_limited):
            n4 +=1
            cur = total_cost(indivisual.id_to_vehicle, indivisual.route_map, indivisual.solution)
            if cur < best_cost:
                best_cost = cur
                best_snapshot = _copy_solution(indivisual.solution)
            if config.is_timeout():
                break
            print(time.time() - begin)
        break
        """ else:
            print(f"PDPairExchange:{n1}; BlockExchange:{n2}; BlockRelocate:{n3}; mPDG:{n4}; cost:{total_cost(indivisual.id_to_vehicle , indivisual.route_map , indivisual.solution ):.2f}"  )
            n1 , n2 , n3 , n4, n5 = 0 ,0 ,0 ,0 ,0
            if not improve_ci_path_by_2_opt(indivisual.solution , indivisual.id_to_vehicle , indivisual.route_map , is_limited):
                indivisual.solution = best_snapshot
                break """

    # Ensure best snapshot is committed upon exit
    indivisual.solution = best_snapshot
    print(f"PDPairExchange:{n1}; BlockExchange:{n2}; BlockRelocate:{n3}; mPDG:{n4}; cost:{total_cost(indivisual.id_to_vehicle , indivisual.route_map , indivisual.solution ):.2f}"  )

def Delaydispatch(id_to_vehicle: Dict[str , Vehicle], vehicleid_to_plan: Dict[str, list[Node]] , route_map: Dict[tuple , tuple]):
    vehicle_num = len(id_to_vehicle)
    slack_time = 0
    emergency_index = [-1] * vehicle_num
    dock_table : Dict[str , List[List[int]]]= {} 
    n = 0 # Đếm số xe có tuyến đường hoạch định
    curr_node = [0] * vehicle_num  # Node hiện tại trong bối cảnh của hàm
    curr_time = [0] * vehicle_num # Thời gian trong bối cảnh của hàm
    n_node = [0] * vehicle_num # số node trong tuyến đường hoạch định của xe
    index = 0 # Đếm số xe

    # Xét từng xe
    for vehicle_id, vehicle in id_to_vehicle.items():
        planned_route = vehicleid_to_plan.get(vehicle_id , [])
        
        # Nếu có tuyến đường được hoạch định
        if planned_route and len(planned_route) > 0:
            curr_node[index] = 0
            n_node[index] = len(planned_route)

            # Nếu phương tiện chưa có đích đến <-> xe đang đỗ
            if vehicle.des is None:
                if vehicle.cur_factory_id == planned_route[0].id:
                    curr_time[index] = vehicle.gps_update_time
                else:
                    dis_and_time = route_map.get((vehicle.cur_factory_id , planned_route[0].id))
                    if dis_and_time is None:
                        print(f"No distance found for route", file = sys.stderr)
                    else:
                        curr_time[index] = vehicle.gps_update_time + int(dis_and_time[1])
            # Xe đang di chuyển
            else:
                if vehicle.cur_factory_id and len(vehicle.cur_factory_id) > 0:
                    if vehicle.cur_factory_id != planned_route[0].id:
                        curr_time[index] = vehicle.leave_time_at_current_factory
                        dis_and_time = route_map.get((vehicle.cur_factory_id , planned_route[0].id))
                        if dis_and_time:
                            curr_time[index] += int(dis_and_time[1])
                    else:
                        curr_time[index] = vehicle.leave_time_at_current_factory
                else:
                    curr_time[index] = vehicle.des.arrive_time
            
            n += 1
        else:
            curr_node[index] = math.inf
            curr_time[index] = math.inf
            n_node[index] = 0
        index += 1
    
    flag = False
    # Xét tất cả các xe có tuyến đường được hoạch định
    while n > 0:
        min_t = math.inf
        min_t2_vehicle_index = 0
        t_true = min_t
        idx = 0

        # Tìm xe có thời gian (đến node gần nhất) nhỏ nhất
        for i in range(vehicle_num):
            if curr_time[i] < min_t:
                min_t = curr_time[i]
                min_t2_vehicle_index = i

        # Mã của xe có thời gian nhỏ nhất
        min_t2_vehicle_id = f"V_{min_t2_vehicle_index + 1}"
        # Tuyến đường được hoạch định của xe
        min_t_node_list = vehicleid_to_plan.get(min_t2_vehicle_id)
        min_t_node = min_t_node_list[curr_node[min_t2_vehicle_index]]

        if min_t_node.delivery_item_list:
            for order_item in min_t_node.delivery_item_list:
                commit_complete_time = order_item.committed_completion_time
                slack_time = commit_complete_time - min_t
                if slack_time < SLACK_TIME_THRESHOLD:
                    emergency_index[min_t2_vehicle_index] = curr_node[min_t2_vehicle_index]
                    break

        used_end_time = []
        time_slots : List[List[int]]= dock_table.get(min_t_node.id, [])

        if time_slots:
            i = 0
            while i < len(time_slots):
                timeslot = time_slots[i]
                if timeslot[1] <= min_t:
                    del time_slots[i]
                    i -=1 
                elif timeslot[0] <= min_t and min_t < timeslot[1]:
                    used_end_time.append(timeslot[1])
                else:
                    print("------------ timeslot.start>minT--------------", file = sys.stderr)
                i += 1

        if len(used_end_time) < 6:
            t_true = min_t
        else:
            flag = True
            idx = len(used_end_time) - 6
            used_end_time = sorted(used_end_time)
            t_true = used_end_time[idx]

        service_time = min_t_node_list[curr_node[min_t2_vehicle_index]].service_time
        cur_factory_id = min_t_node_list[curr_node[min_t2_vehicle_index]].id
        curr_node[min_t2_vehicle_index] += 1

        while ((curr_node[min_t2_vehicle_index] < n_node[min_t2_vehicle_index]) and ( cur_factory_id == min_t_node_list[curr_node[min_t2_vehicle_index]].id)):

            if min_t_node_list[curr_node[min_t2_vehicle_index]].delivery_item_list:
                for order_item in min_t_node_list[curr_node[min_t2_vehicle_index]].delivery_item_list:
                    commit_complete_time = order_item.committed_completion_time
                    slack_time = commit_complete_time - min_t
                    if slack_time < SLACK_TIME_THRESHOLD:
                        emergency_index[min_t2_vehicle_index] = curr_node[min_t2_vehicle_index]
                        break

            service_time += min_t_node_list[curr_node[min_t2_vehicle_index]].service_time
            curr_node[min_t2_vehicle_index] += 1

        if curr_node[min_t2_vehicle_index] >= n_node[min_t2_vehicle_index]:
            n -= 1
            curr_node[min_t2_vehicle_index] = float('inf')
            curr_time[min_t2_vehicle_index] = float('inf')
            n_node[min_t2_vehicle_index] = 0
        else:
            dis_and_time = route_map.get((cur_factory_id , min_t_node_list[curr_node[min_t2_vehicle_index]].id))
            time = int(dis_and_time[1])
            curr_time[min_t2_vehicle_index] = t_true + APPROACHING_DOCK_TIME + service_time + time


        tw = [min_t, t_true + APPROACHING_DOCK_TIME + service_time]
        twList = dock_table.get(min_t_node.id , [])
        twList.append(tw)
        dock_table[min_t_node.id] = twList
    
    idx = 0
    for vehicleID , node_list in vehicleid_to_plan.items():
        vehicle = id_to_vehicle.get(vehicleID)
        
        if node_list and (emergency_index[idx] > -1 or vehicle.carrying_items or vehicle.des):
            delivery_item_list : List[OrderItem] = []
            carrying_items_list = vehicle.carrying_items
            if carrying_items_list:
                i = len(carrying_items_list) - 1
                while i >= 0:
                    delivery_item_list.append(carrying_items_list[i])
                    i -=1
            
            for k in range(len(node_list)):
                if emergency_index[idx] <= -1:
                    break
                
                node = node_list[k]
                delivery_items = node.delivery_item_list
                pickup_items = node.pickup_item_list
                
                if delivery_items and k <= emergency_index[idx]:
                    for order_item in delivery_items:
                        if (not delivery_item_list) or len(delivery_item_list) == 0 or delivery_item_list[0].id != order_item.id:
                            print("violate FILO _ DelayDispatch", file=sys.stderr)
                        delivery_item_list.pop(0)
                
                if pickup_items and k <= emergency_index[idx]:
                    for order_item in pickup_items:
                        delivery_item_list.insert(0, order_item)

            is_des_empty = True
            if vehicle.des and len(delivery_item_list) == 0:
                is_des_empty = False

            e = emergency_index[idx]
            if delivery_item_list or (not is_des_empty):
                for i in range(e + 1, len(node_list)):
                    node = node_list[i]
                    
                    if node.delivery_item_list:
                        for order_item in node.delivery_item_list:
                            if order_item in delivery_item_list:
                                delivery_item_list.remove(order_item)

                    if node.pickup_item_list:
                        for order_item in node.pickup_item_list:
                            delivery_item_list.insert(0, order_item)

                    emergency_index[idx] = i
        idx += 1
    return emergency_index


def write_destination_json_to_file_with_delay_timme(vehicleid_to_destination : Dict[str , Node] , emergency_index: List[int] , id_to_vehicle: Dict[str , Vehicle] , input_directory: str):
    result_json = {}
    
    for index , (vehicleID , des) in enumerate(vehicleid_to_destination.items()):
        current_node = None
        if emergency_index[index] > -1 or id_to_vehicle.get(vehicleID).des:
            if des:
                pickup_items = []
                delivery_items = []
                current_node ={}
                
                if des.pickup_item_list and len(des.pickup_item_list) > 0:
                    for orderitem in des.pickup_item_list:
                        pickup_items.append(orderitem.id)
                        
                if des.delivery_item_list and len(des.delivery_item_list) > 0:
                    for orderitem in des.delivery_item_list:
                        delivery_items.append(orderitem.id)
                
                current_node = {
                    "factory_id": des.id,
                    "lng": des.lng,
                    "lat": des.lat,
                    "delivery_item_list": delivery_items,
                    "pickup_item_list": pickup_items,
                    "arrive_time": des.arrive_time,
                    "leave_time": des.leave_time
                }
        result_json[vehicleID] = current_node
    
      # Đảm bảo input_directory hợp lệ
    if not os.path.isdir(input_directory):
        try:
            os.makedirs(input_directory, exist_ok=True)
        except OSError as e:
            print(f"Lỗi khi tạo thư mục: {e}", file = sys.stderr)
            return  # Tránh tiếp tục nếu có lỗi

    output_file = os.path.join(input_directory, "output_destination.json")

    # Ghi dữ liệu ra file JSON với kiểm soát lỗi
    try:
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(result_json, file, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Lỗi khi ghi file JSON: {e}", file = sys.stderr)
    


def write_route_json_to_file_with_delay_time(vehicleid_to_plan: Dict[str, list[Node]] ,  emergency_index: List[int] , id_to_vehicle: Dict[str , Vehicle] , input_directory: str):
    result_json = {}
    
    for index , (vehicleID , nodelist) in enumerate(vehicleid_to_plan.items()):
        vehicle_items = []
        
        if emergency_index[index] > -1:
            if nodelist:
                for i in range(0 ,emergency_index[index]):
                    node  = nodelist[i]
                    pickup_items = []
                    delivery_items = []
                    current_node ={}
                    
                    if node.pickup_item_list and len(node.pickup_item_list) > 0:
                        for orderitem in node.pickup_item_list:
                            pickup_items.append(orderitem.id)
                            
                    if node.delivery_item_list and len(node.delivery_item_list) > 0:
                        for orderitem in node.delivery_item_list:
                            delivery_items.append(orderitem.id)
                    
                    current_node = {
                        "factory_id": node.id,
                        "lng": node.lng,
                        "lat": node.lat,
                        "delivery_item_list": delivery_items,
                        "pickup_item_list": pickup_items,
                        "arrive_time": node.arrive_time,
                        "leave_time": node.leave_time
                    }
                    vehicle_items.append(current_node)
        result_json[vehicleID] = vehicle_items
        
    # Đảm bảo thư mục đầu ra hợp lệ
    if not os.path.isdir(input_directory):
        try:
            os.makedirs(input_directory, exist_ok=True)
        except OSError as e:
            print(f"Lỗi khi tạo thư mục: {e}", file = sys.stderr)
            return  # Tránh tiếp tục nếu có lỗi

    output_file = os.path.join(input_directory, "output_route.json")

    # Ghi dữ liệu ra file JSON với kiểm soát lỗi
    try:
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(result_json, file, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Lỗi khi ghi file JSON: {e}", file = sys.stderr)


