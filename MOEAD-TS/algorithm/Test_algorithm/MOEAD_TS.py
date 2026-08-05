"""MOEA/D--TS public adapter, single-move samplers and route-level operators.

The public ``MOEAD_TS`` function delegates to ``moead_core``.  Algorithm 4
(``tabu_search``) generates exactly one neighbour per inner iteration by
sampling a random single move from one of the four operators (couple-exchange,
block-exchange, couple-relocate, block-relocate).  The tabu list itself is
solution-based and is maintained by ``moead_core``.  The ``generate_*_neighbors``
enumerators below are kept for focused regression tests of DPDP move invariants.
"""

import copy
import hashlib
from itertools import combinations
import math
import random
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from algorithm.Object import Chromosome, Factory, Node, OrderItem, Vehicle
import algorithm.algorithm_config as config
from algorithm.engine import get_route_after, isFeasible
from algorithm.Test_algorithm.moead_objectives import (
    canonicalize_route, destination_matches, ensure_destination_prefix,
)


SolutionSignature = bytes

# A generated move descriptor: (operator kind, moved unit(s), target vehicle, positions).
# It is returned for traceability; Algorithm 4 tabus complete solutions in moead_core.
MoveKey = Tuple[str, ...]

_ACTIVE_OBJECTIVE_CONTEXT = None


@dataclass(frozen=True)
class PdgUnit:
    """One pickup-delivery supernode recognised by the existing LS code."""
    key: Tuple[str, ...]
    vehicle_id: str
    pickup_indices: Tuple[int, ...]
    delivery_indices: Tuple[int, ...]

    @property
    def start_index(self) -> int:
        return min(self.pickup_indices)

    @property
    def end_index(self) -> int:
        return max(self.delivery_indices)


def solution_signature(solution: Dict[str, List[Node]]) -> SolutionSignature:
    """Return a compact solution identity for neighbourhood de-duplication."""
    route_after = get_route_after(solution, {})
    return hashlib.blake2b(
        route_after.encode("utf-8"),
        digest_size=16,
    ).digest()


def _cached_signature(candidate: Chromosome) -> SolutionSignature:
    """Return a candidate's immutable neighbourhood signature."""
    signature = getattr(candidate, "_ts_signature", None)
    if signature is None:
        signature = solution_signature(candidate.solution)
        setattr(candidate, "_ts_signature", signature)
    return signature


def _cached_fitness(candidate: Chromosome) -> float:
    """Evaluate a TS candidate once; its solution is immutable after creation."""
    if _ACTIVE_OBJECTIVE_CONTEXT is not None:
        from algorithm.Test_algorithm.moead_objectives import evaluate_solution
        objective = evaluate_solution(candidate.solution, _ACTIVE_OBJECTIVE_CONTEXT)
        candidate._moead_objectives = objective
        candidate._ts_fitness = objective.tc
        return objective.tc
    fitness = getattr(candidate, "_ts_fitness", None)
    if fitness is None:
        fitness = candidate.fitness
        setattr(candidate, "_ts_fitness", fitness)
    return fitness


def _solution_coverage(solution: Dict[str, List[Node]]) -> Counter:
    """Count route nodes independently of their assigned vehicle or position."""
    return Counter(
        (
            node.id,
            tuple(sorted(item.id for item in node.pickup_item_list)),
            tuple(sorted(item.id for item in node.delivery_item_list)),
        )
        for route in solution.values()
        for node in route
    )


def _changed_vehicle_ids(original: Dict[str, List[Node]],
                         candidate: Dict[str, List[Node]]) -> Set[str]:
    """Return only routes modified by a neighbourhood operation."""
    changed = set()
    for vehicle_id in set(original).union(candidate):
        original_route = original.get(vehicle_id, [])
        candidate_route = candidate.get(vehicle_id, [])
        original_nodes = tuple(
            (node.id, tuple(item.id for item in node.pickup_item_list),
             tuple(item.id for item in node.delivery_item_list))
            for node in original_route
        )
        candidate_nodes = tuple(
            (node.id, tuple(item.id for item in node.pickup_item_list),
             tuple(item.id for item in node.delivery_item_list))
            for node in candidate_route
        )
        if original_nodes != candidate_nodes:
            changed.add(vehicle_id)
    return changed


def _has_destination_prefix(solution: Dict[str, List[Node]],
                            id_to_vehicle: Dict[str, Vehicle],
                            vehicle_ids: Optional[Set[str]] = None) -> bool:
    """Ensure selected in-progress vehicles keep their fixed destination."""
    checked_vehicle_ids = vehicle_ids if vehicle_ids is not None else set(id_to_vehicle)
    for vehicle_id in checked_vehicle_ids:
        vehicle = id_to_vehicle.get(vehicle_id)
        if vehicle is None:
            return False
        route = solution.get(vehicle_id, [])
        if vehicle.des and (not route or not destination_matches(route[0], vehicle.des)):
            return False
    return True


def _ensure_destination_prefix(solution: Dict[str, List[Node]],
                               id_to_vehicle: Dict[str, Vehicle]) -> None:
    """Restore omitted dynamic destinations before dispatching or moving nodes.

    The simulator can report a vehicle with a fixed next destination while the
    persisted route contains no node for that destination.  All neighbourhood
    operators reserve index zero in that case, so materialise the node once in
    the initial solution instead of allowing an invalid insertion range.
    """
    for vehicle_id, vehicle in id_to_vehicle.items():
        route = solution.setdefault(vehicle_id, [])
        ensure_destination_prefix(route, vehicle)


def _insertion_start(route: List[Node], vehicle: Vehicle) -> Optional[int]:
    """Return the first movable insertion index, or reject an invalid route."""
    if not vehicle.des:
        return 0
    if not route or route[0].id != vehicle.des.id:
        return None
    return 1


def _is_feasible_solution(candidate: Chromosome,
                          changed_vehicle_ids: Optional[Set[str]] = None) -> bool:
    """Validate capacity/FILO only for routes changed from the restored scene."""
    vehicle_ids = changed_vehicle_ids if changed_vehicle_ids is not None else set(candidate.solution)
    for vehicle_id in vehicle_ids:
        route = candidate.solution.get(vehicle_id, [])
        vehicle = candidate.id_to_vehicle.get(vehicle_id)
        if vehicle is None:
            return False
        if vehicle.des and (not route or not destination_matches(route[0], vehicle.des)):
            return False
        carrying = vehicle.carrying_items or []
        if not isFeasible(canonicalize_route(route, bool(vehicle.des)),
                          carrying, vehicle.board_capacity):
            return False
    return True


def _extract_pdg_units(solution: Dict[str, List[Node]],
                       id_to_vehicle: Dict[str, Vehicle]) -> List[PdgUnit]:
    """Extract non-overlapping movable PD pairs directly from the LIFO stack.

    The legacy ``new_get_UnongoingSuperNode`` assumes that a visit is either a
    pickup or delivery node.  MOEA/D--TS expands mutable visits into atomic
    actions before local search; reject an unnormalised combined node here so
    an external caller cannot create overlapping move units by accident.
    """
    records_by_order: Dict[str, List[Tuple[str, str, int, int, OrderItem]]] = {}
    min_capacity = min(
        (vehicle.board_capacity for vehicle in id_to_vehicle.values()), default=0.0
    )

    for vehicle_id, vehicle in id_to_vehicle.items():
        route = solution.get(vehicle_id, [])
        movable_start = 1 if vehicle.des else 0
        # ``carrying_items`` is stored bottom-to-top, therefore list.pop()
        # faithfully returns the currently accessible top item.
        stack: List[Tuple[Optional[int], OrderItem]] = [
            (None, item) for item in (vehicle.carrying_items or [])
        ]
        route_records: List[Tuple[str, str, int, int, OrderItem]] = []
        valid = True
        for index, node in enumerate(route):
            if (index >= movable_start and node.delivery_item_list and
                    node.pickup_item_list):
                valid = False
                break
            for delivery in node.delivery_item_list or []:
                if not stack:
                    valid = False
                    break
                pickup_index, pickup = stack.pop()
                if pickup.id != delivery.id:
                    valid = False
                    break
                if pickup_index is not None:
                    route_records.append((
                        delivery.order_id or delivery.id, vehicle_id,
                        pickup_index, index, delivery,
                    ))
            if not valid:
                break
            for pickup in node.pickup_item_list or []:
                stack.append((index if index >= movable_start else None, pickup))
        if not valid:
            continue
        for record in route_records:
            records_by_order.setdefault(record[0], []).append(record)

    units: List[PdgUnit] = []
    for order_id in sorted(records_by_order):
        records = records_by_order[order_id]
        order_demand = sum(record[4].demand for record in records)
        by_vehicle: Dict[str, List[Tuple[str, str, int, int, OrderItem]]] = {}
        for record in records:
            by_vehicle.setdefault(record[1], []).append(record)
        # An order that fits every vehicle must move as one unit to preserve
        # the simulator's no-splitting constraint.  Oversized orders may have
        # been legally split by the initial dispatcher, so preserve each
        # existing vehicle-specific part.
        groups = (
            [records] if len(by_vehicle) == 1 and order_demand <= min_capacity + 1e-9
            else [by_vehicle[vehicle_id] for vehicle_id in sorted(by_vehicle)]
        )
        for group in groups:
            vehicle_ids = {record[1] for record in group}
            if len(vehicle_ids) != 1:
                continue
            units.append(PdgUnit(
                tuple(sorted(record[4].id for record in group)),
                next(iter(vehicle_ids)),
                tuple(sorted(record[2] for record in group)),
                tuple(sorted(record[3] for record in group)),
            ))
    return units


def _remove_nodes(route: List[Node], indices: Tuple[int, ...]) -> List[Node]:
    """Remove indexed nodes while preserving their route order."""
    positions = tuple(sorted(set(indices)))
    if any(index < 0 or index >= len(route) for index in positions):
        return []
    nodes = [route[index] for index in positions]
    for index in reversed(positions):
        del route[index]
    return nodes


def _adjusted_index(index: int, removed_indices: Tuple[int, ...]) -> int:
    return index - sum(1 for removed in removed_indices if removed < index)


def _contiguous_outer_block_runs(units: List[PdgUnit],
                                 vehicle_id: str) -> List[List[Tuple[int, int]]]:
    """Return reversible runs of complete, non-overlapping PDG blocks.

    Nested pickup-delivery pairs are represented by their outer block only;
    crossing spans are excluded.  A run must cover every route node between
    its endpoints, so reversing it cannot drop a partial pair or an unrelated
    node.
    """
    spans = sorted(
        {(unit.start_index, unit.end_index)
         for unit in units if unit.vehicle_id == vehicle_id},
        key=lambda span: (span[0], -span[1]),
    )
    outer_spans: List[Tuple[int, int]] = []
    for start, end in spans:
        if outer_spans and start <= outer_spans[-1][1]:
            if end <= outer_spans[-1][1]:
                continue
            return []
        outer_spans.append((start, end))

    runs: List[List[Tuple[int, int]]] = []
    run: List[Tuple[int, int]] = []
    for span in outer_spans:
        if run and span[0] != run[-1][1] + 1:
            if len(run) >= 2:
                runs.append(run)
            run = []
        run.append(span)
    if len(run) >= 2:
        runs.append(run)
    return runs


def _append_candidate(plan: Dict[str, List[Node]],
                      current: Chromosome,
                      current_signature: SolutionSignature,
                      current_coverage: Counter,
                      seen_signatures: Set[SolutionSignature],
                      results: List[Chromosome],
                      max_neighbors: int) -> bool:
    """Validate a move and retain the best ``max_neighbors`` candidates."""
    if max_neighbors <= 0:
        return False
    candidate = Chromosome(plan, current.route_map, current.id_to_vehicle)
    signature = _cached_signature(candidate)
    changed_vehicle_ids = _changed_vehicle_ids(current.solution, candidate.solution)
    if (signature == current_signature or signature in seen_signatures or
            _solution_coverage(candidate.solution) != current_coverage or
            not changed_vehicle_ids or
            not _has_destination_prefix(candidate.solution, candidate.id_to_vehicle,
                                        changed_vehicle_ids) or
            not _is_feasible_solution(candidate, changed_vehicle_ids)):
        return False
    try:
        if not math.isfinite(_cached_fitness(candidate)):
            return False
    except Exception:
        return False
    seen_signatures.add(signature)
    results.append(candidate)
    results.sort(key=lambda value: (
        _cached_fitness(value), _cached_signature(value)
    ))
    if len(results) > max_neighbors:
        del results[max_neighbors:]
    return True


def _validate_move_plan(plan: Dict[str, List[Node]],
                    current: Chromosome) -> Optional[Chromosome]:
    """Reject a single-move plan that drops coverage, breaks a committed
    destination, or violates capacity/LIFO feasibility on changed routes."""
    candidate = Chromosome(plan, current.route_map, current.id_to_vehicle)
    changed_vehicle_ids = _changed_vehicle_ids(current.solution, candidate.solution)
    if (not changed_vehicle_ids or
            _solution_coverage(candidate.solution) != _solution_coverage(current.solution) or
            not _has_destination_prefix(candidate.solution, candidate.id_to_vehicle,
                                        changed_vehicle_ids) or
            not _is_feasible_solution(candidate, changed_vehicle_ids)):
        return None
    return candidate


def _deadline_reached(deadline: float) -> bool:
    return time.time() >= deadline or config.is_timeout()


def generate_pdg_relocate_neighbors(current: Chromosome, max_neighbors: int,
                                    deadline: float,
                                    seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Return the best feasible couple-relocate moves.

    A pickup-delivery couple is removed once, then every legal pickup and
    delivery insertion position on every route is evaluated.  This is the
    best-improvement relocate-couple operator defined in the paper's ref. [62].
    """
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    vehicle_ids = sorted(current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for unit in units:
        if _deadline_reached(deadline):
            break
        for target_id in vehicle_ids:
            if _deadline_reached(deadline):
                break
            base_plan = copy.deepcopy(current.solution)
            source_route = base_plan[unit.vehicle_id]
            pickup_nodes = [source_route[index] for index in unit.pickup_indices]
            delivery_nodes = [source_route[index] for index in unit.delivery_indices]
            removed = unit.pickup_indices + unit.delivery_indices
            if len(_remove_nodes(source_route, removed)) != len(set(removed)):
                continue
            target_route = base_plan[target_id]
            start = _insertion_start(
                target_route, current.id_to_vehicle[target_id]
            )
            if start is None:
                continue
            for pickup_position in range(start, len(target_route) + 1):
                if _deadline_reached(deadline):
                    break
                first_delivery_position = pickup_position + len(pickup_nodes)
                last_delivery_position = len(target_route) + len(pickup_nodes)
                for delivery_position in range(
                        first_delivery_position, last_delivery_position + 1):
                    if _deadline_reached(deadline):
                        break
                    plan = copy.deepcopy(base_plan)
                    candidate_route = plan[target_id]
                    candidate_route[pickup_position:pickup_position] = copy.deepcopy(
                        pickup_nodes
                    )
                    candidate_route[delivery_position:delivery_position] = copy.deepcopy(
                        delivery_nodes
                    )
                    _append_candidate(
                        plan, current, current_signature, current_coverage,
                        seen_signatures, results, max_neighbors,
                    )
    return results


def generate_pdg_exchange_neighbors(current: Chromosome, max_neighbors: int,
                                    deadline: float,
                                    seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Return the best feasible intra- and inter-route couple exchanges.

    Figure 5(b) in the paper exchanges two pickup-delivery couples within one
    route.  The legacy implementation only supported inter-vehicle exchanges;
    retain that case and add the missing intra-route position swap.
    """
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for left, right in combinations(units, 2):
        if _deadline_reached(deadline):
            break
        if left.vehicle_id == right.vehicle_id:
            all_left_indices = left.pickup_indices + left.delivery_indices
            all_right_indices = right.pickup_indices + right.delivery_indices
            if (set(all_left_indices).intersection(all_right_indices) or
                    len(left.pickup_indices) != len(right.pickup_indices) or
                    len(left.delivery_indices) != len(right.delivery_indices)):
                continue
            plan = copy.deepcopy(current.solution)
            route = plan[left.vehicle_id]
            original_route = list(route)
            for left_index, right_index in zip(left.pickup_indices, right.pickup_indices):
                route[left_index] = original_route[right_index]
                route[right_index] = original_route[left_index]
            for left_index, right_index in zip(left.delivery_indices, right.delivery_indices):
                route[left_index] = original_route[right_index]
                route[right_index] = original_route[left_index]
            _append_candidate(
                plan, current, current_signature, current_coverage,
                seen_signatures, results, max_neighbors,
            )
            continue
        plan = copy.deepcopy(current.solution)
        left_route, right_route = plan[left.vehicle_id], plan[right.vehicle_id]
        left_pickups = [left_route[index] for index in left.pickup_indices]
        left_deliveries = [left_route[index] for index in left.delivery_indices]
        right_pickups = [right_route[index] for index in right.pickup_indices]
        right_deliveries = [right_route[index] for index in right.delivery_indices]
        left_indices = left.pickup_indices + left.delivery_indices
        right_indices = right.pickup_indices + right.delivery_indices
        if (len(_remove_nodes(left_route, left_indices)) != len(set(left_indices)) or
                len(_remove_nodes(right_route, right_indices)) != len(set(right_indices))):
            continue
        left_pickup_position = _adjusted_index(left.start_index, left_indices)
        left_delivery_position = (_adjusted_index(min(left.delivery_indices), left_indices) +
                                  len(right_pickups))
        right_pickup_position = _adjusted_index(right.start_index, right_indices)
        right_delivery_position = (_adjusted_index(min(right.delivery_indices), right_indices) +
                                   len(left_pickups))
        left_route[left_pickup_position:left_pickup_position] = right_pickups
        left_route[left_delivery_position:left_delivery_position] = right_deliveries
        right_route[right_pickup_position:right_pickup_position] = left_pickups
        right_route[right_delivery_position:right_delivery_position] = left_deliveries
        _append_candidate(
            plan, current, current_signature, current_coverage,
            seen_signatures, results, max_neighbors,
        )
    return results


def generate_block_relocate_neighbors(current: Chromosome, max_neighbors: int,
                                      deadline: float,
                                      seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Return the best feasible pickup-to-delivery block relocations."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    vehicle_ids = sorted(current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for unit in units:
        if _deadline_reached(deadline):
            break
        block_indices = tuple(range(unit.start_index, unit.end_index + 1))
        for target_id in vehicle_ids:
            if _deadline_reached(deadline):
                break
            base_plan = copy.deepcopy(current.solution)
            block = _remove_nodes(base_plan[unit.vehicle_id], block_indices)
            if len(block) != len(block_indices):
                continue
            target_route = base_plan[target_id]
            start = _insertion_start(
                target_route, current.id_to_vehicle[target_id]
            )
            if start is None:
                continue
            for position in range(start, len(target_route) + 1):
                if _deadline_reached(deadline):
                    break
                plan = copy.deepcopy(base_plan)
                plan[target_id][position:position] = copy.deepcopy(block)
                _append_candidate(
                    plan, current, current_signature, current_coverage,
                    seen_signatures, results, max_neighbors,
                )
    return results


def generate_block_exchange_neighbors(current: Chromosome, max_neighbors: int,
                                      deadline: float,
                                      seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Return the best feasible inter- or intra-route block exchanges."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for left, right in combinations(units, 2):
        if _deadline_reached(deadline):
            break
        left_indices = tuple(range(left.start_index, left.end_index + 1))
        right_indices = tuple(range(right.start_index, right.end_index + 1))
        if left.vehicle_id == right.vehicle_id:
            if not set(left_indices).isdisjoint(right_indices):
                continue
            plan = copy.deepcopy(current.solution)
            route = plan[left.vehicle_id]
            first, second = ((left, right) if left.start_index < right.start_index
                             else (right, left))
            first_nodes = route[first.start_index:first.end_index + 1]
            second_nodes = route[second.start_index:second.end_index + 1]
            route[:] = (route[:first.start_index] + second_nodes +
                        route[first.end_index + 1:second.start_index] + first_nodes +
                        route[second.end_index + 1:])
        else:
            plan = copy.deepcopy(current.solution)
            left_route, right_route = plan[left.vehicle_id], plan[right.vehicle_id]
            left_nodes = _remove_nodes(left_route, left_indices)
            right_nodes = _remove_nodes(right_route, right_indices)
            if len(left_nodes) != len(left_indices) or len(right_nodes) != len(right_indices):
                continue
            left_position = _adjusted_index(left.start_index, left_indices)
            right_position = _adjusted_index(right.start_index, right_indices)
            left_route[left_position:left_position] = right_nodes
            right_route[right_position:right_position] = left_nodes
        _append_candidate(
            plan, current, current_signature, current_coverage,
            seen_signatures, results, max_neighbors,
        )
    return results


_MOVE_SAMPLING_ATTEMPTS = 32


def sample_pdg_relocate_move(current: Chromosome, deadline: float,
                             max_attempts: int = _MOVE_SAMPLING_ATTEMPTS,
                             ) -> Optional[Tuple[Chromosome, MoveKey]]:
    """Sample one random feasible couple-relocate move and its move key.

    One pickup-delivery couple is removed and reinserted at random pickup and
    delivery positions on a randomly chosen route (Algorithm 4's
    couple-relocate operator, ref. [62] of the paper).
    """
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    if not units:
        return None
    vehicle_ids = sorted(current.id_to_vehicle)
    for _ in range(max_attempts):
        if _deadline_reached(deadline):
            return None
        unit = random.choice(units)
        target_id = random.choice(vehicle_ids)
        base_plan = copy.deepcopy(current.solution)
        source_route = base_plan[unit.vehicle_id]
        pickup_nodes = [source_route[index] for index in unit.pickup_indices]
        delivery_nodes = [source_route[index] for index in unit.delivery_indices]
        removed = unit.pickup_indices + unit.delivery_indices
        if len(_remove_nodes(source_route, removed)) != len(set(removed)):
            continue
        target_route = base_plan[target_id]
        start = _insertion_start(target_route, current.id_to_vehicle[target_id])
        if start is None:
            continue
        pickup_position = random.randint(start, len(target_route))
        first_delivery_position = pickup_position + len(pickup_nodes)
        last_delivery_position = len(target_route) + len(pickup_nodes)
        delivery_position = random.randint(
            first_delivery_position, last_delivery_position
        )
        plan = copy.deepcopy(base_plan)
        candidate_route = plan[target_id]
        candidate_route[pickup_position:pickup_position] = copy.deepcopy(pickup_nodes)
        candidate_route[delivery_position:delivery_position] = copy.deepcopy(
            delivery_nodes
        )
        candidate = _validate_move_plan(plan, current)
        if candidate is None:
            continue
        return candidate, (
            "pdg_relocate", unit.key, target_id, pickup_position, delivery_position,
        )
    return None


def sample_pdg_exchange_move(current: Chromosome, deadline: float,
                             max_attempts: int = _MOVE_SAMPLING_ATTEMPTS,
                             ) -> Optional[Tuple[Chromosome, MoveKey]]:
    """Sample one random feasible intra- or inter-route couple-exchange move."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    if len(units) < 2:
        return None
    for _ in range(max_attempts):
        if _deadline_reached(deadline):
            return None
        left, right = random.sample(units, 2)
        if left.vehicle_id == right.vehicle_id:
            all_left_indices = left.pickup_indices + left.delivery_indices
            all_right_indices = right.pickup_indices + right.delivery_indices
            if (set(all_left_indices).intersection(all_right_indices) or
                    len(left.pickup_indices) != len(right.pickup_indices) or
                    len(left.delivery_indices) != len(right.delivery_indices)):
                continue
            plan = copy.deepcopy(current.solution)
            route = plan[left.vehicle_id]
            original_route = list(route)
            for left_index, right_index in zip(
                    left.pickup_indices, right.pickup_indices):
                route[left_index] = original_route[right_index]
                route[right_index] = original_route[left_index]
            for left_index, right_index in zip(
                    left.delivery_indices, right.delivery_indices):
                route[left_index] = original_route[right_index]
                route[right_index] = original_route[left_index]
        else:
            plan = copy.deepcopy(current.solution)
            left_route, right_route = plan[left.vehicle_id], plan[right.vehicle_id]
            left_pickups = [left_route[index] for index in left.pickup_indices]
            left_deliveries = [left_route[index] for index in left.delivery_indices]
            right_pickups = [right_route[index] for index in right.pickup_indices]
            right_deliveries = [right_route[index] for index in right.delivery_indices]
            left_indices = left.pickup_indices + left.delivery_indices
            right_indices = right.pickup_indices + right.delivery_indices
            if (len(_remove_nodes(left_route, left_indices)) != len(set(left_indices)) or
                    len(_remove_nodes(right_route, right_indices)) != len(set(right_indices))):
                continue
            left_pickup_position = _adjusted_index(left.start_index, left_indices)
            left_delivery_position = (
                _adjusted_index(min(left.delivery_indices), left_indices) +
                len(right_pickups)
            )
            right_pickup_position = _adjusted_index(right.start_index, right_indices)
            right_delivery_position = (
                _adjusted_index(min(right.delivery_indices), right_indices) +
                len(left_pickups)
            )
            left_route[left_pickup_position:left_pickup_position] = right_pickups
            left_route[left_delivery_position:left_delivery_position] = right_deliveries
            right_route[right_pickup_position:right_pickup_position] = left_pickups
            right_route[right_delivery_position:right_delivery_position] = left_deliveries
        candidate = _validate_move_plan(plan, current)
        if candidate is None:
            continue
        return candidate, (
            "pdg_exchange", tuple(sorted((left.key, right.key))),
        )
    return None


def sample_block_relocate_move(current: Chromosome, deadline: float,
                               max_attempts: int = _MOVE_SAMPLING_ATTEMPTS,
                               ) -> Optional[Tuple[Chromosome, MoveKey]]:
    """Sample one random feasible pickup-to-delivery block-relocate move."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    if not units:
        return None
    vehicle_ids = sorted(current.id_to_vehicle)
    for _ in range(max_attempts):
        if _deadline_reached(deadline):
            return None
        unit = random.choice(units)
        block_indices = tuple(range(unit.start_index, unit.end_index + 1))
        target_id = random.choice(vehicle_ids)
        base_plan = copy.deepcopy(current.solution)
        block = _remove_nodes(base_plan[unit.vehicle_id], block_indices)
        if len(block) != len(block_indices):
            continue
        target_route = base_plan[target_id]
        start = _insertion_start(target_route, current.id_to_vehicle[target_id])
        if start is None:
            continue
        position = random.randint(start, len(target_route))
        plan = copy.deepcopy(base_plan)
        plan[target_id][position:position] = copy.deepcopy(block)
        candidate = _validate_move_plan(plan, current)
        if candidate is None:
            continue
        return candidate, (
            "block_relocate", unit.key, target_id, position,
        )
    return None


def sample_block_exchange_move(current: Chromosome, deadline: float,
                               max_attempts: int = _MOVE_SAMPLING_ATTEMPTS,
                               ) -> Optional[Tuple[Chromosome, MoveKey]]:
    """Sample one random feasible intra- or inter-route block-exchange move."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    if len(units) < 2:
        return None
    for _ in range(max_attempts):
        if _deadline_reached(deadline):
            return None
        left, right = random.sample(units, 2)
        left_indices = tuple(range(left.start_index, left.end_index + 1))
        right_indices = tuple(range(right.start_index, right.end_index + 1))
        if left.vehicle_id == right.vehicle_id:
            if not set(left_indices).isdisjoint(right_indices):
                continue
            plan = copy.deepcopy(current.solution)
            route = plan[left.vehicle_id]
            first, second = ((left, right) if left.start_index < right.start_index
                             else (right, left))
            first_nodes = route[first.start_index:first.end_index + 1]
            second_nodes = route[second.start_index:second.end_index + 1]
            route[:] = (route[:first.start_index] + second_nodes +
                        route[first.end_index + 1:second.start_index] + first_nodes +
                        route[second.end_index + 1:])
        else:
            plan = copy.deepcopy(current.solution)
            left_route, right_route = plan[left.vehicle_id], plan[right.vehicle_id]
            left_nodes = _remove_nodes(left_route, left_indices)
            right_nodes = _remove_nodes(right_route, right_indices)
            if (len(left_nodes) != len(left_indices) or
                    len(right_nodes) != len(right_indices)):
                continue
            left_position = _adjusted_index(left.start_index, left_indices)
            right_position = _adjusted_index(right.start_index, right_indices)
            left_route[left_position:left_position] = right_nodes
            right_route[right_position:right_position] = left_nodes
        candidate = _validate_move_plan(plan, current)
        if candidate is None:
            continue
        return candidate, (
            "block_exchange", tuple(sorted((left.key, right.key))),
        )
    return None


def MOEAD_TS(Base_vehicleid_to_plan: Dict[str, List[Node]],
             route_map: Dict[Tuple, Tuple],
             id_to_vehicle: Dict[str, Vehicle],
             id_to_factory: Dict[str, Factory],
             id_to_unlocated_items: Dict[str, OrderItem],
             new_order_itemIDs: List[str]) -> Optional[Chromosome]:
    """Public MOEA/D--TS adapter implementing Algorithms 2--4.

    The production entry point is the decomposition-based population search.
    Algorithm 4 in ``moead_core.tabu_search`` samples the four move types
    below and tabus complete canonical solutions.
    """
    from algorithm.Test_algorithm.moead_core import run_moead_ts
    return run_moead_ts(
        Base_vehicleid_to_plan,
        route_map,
        id_to_vehicle,
        id_to_factory,
        id_to_unlocated_items,
        new_order_itemIDs,
    )
