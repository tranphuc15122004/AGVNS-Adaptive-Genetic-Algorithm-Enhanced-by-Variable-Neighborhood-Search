"""Objective and feasibility primitives for the paper's MOEA/D--TS.

MOEA/D keeps two objectives for decomposition, but their values must match the
established DPDP cost implementation used by the shared AGVNS local search.
The production scoring path therefore obtains ``f1``, ``f2`` and ``TC`` from
one complete ``total_cost`` simulation instead of maintaining a second fleet
simulator or evaluating the components independently.
"""

from collections import Counter
import copy
from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from algorithm.Object import Factory, Node, OrderItem, Vehicle
from algorithm.engine import isFeasible, total_cost
import algorithm.algorithm_config as config


@dataclass(frozen=True)
class Objectives:
    """Raw paper objectives plus the scalar cost from the shared engine."""
    tardiness: float
    average_distance: float
    tc_value: Optional[float] = None

    @property
    def tc(self) -> float:
        if self.tc_value is not None:
            return self.tc_value
        return config.Delta * self.tardiness + self.average_distance

    def as_tuple(self) -> Tuple[float, float]:
        return self.tardiness, self.average_distance


@dataclass
class EvaluationContext:
    route_map: Mapping[Tuple[str, str], Tuple[float, int]]
    id_to_vehicle: Mapping[str, Vehicle]
    id_to_factory: Mapping[str, Factory]
    all_items: Mapping[str, OrderItem]


def _items_on_nodes(route: Iterable[Node]) -> Set[str]:
    result: Set[str] = set()
    for node in route:
        result.update(item.id for item in node.pickup_item_list or [])
        result.update(item.id for item in node.delivery_item_list or [])
    return result


def _node_action_ids(node: Node) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Return ordered pickup/delivery IDs; their order is part of the LIFO state."""
    return (
        tuple(item.id for item in (node.pickup_item_list or [])),
        tuple(item.id for item in (node.delivery_item_list or [])),
    )


def destination_matches(node: Node, destination: Node) -> bool:
    """Check the complete immutable destination contract, not only its factory."""
    return node.id == destination.id and _node_action_ids(node) == _node_action_ids(destination)


def _subtract_committed_actions(items: Iterable[OrderItem],
                                committed_items: Iterable[OrderItem]) -> List[OrderItem]:
    """Keep actions not already represented by the immutable destination node."""
    remaining = Counter(item.id for item in committed_items)
    result: List[OrderItem] = []
    for item in items:
        if remaining[item.id] > 0:
            remaining[item.id] -= 1
        else:
            result.append(item)
    return result


def ensure_destination_prefix(route: List[Node], vehicle: Vehicle) -> None:
    """Materialise a vehicle's committed destination without losing route actions.

    A restored plan can begin at the destination factory but contain actions
    that differ from the simulator-committed node.  Keep the committed node as
    a separate immutable prefix and retain any additional actions in the next
    node.  This prevents a same-factory match from silently changing a vehicle
    that is already en route.
    """
    destination = vehicle.des
    if destination is None:
        return
    if not route:
        route.append(copy.deepcopy(destination))
        return
    if destination_matches(route[0], destination):
        return
    if route[0].id != destination.id:
        route.insert(0, copy.deepcopy(destination))
        return

    original = route[0]
    residual_pickups = _subtract_committed_actions(
        original.pickup_item_list or [], destination.pickup_item_list or []
    )
    residual_deliveries = _subtract_committed_actions(
        original.delivery_item_list or [], destination.delivery_item_list or []
    )
    route[0] = copy.deepcopy(destination)
    if residual_pickups or residual_deliveries:
        route.insert(1, Node(
            original.id, residual_deliveries, residual_pickups,
            original.arrive_time, original.leave_time, original.lng, original.lat,
        ))


def canonicalize_route(route: Iterable[Node],
                       preserve_destination_boundary: bool = False) -> List[Node]:
    """Merge consecutive visits to one factory without mutating a candidate.

    The JSON workflow merges such nodes immediately before dispatch.  Scoring a
    pre-merge route would otherwise charge an extra dock approach and could
    rank a different solution from the one the simulator receives.  Preserve
    the output workflow's service order: unload all delivery items, then load
    all pickup items at the merged factory visit.
    """
    normalized: List[Node] = []
    for index, node in enumerate(route):
        merge_with_previous = (
            normalized and normalized[-1].id == node.id and
            not (preserve_destination_boundary and index == 1)
        )
        if merge_with_previous:
            normalized[-1].pickup_item_list.extend(node.pickup_item_list or [])
            normalized[-1].delivery_item_list.extend(node.delivery_item_list or [])
            continue
        normalized.append(Node(
            node.id,
            list(node.delivery_item_list or []),
            list(node.pickup_item_list or []),
            node.arrive_time,
            node.leave_time,
            node.lng,
            node.lat,
        ))
    return normalized


def canonicalize_solution(
        solution: Mapping[str, List[Node]],
        id_to_vehicle: Optional[Mapping[str, Vehicle]] = None,
) -> Dict[str, List[Node]]:
    """Return the route representation that is archived and dispatched."""
    return {
        vehicle_id: canonicalize_route(
            route,
            bool(id_to_vehicle and id_to_vehicle.get(vehicle_id) and
                 id_to_vehicle[vehicle_id].des),
        )
        for vehicle_id, route in solution.items()
    }


def validate_solution(solution: Mapping[str, List[Node]],
                     context: EvaluationContext) -> bool:
    """Validate the dispatched dynamic DPDP invariants before evaluation."""
    normalized_solution = canonicalize_solution(solution, context.id_to_vehicle)
    if set(normalized_solution) != set(context.id_to_vehicle):
        return False

    seen_pickups: Set[str] = set()
    seen_deliveries: Set[str] = set()
    for vehicle_id, vehicle in context.id_to_vehicle.items():
        route = normalized_solution.get(vehicle_id, [])
        if vehicle.des:
            if not route or not destination_matches(route[0], vehicle.des):
                return False
        carrying = vehicle.carrying_items or []
        if not isFeasible(route, carrying, vehicle.board_capacity):
            return False
        for node in route:
            for item in node.pickup_item_list or []:
                if item.id in seen_pickups:
                    return False
                if item.pickup_factory_id != node.id:
                    return False
                seen_pickups.add(item.id)
            for item in node.delivery_item_list or []:
                if item.id in seen_deliveries:
                    return False
                if item.delivery_factory_id != node.id:
                    return False
                seen_deliveries.add(item.id)

    expected = set(context.all_items)
    carrying_ids = {
        item.id
        for vehicle in context.id_to_vehicle.values()
        for item in (vehicle.carrying_items or [])
    }
    # Items already completed are intentionally absent from the current scene.
    # All other items must have exactly the action(s) required by their state.
    for item_id in expected:
        item = context.all_items[item_id]
        if item_id in carrying_ids and item_id in seen_deliveries and item_id not in seen_pickups:
            continue
        if item_id not in seen_pickups or item_id not in seen_deliveries:
            return False
    if seen_pickups - expected or seen_deliveries - expected:
        return False
    return True


def _evaluate_solution_legacy(solution: Mapping[str, List[Node]],
                              context: EvaluationContext,
                              validate: bool = True) -> Objectives:
    """Deprecated compatibility evaluator; production uses the engine path.

    Arrival time is used for tardiness, matching the simulator history and
    the paper's Eq. (1).  Existing dock reservations are seeded from the
    current vehicle state, and each route is simulated as an event stream so
    vehicle identifiers do not need to be contiguous.
    """
    return evaluate_solution(solution, context, validate)

    normalized_solution = canonicalize_solution(solution, context.id_to_vehicle)
    if validate and not validate_solution(normalized_solution, context):
        return Objectives(math.inf, math.inf)

    intervals: Dict[str, List[Tuple[float, float]]] = {}
    for vehicle in context.id_to_vehicle.values():
        if (vehicle.cur_factory_id and
                vehicle.leave_time_at_current_factory > vehicle.gps_update_time):
            intervals.setdefault(vehicle.cur_factory_id, []).append((
                float(vehicle.arrive_time_at_current_factory),
                float(vehicle.leave_time_at_current_factory),
            ))

    # Heap entries are (arrival, deterministic vehicle order, vehicle id, idx,
    # current factory).  The route is evaluated in chronological order, while
    # preserving the same dock contention semantics as the simulator.
    heap: List[Tuple[float, int, str, int, Optional[str], float]] = []
    vehicle_ids = sorted(context.id_to_vehicle)
    rank = {vehicle_id: index for index, vehicle_id in enumerate(vehicle_ids)}
    total_distance = 0.0
    order_completion: Dict[str, float] = {}
    order_deadline: Dict[str, float] = {}

    for vehicle_id in vehicle_ids:
        vehicle = context.id_to_vehicle[vehicle_id]
        route = normalized_solution.get(vehicle_id, [])
        if not route:
            continue
        first = route[0]
        ready = float(max(vehicle.gps_update_time,
                          vehicle.leave_time_at_current_factory))
        distance, travel_time = _travel(context.route_map,
                                         vehicle.cur_factory_id, first.id)
        total_distance += distance
        arrival = ready + travel_time
        # A vehicle already driving toward a committed destination retains its
        # known arrival time.  A vehicle currently parked at a factory follows
        # the normal travel-time calculation used by the simulator.
        if (vehicle.des and first.id == vehicle.des.id and
                not vehicle.cur_factory_id and vehicle.des.arrive_time):
            arrival = float(vehicle.des.arrive_time)
        heapq.heappush(heap, (arrival, rank[vehicle_id], vehicle_id, 0,
                              vehicle.cur_factory_id, distance))

    while heap:
        arrival, _, vehicle_id, index, previous_factory, _ = heapq.heappop(heap)
        vehicle = context.id_to_vehicle[vehicle_id]
        route = normalized_solution[vehicle_id]
        node = route[index]

        factory = context.id_to_factory.get(node.id)
        dock_count = factory.dock_num if factory else 1
        service_duration = float(config.APPROACHING_DOCK_TIME + node.service_time)
        _, departure = _dock_start(
            intervals, node.id, arrival, service_duration, dock_count
        )

        for item in node.delivery_item_list or []:
            order_id = item.order_id or item.id
            order_completion[order_id] = max(
                order_completion.get(order_id, -math.inf), arrival
            )
            if item.committed_completion_time is not None:
                order_deadline.setdefault(order_id,
                                          float(item.committed_completion_time))

        next_index = index + 1
        if next_index >= len(route):
            continue
        next_node = route[next_index]
        distance, travel_time = _travel(context.route_map, node.id, next_node.id)
        total_distance += distance
        heapq.heappush(heap, (
            departure + travel_time, rank[vehicle_id], vehicle_id,
            next_index, node.id, distance,
        ))

    tardiness = sum(
        max(0.0, completion - order_deadline[order_id])
        for order_id, completion in order_completion.items()
        if order_id in order_deadline
    )
    divisor = max(1, len(context.id_to_vehicle))
    return Objectives(float(tardiness), float(total_distance) / divisor)


def evaluate_solution(solution: Mapping[str, List[Node]],
                      context: EvaluationContext,
                      validate: bool = True) -> Objectives:
    """Evaluate via the shared engine's f1, f2, and total-cost formulas.

    Validation and canonicalisation remain local to protect the immutable
    destination/LIFO contract. ``total_cost(..., mode='components')`` then
    runs one complete dock-aware fleet simulation and returns raw tardiness
    ``f1``, average distance ``f2``, and the scalar cost ``TC`` together.
    """
    normalized_solution = canonicalize_solution(solution, context.id_to_vehicle)
    if validate and not validate_solution(normalized_solution, context):
        return Objectives(math.inf, math.inf, math.inf)
    if not context.id_to_vehicle:
        return Objectives(0.0, 0.0, 0.0)

    try:
        tardiness, average_distance, scalar_cost = total_cost(
            context.id_to_vehicle, context.route_map, normalized_solution,
            mode="components", id_to_factory=context.id_to_factory,
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return Objectives(math.inf, math.inf, math.inf)

    if not all(math.isfinite(value) for value in (
            tardiness, average_distance, scalar_cost)):
        return Objectives(math.inf, math.inf, math.inf)
    return Objectives(
        float(tardiness),
        float(average_distance),
        float(scalar_cost),
    )


def tchebycheff(objectives: Objectives, weight: Tuple[float, float],
                ideal: Tuple[float, float]) -> float:
    if not math.isfinite(objectives.tardiness) or not math.isfinite(objectives.average_distance):
        return math.inf
    return max(
        float(weight[0]) * abs(objectives.tardiness - ideal[0]),
        float(weight[1]) * abs(objectives.average_distance - ideal[1]),
    )
