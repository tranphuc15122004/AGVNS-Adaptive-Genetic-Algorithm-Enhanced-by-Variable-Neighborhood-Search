"""MOEA/D--TS operators and orchestration primitives.

This module follows Algorithms 2--4 in the supplied paper.  The existing
scene restoration and JSON workflow remain outside this module; candidates
are ordinary ``Chromosome`` objects so the simulator adapter does not change.
"""

from dataclasses import dataclass
import copy
import math
import random
import time
from types import TracebackType
from typing import (
    Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Type,
)

from algorithm.Object import Chromosome, Factory, Node, OrderItem, Vehicle
from algorithm.engine import isFeasible, repair_restored_lifo_routes
import algorithm.algorithm_config as config
from .moead_objectives import (
    EvaluationContext, Objectives, canonicalize_route, canonicalize_solution,
    ensure_destination_prefix, evaluate_solution, tchebycheff, validate_solution,
)


@dataclass(frozen=True)
class DispatchUnit:
    item_ids: Tuple[str, ...]
    items: Tuple[OrderItem, ...]


# ---------------------------------------------------------------------------
# Component timing statistics
# ---------------------------------------------------------------------------
# Wall-clock accumulators for every major component of one ``run_moead_ts``
# interval.  ``_timed`` is a context manager, so wrapping a block with
# ``with _timed("name"):`` records both the total seconds and the number of
# calls; nested timings (e.g. ``ci_insert`` inside ``initialize_population``)
# are reported as sub-components and intentionally overlap their parents.
_TIMING_SECONDS: Dict[str, float] = {}
_TIMING_CALLS: Dict[str, int] = {}


class _timed:
    """Accumulate the wall-clock time spent inside a named component."""

    __slots__ = ("_name", "_start")

    def __init__(self, name: str) -> None:
        self._name = name

    def __enter__(self) -> "_timed":
        self._start = time.time()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        elapsed = time.time() - self._start
        _TIMING_SECONDS[self._name] = _TIMING_SECONDS.get(self._name, 0.0) + elapsed
        _TIMING_CALLS[self._name] = _TIMING_CALLS.get(self._name, 0) + 1


def _reset_timing() -> None:
    """Clear the accumulators before a new interval starts."""
    _TIMING_SECONDS.clear()
    _TIMING_CALLS.clear()


def _report_timing_statistics() -> Dict[str, Dict[str, float]]:
    """Print and return the per-component timing summary of this interval.

    The ``total`` row measures the full ``run_moead_ts`` interval.  All other
    rows are sorted by descending wall time.  ``ci_insert`` is a sub-component
    of both ``initialize_population`` and ``crossover``, so its share may be
    counted twice when summing the columns.
    """
    total = _TIMING_SECONDS.get("total", 0.0)
    names = sorted(
        (name for name in _TIMING_SECONDS if name != "total"),
        key=lambda name: _TIMING_SECONDS[name],
        reverse=True,
    )
    print("=== MOEA/D-TS component timing (seconds) ===")
    print("{:<22}{:>8}{:>12}{:>12}{:>10}".format(
        "component", "calls", "total", "avg", "% of run"))
    for name in names:
        seconds = _TIMING_SECONDS[name]
        calls = _TIMING_CALLS.get(name, 0)
        avg = seconds / calls if calls else 0.0
        percent = (100.0 * seconds / total) if total > 0 else 0.0
        print("{:<22}{:>8}{:>12.3f}{:>12.4f}{:>9.1f}%".format(
            name, calls, seconds, avg, percent))
    print("{:<22}{:>8}{:>12.3f}{:>12}{:>10}".format(
        "total", "", total, "", "100.0%"))
    print("NOTE: ci_insert is a sub-component of initialize_population/crossover")
    return {
        name: {
            "calls": float(_TIMING_CALLS.get(name, 0)),
            "seconds": _TIMING_SECONDS[name],
        }
        for name in _TIMING_SECONDS
    }


def _now() -> float:
    # ``algorithm_config`` exposes an epoch-based BEGIN_TIME; use the same
    # clock for the shared deadline so the output reserve is effective.
    return time.time()


def _deadline_reached(deadline: float) -> bool:
    return _now() >= deadline or config.is_timeout()


def _copy_candidate(candidate: Chromosome) -> Chromosome:
    result = Chromosome(
        copy.deepcopy(candidate.solution), candidate.route_map, candidate.id_to_vehicle
    )
    for name in (
            "_moead_objectives", "_moead_tc", "_moead_signature",
            "_ts_fitness", "_ts_signature", "_moead_context"):
        if hasattr(candidate, name):
            setattr(result, name, getattr(candidate, name))
    return result


def _candidate(plan: Dict[str, List[Node]], context: EvaluationContext,
               validate: bool = True) -> Chromosome:
    result = Chromosome(copy.deepcopy(plan), context.route_map, context.id_to_vehicle)
    result._moead_context = context
    _evaluate(result, context, validate=validate)
    return result


def _evaluate(candidate: Chromosome, context: EvaluationContext,
              validate: bool = True) -> Objectives:
    cached = getattr(candidate, "_moead_objectives", None)
    if cached is None or not validate:
        cached = evaluate_solution(candidate.solution, context, validate=validate)
        candidate._moead_objectives = cached
        candidate._moead_tc = cached.tc
    return cached


def _signature(candidate: Chromosome) -> str:
    if not hasattr(candidate, "_moead_signature"):
        parts = []
        canonical_solution = canonicalize_solution(
            candidate.solution, candidate.id_to_vehicle
        )
        for vehicle_id in sorted(canonical_solution):
            nodes = []
            for node in canonical_solution[vehicle_id]:
                nodes.append((
                    node.id,
                    tuple(item.id for item in node.pickup_item_list or []),
                    tuple(item.id for item in node.delivery_item_list or []),
                ))
            parts.append((vehicle_id, tuple(nodes)))
        candidate._moead_signature = repr(parts)
    return candidate._moead_signature


def _ensure_destination_prefix(plan: Dict[str, List[Node]],
                               id_to_vehicle: Mapping[str, Vehicle]) -> None:
    for vehicle_id, vehicle in id_to_vehicle.items():
        route = plan.setdefault(vehicle_id, [])
        ensure_destination_prefix(route, vehicle)


def _expand_plan_for_local_search(plan: Dict[str, List[Node]],
                                  id_to_vehicle: Mapping[str, Vehicle]) -> None:
    """Split mutable multi-action nodes into atomic visits for robust PDG moves.

    Delivery actions are emitted before pickup actions at a factory, exactly as
    the simulator serves a merged node.  The committed first destination is
    deliberately untouched because its action lists are immutable.
    """
    for vehicle_id, route in plan.items():
        vehicle = id_to_vehicle[vehicle_id]
        expanded: List[Node] = []
        for index, node in enumerate(route):
            if index == 0 and vehicle.des:
                expanded.append(node)
                continue
            for item in node.delivery_item_list or []:
                expanded.append(Node(
                    node.id, [item], [], node.arrive_time, node.leave_time,
                    node.lng, node.lat,
                ))
            for item in node.pickup_item_list or []:
                expanded.append(Node(
                    node.id, [], [item], node.arrive_time, node.leave_time,
                    node.lng, node.lat,
                ))
        plan[vehicle_id] = expanded


def _items_from_plan(plan: Mapping[str, List[Node]]) -> Dict[str, OrderItem]:
    result: Dict[str, OrderItem] = {}
    for route in plan.values():
        for node in route:
            for item in (node.pickup_item_list or []) + (node.delivery_item_list or []):
                result[item.id] = item
    return result


def build_dispatch_units(item_ids: Sequence[str],
                         items: Mapping[str, OrderItem],
                         capacity: float) -> List[DispatchUnit]:
    """Group an order into one unit, splitting only when capacity requires it."""
    by_order: Dict[str, List[OrderItem]] = {}
    for item_id in item_ids:
        item = items.get(item_id)
        if item is not None:
            by_order.setdefault(item.order_id or item.id, []).append(item)

    units: List[DispatchUnit] = []
    for order_id in sorted(by_order):
        order_items = sorted(by_order[order_id], key=lambda item: item.id)
        bins: List[List[OrderItem]] = []
        loads: List[float] = []
        for item in order_items:
            if item.demand > capacity:
                # No feasible DPDP unit can carry an item larger than a truck.
                bins.append([item])
                loads.append(float(item.demand))
                continue
            selected = None
            for index, load in enumerate(loads):
                if load + item.demand <= capacity + 1e-9:
                    selected = index
                    break
            if selected is None:
                bins.append([item])
                loads.append(float(item.demand))
            else:
                bins[selected].append(item)
                loads[selected] += float(item.demand)
        for grouped in bins:
            units.append(DispatchUnit(
                tuple(item.id for item in grouped), tuple(grouped)
            ))
    return units


def _unit_nodes(unit: DispatchUnit, factories: Mapping[str, Factory]) -> Optional[Tuple[Node, Node]]:
    if not unit.items:
        return None
    pickup = unit.items[0].pickup_factory_id
    delivery = unit.items[0].delivery_factory_id
    if any(item.pickup_factory_id != pickup or item.delivery_factory_id != delivery
           for item in unit.items):
        return None
    pickup_factory = factories.get(pickup)
    delivery_factory = factories.get(delivery)
    if pickup_factory is None or delivery_factory is None:
        return None
    return (
        Node(pickup, [], list(unit.items), None, None,
             pickup_factory.lng, pickup_factory.lat),
        Node(delivery, list(reversed(unit.items)), [], None, None,
             delivery_factory.lng, delivery_factory.lat),
    )


def _ci_pair_positions(route: Sequence[Node], vehicle: Vehicle,
                       pickup: Node) -> Iterable[Tuple[int, int, List[Node]]]:
    """Yield the pickup/delivery positions from ``dispatch_nodePair``'s CI.

    This is the maintainable equivalent of the legacy
    ``model_nodes_num > 8`` branch in :mod:`algorithm.engine`.  For each
    pickup position it considers every later delivery position.  The actual
    LIFO test remains in ``_insert_unit_best`` because a route may contain
    merged multi-item nodes; inspecting only the first item of a node (as the
    old code does) is not sufficient for those routes.

    The old small-model branches permute existing pairs.  That is unsuitable
    while constructing a dynamic MOEA/D individual: it could reorder already
    accepted work or the committed first destination.  We therefore use the
    pair-insertion branch for *all* route sizes, including short routes.
    """
    # The committed destination is an immutable prefix in the dynamic scene.
    # This intentionally differs from the historical condition that allowed
    # insertion at index 0 when pickup and destination used the same factory.
    first_mutable = 1 if vehicle.des else 0
    route_size = len(route)
    for pickup_pos in range(first_mutable, route_size + 1):
        route_with_pickup = list(route)
        route_with_pickup.insert(pickup_pos, pickup)
        for delivery_pos in range(pickup_pos + 1, route_size + 2):
            yield pickup_pos, delivery_pos, route_with_pickup


def _ci_candidate_route(route_with_pickup: Sequence[Node], delivery: Node,
                        delivery_pos: int) -> List[Node]:
    """Insert a pair using the same index convention as ``dispatch_nodePair``.

    ``delivery_pos`` is an index in the route *after* pickup has been
    inserted.  Building one route-with-pickup per pickup position lets the CI
    loop avoid copying the complete fleet plan for every ``(i, j)`` pair.
    """
    candidate_route = list(route_with_pickup)
    candidate_route.insert(delivery_pos, delivery)
    return candidate_route


def _insert_unit_best_impl(plan: Dict[str, List[Node]], unit: DispatchUnit,
                           context: EvaluationContext,
                           weight: Optional[Tuple[float, float]],
                           ideal: Optional[Tuple[float, float]],
                           deadline: float, use_tc: bool) -> Optional[Dict[str, List[Node]]]:
    """Cheapest insertion (CI) of one pickup--delivery dispatch unit.

    For initial MOEA/D individuals this follows the large-route CI path of
    ``dispatch_nodePair``: enumerate each vehicle and each ordered insertion
    pair ``(pickup_pos, delivery_pos)``, then retain the globally cheapest
    feasible solution.  The objective call is fleet-wide rather than the
    legacy route-only call, so dock contention and lateness caused on other
    routes are part of the insertion decision.

    The candidate route is canonicalised before its LIFO/capacity test.  This
    is essential because adjacent same-factory nodes are merged before the
    simulator sees them, which changes their delivery-then-pickup action
    order.  Only the selected route is copied for a trial; other routes are
    read-only throughout CI.
    """
    nodes = _unit_nodes(unit, context.id_to_factory)
    if nodes is None:
        return None
    pickup, delivery = nodes
    best_plan: Optional[Dict[str, List[Node]]] = None
    best_value = math.inf

    for vehicle_id, vehicle in context.id_to_vehicle.items():
        route = plan.get(vehicle_id, [])
        if vehicle.des and (not route or route[0].id != vehicle.des.id):
            # The restored scene is malformed for this vehicle.  Do not make
            # CI appear feasible by silently dropping its locked destination.
            continue

        for _pickup_pos, delivery_pos, route_with_pickup in _ci_pair_positions(
                route, vehicle, pickup):
            if _deadline_reached(deadline):
                # A partial CI scan is not a completed initialization
                # sequence.  Algorithm 2 discards that individual instead of
                # accepting the best route found before the deadline.
                return None

            candidate_route = _ci_candidate_route(
                route_with_pickup, delivery, delivery_pos
            )
            normalized_route = canonicalize_route(
                candidate_route, bool(vehicle.des)
            )
            if not isFeasible(
                    normalized_route, vehicle.carrying_items or [],
                    vehicle.board_capacity):
                continue

            # ``evaluate_solution`` never mutates its plan argument.  A
            # shallow fleet copy is sufficient here and avoids an O(fleet)
            # deepcopy for every CI position, while the winning route is
            # copied before it becomes the next construction state.
            candidate_plan = dict(plan)
            candidate_plan[vehicle_id] = candidate_route
            objectives = evaluate_solution(candidate_plan, context, validate=False)
            if not math.isfinite(objectives.tc):
                continue
            value = objectives.tc if use_tc else tchebycheff(
                objectives, weight or (0.5, 0.5), ideal or (0.0, 0.0)
            )
            if value < best_value:
                best_value = value
                best_plan = dict(plan)
                best_plan[vehicle_id] = copy.deepcopy(candidate_route)

    return best_plan


def _insert_unit_best(plan: Dict[str, List[Node]], unit: DispatchUnit,
                      context: EvaluationContext,
                      weight: Optional[Tuple[float, float]],
                      ideal: Optional[Tuple[float, float]],
                      deadline: float, use_tc: bool) -> Optional[Dict[str, List[Node]]]:
    """Timed wrapper around the cheapest-insertion implementation.

    ``ci_insert`` is a sub-component of both population initialisation and
    route crossover, so it is measured and reported separately from the
    top-level phases.
    """
    with _timed("ci_insert"):
        return _insert_unit_best_impl(
            plan, unit, context, weight, ideal, deadline, use_tc
        )


def initialize_population(base_plan: Dict[str, List[Node]], units: Sequence[DispatchUnit],
                          context: EvaluationContext, deadline: float) -> List[Chromosome]:
    """Build the valid CI members produced by ``N`` shuffled order sequences.

    Algorithm 2 specifies ``N = 6`` randomized construction sequences.  Each
    sequence is built exclusively by cheapest insertion from the restored
    scene.  If CI cannot finish, or the completed candidate fails the full
    capacity/LIFO/dock-aware validation, that individual is discarded.  No
    alternate constructor is allowed to replace it.
    """
    population: List[Chromosome] = []
    target_size = int(config.MOEAD_POPULATION_SIZE)
    if target_size <= 0:
        raise ValueError("MOEAD_POPULATION_SIZE must be positive")
    if not units:
        # No new orders means all N starts necessarily represent the restored
        # scene.  Keep independent objects so later MOEA/D updates cannot
        # accidentally alias one population member to another.
        return [_candidate(base_plan, context) for _ in range(target_size)]

    for _ in range(target_size):
        plan = copy.deepcopy(base_plan)
        order = list(units)
        random.shuffle(order)
        complete = True
        if _deadline_reached(deadline):
            complete = False
        else:
            for unit in order:
                next_plan = _insert_unit_best(plan, unit, context, None, None,
                                              deadline, use_tc=True)
                if next_plan is None or _deadline_reached(deadline):
                    complete = False
                    break
                plan = next_plan
        if complete:
            candidate = _candidate(plan, context)
            if math.isfinite(candidate._moead_tc):
                population.append(candidate)

    return population


def _paper_vehicle_order(id_to_vehicle: Mapping[str, Vehicle]) -> List[str]:
    """Return the numeric ``r_1, ..., r_K`` order used by Algorithm 3.

    A lexical sort would put ``V_10`` before ``V_2`` and therefore retain a
    different route when the repair step meets a duplicate order.  Vehicle IDs
    in the Huawei input use a numeric suffix, while the fallback keeps the
    result deterministic for other identifiers.
    """
    def sort_key(vehicle_id: str) -> Tuple[int, str, int, str]:
        prefix, separator, suffix = vehicle_id.rpartition("_")
        if separator and suffix.isdigit():
            return 0, prefix, int(suffix), vehicle_id
        return 1, vehicle_id, 0, vehicle_id

    return sorted(id_to_vehicle, key=sort_key)


def _repair_selected_routes(
        plan: Dict[str, List[Node]], context: EvaluationContext,
        vehicle_order: Optional[Sequence[str]] = None,
) -> Set[str]:
    """Repair the partial child after one Algorithm-3 route copy.

    ``vehicle_order`` is the order in which routes have entered ``x_child``.
    Thus the first copied route owns a duplicate order, exactly as the repair
    in each iteration of Algorithm 3.  Actions, rather than whole ``Node``
    objects, are de-duplicated because a simulator node can merge several
    independent orders at one factory.
    """
    ordered_vehicle_ids = list(vehicle_order or _paper_vehicle_order(
        context.id_to_vehicle
    ))
    known_vehicle_ids = set(ordered_vehicle_ids)
    ordered_vehicle_ids.extend(
        vehicle_id for vehicle_id in plan
        if vehicle_id not in known_vehicle_ids
    )
    carrying_ids = {
        item.id
        for vehicle in context.id_to_vehicle.values()
        for item in (vehicle.carrying_items or [])
    }
    seen_pickups: Set[str] = set()
    seen_deliveries: Set[str] = set()
    for vehicle_id in ordered_vehicle_ids:
        if vehicle_id not in plan:
            continue
        vehicle = context.id_to_vehicle[vehicle_id]
        route = plan[vehicle_id]
        repaired: List[Node] = []
        for index, node in enumerate(route):
            pickups = [item for item in node.pickup_item_list or []
                       if item.id not in seen_pickups]
            deliveries = [item for item in node.delivery_item_list or []
                          if item.id not in seen_deliveries]
            if index == 0 and vehicle.des:
                repaired.append(copy.deepcopy(node))
                seen_pickups.update(item.id for item in pickups)
                seen_deliveries.update(item.id for item in deliveries)
            elif pickups or deliveries:
                repaired.append(Node(node.id, deliveries, pickups,
                                     node.arrive_time, node.leave_time,
                                     node.lng, node.lat))
                seen_pickups.update(item.id for item in pickups)
                seen_deliveries.update(item.id for item in deliveries)
        plan[vehicle_id] = repaired

    # A partial pair is unsafe: remove both actions so the full dispatch unit
    # can be reinserted below.
    for vehicle_id, route in plan.items():
        fixed = 1 if context.id_to_vehicle[vehicle_id].des else 0
        for index in range(fixed, len(route)):
            route[index].pickup_item_list[:] = [
                item for item in route[index].pickup_item_list
                if item.id in seen_deliveries and item.id in seen_pickups
            ]
            route[index].delivery_item_list[:] = [
                item for item in route[index].delivery_item_list
                # A currently carried item legitimately has delivery only.
                # It must not be removed then reinserted as a new pickup.
                if (item.id in carrying_ids or
                    (item.id in seen_deliveries and item.id in seen_pickups))
            ]
        plan[vehicle_id] = [
            node for index, node in enumerate(route)
            if index < fixed or node.pickup_item_list or node.delivery_item_list
        ]

    # Route inheritance is performed independently per vehicle.  A pickup
    # from parent 1 and its delivery from parent 2 would otherwise create a
    # split pair.  Remove such partial assignments and let the CI repair step
    # insert the complete unit on one vehicle.
    locations: Dict[str, Dict[str, Set[str]]] = {}
    for vehicle_id, route in plan.items():
        for node in route:
            for item in node.pickup_item_list or []:
                locations.setdefault(item.id, {"pickup": set(), "delivery": set()})[
                    "pickup"].add(vehicle_id)
            for item in node.delivery_item_list or []:
                locations.setdefault(item.id, {"pickup": set(), "delivery": set()})[
                    "delivery"].add(vehicle_id)
    split_items = {
        item_id for item_id, sides in locations.items()
        if item_id not in carrying_ids and not (
            sides["pickup"] and sides["delivery"] and
            sides["pickup"] == sides["delivery"]
        )
    }
    if split_items:
        for vehicle_id, route in plan.items():
            fixed = 1 if context.id_to_vehicle[vehicle_id].des else 0
            for node in route[fixed:]:
                node.pickup_item_list[:] = [
                    item for item in node.pickup_item_list
                    if item.id not in split_items
                ]
                node.delivery_item_list[:] = [
                    item for item in node.delivery_item_list
                    if item.id not in split_items
                ]
            plan[vehicle_id] = [
                node for index, node in enumerate(route)
                if index < fixed or node.pickup_item_list or node.delivery_item_list
            ]

    complete = {
        item_id for item_id, sides in locations.items()
        if ((sides["pickup"] and sides["delivery"] and
             sides["pickup"] == sides["delivery"] and item_id not in split_items) or
            (item_id in carrying_ids and sides["delivery"] and
             not sides["pickup"]))
    }
    return complete


def route_crossover(parent1: Chromosome, parent2: Chromosome,
                    units: Sequence[DispatchUnit], context: EvaluationContext,
                    weight: Tuple[float, float], ideal: Tuple[float, float],
                    deadline: float) -> Optional[Chromosome]:
    """Algorithm 3 route-based crossover with dynamic-scene safeguards.

    ``x_child`` starts empty.  At each ``k`` exactly one route ``r_k`` is
    copied from either parent and the *partial* child is repaired immediately.
    Once all ``K`` routes are present, the unassigned order set is reinserted
    with the current subproblem's Tchebycheff value (Eq. 12).
    """
    vehicle_order = _paper_vehicle_order(context.id_to_vehicle)
    plan: Dict[str, List[Node]] = {
        vehicle_id: [] for vehicle_id in vehicle_order
    }
    covered: Set[str] = set()

    # Lines 3--6: copy r_k then repair x_child before choosing r_(k + 1).
    for vehicle_id in vehicle_order:
        if _deadline_reached(deadline):
            return None
        source = parent1 if random.random() < 0.5 else parent2
        plan[vehicle_id] = copy.deepcopy(source.solution.get(vehicle_id, []))
        # A parent may have been archived without the fixed destination node.
        # Materialise it for this route only; unselected routes must stay empty
        # until their turn in the Algorithm-3 loop.
        ensure_destination_prefix(plan[vehicle_id], context.id_to_vehicle[vehicle_id])
        covered = _repair_selected_routes(plan, context, vehicle_order)

    # Line 7: every non-complete action in the dynamic scene belongs to U.
    all_items = set(context.all_items)
    missing = all_items - covered
    missing_units = []
    for unit in units:
        if any(item_id in missing for item_id in unit.item_ids):
            missing_units.append(DispatchUnit(
                tuple(item_id for item_id in unit.item_ids if item_id in missing),
                tuple(item for item in unit.items if item.id in missing),
            ))
    # Existing route items that are not in `units` are represented as one-item
    # units, preserving the dynamic scene instead of silently dropping them.
    known = {item_id for unit in missing_units for item_id in unit.item_ids}
    for item_id in sorted(missing - known):
        item = context.all_items[item_id]
        missing_units.append(DispatchUnit((item_id,), (item,)))

    for unit in missing_units:
        if _deadline_reached(deadline):
            return None
        next_plan = _insert_unit_best(plan, unit, context, weight, ideal,
                                      deadline, use_tc=False)
        if next_plan is None:
            return None
        plan = next_plan
    result = _candidate(plan, context)
    return result if math.isfinite(result._moead_tc) else None


def uniform_weights(size: int) -> List[Tuple[float, float]]:
    if size <= 1:
        return [(0.5, 0.5)]
    return [(index / float(size - 1), 1.0 - index / float(size - 1))
            for index in range(size)]


def build_neighborhoods(weights: Sequence[Tuple[float, float]], size: int) -> List[List[int]]:
    result: List[List[int]] = []
    for index, weight in enumerate(weights):
        ordered = sorted(
            range(len(weights)),
            key=lambda other: (
                (weight[0] - weights[other][0]) ** 2 +
                (weight[1] - weights[other][1]) ** 2,
                other,
            ),
        )
        result.append(ordered[:max(1, min(size, len(weights)))])
    return result


def _select_parents(pool: Sequence[int]) -> Tuple[int, int]:
    if len(pool) >= 2:
        return tuple(random.sample(list(pool), 2))  # type: ignore
    return pool[0], pool[0]


_TS_OPERATOR_NAMES = (
    "pdg_exchange",      # couple-exchange
    "block_exchange",    # block-exchange
    "pdg_relocate",      # couple-relocate
    "block_relocate",    # block-relocate
)


def _sample_single_move(operator_name: str, current: Chromosome,
                        deadline: float) -> Optional[Tuple[Chromosome, Tuple[str, ...]]]:
    """Construct one random single-move neighbour for Algorithm 4."""
    from algorithm.Test_algorithm.MOEAD_TS import (
        sample_block_exchange_move,
        sample_block_relocate_move,
        sample_pdg_exchange_move,
        sample_pdg_relocate_move,
    )
    samplers = {
        "pdg_exchange": sample_pdg_exchange_move,
        "block_exchange": sample_block_exchange_move,
        "pdg_relocate": sample_pdg_relocate_move,
        "block_relocate": sample_block_relocate_move,
    }
    return samplers[operator_name](current, deadline)


def _update_solution_tabu(tabu_fifo: List[str], tabu_set: Set[str],
                          signature: str) -> None:
    """Record a visited solution without corrupting FIFO/set consistency.

    Algorithm 4 updates the tabu list after assigning ``x_current``.  When no
    neighbour improves on ``x_current``, that assignment is a self-transition.
    Keeping a second copy of the same signature in a FIFO plus a plain set
    would make eviction incorrectly remove a signature that is still present.
    A solution is therefore recorded once for its tenure; this has the same
    tabu membership semantics and keeps the bounded list well-defined.
    """
    if signature in tabu_set:
        return
    tabu_fifo.append(signature)
    tabu_set.add(signature)
    while len(tabu_fifo) > config.MOEAD_TS_TABU_LIST_SIZE:
        expired = tabu_fifo.pop(0)
        tabu_set.discard(expired)


def _has_movable_pdg_unit(candidate: Chromosome) -> bool:
    """Return whether any Algorithm-4 operator can alter ``candidate``.

    All four operators work on a pickup--delivery unit.  If extraction yields
    none, every sampler would immediately return ``None`` for every
    ``MaxIter × NeighborThreshold`` attempt.  Returning the child unchanged is
    therefore an exact empty-neighbourhood termination, not a heuristic early
    acceptance rule.
    """
    from algorithm.Test_algorithm.MOEAD_TS import _extract_pdg_units
    return bool(_extract_pdg_units(candidate.solution, candidate.id_to_vehicle))


def tabu_search(child: Chromosome, context: EvaluationContext,
                deadline: float) -> Chromosome:
    """Algorithm 4: strict-improvement tabu search over four move operators.

    Each inner iteration generates exactly one neighbour (one move) with a
    randomly selected operator, exactly as the pseudocode in the paper.  The
    tabu list stores canonical solution signatures: a candidate ``x_tmp`` is
    tabu when its complete route plan matches a recently visited solution.
    This follows the paper's solution-level ``x_tmp is non-tabu`` test rather
    than imposing a tabu restriction on a move attribute.

    Critically, line 4 sets ``x_bestNeighbor = x_current``.  Therefore a
    sampled neighbour replaces that baseline only when it has a strictly lower
    ``TC``.  ``x_current`` never moves to a worse solution in the published
    pseudocode; crossover and random operator sampling provide its diversity.
    """
    current = _copy_candidate(child)
    best = _copy_candidate(current)
    if not _has_movable_pdg_unit(current):
        return best

    tabu_fifo: List[str] = []
    tabu_set: Set[str] = set()
    _update_solution_tabu(tabu_fifo, tabu_set, _signature(current))

    stagnation = 0
    for _ in range(config.MOEAD_TS_MAX_ITERATIONS):
        if _deadline_reached(deadline):
            break
        # Algorithm 4, line 4: preserve the current solution unless a strictly
        # better non-tabu neighbour is found during NeighborThreshold samples.
        best_neighbor = current
        best_neighbor_tc = _evaluate(best_neighbor, context).tc
        current_tc = best_neighbor_tc
        for _ in range(config.MOEAD_TS_NEIGHBOR_THRESHOLD):
            if _deadline_reached(deadline):
                break
            operator_name = random.choice(_TS_OPERATOR_NAMES)
            sampled = _sample_single_move(operator_name, current, deadline)
            if sampled is None:
                continue
            candidate, _move_key = sampled
            if _signature(candidate) in tabu_set:
                continue
            candidate_objectives = _evaluate(candidate, context)
            if not math.isfinite(candidate_objectives.tc):
                continue
            if candidate_objectives.tc < best_neighbor_tc:
                best_neighbor = candidate
                best_neighbor_tc = candidate_objectives.tc

        # Lines 12--16: update the TS-best, then make the selected neighbour
        # (or the unchanged current baseline) the new current solution.
        if best_neighbor_tc < _evaluate(best, context).tc:
            best = _copy_candidate(best_neighbor)
        current = _copy_candidate(best_neighbor)
        _update_solution_tabu(tabu_fifo, tabu_set, _signature(current))

        # Early stopping (implementation choice, not in the paper): ``best_neighbor``
        # is only replaced on a strict TC improvement, so ``best_neighbor_tc ==
        # current_tc`` means this outer iteration found no better neighbour and
        # ``x_current`` was left unchanged.  After ``MOEAD_TS_STAGNATION_LIMIT``
        # consecutive such iterations, resampling the same neighbourhood is
        # unlikely to help, so stop the outer loop.  Set the limit to 0 to run
        # exactly ``MOEAD_TS_MAX_ITERATIONS`` as the paper specifies.
        if best_neighbor_tc < current_tc:
            stagnation = 0
        else:
            stagnation += 1
            if (config.MOEAD_TS_STAGNATION_LIMIT > 0 and
                    stagnation >= config.MOEAD_TS_STAGNATION_LIMIT):
                break
    return best


def _run_moead_ts_impl(base_plan: Dict[str, List[Node]], route_map,
                       id_to_vehicle: Dict[str, Vehicle], id_to_factory: Dict[str, Factory],
                       id_to_unlocated_items: Dict[str, OrderItem],
                       new_order_item_ids: Sequence[str]) -> Optional[Chromosome]:
    if config.BEGIN_TIME == 0:
        config.set_begin_time()
    deadline = config.search_deadline()

    with _timed("scene_restore"):
        plan = copy.deepcopy(base_plan)
        _ensure_destination_prefix(plan, id_to_vehicle)
        if not repair_restored_lifo_routes(plan, id_to_vehicle):
            raise RuntimeError(
                "the restored dynamic scene cannot be repaired to a valid LIFO route"
            )
        _expand_plan_for_local_search(plan, id_to_vehicle)
        # Every action in the restored scene, including a committed destination,
        # belongs to the validation contract.  Excluding the prefix allowed a
        # same-factory node to replace its immutable item lists undetected.
        all_items = _items_from_plan(plan)
        for vehicle in id_to_vehicle.values():
            for item in vehicle.carrying_items or []:
                all_items[item.id] = item
        context = EvaluationContext(route_map, id_to_vehicle, id_to_factory, all_items)
        locked_ids = {
            item.id
            for vehicle in id_to_vehicle.values()
            for item in ((vehicle.carrying_items or []) +
                         ((vehicle.des.pickup_item_list or []) if vehicle.des else []) +
                         ((vehicle.des.delivery_item_list or []) if vehicle.des else []))
        }
        effective_new_ids = [item_id for item_id in new_order_item_ids
                             if item_id not in locked_ids]
    if not effective_new_ids:
        # Retain the N-member MOEA/D population invariant even when the
        # dynamic interval brings no new orders.  The six solutions are
        # necessarily equivalent restored scenes, but they are independent
        # chromosomes and the reported initial-population statistic remains
        # consistent with all other intervals.
        with _timed("initialize_population"):
            population = initialize_population(plan, (), context, deadline)
        if not all(math.isfinite(candidate._moead_tc) for candidate in population):
            raise RuntimeError(
                "the restored dynamic scene is infeasible after preserving "
                "all committed destinations"
            )
        initial_population_mean_tc = sum(
            candidate._moead_tc for candidate in population
        ) / float(len(population))
        restored = _copy_candidate(population[0])
        restored._moead_initial_population_mean_tc = initial_population_mean_tc
        restored._moead_initial_population_size = len(population)
        return restored
    missing_input_ids = [
        item_id for item_id in effective_new_ids
        if item_id not in id_to_unlocated_items
    ]
    if missing_input_ids:
        raise ValueError(
            "new order items are absent from the unlocated-item input: {}".format(
                ", ".join(sorted(missing_input_ids))
            )
        )
    for item_id in effective_new_ids:
        all_items[item_id] = id_to_unlocated_items[item_id]
    units = build_dispatch_units(
        effective_new_ids, id_to_unlocated_items,
        min((vehicle.board_capacity for vehicle in id_to_vehicle.values()), default=0),
    )
    print(f"Number of unlocated units: {len(units)}")
    with _timed("initialize_population"):
        # The paper imposes no separate initialization time limit: Algorithm 2
        # builds the N CI sequences from the restored scene within the single
        # 600 s runtime budget, and the only stopping criteria are the
        # 50-iteration cap and the 600 s deadline.  Passing the full search
        # deadline lets CI finish on large instances instead of truncating
        # the population when a self-imposed initialization slice expires.
        population = initialize_population(plan, units, context, deadline)
    if not population:
        raise RuntimeError(
            "MOEA/D-TS initialization discarded every CI sequence; "
            "no feasible initial solution remains"
        )

    carrying_ids = {
        item.id
        for vehicle in id_to_vehicle.values()
        for item in (vehicle.carrying_items or [])
    }
    crossover_units = build_dispatch_units(
        [item_id for item_id in context.all_items if item_id not in carrying_ids],
        context.all_items,
        min((vehicle.board_capacity for vehicle in id_to_vehicle.values()), default=0),
    )

    population_size = len(population)
    weights = uniform_weights(population_size)
    neighborhoods = build_neighborhoods(weights, config.MOEAD_NEIGHBOR_SIZE)
    objective_values = [_evaluate(candidate, context) for candidate in population]
    initial_population_mean_tc = sum(
        value.tc for value in objective_values
    ) / float(population_size)
    ideal = (
        min(value.tardiness for value in objective_values),
        min(value.average_distance for value in objective_values),
    )

    with _timed("evolution"):
        stagnant_generations = 0
        for generation in range(config.MOEAD_MAX_GENERATIONS):
            if _deadline_reached(deadline):
                break
            generation_replacements = 0
            for index in range(population_size):
                if _deadline_reached(deadline):
                    break
                pool = neighborhoods[index] if random.random() < config.MOEAD_DELTA else list(range(len(population)))
                left, right = _select_parents(pool)
                with _timed("crossover"):
                    child = route_crossover(population[left], population[right], crossover_units,
                                            context, weights[index], ideal, deadline)
                if child is None:
                    continue
                with _timed("tabu_search"):
                    child = tabu_search(child, context, deadline)
                child_objectives = _evaluate(child, context)
                ideal = (
                    min(ideal[0], child_objectives.tardiness),
                    min(ideal[1], child_objectives.average_distance),
                )
                with _timed("replacement_update"):
                    replacements = 0
                    replacement_pool = list(pool)
                    random.shuffle(replacement_pool)
                    for candidate_index in replacement_pool:
                        old_objectives = _evaluate(population[candidate_index], context)
                        if (tchebycheff(child_objectives, weights[candidate_index], ideal) <
                                tchebycheff(old_objectives, weights[candidate_index], ideal)):
                            population[candidate_index] = _copy_candidate(child)
                            replacements += 1
                            if replacements >= config.MOEAD_MAX_REPLACEMENTS:
                                break
                generation_replacements += replacements

            # Early stopping (implementation choice, not in the paper): when a
            # full generation performs zero replacements, no subproblem's current
            # solution was improved, so the population is stagnant.  Stop after
            # ``MOEAD_STAGNATION_GENERATIONS`` such generations.  Set it to 0 to
            # run exactly ``MOEAD_MAX_GENERATIONS`` as the paper specifies.
            if config.MOEAD_STAGNATION_GENERATIONS > 0:
                if generation_replacements == 0:
                    stagnant_generations += 1
                    if stagnant_generations >= config.MOEAD_STAGNATION_GENERATIONS:
                        break
                else:
                    stagnant_generations = 0

    best = min(population, key=lambda candidate: (
        _evaluate(candidate, context).tc, _signature(candidate)
    ))
    result = _copy_candidate(best)
    # ``main.py`` reports this as TC before optimization.  Keep the statistic
    # on the returned chromosome so logging does not require a second,
    # different construction of the initial population.
    result._moead_initial_population_mean_tc = initial_population_mean_tc
    result._moead_initial_population_size = population_size
    return result


def run_moead_ts(base_plan: Dict[str, List[Node]], route_map,
                 id_to_vehicle: Dict[str, Vehicle], id_to_factory: Dict[str, Factory],
                 id_to_unlocated_items: Dict[str, OrderItem],
                 new_order_item_ids: Sequence[str]) -> Optional[Chromosome]:
    """Public MOEA/D--TS entry point with per-component timing statistics.

    Delegates to :func:`_run_moead_ts_impl` while measuring the total wall
    time and reporting the per-component breakdown.  The timing summary is
    stored on the returned chromosome as ``_moead_timing_statistics`` so the
    simulator adapter can log it without re-instrumenting the search.
    """
    if config.BEGIN_TIME == 0:
        config.set_begin_time()
    _reset_timing()
    with _timed("total"):
        result = _run_moead_ts_impl(
            base_plan, route_map, id_to_vehicle, id_to_factory,
            id_to_unlocated_items, new_order_item_ids,
        )
    if result is not None:
        result._moead_timing_statistics = _report_timing_statistics()
    return result
