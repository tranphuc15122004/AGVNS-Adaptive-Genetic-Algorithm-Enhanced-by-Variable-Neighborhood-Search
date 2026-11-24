"""Replay the downloaded terminal snapshot without writing algorithm outputs."""

import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
REPOSITORY = AUDIT.parent.parent
VARIANT = REPOSITORY / '2' / 'Y_final_submission'
SNAPSHOT = AUDIT / 'latest_output' / REPOSITORY.name / '2' / 'Y_final_submission'
sys.dont_write_bytecode = True
sys.path.insert(0, str(VARIANT))

from algorithm.algorithm_demo import new_dispatch
from src.common.route import Map
from src.conf.configs import Configs
from src.utils.input_utils import get_factory_info, get_route_map
from src.utils.json_tools import get_order_item_dict, get_vehicle_instance_dict


def main() -> None:
    data = SNAPSHOT / 'algorithm' / 'data_interaction'
    factories = get_factory_info(Configs.factory_info_file_path)
    route_map = Map(get_route_map(Configs.route_info_file_path))
    unallocated = get_order_item_dict(json.loads((data / 'unallocated_order_items.json').read_text()), 'OrderItem')
    ongoing = get_order_item_dict(json.loads((data / 'ongoing_order_items.json').read_text()), 'OrderItem')
    vehicles = get_vehicle_instance_dict(json.loads((data / 'vehicle_info.json').read_text()), {**unallocated, **ongoing}, factories)
    available = [v.id for v in vehicles.values() if v.destination is None and v.leave_time_at_current_factory == v.gps_update_time]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        destinations, routes = new_dispatch(unallocated, vehicles, factories, route_map)
    planned_items = set()
    for vid, destination in destinations.items():
        for node in ([destination] if destination else []) + routes[vid]:
            planned_items.update(item.id for item in node.pickup_items + node.delivery_items)
    missing = sorted(set(unallocated) - planned_items)
    saved_destinations = json.loads((data / 'output_destination.json').read_text())
    saved_routes = json.loads((data / 'output_route.json').read_text())
    replayed_destinations = {vid: node.id if node else None for vid, node in destinations.items()}
    recorded_destinations = {vid: node['factory_id'] if node else None for vid, node in saved_destinations.items()}
    replayed_routes = {vid: [node.id for node in nodes] for vid, nodes in routes.items()}
    recorded_routes = {vid: [node['factory_id'] for node in nodes] for vid, nodes in saved_routes.items()}
    assert available == []
    assert missing == ['2323390097-1', '2326550098-1']
    assert replayed_destinations == recorded_destinations
    assert replayed_routes == recorded_routes
    report = {
        'simulation_time_utc': datetime.fromtimestamp(vehicles['V_1'].gps_update_time, timezone.utc).isoformat(),
        'available_vehicles': available,
        'missing_unallocated_items': missing,
        'destinations_and_routes_match_saved_output': True,
        'vehicle_filter': [{
            'id': v.id,
            'has_destination': v.destination is not None,
            'seconds_until_leave': v.leave_time_at_current_factory - v.gps_update_time,
            'carrying_items': len(v.get_unloading_sequence()),
        } for v in vehicles.values()],
        'algorithm_stdout': captured.getvalue(),
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
