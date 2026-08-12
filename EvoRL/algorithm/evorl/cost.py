"""Objective-compatible projected cost for DPDP plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from .dto import item_attr


@dataclass(frozen=True)
class CostBreakdown:
    distance: float = 0.0
    overtime_seconds: float = 0.0
    benchmark_cost: float = 0.0
    shaping_cost: float = 0.0
    queue_wait_seconds: float = 0.0


def _node_id(node: Any) -> str:
    return str(getattr(node, "id", getattr(node, "factory_id", "")))


def _items(node: Any, pickup: bool):
    dto_name = "pickup_item_ids" if pickup else "delivery_item_ids"
    if hasattr(node, dto_name):
        return list(getattr(node, dto_name) or ())
    names = ("pickup_item_list", "pickup_items") if pickup else ("delivery_item_list", "delivery_items")
    value = getattr(node, names[0], None)
    if value is None:
        value = getattr(node, names[1], ())
    return list(value or ())


def _node_key(node: Any):
    return (
        _node_id(node),
        tuple(str(getattr(item, "id", item)) for item in _items(node, pickup=True)),
        tuple(str(getattr(item, "id", item)) for item in _items(node, pickup=False)),
    )


def full_route_for_vehicle(vehicle: Any, suffix: Sequence[Any]) -> Tuple[Any, ...]:
    """Compose the committed destination and mutable suffix exactly once."""
    nodes = list(suffix or ())
    destination = getattr(vehicle, "destination", getattr(vehicle, "des", None))
    if destination is not None and (not nodes or _node_key(nodes[0]) != _node_key(destination)):
        nodes.insert(0, destination)
    return tuple(nodes)


def _edge(route_map: Mapping[Tuple[str, str], Any], start: str, end: str) -> Tuple[float, float]:
    value = route_map.get((start, end))
    if value is None:
        value = route_map.get((end, start))
    if value is None:
        return 0.0, 0.0
    if isinstance(value, Mapping):
        return float(value.get("distance", 0.0)), float(value.get("time", 0.0))
    return float(value[0]), float(value[1])


def projected_cost(
    routes: Mapping[str, Sequence[Any]],
    vehicles: Mapping[str, Any],
    route_map: Mapping[Tuple[str, str], Any],
    items: Mapping[str, Any] | Iterable[Any],
    *,
    current_time: int = 0,
    shaping_weight: float = 0.0,
    include_waiting: bool = False,
) -> CostBreakdown:
    """Compute projected suffix cost with order-level overtime aggregation."""

    item_map = items if isinstance(items, Mapping) else {
        str(item_attr(x, "id", "")): x for x in items
    }
    total_distance = 0.0
    order_completion: Dict[str, float] = {}
    order_deadline: Dict[str, float] = {}
    wait_seconds = 0.0
    vehicle_count = max(1, len(vehicles))

    for vehicle_id, vehicle in vehicles.items():
        previous = str(getattr(
            vehicle, "cur_factory_id", getattr(vehicle, "current_factory_id", ""),
        ) or "")
        if not previous:
            destination = getattr(vehicle, "des", getattr(vehicle, "destination", None))
            previous = _node_id(destination) if destination is not None else ""
        clock = float(current_time)
        carrying = getattr(vehicle, "carrying_items", ())
        if hasattr(vehicle, "carrying_item_ids"):
            carrying = getattr(vehicle, "carrying_item_ids") or ()
        if hasattr(carrying, "items"):
            carrying = list(carrying.items)
        for item in carrying or ():
            order_id = str(item_attr(item, "order_id", ""))
            order_deadline[order_id] = float(item_attr(item, "committed_completion_time", 0) or 0)
        for node in full_route_for_vehicle(vehicle, routes.get(vehicle_id, ()) or ()):
            current = _node_id(node)
            distance, travel_time = _edge(route_map, previous, current)
            total_distance += distance
            clock += travel_time
            recorded_arrival = float(getattr(node, "arrive_time", 0) or 0)
            if recorded_arrival > clock:
                clock = recorded_arrival
            deliveries = _items(node, pickup=False)
            for item in deliveries:
                item_id = str(getattr(item, "id", item))
                data = item_map.get(item_id, item)
                order_id = str(item_attr(data, "order_id", ""))
                order_completion[order_id] = max(order_completion.get(order_id, 0.0), clock)
                order_deadline[order_id] = float(item_attr(data, "committed_completion_time", 0) or 0)
                clock += float(item_attr(data, "unload_time", 0) or 0)
            for item in _items(node, pickup=True):
                data = item_map.get(str(getattr(item, "id", item)), item)
                order_id = str(item_attr(data, "order_id", ""))
                order_deadline[order_id] = float(item_attr(data, "committed_completion_time", 0) or 0)
                clock += float(item_attr(data, "load_time", 0) or 0)
            recorded_leave = float(getattr(node, "leave_time", 0) or 0)
            if recorded_leave > clock:
                clock = recorded_leave
            previous = current

    overtime = sum(max(0.0, completion - order_deadline.get(order_id, completion))
                   for order_id, completion in order_completion.items())
    benchmark = total_distance / vehicle_count + overtime * 10000.0 / 3600.0
    shaping = shaping_weight * (overtime + total_distance / vehicle_count)
    return CostBreakdown(
        distance=total_distance,
        overtime_seconds=overtime,
        benchmark_cost=benchmark,
        shaping_cost=shaping,
        queue_wait_seconds=wait_seconds if include_waiting else 0.0,
    )


def cost_delta(before: CostBreakdown, after: CostBreakdown) -> float:
    """Positive reward magnitude for an improvement in benchmark cost."""

    return before.benchmark_cost - after.benchmark_cost
