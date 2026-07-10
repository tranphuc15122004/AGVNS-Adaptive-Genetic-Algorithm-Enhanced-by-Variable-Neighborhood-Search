#!/usr/bin/env python3
"""
render_animation.py — Render smooth animated trajectory visualization from simulation snapshots.

Creates a continuous time-based animation where:
  - Vehicles move smoothly between factories (interpolated)
  - Pickup/delivery events are shown with visual indicators
  - Playback is controlled by a timeline slider

Usage:
    python render_animation.py --input <summary_json_path> --output <output_dir>
    python render_animation.py  # auto-detects latest summary
"""

import argparse
import json
import math
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.conf.configs import Configs


def load_summary(summary_path: str) -> dict:
    """Load the epoch summary JSON file."""
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_timeline(epochs, frame_interval=30):
    """
    Build a continuous timeline from all epoch data.
    - frame_interval: simulated seconds per animation frame (default 30 = smooth)
    - Returns: frames list, each frame has a simulation_time and interpolated state
    """
    if not epochs:
        return [], []

    # Find global time bounds from all vehicles' trajectories
    min_time = epochs[0]["epoch_time"]
    max_time = epochs[-1]["epoch_time"]

    # Also scan trajectories for wider bounds
    for ep in epochs:
        for v in ep.get("vehicles", []):
            for tr in v.get("trajectory", []):
                if tr.get("arrive_time", 0) > 0 and tr["arrive_time"] < min_time:
                    min_time = tr["arrive_time"]
                if tr.get("leave_time", 0) > max_time:
                    max_time = tr["leave_time"]

    # Generate frame timestamps
    num_frames = max(1, int((max_time - min_time) / frame_interval))
    frame_times = [min_time + i * frame_interval for i in range(num_frames + 1)]

    return frame_times, min_time, max_time


def interpolate_position_at_time(vehicle_data, sim_time, factory_lookup):
    """
    Given a vehicle's trajectory (list of nodes with arrive/leave times),
    compute its interpolated position at sim_time.

    Returns: {lat, lng, status, from_factory, to_factory, progress, events_here}
    """
    trajectory = vehicle_data.get("trajectory", [])
    if not trajectory:
        return None

    # Find the two consecutive nodes that bracket sim_time
    for i in range(len(trajectory)):
        node = trajectory[i]
        if sim_time < node["arrive_time"] and i == 0:
            # Before first node — return first node
            return {
                "lat": node["lat"],
                "lng": node["lng"],
                "status": "waiting",
                "factory_id": node["factory_id"],
                "progress": 0
            }

        if node["arrive_time"] <= sim_time <= node["leave_time"]:
            # At this factory (loading/unloading or idle)
            return {
                "lat": node["lat"],
                "lng": node["lng"],
                "status": "at_factory" if node["status"] == "current" else "loading",
                "factory_id": node["factory_id"],
                "progress": 0
            }

        if i < len(trajectory) - 1:
            next_node = trajectory[i + 1]
            if node["leave_time"] < sim_time < next_node["arrive_time"]:
                # En route between node and next_node
                total = next_node["arrive_time"] - node["leave_time"]
                ratio = (sim_time - node["leave_time"]) / total if total > 0 else 0
                ratio = max(0, min(1, ratio))
                lat = node["lat"] + ratio * (next_node["lat"] - node["lat"])
                lng = node["lng"] + ratio * (next_node["lng"] - node["lng"])
                return {
                    "lat": lat,
                    "lng": lng,
                    "status": "en_route",
                    "from_factory": node["factory_id"],
                    "to_factory": next_node["factory_id"],
                    "progress": ratio
                }

    # After all nodes — return last node
    last = trajectory[-1]
    return {
        "lat": last["lat"],
        "lng": last["lng"],
        "status": "parked",
        "factory_id": last["factory_id"],
        "progress": 1
    }


def get_active_events_at_time(vehicle_data, sim_time, window=10):
    """
    Check if any events (pickup/delivery) occur near sim_time.
    Returns a list of event dicts happening within `window` seconds.
    """
    active = []
    for ev in vehicle_data.get("events", []):
        if abs(ev["time"] - sim_time) <= window:
            active.append(ev)
    return active


def build_frame_data(epochs, factory_data, frame_times):
    """
    Build all animation frames with interpolated vehicle positions.
    """
    # Build factory coordinate lookup
    factory_lookup = {f["id"]: f for f in factory_data}

    frames = []

    # Determine which epoch each frame_time belongs to (for order stats)
    epoch_times = [ep["epoch_time"] for ep in epochs]

    for ft in frame_times:
        # Find current epoch index for order statistics
        epoch_idx = 0
        for i, et in enumerate(epoch_times):
            if ft >= et:
                epoch_idx = i
        epoch = epochs[min(epoch_idx, len(epochs) - 1)]

        vehicles_frame = []
        events_frame = []

        for v in epoch.get("vehicles", []):
            pos = interpolate_position_at_time(v, ft, factory_lookup)
            if pos is None:
                continue

            # Check for events at this time
            active_events = get_active_events_at_time(v, ft)
            events_frame.extend(active_events)

            vehicles_frame.append({
                "id": v["id"],
                "latitude": pos["lat"],
                "longitude": pos["lng"],
                "status": pos["status"],
                "item_count": v["carrying_item_count"],
                "progress": pos.get("progress", 0),
                "from": pos.get("from_factory", ""),
                "to": pos.get("to_factory", ""),
                "factory_id": pos.get("factory_id", "")
            })

        # ── Enrich order items with factory coordinates ──
        orders_frame = []

        def add_orders(order_list, state_name):
            for oi in order_list:
                pickup_f = factory_lookup.get(oi["pickup_factory_id"])
                delivery_f = factory_lookup.get(oi["delivery_factory_id"])
                # Only show orders that have been created by this frame time
                if oi["creation_time"] <= ft:
                    orders_frame.append({
                        "id": oi["id"],
                        "type": oi["type"],
                        "demand": oi["demand"],
                        "pickup_lat": pickup_f["lat"] if pickup_f else 0,
                        "pickup_lng": pickup_f["lng"] if pickup_f else 0,
                        "delivery_lat": delivery_f["lat"] if delivery_f else 0,
                        "delivery_lng": delivery_f["lng"] if delivery_f else 0,
                        "pickup_factory_id": oi["pickup_factory_id"],
                        "delivery_factory_id": oi["delivery_factory_id"],
                        "creation_time": oi["creation_time"],
                        "deadline": oi["committed_completion_time"],
                        "state": state_name
                    })

        add_orders(epoch.get("order_items", {}).get("unallocated", []), "unallocated")
        add_orders(epoch.get("order_items", {}).get("ongoing", []), "ongoing")
        add_orders(epoch.get("order_items", {}).get("completed", []), "completed")

        frames.append({
            "time": ft,
            "datetime": __import__('datetime').datetime.fromtimestamp(ft).strftime('%H:%M:%S'),
            "epoch_index": epoch.get("epoch_index", 0),
            "unallocated": epoch["orders"]["unallocated"],
            "ongoing": epoch["orders"]["ongoing"],
            "completed": epoch["orders"]["completed"],
            "vehicles": vehicles_frame,
            "events": events_frame,
            "orders": orders_frame
        })

    return frames


def render_animation(summary: dict, output_dir: str, title: str = "DPDP Simulation",
                     frame_interval: int = 30, playback_speed: int = 50):
    """
    Generate a self-contained HTML file with smooth continuous animation.

    Args:
        summary: Loaded epoch_summary.json dict
        output_dir: Directory to save output
        title: Map title
        frame_interval: Simulated seconds per animation frame (smaller = smoother)
        playback_speed: Milliseconds per frame in browser (smaller = faster)
    """
    try:
        import folium
    except ImportError:
        print("folium is required. Install it with: pip install folium")
        sys.exit(1)

    epochs = summary.get("epochs", [])
    factory_data = summary.get("factory_data", [])

    if not epochs:
        print("No epoch data found in summary.")
        return

    # Build continuous timeline
    frame_times, min_time, max_time = build_timeline(epochs, frame_interval)
    frames = build_frame_data(epochs, factory_data, frame_times)
    est_size_mb = len(frames) * 0.015  # ~15KB per frame
    print(f"  Built {len(frames)} animation frames ({frame_interval}s intervals)")
    print(f"  Estimated file size: ~{est_size_mb:.1f} MB")
    if est_size_mb > 15:
        print(f"  ⚠ File may be large. Use --frame-interval {int(frame_interval * 2)} for smaller output.")
    print(f"  Time range: {__import__('datetime').datetime.fromtimestamp(min_time)} → "
          f"{__import__('datetime').datetime.fromtimestamp(max_time)}")

    # Compute map center
    lats = [f["lat"] for f in factory_data]
    lngs = [f["lng"] for f in factory_data]
    center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]

    m = folium.Map(location=center, zoom_start=11, tiles='CartoDB positron',
                   attr='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>')

    # ── Add static factories ──
    for fd in factory_data:
        folium.CircleMarker(
            location=[fd["lat"], fd["lng"]],
            radius=4,
            color='#666',
            fill=True,
            fill_color='#666',
            fill_opacity=0.5,
            popup=f"Factory: {fd['id'][:12]}...<br>Docks: {fd['dock_num']}"
        ).add_to(m)

    # ── Serialize frames to JSON ──
    frames_json = json.dumps(frames)

    # ── Compute time bounds for slider ──
    total_frames = len(frames)

    # ── Inject JavaScript animation code ──
    js_code = f"""
    <div id="animation-controls" style="
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: white; padding: 10px 20px; border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3); text-align: center;
        font-family: Arial, sans-serif; min-width: 500px; max-width: 90%;">
        <div style="margin-bottom: 4px; display: flex; align-items: center; justify-content: center; gap: 12px;">
            <b style="font-size:13px;">⏱ <span id="time-label">00:00</span></b>
            <b style="font-size:13px; color:#2c3e50;">Epoch <span id="epoch-label">0</span></b>
            <span style="font-size:12px; color:#555;">
                📦<span id="stat-unalloc">0</span>
                🚚<span id="stat-ongoing">0</span>
                ✅<span id="stat-completed">0</span>
            </span>
        </div>
        <div style="display: flex; align-items: center; justify-content: center; gap: 6px;">
            <button onclick="togglePlay()" id="play-btn" style="padding: 4px 14px; font-size:16px; cursor:pointer;">▶</button>
            <input type="range" id="frame-slider" min="0" max="{total_frames - 1}" value="0"
                   oninput="goToFrame(parseInt(this.value))"
                   style="width: 300px; cursor:pointer;">
            <span id="frame-count" style="font-size:11px; color:#888;">0/{total_frames - 1}</span>
        </div>
        <div style="margin-top:2px; font-size:11px; color:#999; display:flex; align-items:center; justify-content:center; gap:10px; flex-wrap:wrap;">
            <span>Speed: <input type="range" id="speed-slider" min="20" max="200" value="{playback_speed}"
                   style="width:80px; vertical-align:middle; cursor:pointer;">
            <span id="speed-label">{playback_speed}ms</span></span>
            <span id="event-badge" style="display:none; background:#ff6b6b; color:white; padding:1px 8px; border-radius:10px; font-size:11px;"></span>
            <span style="color:#f39c12;">📤 Pickup</span>
            <span style="color:#3498db;">📥 Delivery</span>
            <span style="color:#999;">⎯⎯ Order route</span>
        </div>
    </div>

    <script>
    var frames = {frames_json};
    var currentFrame = 0;
    var isPlaying = false;
    var playTimer = null;
    var vehicleMarkers = {{}};
    var eventMarkers = [];
    var orderMarkers = [];
    var orderLines = [];
    var vehicleColors = {{}};
    var prevPositions = {{}};

    var colorPalette = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
                        '#42d4f4', '#f032e6', '#bfef45', '#469990', '#dcbeff',
                        '#9A6324', '#800000', '#aaffc3', '#ffd8b1', '#000075'];

    function getVehicleColor(id) {{
        if (!vehicleColors[id]) {{
            var idx = Object.keys(vehicleColors).length % colorPalette.length;
            vehicleColors[id] = colorPalette[idx];
        }}
        return vehicleColors[id];
    }}

    function interpolateMarker(v, prevPos) {{
        var color = getVehicleColor(v.id);
        var iconChar = v.status === 'en_route' ? '🚚' :
                       v.status === 'loading' ? '⏳' :
                       v.status === 'at_factory' ? '🚛' :
                       v.status === 'parked' ? '🅿️' : '🚛';

        var popupText = '<b>' + v.id + '</b><br>' +
                        'Status: ' + v.status + '<br>' +
                        'Items: ' + v.item_count +
                        (v.from ? '<br>From: ' + v.from.slice(0,12) + '...' : '') +
                        (v.to ? '<br>To: ' + v.to.slice(0,12) + '...' : '') +
                        (v.progress ? '<br>Progress: ' + Math.round(v.progress*100) + '%' : '');

        var icon = L.divIcon({{
            className: 'vehicle-icon',
            html: '<div style="font-size:20px; transition: all 0.3s;">' + iconChar + '</div>',
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        }});

        var marker = L.marker([v.latitude, v.longitude], {{
            icon: icon,
            zIndexOffset: 1000
        }}).bindPopup(popupText);
        return marker;
    }}

    function clearDynamicLayers() {{
        for (var id in vehicleMarkers) {{
            map.removeLayer(vehicleMarkers[id]);
        }}
        for (var i = 0; i < eventMarkers.length; i++) {{
            map.removeLayer(eventMarkers[i]);
        }}
        for (var i = 0; i < orderMarkers.length; i++) {{
            map.removeLayer(orderMarkers[i]);
        }}
        for (var i = 0; i < orderLines.length; i++) {{
            map.removeLayer(orderLines[i]);
        }}
        vehicleMarkers = {{}};
        eventMarkers = [];
        orderMarkers = [];
        orderLines = [];
    }}

    function showEventMarkers(events) {{
        for (var i = 0; i < events.length; i++) {{
            var ev = events[i];
            var color = ev.type === 'pickup' ? '#2ecc71' : '#e74c3c';
            var symbol = ev.type === 'pickup' ? '📦' : '✅';
            var label = ev.type === 'pickup' ? 'Pickup' : 'Delivery';

            var circle = L.circleMarker([ev.lat, ev.lng], {{
                radius: 12,
                color: color,
                fillColor: color,
                fillOpacity: 0.3,
                weight: 2,
                opacity: 0.8
            }}).addTo(map);
            eventMarkers.push(circle);

            // Animate with a second pulsing circle
            var pulse = L.circleMarker([ev.lat, ev.lng], {{
                radius: 20,
                color: color,
                fillColor: color,
                fillOpacity: 0.1,
                weight: 1,
                opacity: 0.4
            }}).addTo(map);
            eventMarkers.push(pulse);

            // Update event badge
            var badge = document.getElementById('event-badge');
            badge.style.display = 'inline';
            badge.textContent = symbol + ' ' + ev.item_id.slice(0,8) + '... ' + label + ' at ' + ev.factory_id.slice(0,8) + '...';
            setTimeout(function() {{
                badge.style.display = 'none';
            }}, 3000);
        }}
    }}

    function goToFrame(idx) {{
        if (idx < 0 || idx >= frames.length) return;
        var frame = frames[idx];
        currentFrame = idx;

        // Compute current epoch number (count how many distinct epoch_index values up to idx)
        var currentEpoch = frame.epoch_index;
        // Find the total number of distinct epochs in the simulation
        var maxEpoch = 0;
        for (var i = 0; i < frames.length; i++) {{
            if (frames[i].epoch_index > maxEpoch) maxEpoch = frames[i].epoch_index;
        }}

        // Update UI
        document.getElementById('time-label').textContent = frame.datetime;
        document.getElementById('epoch-label').textContent = currentEpoch + '/' + maxEpoch;
        document.getElementById('stat-unalloc').textContent = frame.unallocated;
        document.getElementById('stat-ongoing').textContent = frame.ongoing;
        document.getElementById('stat-completed').textContent = frame.completed;
        document.getElementById('frame-slider').value = idx;
        document.getElementById('frame-count').textContent = idx + '/' + (frames.length - 1);

        // Clear old
        clearDynamicLayers();

        // Add vehicles
        for (var i = 0; i < frame.vehicles.length; i++) {{
            var v = frame.vehicles[i];
            var marker = interpolateMarker(v, prevPositions[v.id]);
            marker.addTo(map);
            vehicleMarkers[v.id] = marker;
            prevPositions[v.id] = v;
        }}

        // Show events
        showEventMarkers(frame.events);

        // Show orders
        showOrderMarkers(frame.orders, frame.time);
    }}

    function showOrderMarkers(orders, currentTime) {{
        if (!orders || orders.length === 0) return;

        // Group orders by (pickup_factory, delivery_factory) pairs AND state
        var groups = {{}};
        for (var i = 0; i < orders.length; i++) {{
            var o = orders[i];
            var key = o.pickup_factory_id + '|' + o.delivery_factory_id + '|' + o.state;
            if (!groups[key]) {{
                groups[key] = {{
                    pickup_lat: o.pickup_lat,
                    pickup_lng: o.pickup_lng,
                    delivery_lat: o.delivery_lat,
                    delivery_lng: o.delivery_lng,
                    pickup_factory_id: o.pickup_factory_id,
                    delivery_factory_id: o.delivery_factory_id,
                    state: o.state,
                    ids: [],
                    count: 0
                }};
            }}
            groups[key].count++;
            groups[key].ids.push(o.id);
        }}

        for (var key in groups) {{
            var g = groups[key];
            var isCompleted = g.state === 'completed';
            var countLabel = g.count > 1 ? '×' + g.count : '';
            var shortId = g.ids[0];
            var displayId = shortId.length > 8 ? shortId.slice(0,8) : shortId;

            // Determine colors based on state
            var pickupBg, deliveryBg, lineColor, opacity;
            if (isCompleted) {{
                pickupBg = '#95a5a6';    // gray
                deliveryBg = '#95a5a6';   // gray
                lineColor = '#95a5a6';    // gray
                opacity = 0.25;
            }} else if (g.state === 'ongoing') {{
                pickupBg = '#2ecc71';     // green
                deliveryBg = '#2ecc71';    // green
                lineColor = '#2ecc71';
                opacity = 0.5;
            }} else {{
                pickupBg = '#f39c12';     // orange (unallocated)
                deliveryBg = '#3498db';    // blue
                lineColor = '#f39c12';
                opacity = 0.35;
            }}

            // ── Pickup badge ──
            var pickupLabel = '📤' + (isCompleted ? '' : displayId + countLabel);
            var pickupIcon = L.divIcon({{
                className: 'order-icon',
                html: '<div style="font-size:10px; background:' + pickupBg + '; color:white; border-radius:10px; padding:2px 6px; font-weight:bold; box-shadow:0 1px 3px rgba(0,0,0,0.3); white-space:nowrap; opacity:' + (isCompleted ? 0.4 : 1) + ';">' + pickupLabel + '</div>',
                iconSize: isCompleted ? [35, 18] : [60, 18],
                iconAnchor: isCompleted ? [17, 9] : [30, 9]
            }});
            var pm = L.marker([g.pickup_lat, g.pickup_lng], {{
                icon: pickupIcon,
                zIndexOffset: isCompleted ? 100 : 500
            }}).addTo(map);
            orderMarkers.push(pm);

            // ── Delivery badge ──
            var deliveryLabel = '📥' + (isCompleted ? '' : displayId + countLabel);
            var deliveryIcon = L.divIcon({{
                className: 'order-icon',
                html: '<div style="font-size:10px; background:' + deliveryBg + '; color:white; border-radius:10px; padding:2px 6px; font-weight:bold; box-shadow:0 1px 3px rgba(0,0,0,0.3); white-space:nowrap; opacity:' + (isCompleted ? 0.4 : 1) + ';">' + deliveryLabel + '</div>',
                iconSize: isCompleted ? [35, 18] : [60, 18],
                iconAnchor: isCompleted ? [17, 9] : [30, 9]
            }});
            var dm = L.marker([g.delivery_lat, g.delivery_lng], {{
                icon: deliveryIcon,
                zIndexOffset: isCompleted ? 100 : 500
            }}).addTo(map);
            orderMarkers.push(dm);

            // ── Connecting line ──
            var line = L.polyline(
                [[g.pickup_lat, g.pickup_lng], [g.delivery_lat, g.delivery_lng]],
                {{
                    color: lineColor,
                    weight: isCompleted ? 1 : 1.5,
                    opacity: isCompleted ? 0.15 : opacity,
                    dashArray: isCompleted ? '3, 5' : '8, 6'
                }}
            ).addTo(map);
            orderLines.push(line);

            // ── Tooltip ──
            if (!isCompleted) {{
                var tooltipParts = ['<b>' + g.state + '</b>: ' + g.count + ' order(s)'];
                tooltipParts.push('IDs: ' + g.ids.join(', '));
                line.bindTooltip(tooltipParts.join('<br>'));
            }}
        }}
    }}

    function togglePlay() {{
        if (isPlaying) {{
            stopPlay();
        }} else {{
            startPlay();
        }}
    }}

    function startPlay() {{
        if (currentFrame >= frames.length - 1) {{
            goToFrame(0);
        }}
        isPlaying = true;
        document.getElementById('play-btn').textContent = '⏸';
        var speed = parseInt(document.getElementById('speed-slider').value);
        document.getElementById('speed-label').textContent = speed + 'ms';
        playTimer = setInterval(function() {{
            if (currentFrame < frames.length - 1) {{
                goToFrame(currentFrame + 1);
            }} else {{
                stopPlay();
            }}
        }}, speed);
    }}

    function stopPlay() {{
        isPlaying = false;
        document.getElementById('play-btn').textContent = '▶';
        if (playTimer) {{
            clearInterval(playTimer);
            playTimer = null;
        }}
    }}

    // Listen for speed changes
    document.addEventListener('DOMContentLoaded', function() {{
        document.getElementById('speed-slider').addEventListener('input', function() {{
            var s = parseInt(this.value);
            document.getElementById('speed-label').textContent = s + 'ms';
            if (isPlaying) {{
                stopPlay();
                startPlay();
            }}
        }});
    }});

    function initAnimation() {{
        window.map = null;
        for (var key in window) {{
            if (key.startsWith('map_') && window[key] instanceof L.Map) {{
                window.map = window[key];
                break;
            }}
        }}
        if (window.map) {{
            goToFrame(0);
        }} else {{
            setTimeout(initAnimation, 100);
        }}
    }}
    if (document.readyState === 'complete') {{
        initAnimation();
    }} else {{
        window.addEventListener('load', initAnimation);
    }}
    </script>

    <style>
    .vehicle-icon {{
        background: none !important;
        border: none !important;
    }}
    .order-icon {{
        background: none !important;
        border: none !important;
    }}
    .leaflet-popup-content {{
        font-family: Arial, sans-serif;
        font-size: 12px;
    }}
    #animation-controls button:hover {{
        background: #f0f0f0;
    }}
    </style>
    """

    m.get_root().html.add_child(folium.Element(js_code))

    # Save
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "animated_simulation.html")
    m.save(output_path)
    print(f"[OK] Animated simulation saved to: {output_path}")
    return output_path


def find_latest_summary(base_dir: str = None) -> str:
    """Find the most recent epoch_summary.json in the visualization output directories."""
    base_dir = base_dir or Configs.VISUALIZATION_OUTPUT_DIR
    if not os.path.isdir(base_dir):
        return None

    summary_paths = []
    for root, dirs, files in os.walk(base_dir):
        if "epoch_summary.json" in files:
            summary_paths.append(os.path.join(root, "epoch_summary.json"))

    if not summary_paths:
        return None

    return max(summary_paths, key=os.path.getmtime)


def main():
    parser = argparse.ArgumentParser(description="Render smooth animated DPDP simulation")
    parser.add_argument("--input", "-i", help="Path to epoch_summary.json (auto-detected if omitted)")
    parser.add_argument("--output", "-o", default="visualization_output/animation",
                        help="Output directory for the animation HTML")
    parser.add_argument("--frame-interval", "-f", type=int, default=300,
                        help="Simulated seconds per animation frame (default: 300 = 5 min). "
                             "Smaller = smoother but larger file. Use 30 for smooth, 600 for lightweight.")
    parser.add_argument("--playback-speed", "-s", type=int, default=80,
                        help="Milliseconds per frame in browser (default: 80). "
                             "Smaller = faster playback.")
    args = parser.parse_args()

    summary_path = args.input
    if not summary_path:
        summary_path = find_latest_summary()
        if not summary_path:
            print("No epoch_summary.json found. Run the simulator first or specify --input.")
            sys.exit(1)
        print(f"Auto-detected summary: {summary_path}")

    summary = load_summary(summary_path)
    print(f"Loaded {len(summary.get('epochs', []))} epochs from {summary_path}")
    print(f"  Factories: {summary.get('factory_count', 0)}")

    output_path = render_animation(summary, args.output,
                                    frame_interval=args.frame_interval,
                                    playback_speed=args.playback_speed)
    print(f"\nDone! Open in browser:")
    print(f"  file:///{output_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
