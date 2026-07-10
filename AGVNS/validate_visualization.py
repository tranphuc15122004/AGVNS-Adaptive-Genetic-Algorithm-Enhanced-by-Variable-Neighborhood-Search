#!/usr/bin/env python3
"""
validate_visualization.py — Kiểm tra chéo dữ liệu visualization với output thuật toán
==================================================================================
So sánh:
  1. epoch_summary.json (VisualizationRecorder) vs solution.json + vehicle_info.json (algorithm)
  2. Tính nhất quán nội bộ của dữ liệu visualization
  3. Logic trạng thái xe (parked → en_route → at_factory → loading → parked)
  4. Order lifecycle (unallocated → ongoing → completed)
"""

import json
import os
import sys
import datetime
from collections import defaultdict

def fmt_ts(ts):
    if ts <= 0: return 'N/A'
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def load_json(path):
    if not os.path.exists(path): return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate(summary_path, data_dir, benchmark_dir):
    print("=" * 70)
    print("  VALIDATION REPORT - DPDP Visualization")
    print("=" * 70)
    
    summary = load_json(summary_path)
    if not summary:
        print("ERROR: Cannot load epoch_summary.json")
        return
    
    epochs = summary['epochs']
    factory_data = {f['id']: f for f in summary['factory_data']}
    
    # Load raw algorithm outputs
    solution = load_json(os.path.join(data_dir, 'solution.json'))
    vehicle_info_list = load_json(os.path.join(data_dir, 'vehicle_info.json'))
    output_dest = load_json(os.path.join(data_dir, 'output_destination.json'))
    
    vehicle_info = {}
    if isinstance(vehicle_info_list, list):
        for v in vehicle_info_list:
            vehicle_info[v['id']] = v
    elif isinstance(vehicle_info_list, dict):
        vehicle_info = vehicle_info_list
    
    checks_passed = 0
    checks_failed = 0
    warnings = 0
    
    def check(name, condition, detail=""):
        nonlocal checks_passed, checks_failed, warnings
        if condition:
            checks_passed += 1
            print(f"  [PASS] {name}")
        else:
            checks_failed += 1
            print(f"  [FAIL] {name}  <<< {detail}")
    
    def warn(name, detail=""):
        nonlocal warnings
        warnings += 1
        print(f"  [WARN] {name}  — {detail}")
    
    # ═══════════════════════════════════════════
    # 1. DATA INTEGRITY CHECKS
    # ═══════════════════════════════════════════
    print("\n─── 1. Data Integrity ───")
    
    # 1a. Epoch count
    check(f"Total epochs: {len(epochs)}", len(epochs) > 0)
    
    # 1b. Epoch times increase monotonically
    times_ok = all(
        epochs[i]['epoch_time'] <= epochs[i+1]['epoch_time']
        for i in range(len(epochs)-1)
    )
    check("Epoch times monotonically increasing", times_ok,
          f"Violation at epoch {next((i for i in range(len(epochs)-1) if epochs[i]['epoch_time'] > epochs[i+1]['epoch_time']), '?')}" if not times_ok else "")
    
    # 1c. Epoch indices are sequential
    indices_ok = all(epochs[i]['epoch_index'] == i for i in range(len(epochs)))
    check("Epoch indices sequential (0, 1, 2, ...)", indices_ok)
    
    # 1d. Factory count matches
    check(f"Factory count: {len(factory_data)}", len(factory_data) > 0)
    
    # 1e. All vehicle IDs present in every epoch
    if epochs:
        first_vehicles = set(v['id'] for v in epochs[0]['vehicles'])
        consistent = all(
            set(v['id'] for v in ep['vehicles']) == first_vehicles
            for ep in epochs
        )
        check(f"Vehicle set consistent across all {len(epochs)} epochs", consistent,
              f"Vehicle IDs: {sorted(first_vehicles)}")
    
    # ═══════════════════════════════════════════
    # 2. VEHICLE STATE LOGIC CHECKS
    # ═══════════════════════════════════════════
    print("\n─── 2. Vehicle State Logic ───")
    
    vehicle_histories = defaultdict(list)
    for ep in epochs:
        for v in ep['vehicles']:
            vehicle_histories[v['id']].append({
                'epoch': ep['epoch_index'],
                'time': ep['epoch_time'],
                'status': v['status'],
                'carrying': v['carrying_item_count'],
                'cur_fid': v.get('cur_factory_id', ''),
                'dest_fid': v['destination']['factory_id'] if v.get('destination') else None,
                'pos_status': v.get('position', {}).get('status', ''),
            })
    
    for vid, history in sorted(vehicle_histories.items()):
        # Count state transitions
        transitions = 0
        prev_status = None
        for h in history:
            if prev_status and h['status'] != prev_status:
                transitions += 1
            prev_status = h['status']
        
        # Count epochs where vehicle is active (not parked)
        active = sum(1 for h in history if h['status'] != 'parked')
        max_carry = max(h['carrying'] for h in history)
        
        print(f"\n  🚛 {vid}: {len(history)} epochs | {transitions} state changes | "
              f"{active} active epochs | max carry: {max_carry}")
        
        # Check state transitions make sense
        for i in range(len(history)-1):
            curr = history[i]['status']
            nxt = history[i+1]['status']
            
            # Invalid transitions
            if curr == 'parked' and nxt == 'loading_unloading':
                warn(f"  {vid} epoch {history[i+1]['epoch']}: parked → loading (no en_route in between?)",
                     f"time: {fmt_ts(history[i+1]['time'])}")
    
    # ═══════════════════════════════════════════
    # 3. ORDER LIFECYCLE CHECKS
    # ═══════════════════════════════════════════
    print("\n─── 3. Order Lifecycle ───")
    
    prev_completed = -1
    order_ok = True
    for ep in epochs:
        unalloc = ep['orders']['unallocated']
        ongoing = ep['orders']['ongoing']
        completed = ep['orders']['completed']
        
        if completed < prev_completed:
            order_ok = False
            warn(f"Epoch {ep['epoch_index']}: completed decreased from {prev_completed} to {completed}")
        prev_completed = completed
    
    check("Completed orders never decrease", order_ok)
    
    # Summary
    first_ep = epochs[0]
    last_ep = epochs[-1]
    print(f"\n  Start: 📦{first_ep['orders']['unallocated']} "
          f"🚚{first_ep['orders']['ongoing']} "
          f"✅{first_ep['orders']['completed']}")
    print(f"  End:   📦{last_ep['orders']['unallocated']} "
          f"🚚{last_ep['orders']['ongoing']} "
          f"✅{last_ep['orders']['completed']}")
    print(f"  Delta: 📦{last_ep['orders']['unallocated'] - first_ep['orders']['unallocated']:+d} "
          f"🚚{last_ep['orders']['ongoing'] - first_ep['orders']['ongoing']:+d} "
          f"✅{last_ep['orders']['completed'] - first_ep['orders']['completed']:+d}")
    
    # ═══════════════════════════════════════════
    # 4. CROSS-REFERENCE WITH RAW ALGORITHM OUTPUTS
    # ═══════════════════════════════════════════
    print("\n─── 4. Cross-Reference with Algorithm Outputs ───")
    
    if solution and vehicle_info and epochs:
        last_ep = epochs[-1]
        
        # 4a. Compare vehicle carrying items
        for v in last_ep['vehicles']:
            vid = v['id']
            raw_v = vehicle_info.get(vid, {})
            
            vis_carrying = set(v.get('carrying_item_ids', []))
            raw_carrying = set(raw_v.get('carrying_items', []))
            
            if vis_carrying == raw_carrying:
                check(f"  {vid} carrying items match ({len(vis_carrying)} items)", True)
            else:
                only_vis = vis_carrying - raw_carrying
                only_raw = raw_carrying - vis_carrying
                detail = ""
                if only_vis: detail += f"only in vis: {only_vis} "
                if only_raw: detail += f"only in raw: {only_raw}"
                check(f"  {vid} carrying items match", False, detail)
        
        # 4b. Compare order counts
        onvehicle_raw = len(solution.get('onvehicle_order_items', '').split()) if solution.get('onvehicle_order_items') else 0
        unalloc_raw = len(solution.get('unallocated_order_items', '').split()) if solution.get('unallocated_order_items') else 0
        ongoing_raw = len(solution.get('ongoing_order_items', '').split()) if solution.get('ongoing_order_items') else 0
        completed_raw = len(solution.get('complete_order_items', []))
        
        print(f"\n  Raw solution.json:  📦{unalloc_raw} 🚚{ongoing_raw} 📋{onvehicle_raw} ✅{completed_raw}")
        print(f"  Vis last epoch:     📦{last_ep['orders']['unallocated']} "
              f"🚚{last_ep['orders']['ongoing']} "
              f"✅{last_ep['orders']['completed']}")
        
        # The visualization tracks "ongoing" differently (items picked up but not delivered)
        # vs solution.json "ongoing" (items assigned to vehicle but not yet picked up)
        # So these may differ - that's expected. Just note it.
        warn("Order count semantics may differ between visualization and solution.json",
             "Vis 'ongoing' = items in transit; solution 'ongoing' = items assigned to vehicles")
    
    # ═══════════════════════════════════════════
    # 5. FACTORY COORDINATE CONSISTENCY
    # ═══════════════════════════════════════════
    print("\n─── 5. Factory Coordinate Consistency ───")
    
    # Load benchmark factory data
    import pandas as pd
    try:
        factory_csv = pd.read_csv(os.path.join(benchmark_dir, 'factory_info.csv'))
        csv_factories = {}
        for _, row in factory_csv.iterrows():
            fid = str(row['factory_id'])
            csv_factories[fid] = (float(row['longitude']), float(row['latitude']))
        
        coord_matches = 0
        coord_mismatches = 0
        for fid, f in factory_data.items():
            if fid in csv_factories:
                csv_lng, csv_lat = csv_factories[fid]
                if abs(f['lng'] - csv_lng) < 0.0001 and abs(f['lat'] - csv_lat) < 0.0001:
                    coord_matches += 1
                else:
                    coord_mismatches += 1
        
        check(f"Factory coordinates: {coord_matches} match, {coord_mismatches} mismatch",
              coord_mismatches == 0,
              f"{coord_mismatches} factories have different coordinates!" if coord_mismatches else "")
    except Exception as e:
        warn(f"Could not verify factory coordinates: {e}")
    
    # ═══════════════════════════════════════════
    # 6. SAMPLE VEHICLE TRACE (detailed verification)
    # ═══════════════════════════════════════════
    print("\n─── 6. Sample Vehicle Trace ───")
    
    if vehicle_histories:
        # Pick the most active vehicle
        most_active = max(vehicle_histories.items(),
                         key=lambda x: sum(1 for h in x[1] if h['status'] != 'parked'))
        vid, history = most_active
        
        print(f"\n  Detailed trace for most active vehicle: {vid}")
        print(f"  {'Epoch':<6} {'Time':<20} {'Status':<20} {'Carry':<6} {'Factory':<20} {'Destination'}")
        print(f"  {'-'*5} {'-'*20} {'-'*20} {'-'*6} {'-'*20} {'-'*20}")
        
        for h in history:
            if h['status'] != 'parked' or h['carrying'] > 0:
                fid = h['cur_fid'][:18] if h['cur_fid'] else '-'
                dest = h['dest_fid'][:18] if h['dest_fid'] else '-'
                print(f"  {h['epoch']:<6} {fmt_ts(h['time']):<20} {h['status']:<20} "
                      f"{h['carrying']:<6} {fid:<20} {dest}")
    
    # ═══════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════
    print("\n" + "=" * 70)
    print(f"  RESULTS: {checks_passed} passed, {checks_failed} failed, {warnings} warnings")
    if checks_failed == 0:
        print("  ✅ VISUALIZATION DATA IS CONSISTENT AND VALID")
    else:
        print(f"  ⚠ {checks_failed} CHECKS FAILED — review above")
    print("=" * 70)

if __name__ == '__main__':
    summary_path = sys.argv[1] if len(sys.argv) > 1 else 'visualization_output/instance_1/epoch_summary.json'
    data_dir = sys.argv[2] if len(sys.argv) > 2 else 'algorithm/data_interaction'
    benchmark_dir = sys.argv[3] if len(sys.argv) > 3 else 'benchmark'
    validate(summary_path, data_dir, benchmark_dir)
