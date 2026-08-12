"""Evaluator for the four GA fitness components in paper Eq. (29)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from algorithm.evorl.cost import _edge
from algorithm.evorl.dto import EpochState, item_attr


@dataclass(frozen=True)
class PaperFitness:
    current_overtime: float = 0.0
    inefficient_completion: float = 0.0
    carried_overtime: float = 0.0
    queue_wait: float = 0.0
    utility: float = 0.0


def evaluate_paper_fitness(state: EpochState, *, weights=(1.0, 1.0, 1.0, 1.0)) -> PaperFitness:
    """Estimate Eq. (29) without mutating simulator or route objects.

    The paper does not publish a complete queue estimator.  Queue wait is
    therefore zero in the deterministic compatibility evaluator and remains a
    logged component; the official ICAPS score is still computed separately.
    """

    item_map = state.items
    order_items_by_order: Dict[str, list] = {}
    for item in item_map.values():
        order_items_by_order.setdefault(str(item_attr(item, "order_id", "")), []).append(item)
    completion: Dict[str, float] = {}
    deadline: Dict[str, float] = {}
    fastest: Dict[str, float] = {}
    carried_orders: Dict[str, float] = {}
    for vehicle in state.vehicles.values():
        previous = vehicle.current_factory_id
        if not previous and vehicle.destination is not None:
            previous = vehicle.destination.factory_id
        clock = float(state.current_time)
        route = list(vehicle.planned_route)
        if vehicle.destination is not None:
            route.insert(0, vehicle.destination)
        for item_id in vehicle.carrying_item_ids:
            item = item_map.get(item_id)
            order_id = str(item_attr(item, "order_id", ""))
            carried_orders[order_id] = max(
                carried_orders.get(order_id, 0.0),
                float(item_attr(item, "committed_completion_time", 0) or 0),
            )
        for node in route:
            distance, travel_time = _edge(state.route_map, previous, node.factory_id)
            clock += float(travel_time)
            for item_id in node.delivery_item_ids:
                item = item_map.get(item_id)
                order_id = str(item_attr(item, "order_id", ""))
                deadline[order_id] = float(item_attr(item, "committed_completion_time", 0) or 0)
                clock += float(item_attr(item, "unload_time", 0) or 0)
                completion[order_id] = max(completion.get(order_id, 0.0), clock)
            for item_id in node.pickup_item_ids:
                item = item_map.get(item_id)
                order_id = str(item_attr(item, "order_id", ""))
                deadline[order_id] = float(item_attr(item, "committed_completion_time", 0) or 0)
                clock += float(item_attr(item, "load_time", 0) or 0)
            previous = node.factory_id
    current_overtime = sum(max(0.0, completion_id - deadline.get(order_id, completion_id)) for order_id, completion_id in completion.items())
    inefficient = 0.0
    for order_id, completion_time in completion.items():
        # Fastest completion is a direct pickup-delivery estimate for the
        # first item of the original order.  It is a lower bound, not a second
        # official objective.
        order_items = order_items_by_order.get(order_id, [])
        if not order_items:
            continue
        first = order_items[0]
        pickup = str(item_attr(first, "pickup_factory_id", ""))
        delivery = str(item_attr(first, "delivery_factory_id", ""))
        _, pickup_time = _edge(state.route_map, pickup, delivery)
        fastest_time = float(item_attr(first, "load_time", 0) or 0) + float(item_attr(first, "unload_time", 0) or 0) + pickup_time
        inefficient += max(0.0, completion_time - fastest_time - float(item_attr(first, "creation_time", 0) or 0))
    carried_overtime = sum(max(0.0, state.current_time - deadline) for deadline in carried_orders.values())
    queue_wait = 0.0
    penalty = (
        float(weights[0]) * current_overtime
        + float(weights[1]) * inefficient
        + float(weights[2]) * carried_overtime
        + float(weights[3]) * queue_wait
    )
    return PaperFitness(current_overtime, inefficient, carried_overtime, queue_wait, -penalty)
