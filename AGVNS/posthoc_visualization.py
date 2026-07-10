#!/usr/bin/env python3
"""
posthoc_visualization.py — Post-hoc Visualization from Algorithm JSON Outputs
=============================================================================
Suy luận toàn bộ quá trình di chuyển của xe TỪ CÁC FILE OUTPUT JSON
mà KHÔNG cần sửa đổi thuật toán chính.

Từ các file:
  - solution.json (route_before, route_after, order states)
  - vehicle_info.json (vị trí, carrying_items, destination, thời gian)
  - output_destination.json (điểm đến kế tiếp + item list)
  - factory_info.csv (tọa độ factory)
  - route_info.csv (thời gian di chuyển giữa các factory)
  - ongoing_order_items.json / unallocated_order_items.json (chi tiết item)

Tạo ra:
  1. Bản đồ Folium tương tác với vị trí xe + lộ trình
  2. Bảng timeline Gantt-chart cho từng xe
  3. File HTML hoàn chỉnh có thể mở bằng browser

Usage:
    python posthoc_visualization.py
    python posthoc_visualization.py --data-dir algorithm/data_interaction
    python posthoc_visualization.py --data-dir algorithm/data_interaction_debug
"""

import argparse
import datetime
import json
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ─── Color palette for vehicles ───
VEHICLE_COLORS = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#469990', '#dcbeff',
    '#9A6324', '#800000', '#aaffc3', '#ffd8b1', '#000075',
    '#ff6f61', '#6b5b95', '#88b04b', '#f7cac9', '#92a8d1',
]

STATUS_LABELS = {
    'at_factory': '⏸ Đang đỗ tại factory',
    'loading': '📦 Đang bốc/dỡ hàng',
    'en_route': '🚚 Đang di chuyển',
    'waiting': '⏳ Đang chờ',
    'parked': '🅿️ Đỗ (không có việc)',
    'unknown': '❓ Không rõ',
}


def load_factories(benchmark_dir: str) -> Dict[str, dict]:
    """Load factory info: id → {lng, lat, dock_num}."""
    df = pd.read_csv(os.path.join(benchmark_dir, 'factory_info.csv'))
    factories = {}
    for _, row in df.iterrows():
        fid = str(row['factory_id'])
        factories[fid] = {
            'lng': float(row['longitude']),
            'lat': float(row['latitude']),
            'dock_num': int(row['port_num']),
        }
    return factories


def load_route_map(benchmark_dir: str) -> Dict[Tuple[str, str], Tuple[float, int]]:
    """Load route info: (start, end) → (distance_km, time_seconds)."""
    df = pd.read_csv(os.path.join(benchmark_dir, 'route_info.csv'))
    route_map = {}
    for _, row in df.iterrows():
        key = (str(row['start_factory_id']), str(row['end_factory_id']))
        route_map[key] = (float(row['distance']), int(row['time']))
    return route_map


def load_json(path: str) -> dict:
    """Load a JSON file, return empty dict/list on failure."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_order_items(path: str) -> Dict[str, dict]:
    """Load order items from JSON array, keyed by item id."""
    data = load_json(path)
    if isinstance(data, list):
        return {item['id']: item for item in data}
    return {}


def get_travel_time(route_map: dict, from_fid: str, to_fid: str) -> int:
    """Get travel time in seconds between two factories. Estimate if missing."""
    key = (from_fid, to_fid)
    if key in route_map:
        return route_map[key][1]  # time in seconds
    # Estimate: 1 km ≈ 120 seconds (30 km/h average)
    return 600  # default 10 min


def parse_node_string(node_str: str) -> dict:
    """
    Parse a single route node string like 'd6_2300460049-6' or 'p1_2354040050-1'.
    Returns: {operation, quantity, order_id, item_id}
    """
    node_str = node_str.strip()
    if not node_str:
        return None
    operation = node_str[0]  # 'd' or 'p'
    rest = node_str[1:]  # e.g., '6_2300460049-6'
    parts = rest.split('_', 1)
    if len(parts) != 2:
        return None
    quantity = int(parts[0])
    item_id = parts[1]  # e.g., '2300460049-6'
    # Extract order_id (part before the last '-')
    order_id = '-'.join(item_id.split('-')[:-1])
    return {
        'operation': operation,
        'quantity': quantity,
        'order_id': order_id,
        'item_id': item_id,
        'raw': node_str,
    }


def parse_route_string(route_str: str) -> Dict[str, List[dict]]:
    """
    Parse full route string like:
    "V_1:[d6_2300460049-6 d2_2218470047-2] V_2:[] V_3:[p1_2354040050-1 d1_2354040050-1]"
    Returns: {vehicle_id: [parsed_nodes]}
    """
    result = {}
    if not route_str:
        return result

    # Split by "V_" prefix
    segments = route_str.split('V_')
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # seg looks like "1:[d6_2300460049-6 d2_2218470047-2]"
        try:
            num_end = seg.index(':')
            vehicle_num = seg[:num_end]
            vehicle_id = f"V_{vehicle_num}"
            bracket_start = seg.index('[')
            bracket_end = seg.index(']')
            nodes_str = seg[bracket_start + 1:bracket_end].strip()
            nodes = []
            if nodes_str:
                for node_str in nodes_str.split():
                    parsed = parse_node_string(node_str)
                    if parsed:
                        nodes.append(parsed)
            result[vehicle_id] = nodes
        except (ValueError, IndexError):
            continue
    return result


def resolve_factory_for_node(node: dict, item_registry: dict, vehicle_dest_fid: str = None) -> Optional[str]:
    """
    Determine which factory a route node refers to.
    - For delivery (d): factory = delivery_factory_id of the item
    - For pickup (p): factory = pickup_factory_id of the item
    Falls back to vehicle's current destination if item not found.
    """
    item_id = node['item_id']

    # Try to find the exact item in registry
    if item_id in item_registry:
        item = item_registry[item_id]
        if node['operation'] == 'd':
            return item.get('delivery_factory_id')
        else:
            return item.get('pickup_factory_id')

    # Try matching by order_id prefix (for sub-items like xxx-1, xxx-2)
    order_id = node['order_id']
    for iid, item in item_registry.items():
        if iid.startswith(order_id):
            if node['operation'] == 'd':
                return item.get('delivery_factory_id')
            else:
                return item.get('pickup_factory_id')

    # Fallback: if delivery and we have vehicle destination
    if node['operation'] == 'd' and vehicle_dest_fid:
        return vehicle_dest_fid

    return None


def build_item_registry(data_dir: str) -> Dict[str, dict]:
    """Build complete item registry from all available sources."""
    registry = {}

    # From ongoing items
    ongoing = load_order_items(os.path.join(data_dir, 'ongoing_order_items.json'))
    registry.update(ongoing)

    # From unallocated items
    unallocated = load_order_items(os.path.join(data_dir, 'unallocated_order_items.json'))
    registry.update(unallocated)

    # Also try debug folder if exists
    parent = os.path.dirname(data_dir)
    debug_dir = os.path.join(parent, 'data_interaction_debug')
    if os.path.isdir(debug_dir):
        ongoing2 = load_order_items(os.path.join(debug_dir, 'ongoing_order_items.json'))
        registry.update(ongoing2)
        unallocated2 = load_order_items(os.path.join(debug_dir, 'unallocated_order_items.json'))
        registry.update(unallocated2)

    return registry


def reconstruct_vehicle_timeline(
    vehicle_id: str,
    route_nodes: List[dict],
    vehicle_info: dict,
    item_registry: dict,
    factories: dict,
    route_map: dict,
) -> List[dict]:
    """
    Reconstruct the full timeline for a vehicle.
    Returns list of {time, factory_id, lng, lat, status, event, carrying_items, ...}
    
    Logic:
    1. Start from current position (cur_factory_id, arrive/leave times)
    2. Process destination (next immediate stop from vehicle_info)
    3. Process remaining route nodes from route_after
    4. For each stop: calculate travel time → arrive → service → leave
    5. Track carrying items: remove on delivery, add on pickup
    """
    timeline = []
    if not vehicle_info:
        return timeline

    cur_fid = vehicle_info.get('cur_factory_id', '')
    leave_cur = vehicle_info.get('leave_time_at_current_factory', 0)
    update_time = vehicle_info.get('update_time', 0)
    carrying = list(vehicle_info.get('carrying_items', []))
    dest_info = vehicle_info.get('destination')
    
    # ── Build unified list of ALL stops (destination + route nodes) ──
    all_stops = []  # Each: {factory_id, operation, items_involved, quantity, order_id}
    
    if dest_info:
        dest_fid = dest_info.get('factory_id', '')
        delivery_items = dest_info.get('delivery_item_list', [])
        pickup_items = dest_info.get('pickup_item_list', [])
        if dest_fid:
            if delivery_items:
                all_stops.append({
                    'factory_id': dest_fid,
                    'operation': 'd',
                    'items': delivery_items,
                    'quantity': len(delivery_items),
                    'order_id': delivery_items[0].split('-')[0] if delivery_items else '',
                    'source': 'destination',
                })
            if pickup_items:
                all_stops.append({
                    'factory_id': dest_fid,
                    'operation': 'p',
                    'items': pickup_items,
                    'quantity': len(pickup_items),
                    'order_id': pickup_items[0].split('-')[0] if pickup_items else '',
                    'source': 'destination',
                })
    
    # Add route nodes (skip if same factory as destination to avoid duplicates)
    dest_fid_from_info = dest_info.get('factory_id', '') if dest_info else ''
    skipped_dest_fid = False  # Only skip first occurrence of dest factory
    for node in route_nodes:
        node_fid = resolve_factory_for_node(node, item_registry, dest_fid_from_info)
        if not node_fid:
            continue
        # Skip route nodes that are at the same factory as the current destination
        # (the destination in vehicle_info already covers the immediate next stop)
        if node_fid == dest_fid_from_info and not skipped_dest_fid:
            skipped_dest_fid = True
            continue
        all_stops.append({
            'factory_id': node_fid,
            'operation': node['operation'],
            'quantity': node['quantity'],
            'order_id': node['order_id'],
            'source': 'route',
        })
    
    # ── Merge consecutive stops at the same factory ──
    merged_stops = []
    for stop in all_stops:
        if merged_stops and merged_stops[-1]['factory_id'] == stop['factory_id']:
            # Merge: combine quantities for same operation type
            prev = merged_stops[-1]
            if prev['operation'] == stop['operation'] and prev['order_id'] == stop['order_id']:
                prev['quantity'] += stop['quantity']
            else:
                # Different operation or order at same factory - keep separate but note
                merged_stops.append(stop)
        else:
            merged_stops.append(stop)
    all_stops = merged_stops
    
    # ── No destination needed if vehicle parked ──
    if not all_stops and not cur_fid:
        return timeline
    
    # ── Add current position entry ──
    if cur_fid and cur_fid in factories:
        factory = factories[cur_fid]
        if leave_cur >= update_time:
            timeline.append({
                'time': update_time,
                'factory_id': cur_fid,
                'lng': factory['lng'],
                'lat': factory['lat'],
                'status': 'loading' if leave_cur > update_time else 'at_factory',
                'event': f'📍 HIỆN TẠI: {cur_fid[:16]}... | Chở {len(carrying)} item',
                'carrying_items': carrying.copy(),
                'is_current': True,
            })
            if leave_cur > update_time:
                timeline.append({
                    'time': leave_cur,
                    'factory_id': cur_fid,
                    'lng': factory['lng'],
                    'lat': factory['lat'],
                    'status': 'departing',
                    'event': f'🚪 Rời {cur_fid[:16]}...',
                    'carrying_items': carrying.copy(),
                })
    elif not cur_fid and dest_info and dest_info.get('arrive_time', 0) > update_time:
        # Vehicle is en-route (no current factory, has destination not yet arrived)
        dest_fid = dest_info.get('factory_id', '')
        if dest_fid and dest_fid in factories:
            timeline.append({
                'time': update_time,
                'factory_id': None,
                'lng': None,
                'lat': None,
                'from_fid': '?',
                'to_fid': dest_fid,
                'status': 'en_route',
                'event': f'📍 HIỆN TẠI: Đang di chuyển → {dest_fid[:16]}... | Chở {len(carrying)} item',
                'carrying_items': carrying.copy(),
                'is_current': True,
            })
    elif cur_fid and cur_fid in factories:
        # Vehicle at factory but already left (past state, still show)
        factory = factories[cur_fid]
        timeline.append({
            'time': update_time,
            'factory_id': cur_fid,
            'lng': factory['lng'],
            'lat': factory['lat'],
            'status': 'at_factory',
            'event': f'📍 HIỆN TẠI: {cur_fid[:16]}... | Chở {len(carrying)} item',
            'carrying_items': carrying.copy(),
            'is_current': True,
        })
    
    # ── Process stops sequentially ──
    prev_fid = cur_fid
    prev_leave_time = leave_cur if leave_cur > 0 else update_time
    
    for stop in all_stops:
        node_fid = stop['factory_id']
        if node_fid not in factories:
            continue
        factory = factories[node_fid]
        
        # Calculate travel time
        if prev_fid and prev_fid != node_fid:
            travel_time = get_travel_time(route_map, prev_fid, node_fid)
        else:
            travel_time = 0  # Same factory, no travel
        
        arrive_time = prev_leave_time + travel_time if prev_leave_time > 0 else 0
        
        # Service time
        if stop['operation'] == 'd':
            service_time = 240 * stop['quantity']  # unload: 4 min per item
            event_desc = f"📥 GIAO {stop['quantity']} item ({stop['order_id']})"
        else:
            service_time = 240 * stop['quantity']  # load: 4 min per item
            event_desc = f"📤 NHẬN {stop['quantity']} item ({stop['order_id']})"
        
        leave_time = arrive_time + service_time
        
        # Update carrying items
        carrying_before = carrying.copy()
        if stop['operation'] == 'd':
            # Remove delivered items from carrying list
            items_to_remove = []
            if 'items' in stop:
                items_to_remove = stop['items']
            else:
                # Try to find items by order_id prefix
                for c in carrying:
                    if c.startswith(stop['order_id']):
                        items_to_remove.append(c)
            for it in items_to_remove[:stop['quantity']]:
                if it in carrying:
                    carrying.remove(it)
        else:
            # Add picked up items
            if 'items' in stop:
                for it in stop['items']:
                    if it not in carrying:
                        carrying.append(it)
        
        # Add en-route entry (only if actually traveling)
        if travel_time > 0 and prev_leave_time > 0:
            mid_time = (prev_leave_time + arrive_time) // 2
            timeline.append({
                'time': mid_time,
                'factory_id': None,
                'lng': None,
                'lat': None,
                'from_fid': prev_fid,
                'to_fid': node_fid,
                'status': 'en_route',
                'event': f'🚚 Di chuyển → {node_fid[:12]}... ({travel_time//60} phút)',
                'travel_time_min': travel_time // 60,
                'carrying_items': carrying_before,
            })
        
        # Add arrival/service entry
        timeline.append({
            'time': arrive_time,
            'factory_id': node_fid,
            'lng': factory['lng'],
            'lat': factory['lat'],
            'status': 'loading',
            'event': event_desc + f' tại {node_fid[:16]}...',
            'operation': stop['operation'],
            'service_time_min': service_time // 60,
            'carrying_items_before': carrying_before,
            'carrying_items_after': carrying.copy(),
        })
        
        # Add departure
        timeline.append({
            'time': leave_time,
            'factory_id': node_fid,
            'lng': factory['lng'],
            'lat': factory['lat'],
            'status': 'departing',
            'event': f'✅ Hoàn thành, rời {node_fid[:16]}... (chở {len(carrying)} item)',
            'carrying_items': carrying.copy(),
        })
        
        prev_fid = node_fid
        prev_leave_time = leave_time
    
    # Sort by time
    timeline.sort(key=lambda x: x['time'])
    return timeline


def format_time(timestamp: int) -> str:
    """Convert unix timestamp to HH:MM string."""
    if timestamp <= 0:
        return '--:--'
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime('%H:%M')


def format_datetime(timestamp: int) -> str:
    """Convert unix timestamp to full datetime string."""
    if timestamp <= 0:
        return 'N/A'
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def build_interpolated_position(
    vehicle_id: str,
    sim_time: int,
    timeline: List[dict],
) -> Optional[dict]:
    """
    Find interpolated position of a vehicle at a given simulation time.
    Returns {lng, lat, status, factory_id, ...}
    """
    if not timeline:
        return None

    # Find bracketing timeline entries
    before = None
    after = None
    for entry in timeline:
        if entry['time'] <= sim_time:
            before = entry
        if entry['time'] > sim_time and after is None:
            after = entry
            break

    if before is None:
        return None

    # At a factory?
    if before['status'] in ('at_factory', 'loading') and before.get('factory_id'):
        return {
            'lng': before['lng'],
            'lat': before['lat'],
            'status': before['status'],
            'factory_id': before['factory_id'],
            'carrying_items': before.get('carrying_items', []),
        }

    # En route?
    if before['status'] == 'en_route' and after and after['status'] in ('at_factory', 'loading'):
        from_f = factories.get(before['from_fid']) if 'from_fid' in before else None
        to_f = factories.get(after['factory_id']) if after.get('factory_id') else None
        if from_f and to_f:
            total_t = after['time'] - before['time']
            ratio = (sim_time - before['time']) / total_t if total_t > 0 else 0
            ratio = max(0, min(1, ratio))
            return {
                'lng': from_f['lng'] + ratio * (to_f['lng'] - from_f['lng']),
                'lat': from_f['lat'] + ratio * (to_f['lat'] - from_f['lat']),
                'status': 'en_route',
                'from_fid': before.get('from_fid', ''),
                'to_fid': after.get('factory_id', ''),
                'progress': ratio,
                'carrying_items': before.get('carrying_items', []),
            }

    return None


# ──────────────────────────────────────────────
# HTML GENERATION
# ──────────────────────────────────────────────

def generate_map_html(
    all_timelines: Dict[str, List[dict]],
    vehicle_infos: Dict[str, dict],
    factories: dict,
    route_map: dict,
    output_path: str,
):
    """Generate an interactive Folium map with vehicle positions and routes."""
    try:
        import folium
    except ImportError:
        print("⚠ folium not installed. Install with: pip install folium")
        print("  Generating plain HTML without map...")
        generate_plain_html(all_timelines, vehicle_infos, factories, output_path)
        return

    # Center map
    lats = [f['lat'] for f in factories.values()]
    lngs = [f['lng'] for f in factories.values()]
    center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]

    m = folium.Map(location=center, zoom_start=11, tiles='CartoDB positron',
                   attr='&copy; OSM &copy; CARTO')

    # Add factory markers
    for fid, f in factories.items():
        folium.CircleMarker(
            location=[f['lat'], f['lng']],
            radius=3,
            color='#999',
            fill=True,
            fill_color='#999',
            fill_opacity=0.4,
            popup=f"<b>Factory</b><br>{fid[:16]}...<br>Docks: {f['dock_num']}",
        ).add_to(m)

    # Add vehicle markers and routes
    for i, (vid, timeline) in enumerate(all_timelines.items()):
        color = VEHICLE_COLORS[i % len(VEHICLE_COLORS)]
        vinfo = vehicle_infos.get(vid, {})

        # Current position marker
        cur_fid = vinfo.get('cur_factory_id', '')
        dest = vinfo.get('destination', {})
        
        if cur_fid and cur_fid in factories:
            f = factories[cur_fid]
            lat, lng = f['lat'], f['lng']
        elif dest and dest.get('factory_id') and dest['factory_id'] in factories:
            # Vehicle en-route: place at destination factory (or interpolate)
            f = factories[dest['factory_id']]
            lat, lng = f['lat'], f['lng']
        else:
            continue  # Can't place this vehicle
        
        # Build popup with rich detail
        carrying_list = vinfo.get('carrying_items', [])
        carrying_preview = '<br>'.join(carrying_list[:15]) if carrying_list else '(trống)'
        if len(carrying_list) > 15:
            carrying_preview += f'<br>... và {len(carrying_list) - 15} item khác'

        dest_str = 'Không có'
        if dest:
            dest_fid = dest.get('factory_id', '')[:20]
            dest_arrive = format_datetime(dest.get('arrive_time', 0))
            dest_leave = format_datetime(dest.get('leave_time', 0))
            delivery_n = len(dest.get('delivery_item_list', []))
            pickup_n = len(dest.get('pickup_item_list', []))
            dest_str = (f"{dest_fid}...<br>"
                       f"  Đến: {dest_arrive} | Rời: {dest_leave}<br>"
                       f"  Giao: {delivery_n} item | Nhận: {pickup_n} item")

        # Determine status from times
        leave_time = vinfo.get('leave_time_at_current_factory', 0)
        update_time = vinfo.get('update_time', 0)
        if not cur_fid and dest:
            status_text = '🚚 Đang di chuyển (en-route)'
            icon_color = 'orange'
            icon_name = 'play'
        elif leave_time > update_time:
            status_text = '📦 Đang bốc/dỡ hàng'
            icon_color = 'red'
            icon_name = 'stop'
        elif dest:
            status_text = '⏸ Đỗ, có lịch trình tiếp'
            icon_color = 'orange'
            icon_name = 'pause'
        else:
            status_text = '🅿️ Đỗ, không có việc'
            icon_color = 'blue'
            icon_name = 'stop'

        popup_html = f"""
        <div style="font-family: monospace; font-size: 12px; max-width: 350px;">
            <b style="color:{color}; font-size:15px;">🚛 {vid}</b>
            <hr style="margin:4px 0;">
            <b>Trạng thái:</b> {status_text}<br>
            <b>Vị trí:</b> {cur_fid[:20] if cur_fid else 'Đang di chuyển'}...<br>
            <b>Cập nhật lúc:</b> {format_datetime(update_time)}<br>
            <hr style="margin:4px 0;">
            <b>📋 Đang chở ({len(carrying_list)} item):</b><br>
            <div style="max-height:180px; overflow-y:auto; background:#f9f9f9; padding:4px; border-radius:4px;">
                {carrying_preview}
            </div>
            <hr style="margin:4px 0;">
            <b>🎯 Điểm đến tiếp:</b><br>
            <div style="background:#fff3e0; padding:4px; border-radius:4px;">{dest_str}</div>
        </div>
        """

        folium.Marker(
            location=[lat, lng],
            popup=folium.Popup(popup_html, max_width=370),
            icon=folium.Icon(color=icon_color, icon='truck', prefix='fa'),
        ).add_to(m)

        # Draw route as polyline
        route_coords = []
        visited_fids = set()
        for entry in timeline:
            if entry.get('factory_id') and entry['factory_id'] in factories:
                f = factories[entry['factory_id']]
                coord = [f['lat'], f['lng']]
                fid = entry['factory_id']
                if fid not in visited_fids or entry.get('is_current'):
                    route_coords.append(coord)
                    visited_fids.add(fid)
                    # Add event marker at factory
                    if entry.get('event') and 'Giao' in entry['event']:
                        folium.CircleMarker(
                            location=coord, radius=6, color='#e74c3c',
                            fill=True, fill_color='#e74c3c', fill_opacity=0.3,
                            popup=f"{vid}: {entry['event']}",
                        ).add_to(m)
                    elif entry.get('event') and 'Nhận' in entry['event']:
                        folium.CircleMarker(
                            location=coord, radius=6, color='#2ecc71',
                            fill=True, fill_color='#2ecc71', fill_opacity=0.3,
                            popup=f"{vid}: {entry['event']}",
                        ).add_to(m)

        if len(route_coords) >= 2:
            folium.PolyLine(
                locations=route_coords,
                weight=3,
                color=color,
                opacity=0.7,
                popup=f"<b>{vid}</b> route",
            ).add_to(m)

    # ── Add legend ──
    legend_html = """
    <div style="position:fixed; bottom:50px; left:12px; z-index:9999; background:white;
                padding:10px 14px; border-radius:6px; box-shadow:0 2px 8px rgba(0,0,0,0.2);
                font-family:Arial; font-size:12px;">
        <b>Chú thích</b><br>
        <span style="color:#e74c3c;">●</span> Giao hàng (delivery)<br>
        <span style="color:#2ecc71;">●</span> Nhận hàng (pickup)<br>
        <span style="color:#3498db;">●</span> Factory<br>
        <span style="color:red;">🚛</span> Xe đang loading<br>
        <span style="color:blue;">🚛</span> Xe đang đỗ<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(output_path)
    print(f"✅ Bản đồ đã lưu: {output_path}")


def generate_plain_html(
    all_timelines: Dict[str, List[dict]],
    vehicle_infos: Dict[str, dict],
    factories: dict,
    output_path: str,
):
    """Generate a plain HTML with timeline tables (no folium dependency)."""
    import html as html_mod

    rows = []
    for vid, timeline in all_timelines.items():
        vinfo = vehicle_infos.get(vid, {})
        color = VEHICLE_COLORS[len(rows) % len(VEHICLE_COLORS)]

        rows.append(f"""
        <div style="margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
            <div style="background: {color}; color: white; padding: 8px 16px; font-weight: bold; font-size: 16px;">
                🚛 {vid}
                <span style="font-size: 12px; font-weight: normal; margin-left: 12px;">
                    Đang chở: {len(vinfo.get('carrying_items', []))} item |
                    Vị trí: {vinfo.get('cur_factory_id', 'N/A')[:16]}...
                </span>
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <tr style="background: #f5f5f5;">
                    <th style="padding: 6px 12px; border-bottom: 1px solid #ddd;">Thời gian</th>
                    <th style="padding: 6px 12px; border-bottom: 1px solid #ddd;">Trạng thái</th>
                    <th style="padding: 6px 12px; border-bottom: 1px solid #ddd;">Factory</th>
                    <th style="padding: 6px 12px; border-bottom: 1px solid #ddd;">Sự kiện</th>
                    <th style="padding: 6px 12px; border-bottom: 1px solid #ddd;">Đang chở</th>
                </tr>
        """)

        for entry in timeline:
            time_str = format_datetime(entry['time'])
            status_icons = {
                'loading': '📦',
                'departing': '🚪',
                'en_route': '🚚',
                'at_factory': '⏸',
                'waiting': '⏳',
                'parked': '🅿️',
            }
            icon = status_icons.get(entry['status'], '❓')
            status = entry['status']

            # Factory or route segment
            if entry.get('factory_id'):
                fid = entry['factory_id'][:16] + '...'
            elif entry.get('from_fid') and entry.get('to_fid'):
                fid = f"{entry['from_fid'][:8]}... → {entry['to_fid'][:8]}..."
            else:
                fid = '-'

            event = html_mod.escape(entry.get('event', '')[:100])

            # Carrying items display
            carrying_before = entry.get('carrying_items_before', entry.get('carrying_items', []))
            carrying_after = entry.get('carrying_items_after', entry.get('carrying_items', []))
            n_before = len(carrying_before)
            n_after = len(carrying_after)

            if entry.get('operation') == 'd':
                carry_display = f'{n_before} → {n_after} item (đã giao {n_before - n_after})'
            elif entry.get('operation') == 'p':
                carry_display = f'{n_before} → {n_after} item (đã nhận {n_after - n_before})'
            else:
                carry_display = f'{n_before} item'

            row_style = 'background: #fffde7; font-weight: bold;' if entry.get('is_current') else ''

            rows.append(f"""
                <tr style="{row_style}">
                    <td style="padding: 4px 12px; border-bottom: 1px solid #eee; white-space: nowrap;">{time_str}</td>
                    <td style="padding: 4px 12px; border-bottom: 1px solid #eee;">{icon} {status}</td>
                    <td style="padding: 4px 12px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 11px;">{fid}</td>
                    <td style="padding: 4px 12px; border-bottom: 1px solid #eee;">{event}</td>
                    <td style="padding: 4px 12px; border-bottom: 1px solid #eee;">{carry_display}</td>
                </tr>
            """)

        rows.append("</table></div>")

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>DPDP Vehicle Timeline</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }}
        h1 {{ color: #2c3e50; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .summary {{ background: white; padding: 16px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        tr:hover {{ background: #f0f7ff !important; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 DPDP - Lịch trình vận chuyển chi tiết</h1>
        <div class="summary">
            <b>Xe:</b> {len(all_timelines)} |
            <b>Factory:</b> {len(factories)}
        </div>
        {''.join(rows)}
    </div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ Timeline HTML đã lưu: {output_path}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Post-hoc DPDP Visualization')
    parser.add_argument('--data-dir', type=str,
                        default='algorithm/data_interaction',
                        help='Path to data_interaction folder')
    parser.add_argument('--benchmark-dir', type=str,
                        default='benchmark',
                        help='Path to benchmark folder')
    parser.add_argument('--output', type=str,
                        default='visualization_output/posthoc_map.html',
                        help='Output HTML file path')
    parser.add_argument('--output-timeline', type=str,
                        default='visualization_output/posthoc_timeline.html',
                        help='Output timeline HTML file path')
    parser.add_argument('--no-map', action='store_true',
                        help='Skip folium map, only generate timeline')
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 DPDP Post-hoc Visualization")
    print("=" * 60)
    print(f"   Data dir:    {args.data_dir}")
    print(f"   Benchmark:   {args.benchmark_dir}")
    print()

    # ── Load data ──
    print("📂 Loading data...")
    global factories
    factories = load_factories(args.benchmark_dir)
    route_map = load_route_map(args.benchmark_dir)
    vehicle_infos_list = load_json(os.path.join(args.data_dir, 'vehicle_info.json'))
    solution = load_json(os.path.join(args.data_dir, 'solution.json'))
    output_dest = load_json(os.path.join(args.data_dir, 'output_destination.json'))

    # Convert vehicle list to dict
    vehicle_infos = {}
    if isinstance(vehicle_infos_list, list):
        for v in vehicle_infos_list:
            vehicle_infos[v['id']] = v
    elif isinstance(vehicle_infos_list, dict):
        vehicle_infos = vehicle_infos_list

    # Build item registry
    item_registry = build_item_registry(args.data_dir)

    print(f"   Factories:   {len(factories)}")
    print(f"   Vehicles:    {len(vehicle_infos)}")
    print(f"   Items known: {len(item_registry)}")
    print(f"   Routes:      {len(route_map)}")
    print()

    # ── Parse routes ──
    route_after = solution.get('route_after', '')
    route_before = solution.get('route_before', '')
    parsed_routes = parse_route_string(route_after)
    delta_t = solution.get('deltaT', '?')

    print(f"📋 Solution snapshot:")
    print(f"   Epoch:       {solution.get('no.', '?')}")
    print(f"   Time window: {delta_t}")
    print(f"   Completed:   {len(solution.get('complete_order_items', []))} items")
    print(f"   On-vehicle:  {len(solution.get('onvehicle_order_items', '').split())} items")
    print(f"   Unallocated: {len(solution.get('unallocated_order_items', '').split())} items")
    print()

    # ── Build timelines ──
    print("🔧 Reconstructing vehicle timelines...")
    all_timelines = {}
    for vid, vinfo in vehicle_infos.items():
        route_nodes = parsed_routes.get(vid, [])
        timeline = reconstruct_vehicle_timeline(
            vid, route_nodes, vinfo, item_registry, factories, route_map
        )
        all_timelines[vid] = timeline
        print(f"   {vid}: {len(timeline)} timeline entries, "
              f"{len(route_nodes)} route nodes, "
              f"carrying {len(vinfo.get('carrying_items', []))} items")

    # ── Print timeline summary ──
    print()
    print("=" * 60)
    print("📊 TÓM TẮT LỊCH TRÌNH TỪNG XE")
    print("=" * 60)
    for vid, timeline in all_timelines.items():
        vinfo = vehicle_infos.get(vid, {})
        print(f"\n{'─' * 50}")
        print(f"🚛 {vid} | Vị trí hiện tại: {vinfo.get('cur_factory_id', 'N/A')[:20]}...")
        print(f"   Đang chở: {vinfo.get('carrying_items', [])}")

        if timeline:
            print(f"   Timeline ({len(timeline)} mốc):")
            for entry in timeline:
                time_str = format_datetime(entry['time'])
                marker = '📍 HIỆN TẠI' if entry.get('is_current') else '  '
                status = entry['status']
                fid = (entry.get('factory_id', '') or '')[:16]
                n_items = len(entry.get('carrying_items', []))
                event = entry.get('event', '')[:70]
                print(f"   {marker} {time_str} | {status:12s} | {fid:18s} | {n_items:2d} items | {event}")
        else:
            print("   (không có dữ liệu timeline)")

    # ── Generate outputs ──
    os.makedirs(os.path.dirname(args.output) or 'visualization_output', exist_ok=True)

    # Generate timeline HTML
    print(f"\n📄 Generating timeline HTML...")
    generate_plain_html(all_timelines, vehicle_infos, factories, args.output_timeline)

    # Generate map HTML
    if not args.no_map:
        print(f"🗺 Generating map HTML...")
        generate_map_html(all_timelines, vehicle_infos, factories, route_map, args.output)

    print()
    print("=" * 60)
    print("✅ HOÀN THÀNH!")
    print(f"   Timeline: file:///{os.path.abspath(args.output_timeline).replace(os.sep, '/')}")
    if not args.no_map:
        print(f"   Bản đồ:   file:///{os.path.abspath(args.output).replace(os.sep, '/')}")
    print("=" * 60)


if __name__ == '__main__':
    # Global factories for interpolation function
    factories = {}
    main()
