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
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

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


def _now() -> float:
    # ``algorithm_config`` exposes an epoch-based BEGIN_TIME; use the same
    # clock for the shared deadline so the output reserve is effective.
    return time.time()


def _deadline_reached(deadline: float) -> bool:
    return _now() >= deadline or config.is_timeout()


def _initialization_deadline(deadline: float) -> float:
    """Reserve part of an interval for MOEA/D evolution and mandatory output."""
    remaining = max(0.0, deadline - _now())
    budget = min(
        float(config.MOEAD_INITIALIZATION_MAX_SECONDS),
        remaining * float(config.MOEAD_INITIALIZATION_TIME_FRACTION),
    )
    return min(deadline, _now() + budget)


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


def _insert_unit_best(plan: Dict[str, List[Node]], unit: DispatchUnit,
                      context: EvaluationContext,
                      weight: Optional[Tuple[float, float]],
                      ideal: Optional[Tuple[float, float]],
                      deadline: float, use_tc: bool) -> Optional[Dict[str, List[Node]]]:
    nodes = _unit_nodes(unit, context.id_to_factory)
    if nodes is None:
        return None
    pickup, delivery = nodes
    best_plan: Optional[Dict[str, List[Node]]] = None
    best_value = math.inf

    for vehicle_id, vehicle in context.id_to_vehicle.items():
        route = plan.get(vehicle_id, [])
        start = 1 if vehicle.des else 0
        if vehicle.des and (not route or route[0].id != vehicle.des.id):
            continue
        for pickup_pos in range(start, len(route) + 1):
            for delivery_pos in range(pickup_pos + 1, len(route) + 2):
                if _deadline_reached(deadline):
                    return best_plan
                candidate_plan = copy.deepcopy(plan)
                candidate_route = candidate_plan[vehicle_id]
                candidate_route.insert(pickup_pos, copy.deepcopy(pickup))
                candidate_route.insert(delivery_pos, copy.deepcopy(delivery))
                feasible = isFeasible(
                    canonicalize_route(candidate_route, bool(vehicle.des)),
                    vehicle.carrying_items or [], vehicle.board_capacity,
                )
                if not feasible:
                    continue
                objectives = evaluate_solution(candidate_plan, context, validate=False)
                if not math.isfinite(objectives.tc):
                    continue
                value = objectives.tc if use_tc else tchebycheff(
                    objectives, weight or (0.5, 0.5), ideal or (0.0, 0.0)
                )
                if value < best_value:
                    best_value = value
                    best_plan = candidate_plan
    return best_plan


def initialize_population(base_plan: Dict[str, List[Node]], units: Sequence[DispatchUnit],
                          context: EvaluationContext, deadline: float) -> List[Chromosome]:
    population: List[Chromosome] = []
    if not units:
        return [_candidate(base_plan, context)]

    for _ in range(config.MOEAD_POPULATION_SIZE):
        if _deadline_reached(deadline):
            break
        plan = copy.deepcopy(base_plan)
        order = list(units)
        random.shuffle(order)
        complete = True
        for unit in order:
            next_plan = _insert_unit_best(plan, unit, context, None, None,
                                          deadline, use_tc=True)
            if next_plan is None:
                complete = False
                break
            plan = next_plan
        if complete:
            candidate = _candidate(plan, context)
            if math.isfinite(candidate._moead_tc):
                population.append(candidate)

    # Do not fill an incomplete population by cloning a candidate.  Clones
    # falsely advertise the N randomized CI starts required by MOEA/D while
    # providing no diversity.  The caller runs the remaining budget with the
    # actual set of feasible constructions instead.
    return population


def construct_safe_fallback(base_plan: Dict[str, List[Node]],
                            units: Sequence[DispatchUnit],
                            context: EvaluationContext) -> Optional[Chromosome]:
    """Build a complete feasible incumbent in linear time for deadline fallback.

    Each unit is appended as pickup then delivery after a route that already
    ends with an empty stack.  This is less greedy than exhaustive CI, but it
    preserves all DPDP constraints and prevents an interval from failing only
    because the full initial population could not be enumerated in time.
    """
    plan = copy.deepcopy(base_plan)
    for unit in units:
        nodes = _unit_nodes(unit, context.id_to_factory)
        if nodes is None:
            return None
        pickup, delivery = nodes
        load = sum(item.demand for item in unit.items)
        eligible = [
            vehicle_id for vehicle_id, vehicle in context.id_to_vehicle.items()
            if vehicle.board_capacity + 1e-9 >= load
        ]
        if not eligible:
            return None
        vehicle_id = min(eligible, key=lambda value: (len(plan.get(value, [])), value))
        plan.setdefault(vehicle_id, []).extend([
            copy.deepcopy(pickup), copy.deepcopy(delivery),
        ])
    candidate = _candidate(plan, context)
    return candidate if math.isfinite(candidate._moead_tc) else None


def _repair_selected_routes(plan: Dict[str, List[Node]],
                            context: EvaluationContext) -> Set[str]:
    """Remove duplicate/partial item occurrences after route inheritance."""
    seen_pickups: Set[str] = set()
    seen_deliveries: Set[str] = set()
    for vehicle_id in sorted(plan):
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
                if item.id in seen_deliveries and item.id in seen_pickups
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
    carrying_ids = {
        item.id
        for vehicle in context.id_to_vehicle.values()
        for item in (vehicle.carrying_items or [])
    }
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
    plan: Dict[str, List[Node]] = {}
    for vehicle_id in context.id_to_vehicle:
        source = parent1 if random.random() < 0.5 else parent2
        plan[vehicle_id] = copy.deepcopy(source.solution.get(vehicle_id, []))
    _ensure_destination_prefix(plan, context.id_to_vehicle)
    covered = _repair_selected_routes(plan, context)
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


def tabu_search(child: Chromosome, context: EvaluationContext,
                deadline: float) -> Chromosome:
    """Algorithm 4: one random single move per inner iteration, solution tabu list.

    Each inner iteration generates exactly one neighbour (one move) with a
    randomly selected operator, exactly as the pseudocode in the paper.  The
    tabu list stores canonical solution signatures: a candidate ``x_tmp`` is
    tabu when its complete route plan matches a recently visited solution.
    This follows the paper's solution-level ``x_tmp is non-tabu`` test rather
    than imposing a tabu restriction on a move attribute.
    """
    current = _copy_candidate(child)
    best = _copy_candidate(current)
    tabu_fifo: List[str] = [_signature(current)]
    tabu_set: Set[str] = set(tabu_fifo)

    for _ in range(config.MOEAD_TS_MAX_ITERATIONS):
        if _deadline_reached(deadline):
            break
        best_neighbor: Optional[Chromosome] = None
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
            if (best_neighbor is None or
                    candidate_objectives.tc < _evaluate(best_neighbor, context).tc):
                best_neighbor = candidate
        if best_neighbor is None:
            break
        current = best_neighbor
        current_signature = _signature(current)
        tabu_fifo.append(current_signature)
        tabu_set.add(current_signature)
        while len(tabu_fifo) > config.MOEAD_TS_TABU_LIST_SIZE:
            tabu_set.discard(tabu_fifo.pop(0))
        if _evaluate(current, context).tc < _evaluate(best, context).tc:
            best = _copy_candidate(current)
    return best


def run_moead_ts(base_plan: Dict[str, List[Node]], route_map,
                 id_to_vehicle: Dict[str, Vehicle], id_to_factory: Dict[str, Factory],
                 id_to_unlocated_items: Dict[str, OrderItem],
                 new_order_item_ids: Sequence[str]) -> Optional[Chromosome]:
    if config.BEGIN_TIME == 0:
        config.set_begin_time()
    deadline = config.search_deadline()

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
        restored = _candidate(plan, context)
        if not math.isfinite(restored._moead_tc):
            raise RuntimeError(
                "the restored dynamic scene is infeasible after preserving "
                "all committed destinations"
            )
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
    fallback = construct_safe_fallback(plan, units, context)
    population = initialize_population(
        plan, units, context, _initialization_deadline(deadline)
    )
    if not population:
        if fallback is None:
            raise RuntimeError(
                "MOEA/D-TS could not construct a feasible initial population "
                "or a safe fallback for this dynamic interval"
            )
        population = [_copy_candidate(fallback)]

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
    ideal = (
        min(value.tardiness for value in objective_values),
        min(value.average_distance for value in objective_values),
    )

    for generation in range(config.MOEAD_MAX_GENERATIONS):
        if _deadline_reached(deadline):
            break
        for index in range(population_size):
            if _deadline_reached(deadline):
                break
            pool = neighborhoods[index] if random.random() < config.MOEAD_DELTA else list(range(len(population)))
            left, right = _select_parents(pool)
            child = route_crossover(population[left], population[right], crossover_units,
                                    context, weights[index], ideal, deadline)
            if child is None:
                continue
            child = tabu_search(child, context, deadline)
            child_objectives = _evaluate(child, context)
            ideal = (
                min(ideal[0], child_objectives.tardiness),
                min(ideal[1], child_objectives.average_distance),
            )
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

    best = min(population, key=lambda candidate: (
        _evaluate(candidate, context).tc, _signature(candidate)
    ))
    return _copy_candidate(best)
