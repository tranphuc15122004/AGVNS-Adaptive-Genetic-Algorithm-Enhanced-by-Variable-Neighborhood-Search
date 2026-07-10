#!/usr/bin/env python3
"""
build_instance_timeline.py — Build comprehensive timeline from epoch_summary.json
=================================================================================
V2: Improved display
  - "Kế hoạch" column: per-node structured cards (factory, time, items)
  - Detects nodes completed within each epoch (future→past transitions)
  - Groups events by node for clean display
"""
import json, datetime, os, sys, html as html_mod

VEHICLE_COLORS = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#469990', '#dcbeff',
]

def fmt_ts(ts):
    if ts <= 0: return '--:--'
    return datetime.datetime.fromtimestamp(ts).strftime('%H:%M')

def fmt_date(ts):
    if ts <= 0: return 'N/A'
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

def build_node_plan(trajectory_nodes, events, cur_time):
    """
    Build structured plan from trajectory + events.
    Returns list of {factory_id, arrive, leave, status, deliveries, pickups}
    """
    # Index events by (factory_id, time_bucket) for matching
    event_by_node = {}  # factory_id -> {arrive_time: {delivery: [...], pickup: [...]}}
    for ev in events:
        fid = ev['factory_id']
        t = ev['time']
        if fid not in event_by_node:
            event_by_node[fid] = {}
        # Round time to nearest match (events use arrive_time or arrive_time+1)
        matched = False
        for node_time in list(event_by_node[fid].keys()):
            if abs(node_time - t) <= 2:  # within 2 seconds = same node
                key = node_time
                matched = True
                break
        if not matched:
            key = t
            event_by_node[fid][key] = {'delivery': [], 'pickup': []}
        if ev['type'] == 'delivery':
            event_by_node[fid][key]['delivery'].append(ev['item_id'])
        else:
            event_by_node[fid][key]['pickup'].append(ev['item_id'])
    
    plan = []
    for node in trajectory_nodes:
        fid = node['factory_id']
        arr = node['arrive_time']
        leave = node['leave_time']
        status = node.get('status', 'future')
        
        # Find matching events
        deliveries = []
        pickups = []
        if fid in event_by_node:
            for t, items in event_by_node[fid].items():
                if abs(t - arr) <= 2 or (arr <= t <= leave):
                    deliveries = items['delivery']
                    pickups = items['pickup']
                    break
        
        plan.append({
            'factory_id': fid,
            'arrive': arr,
            'leave': leave,
            'status': status,
            'deliveries': deliveries,
            'pickups': pickups,
        })
    return plan

def render_node_card(node, is_completed_this_epoch=False):
    """Render a single node as an HTML card."""
    fid_short = node['factory_id'][:12] + '...'
    arr_str = fmt_ts(node['arrive'])
    leave_str = fmt_ts(node['leave'])
    
    status_badge = {
        'past': ('✅', '#27ae60', 'Đã xong'),
        'current': ('📍', '#e67e22', 'Đang thực hiện'),
        'future': ('⏳', '#95a5a6', 'Sắp tới'),
    }.get(node['status'], ('❓', '#999', node['status']))
    
    highlight = 'border: 2px solid #27ae60;' if is_completed_this_epoch else ''
    
    parts = [f'<div style="font-size:10px; margin:2px 0; padding:4px 6px; background:#fafafa; '
             f'border-radius:4px; {highlight}">']
    parts.append(f'<b style="color:{status_badge[1]}">{status_badge[0]} {status_badge[2]}</b> ')
    parts.append(f'<span style="font-family:monospace; font-size:9px;">{fid_short}</span><br>')
    parts.append(f'<span style="font-size:9px; color:#888;">{arr_str} → {leave_str}</span>')
    
    if node['deliveries']:
        n = len(node['deliveries'])
        preview = ', '.join(node['deliveries'][:3])
        more = f' +{n-3}' if n > 3 else ''
        parts.append(f'<br><span style="color:#e74c3c;">📥 Giao {n}: {preview}{more}</span>')
    if node['pickups']:
        n = len(node['pickups'])
        preview = ', '.join(node['pickups'][:3])
        more = f' +{n-3}' if n > 3 else ''
        parts.append(f'<br><span style="color:#2ecc71;">📤 Nhận {n}: {preview}{more}</span>')
    
    parts.append('</div>')
    return ''.join(parts)


def main():
    summary_path = sys.argv[1] if len(sys.argv) > 1 else 'visualization_output/instance_1/epoch_summary.json'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'visualization_output/instance_1/timeline.html'
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    epochs = summary['epochs']
    factory_data = {f['id']: f for f in summary['factory_data']}
    
    # ── Build rich timeline with trajectory + plan ──
    vehicle_timelines = {}
    
    for ep in epochs:
        ep_time = ep['epoch_time']
        ep_idx = ep['epoch_index']
        for v in ep['vehicles']:
            vid = v['id']
            if vid not in vehicle_timelines:
                vehicle_timelines[vid] = []
            
            pos = v.get('position', {})
            fid = pos.get('factory_id', v.get('cur_factory_id', ''))
            status = v.get('status', pos.get('status', 'unknown'))
            
            # Build structured plan from trajectory + events
            trajectory = v.get('trajectory', [])
            events = v.get('events', [])
            plan = build_node_plan(trajectory, events, ep_time)
            
            vehicle_timelines[vid].append({
                'epoch': ep_idx,
                'time': ep_time,
                'factory_id': fid if fid else None,
                'lng': pos.get('lng', 0),
                'lat': pos.get('lat', 0),
                'from_fid': pos.get('from_factory', ''),
                'to_fid': pos.get('to_factory', ''),
                'progress': pos.get('progress', 0),
                'status': status,
                'carrying_count': v.get('carrying_item_count', 0),
                'carrying_ids': v.get('carrying_item_ids', []),
                'dest_fid': v['destination']['factory_id'] if v.get('destination') else None,
                'plan': plan,  # ← structured node plan
            })
    
    # ── Detect completed nodes between epochs ──
    for vid, timeline in vehicle_timelines.items():
        for i in range(len(timeline) - 1):
            curr_plan = timeline[i]['plan']
            next_plan = timeline[i + 1]['plan']
            
            # Find nodes that were "future" in curr but "past" in next
            completed = []
            curr_future_nodes = {n['factory_id']: n for n in curr_plan if n['status'] == 'future'}
            next_past_nodes = {n['factory_id']: n for n in next_plan if n['status'] == 'past'}
            
            for fid, node in curr_future_nodes.items():
                if fid in next_past_nodes:
                    node['_completed_this_epoch'] = True
                    completed.append(fid)
            
            # Also detect nodes that disappeared (completed AND pruned)
            curr_all_fids = {n['factory_id'] for n in curr_plan}
            next_all_fids = {n['factory_id'] for n in next_plan}
            disappeared = curr_all_fids - next_all_fids
            for fid in disappeared:
                # This node was completed and removed from trajectory
                node = curr_future_nodes.get(fid)
                if node:
                    node['_completed_this_epoch'] = True
        
        # Mark current node if it just became current
        for i in range(len(timeline) - 1):
            curr_plan = timeline[i]['plan']
            next_plan = timeline[i + 1]['plan']
            for node in next_plan:
                if node['status'] == 'current':
                    # Check if it was future in previous epoch
                    prev_node = next((n for n in curr_plan if n['factory_id'] == node['factory_id']), None)
                    if prev_node and prev_node['status'] == 'future':
                        node['_just_started'] = True
    
    # ── Build HTML ──
    rows = []
    for i, (vid, timeline) in enumerate(sorted(vehicle_timelines.items())):
        color = VEHICLE_COLORS[i % len(VEHICLE_COLORS)]
        
        total_epochs = len(timeline)
        active_epochs = sum(1 for t in timeline if t['status'] not in ('parked', 'unknown'))
        max_carry = max((t['carrying_count'] for t in timeline), default=0)
        
        rows.append(f"""
        <div style="margin-bottom:20px; border:1px solid #ddd; border-radius:8px; overflow:hidden;">
            <div style="background:{color}; color:white; padding:10px 16px; font-weight:bold; font-size:16px;">
                🚛 {vid}
                <span style="font-size:12px; font-weight:normal; margin-left:12px;">
                    📊 {total_epochs} epochs | 🟢 Active: {active_epochs} | 📦 Max carry: {max_carry} items
                </span>
            </div>
            <div style="max-height:500px; overflow-y:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
                <tr style="background:#f5f5f5; position:sticky; top:0; z-index:5;">
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">Epoch</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">Thời gian</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">Trạng thái</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">Vị trí</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">📦</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd;">🎯 Điểm đến</th>
                    <th style="padding:4px 8px; border-bottom:1px solid #ddd; min-width:280px;">🗺 Kế hoạch (lộ trình)</th>
                </tr>
        """)
        
        prev_fid = None
        for t in timeline:
            status_icon = {
                'en_route': '🚚', 'at_factory': '⏸', 'loading_unloading': '📦',
                'parked': '🅿️', 'idle_at_factory': '⏸', 'unknown': '❓',
            }.get(t['status'], '❓')
            
            fid_display = t['factory_id'][:16] + '...' if t['factory_id'] else (
                f"{t['from_fid'][:8]}... → {t['to_fid'][:8]}..." if t['from_fid'] else '-'
            )
            
            dest_display = t['dest_fid'][:16] + '...' if t['dest_fid'] else '-'
            
            # ── Render plan as node cards ──
            plan_html_parts = []
            for node in t['plan']:
                is_completed = node.get('_completed_this_epoch', False)
                is_just_started = node.get('_just_started', False)
                
                card = render_node_card(node, is_completed)
                if is_completed:
                    card = '<div style="background:#eafaf1; border-radius:4px; margin:1px 0;">' + card + '</div>'
                if is_just_started:
                    card = '<div style="background:#fef9e7; border-radius:4px; margin:1px 0;">' + card + '</div>'
                plan_html_parts.append(card)
            
            plan_html = ''.join(plan_html_parts) if plan_html_parts else '<span style="color:#ccc;">—</span>'
            
            # Row highlight
            row_style = ''
            if t['factory_id'] and t['factory_id'] != prev_fid:
                row_style = 'background:#f0fff0;'
            if t['status'] == 'en_route':
                row_style = 'background:#fff8e1;'
            
            rows.append(f"""
                <tr style="{row_style}">
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; vertical-align:top;">{t['epoch']}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; white-space:nowrap; vertical-align:top;">{fmt_date(t['time'])}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; vertical-align:top;">{status_icon} {t['status']}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; font-family:monospace; font-size:10px; vertical-align:top;">{fid_display}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; text-align:center; vertical-align:top;">{t['carrying_count']}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; font-family:monospace; font-size:10px; vertical-align:top;">{dest_display}</td>
                    <td style="padding:2px 8px; border-bottom:1px solid #eee; vertical-align:top;">{plan_html}</td>
                </tr>
            """)
            prev_fid = t['factory_id']
        
        rows.append("</table></div></div>")
    
    # ── Summary ──
    total_orders_completed = epochs[-1]['orders']['completed'] if epochs else 0
    total_orders_ongoing = epochs[-1]['orders']['ongoing'] if epochs else 0
    
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>DPDP Instance 1 - Full Timeline</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #2c3e50; }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        .summary {{ background: white; padding: 16px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        tr:hover {{ background: #e3f2fd !important; }}
        .legend {{ background: white; padding: 10px 16px; border-radius: 8px; margin-bottom: 12px; font-size: 12px; }}
        .legend span {{ margin-right: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 DPDP Instance 1 - Lịch trình toàn bộ quá trình vận chuyển</h1>
        <div class="summary">
            <b>🕐 Thời gian mô phỏng:</b> {fmt_date(epochs[0]['epoch_time'])} → {fmt_date(epochs[-1]['epoch_time'])}<br>
            <b>📊 Số epochs:</b> {len(epochs)} | <b>🚛 Số xe:</b> {len(vehicle_timelines)} | <b>🏭 Số factory:</b> {len(factory_data)}<br>
            <b>📦 Đơn hàng hoàn thành:</b> {total_orders_completed} | <b>🚚 Đang xử lý:</b> {total_orders_ongoing}<br>
            <b>🎬 Animation:</b> <a href="animation/animated_simulation.html">Xem animation động</a>
        </div>
        <div class="legend">
            <b>🗺 Cột Kế hoạch:</b>
            <span style="color:#27ae60;">✅ Đã xong</span>
            <span style="color:#e67e22;">📍 Đang thực hiện</span>
            <span style="color:#95a5a6;">⏳ Sắp tới</span>
            <span style="background:#eafaf1; padding:2px 8px; border-radius:4px;">🟢 Viền xanh = vừa hoàn thành trong epoch này</span>
            <span style="background:#fef9e7; padding:2px 8px; border-radius:4px;">🟡 Viền vàng = vừa bắt đầu trong epoch này</span>
        </div>
        {''.join(rows)}
    </div>
</body>
</html>"""
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Timeline saved: {output_path}")
    print(f"   Vehicles: {len(vehicle_timelines)}")
    print(f"   Epochs: {len(epochs)}")
    print(f"   Time range: {fmt_date(epochs[0]['epoch_time'])} → {fmt_date(epochs[-1]['epoch_time'])}")

if __name__ == '__main__':
    main()
