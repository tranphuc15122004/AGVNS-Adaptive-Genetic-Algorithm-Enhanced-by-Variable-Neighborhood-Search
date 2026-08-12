"""Deterministic atomic-order construction and mutable-item discovery."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .dto import AtomicOrder, item_attr


def _item_key(item_id: str) -> Tuple[str, int, str]:
    match = re.match(r"^(.*?)-(\d+)$", str(item_id))
    return (match.group(1), int(match.group(2)), str(item_id)) if match else (str(item_id), -1, str(item_id))


def chunk_items(items: Iterable[Any], capacity: float = 15.0) -> List[AtomicOrder]:
    """Create stable capacity-feasible groups without losing any item.

    Items are grouped by original order and sorted by their numeric suffix.
    Next-fit is deterministic and preserves exact item coverage.  ICAPS mode
    uses a uniform capacity of 15; heterogeneous capacities fail fast at the
    caller rather than silently producing an invalid split.
    """

    if capacity <= 0:
        raise ValueError("capacity must be positive")
    grouped: Dict[str, List[Any]] = defaultdict(list)
    for item in items:
        order_id = str(item_attr(item, "order_id", ""))
        if not order_id:
            raise ValueError("every item must have an order_id")
        demand = float(item_attr(item, "demand", 0.0) or 0.0)
        if demand <= 0 or demand > capacity:
            raise ValueError(f"item {item_attr(item, 'id')} demand {demand} exceeds capacity {capacity}")
        grouped[order_id].append(item)

    result: List[AtomicOrder] = []
    for order_id in sorted(grouped):
        order_items = sorted(grouped[order_id], key=lambda x: _item_key(str(item_attr(x, "id", ""))))
        chunk: List[Any] = []
        demand = 0.0
        chunk_index = 0
        for item in order_items:
            item_demand = float(item_attr(item, "demand", 0.0) or 0.0)
            if chunk and demand + item_demand > capacity:
                result.append(_make_atomic(order_id, chunk_index, chunk, demand))
                chunk_index += 1
                chunk, demand = [], 0.0
            chunk.append(item)
            demand += item_demand
        if chunk:
            result.append(_make_atomic(order_id, chunk_index, chunk, demand))
    return result


def _make_atomic(order_id: str, index: int, items: Sequence[Any], demand: float) -> AtomicOrder:
    first = items[0]
    ids = tuple(str(item_attr(x, "id", "")) for x in items)
    return AtomicOrder(
        atomic_id=f"{order_id}::chunk-{index}",
        order_id=order_id,
        item_ids=ids,
        demand=float(demand),
        pickup_factory_id=str(item_attr(first, "pickup_factory_id", "")),
        delivery_factory_id=str(item_attr(first, "delivery_factory_id", "")),
        committed_completion_time=int(item_attr(first, "committed_completion_time", 0) or 0),
        creation_time=int(item_attr(first, "creation_time", 0) or 0),
    )


def mutable_item_ids(
    all_item_ids: Iterable[str],
    vehicles: Mapping[str, Any],
    planned_routes: Mapping[str, Sequence[Any]],
    destinations: Mapping[str, Any] | None = None,
) -> List[str]:
    """Return all generated items not already picked, delivered, or planned.

    This intentionally does not compute ``current_unallocated - previous``;
    doing so loses deferred/planned-but-unpicked items at the next epoch.
    """

    covered = set()

    def node_items(node: Any, pickup: bool) -> Iterable[Any]:
        dto_name = "pickup_item_ids" if pickup else "delivery_item_ids"
        if hasattr(node, dto_name):
            return getattr(node, dto_name) or ()
        names = ("pickup_item_list", "pickup_items") if pickup else ("delivery_item_list", "delivery_items")
        value = getattr(node, names[0], None)
        if value is None:
            value = getattr(node, names[1], ())
        return value or ()

    for vehicle in vehicles.values():
        carrying = getattr(vehicle, "carrying_items", ())
        if hasattr(vehicle, "carrying_item_ids"):
            carrying = getattr(vehicle, "carrying_item_ids")
        if hasattr(carrying, "items"):
            carrying = list(carrying.items)
        covered.update(str(getattr(x, "id", x)) for x in (carrying or ()))
        destination = getattr(vehicle, "destination", getattr(vehicle, "des", None))
        if destination is not None:
            covered.update(str(getattr(x, "id", x)) for x in node_items(destination, True))
            covered.update(str(getattr(x, "id", x)) for x in node_items(destination, False))
        # The official input object can retain a route suffix even when the
        # legacy ``plans`` dictionary has just been rebuilt from solution.json.
        # Scan both sources so a previously accepted but not-yet-picked item
        # cannot be scheduled a second time on the next epoch.
        for node in (getattr(vehicle, "planned_route", ()) or ()):
            covered.update(str(getattr(x, "id", x)) for x in node_items(node, True))
            covered.update(str(getattr(x, "id", x)) for x in node_items(node, False))
    for route in planned_routes.values():
        for node in route or ():
            pickups = node_items(node, True)
            deliveries = node_items(node, False)
            covered.update(str(getattr(x, "id", x)) for x in pickups)
            covered.update(str(getattr(x, "id", x)) for x in deliveries)
    if destinations:
        for node in destinations.values():
            if node is None:
                continue
            covered.update(str(getattr(x, "id", x)) for x in node_items(node, True))
            covered.update(str(getattr(x, "id", x)) for x in node_items(node, False))
    return sorted({str(x) for x in all_item_ids} - covered, key=_item_key)
