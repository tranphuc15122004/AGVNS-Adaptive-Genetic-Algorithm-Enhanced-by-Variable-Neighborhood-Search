#!/usr/bin/env python3
"""
extract_executed_routes_from_summary.py
========================================
Extracts actual executed vehicle routes from an existing epoch_summary.json
(produced by VisualizationRecorder) and outputs an executed_routes.json file
compatible with build_executed_route_viz.py.

This allows visualizing executed routes from previously-run simulations
without needing to re-run with ExecutedRouteRecorder enabled.

How it works:
  1. Iterates ALL epochs for each vehicle
  2. Collects trajectory nodes with status="past" (completed)
  3. Deduplicates by (vehicle_id, factory_id, arrive_time)
  4. Matches pickup/delivery events to each node by factory_id + time proximity
  5. Computes carrying_after via LIFO replay
  6. Outputs executed_routes.json

Usage:
    python extract_executed_routes_from_summary.py <epoch_summary.json> [output.json]
    
    python extract_executed_routes_from_summary.py visualization_output/instance_10/epoch_summary.json
"""

import datetime
import json
import os
import sys


def fmt_ts(ts: int) -> str:
    if ts <= 0:
        return '--:--'
    return datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')


def extract_executed_routes(summary: dict) -> dict:
    """
    Extract executed routes from epoch summary.
    
    Returns dict compatible with ExecutedRouteRecorder.save() output.
    """
    epochs = summary.get('epochs', [])
    factory_data = summary.get('factory_data', [])
    
    if not epochs:
        print("WARNING: No epochs found in summary.")
        return None
    
    # ── Collect all vehicles across all epochs ──
    all_vehicle_ids = set()
    for ep in epochs:
        for v in ep.get('vehicles', []):
            all_vehicle_ids.add(v['id'])
    
    print(f"  Vehicles: {len(all_vehicle_ids)}")
    print(f"  Epochs: {len(epochs)}")
    
    # ── STEP 1: Collect past trajectory nodes from ALL epochs ──
    vehicle_nodes_raw = {vid: [] for vid in all_vehicle_ids}
    recorded = set()  # (vid, fid, arrive_time)
    
    for ep in epochs:
        for v in ep.get('vehicles', []):
            vid = v['id']
            for node in v.get('trajectory', []):
                if node.get('status') != 'past':
                    continue
                fid = node.get('factory_id', '')
                arr = node.get('arrive_time', 0)
                lv = node.get('leave_time', 0)
                if arr <= 0:
                    continue
                dedup_key = (vid, fid, arr)
                if dedup_key in recorded:
                    continue
                recorded.add(dedup_key)
                vehicle_nodes_raw[vid].append({
                    'factory_id': fid, 'arrive_time': arr, 'leave_time': lv,
                    'service_time': max(0, lv - arr) if lv > arr else 0,
                    'delivery_items': [], 'pickup_items': [],
                })
    
    # ── STEP 2: Capture final uncompleted nodes from the LAST epoch ──
    # simulate_the_left_ongoing_orders_of_vehicles() runs AFTER the last
    # VisualizationRecorder snapshot. Its nodes are never marked "past".
    # We capture them from planned_route_nodes in the last epoch.
    last_epoch = epochs[-1]
    for v in last_epoch.get('vehicles', []):
        vid = v['id']
        for pn in v.get('planned_route_nodes', []):
            fid = pn.get('factory_id', '')
            arr = pn.get('arrive_time', 0)
            lv = pn.get('leave_time', 0)
            if arr <= 0:
                continue
            # Check if this node was already recorded (by proximity)
            already = False
            for existing in vehicle_nodes_raw.get(vid, []):
                if existing['factory_id'] == fid and abs(existing['arrive_time'] - arr) <= 10:
                    already = True
                    break
            if already:
                continue
            dedup_key = (vid, fid, arr)
            if dedup_key in recorded:
                continue
            recorded.add(dedup_key)
            vehicle_nodes_raw[vid].append({
                'factory_id': fid,
                'arrive_time': arr,
                'leave_time': lv if lv > 0 else arr + 60,
                'service_time': max(0, lv - arr) if lv > arr else 60,
                'delivery_items': [], 'pickup_items': [],
            })
    
    # ── STEP 3: Collect DEDUPLICATED events from all epochs ──
    # Events are recorded EVERY epoch for ALL future nodes in planned_route,
    # causing 10-15x duplication. We deduplicate by (item_id, type, factory_id):
    # each item is picked up ONCE and delivered ONCE at a specific factory.
    vehicle_events = {vid: [] for vid in all_vehicle_ids}
    event_dedup = set()  # (vehicle_id, item_id, type, factory_id)
    
    for ep in epochs:
        for v in ep.get('vehicles', []):
            vid = v['id']
            for ev in v.get('events', []):
                dedup_key = (vid, ev.get('item_id', ''), ev.get('type', ''),
                             ev.get('factory_id', ''))
                if dedup_key in event_dedup:
                    continue
                event_dedup.add(dedup_key)
                vehicle_events[vid].append({
                    'type': ev.get('type', ''),
                    'item_id': ev.get('item_id', ''),
                    'item_type': ev.get('item_type', ''),
                    'factory_id': ev.get('factory_id', ''),
                    'time': ev.get('time', 0),
                })
    
    # ── Sort nodes by arrive_time ──
    for vid in vehicle_nodes_raw:
        vehicle_nodes_raw[vid].sort(key=lambda n: n['arrive_time'])
    
    # ── Match events to nodes by proximity ──
    for vid, nodes in vehicle_nodes_raw.items():
        events = vehicle_events.get(vid, [])
        # Index events by (factory_id, time)
        for node in nodes:
            fid = node['factory_id']
            node_arr = node['arrive_time']
            node_lv = node['leave_time']
            
            # Find events at this factory within the node's time window
            for ev in events:
                if ev['factory_id'] != fid:
                    continue
                ev_time = ev['time']
                # Event should be close to node's arrive time
                if abs(ev_time - node_arr) <= 5 or (node_arr <= ev_time <= node_lv):
                    if ev['type'] == 'delivery':
                        node['delivery_items'].append({
                            'item_id': ev['item_id'],
                            'order_id': ev['item_id'].rsplit('_', 1)[0] if '_' in ev['item_id'] else '',
                            'type': ev.get('item_type', ''),
                            'demand': 0,
                        })
                    elif ev['type'] == 'pickup':
                        node['pickup_items'].append({
                            'item_id': ev['item_id'],
                            'order_id': ev['item_id'].rsplit('_', 1)[0] if '_' in ev['item_id'] else '',
                            'type': ev.get('item_type', ''),
                            'demand': 0,
                        })
    
    # ── Compute carrying_after via LIFO replay ──
    for vid, nodes in vehicle_nodes_raw.items():
        carrying = []  # bottom-to-top (loading order)
        for node in nodes:
            for _ in node.get("delivery_items", []):
                if carrying:
                    carrying.pop()
            for item in node.get("pickup_items", []):
                carrying.append(item["item_id"])
            node["carrying_after"] = list(carrying)
    
    # ── STEP 5b: Fill in missing final deliveries ──
    # Items picked up but not yet delivered, yet marked "completed",
    # were delivered by the final route (simulate_the_left_ongoing_orders).
    # We create a synthetic "cleanup node" at the end of each vehicle's route.
    last_epoch = epochs[-1]
    completed_items_lookup = {}
    for item in last_epoch.get("order_items", {}).get("completed", []):
        completed_items_lookup[item["id"]] = item
    
    for vid, nodes in vehicle_nodes_raw.items():
        if not nodes:
            continue
        
        # Collect all item_ids picked up and delivered by this vehicle
        picked_by_vehicle = set()
        delivered_by_vehicle = set()
        for node in nodes:
            for d in node.get("delivery_items", []):
                delivered_by_vehicle.add(d["item_id"])
            for p in node.get("pickup_items", []):
                picked_by_vehicle.add(p["item_id"])
        
        # Items picked up but not delivered, yet marked completed
        undelivered = picked_by_vehicle - delivered_by_vehicle
        
        # ALSO: items still in carrying_after at last node (initial items + pickups)
        last_carrying = set(nodes[-1].get("carrying_after", []))
        undelivered |= (last_carrying - delivered_by_vehicle)
        missing_items = []
        for item_id in undelivered:
            citem = completed_items_lookup.get(item_id)
            if citem and citem.get("delivery_state", 0) >= 3:
                missing_items.append({
                    "item_id": item_id,
                    "order_id": citem.get("order_id", item_id.rsplit("-", 1)[0] if "-" in item_id else ""),
                    "type": citem.get("type", ""),
                    "demand": citem.get("demand", 0),
                    "delivery_factory_id": citem.get("delivery_factory_id", ""),
                })
        
        if not missing_items:
            continue
        
        # Group by delivery factory and create final cleanup nodes
        base_time = nodes[-1].get("leave_time", nodes[-1].get("arrive_time", 0)) + 60
        by_factory = {}
        for item in missing_items:
            dfid = item["delivery_factory_id"]
            if dfid not in by_factory:
                by_factory[dfid] = []
            by_factory[dfid].append(item)
        
        for dfid, items in by_factory.items():
            new_node = {
                "factory_id": dfid,
                "arrive_time": base_time,
                "leave_time": base_time + 300,
                "service_time": 300,
                "delivery_items": [{k: v for k, v in item.items() if k != "delivery_factory_id"} for item in items],
                "pickup_items": [],
            }
            nodes.append(new_node)
            base_time += 360  # spacing between final nodes
    
    # Re-sort vehicles' nodes after adding final deliveries
    for vid in vehicle_nodes_raw:
        vehicle_nodes_raw[vid].sort(key=lambda n: n["arrive_time"])
    
    # Re-sort vehicles' nodes after adding final deliveries
    for vid in vehicle_nodes_raw:
        vehicle_nodes_raw[vid].sort(key=lambda n: n["arrive_time"])
    
    # Re-compute carrying_after after adding missing deliveries
    for vid, nodes in vehicle_nodes_raw.items():
        carrying = []
        for node in nodes:
            for _ in node.get("delivery_items", []):
                if carrying:
                    carrying.pop()
            for item in node.get("pickup_items", []):
                carrying.append(item["item_id"])
            node["carrying_after"] = list(carrying)
    
    # ── Build output ──
    vehicles_output = {}
    total_nodes = 0
    for vid in sorted(vehicle_nodes_raw.keys()):
        nodes = vehicle_nodes_raw[vid]
        vehicles_output[vid] = {
            'executed_nodes': nodes,
            'total_nodes': len(nodes),
        }
        total_nodes += len(nodes)
    
    output = {
        'instance': os.path.basename(os.path.dirname(os.path.abspath(sys.argv[1]))) if len(sys.argv) > 1 else 'unknown',
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_executed_nodes': total_nodes,
        'vehicle_count': len(vehicle_nodes_raw),
        'factory_data': factory_data,
        'vehicles': vehicles_output,
    }
    
    # ── Log stats ──
    vehicles_with_routes = sum(1 for v in vehicles_output.values() if v['total_nodes'] > 0)
    print(f"  Vehicles with executed routes: {vehicles_with_routes}/{len(vehicle_nodes_raw)}")
    print(f"  Total executed nodes: {total_nodes}")
    
    return output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("ERROR: Please provide path to epoch_summary.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    
    # Output path
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_dir = os.path.dirname(input_path)
        output_path = os.path.join(output_dir, 'executed_routes.json')
    
    print(f"Loading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    print(f"  Epochs: {summary.get('total_epochs', '?')}")
    print(f"  Factories: {summary.get('factory_count', '?')}")
    
    print("Extracting executed routes...")
    output = extract_executed_routes(summary)
    
    if output is None:
        print("ERROR: Could not extract routes.")
        sys.exit(1)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Saved: {output_path}")
    print(f"  Size: {os.path.getsize(output_path):,} bytes")


if __name__ == '__main__':
    main()
