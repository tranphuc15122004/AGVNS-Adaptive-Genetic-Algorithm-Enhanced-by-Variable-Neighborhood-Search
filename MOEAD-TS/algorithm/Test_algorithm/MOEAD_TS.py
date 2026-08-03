"""Solution-based Tabu Search for the dynamic pickup and delivery problem."""

import copy
import hashlib
import math
import random
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from algorithm.Object import Chromosome, Factory, Node, OrderItem, Vehicle
import algorithm.algorithm_config as config
from algorithm.engine import get_route_after, isFeasible
from algorithm.Test_algorithm.new_engine import new_dispatch_new_orders , worse_dispatch_new_orders
from algorithm.Test_algorithm.new_LS import new_get_UnongoingSuperNode


SolutionSignature = bytes

_OUTPUT_RESERVE_SECONDS = 5.0


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
    """Return the compact BLAKE2b tabu item for one canonical solution."""
    route_after = get_route_after(solution, {})
    return hashlib.blake2b(
        route_after.encode("utf-8"),
        digest_size=16,
    ).digest()


def _cached_signature(candidate: Chromosome) -> SolutionSignature:
    """Return a candidate's immutable tabu signature without reserialising it."""
    signature = getattr(candidate, "_ts_signature", None)
    if signature is None:
        signature = solution_signature(candidate.solution)
        setattr(candidate, "_ts_signature", signature)
    return signature


def _cached_fitness(candidate: Chromosome) -> float:
    """Evaluate a TS candidate once; its solution is immutable after creation."""
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
    """Return only routes modified by a sampled neighbourhood operation."""
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
        if vehicle.des and (not route or route[0].id != vehicle.des.id):
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
        if vehicle.des and (not route or route[0].id != vehicle.des.id):
            route.insert(0, copy.deepcopy(vehicle.des))


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
        if vehicle.des and (not route or route[0].id != vehicle.des.id):
            return False
        carrying = vehicle.carrying_items if vehicle.des else []
        if not isFeasible(route, carrying, vehicle.board_capacity):
            return False
    return True


def add_tabu_signature(signature: SolutionSignature,
                       tabu_fifo: deque,
                       tabu_signatures: Set[SolutionSignature],
                       max_size: int) -> None:
    """Store one visited solution in bounded FIFO tabu memory."""
    if max_size <= 0 or signature in tabu_signatures:
        return
    while len(tabu_fifo) >= max_size:
        tabu_signatures.discard(tabu_fifo.popleft())
    tabu_fifo.append(signature)
    tabu_signatures.add(signature)


def select_admissible_solution(
        candidates: List[Chromosome],
        tabu_signatures: Set[SolutionSignature],
        global_best_cost: float,
) -> Tuple[Optional[Chromosome], Optional[SolutionSignature], int, int]:
    """Select the lowest-cost neighbour that satisfies tabu/aspiration rules."""
    chosen: Optional[Chromosome] = None
    chosen_signature: Optional[SolutionSignature] = None
    chosen_cost = math.inf
    tabu_rejections = 0
    aspirations = 0

    for candidate in candidates:
        signature = _cached_signature(candidate)
        candidate_cost = _cached_fitness(candidate)
        tabu = signature in tabu_signatures
        aspirated = tabu and candidate_cost < global_best_cost
        if tabu and not aspirated:
            tabu_rejections += 1
            continue
        if aspirated:
            aspirations += 1
        if candidate_cost < chosen_cost:
            chosen = candidate
            chosen_signature = signature
            chosen_cost = candidate_cost
    return chosen, chosen_signature, tabu_rejections, aspirations


def _extract_pdg_units(solution: Dict[str, List[Node]],
                       id_to_vehicle: Dict[str, Vehicle]) -> List[PdgUnit]:
    """Adapt the legacy LS supernode map into stable TS sampling units."""
    units: List[PdgUnit] = []
    for supernode in new_get_UnongoingSuperNode(solution, id_to_vehicle).values():
        entries = []
        for vehicle_and_position, node in supernode.items():
            vehicle_id, position = vehicle_and_position.rsplit(",", 1)
            entries.append((vehicle_id, int(position), node))
        if not entries or len({entry[0] for entry in entries}) != 1:
            continue
        vehicle_id = entries[0][0]
        pickup_indices = tuple(sorted(entry[1] for entry in entries
                                      if entry[2].pickup_item_list))
        delivery_indices = tuple(sorted(entry[1] for entry in entries
                                        if entry[2].delivery_item_list))
        item_ids = tuple(sorted(
            item.id for _, _, node in entries for item in node.pickup_item_list
        ))
        if pickup_indices and delivery_indices and item_ids:
            units.append(PdgUnit(item_ids, vehicle_id, pickup_indices,
                                 delivery_indices))
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
                      results: List[Chromosome]) -> bool:
    """Validate, evaluate and deduplicate one sampled solution neighbour."""
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
    return True


def _deadline_reached(deadline: float, results: List[Chromosome],
                      max_neighbors: int) -> bool:
    return (time.time() >= deadline or config.is_timeout() or
            len(results) >= max_neighbors)


def generate_pdg_relocate_neighbors(current: Chromosome, max_neighbors: int,
                                    deadline: float,
                                    seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Sample feasible one-PDG relocations without requiring an improvement."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    random.shuffle(units)
    vehicle_ids = list(current.id_to_vehicle)
    random.shuffle(vehicle_ids)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for unit in units:
        if _deadline_reached(deadline, results, max_neighbors):
            break
        for target_id in vehicle_ids:
            if _deadline_reached(deadline, results, max_neighbors):
                break
            for _ in range(2):
                plan = copy.deepcopy(current.solution)
                source_route = plan[unit.vehicle_id]
                pickup_nodes = [source_route[index] for index in unit.pickup_indices]
                delivery_nodes = [source_route[index] for index in unit.delivery_indices]
                removed = unit.pickup_indices + unit.delivery_indices
                if len(_remove_nodes(source_route, removed)) != len(set(removed)):
                    continue
                target_route = plan[target_id]
                start = _insertion_start(
                    target_route, current.id_to_vehicle[target_id]
                )
                if start is None:
                    continue
                pickup_position = random.randint(start, len(target_route))
                delivery_position = random.randint(
                    pickup_position + len(pickup_nodes),
                    len(target_route) + len(pickup_nodes),
                )
                target_route[pickup_position:pickup_position] = pickup_nodes
                target_route[delivery_position:delivery_position] = delivery_nodes
                _append_candidate(plan, current, current_signature, current_coverage,
                                  seen_signatures, results)
    return results


def generate_pdg_exchange_neighbors(current: Chromosome, max_neighbors: int,
                                    deadline: float,
                                    seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Sample feasible inter-vehicle PDG exchanges without a cost filter."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)
    attempts = max_neighbors * 12

    for _ in range(attempts):
        if _deadline_reached(deadline, results, max_neighbors) or len(units) < 2:
            break
        left, right = random.sample(units, 2)
        if left.vehicle_id == right.vehicle_id:
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
        _append_candidate(plan, current, current_signature, current_coverage,
                          seen_signatures, results)
    return results


def generate_block_relocate_neighbors(current: Chromosome, max_neighbors: int,
                                      deadline: float,
                                      seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Sample whole pickup-to-delivery block relocations without a cost filter."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    random.shuffle(units)
    vehicle_ids = list(current.id_to_vehicle)
    random.shuffle(vehicle_ids)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)

    for unit in units:
        if _deadline_reached(deadline, results, max_neighbors):
            break
        block_indices = tuple(range(unit.start_index, unit.end_index + 1))
        for target_id in vehicle_ids:
            if _deadline_reached(deadline, results, max_neighbors):
                break
            plan = copy.deepcopy(current.solution)
            block = _remove_nodes(plan[unit.vehicle_id], block_indices)
            if len(block) != len(block_indices):
                continue
            target_route = plan[target_id]
            start = _insertion_start(
                target_route, current.id_to_vehicle[target_id]
            )
            if start is None:
                continue
            position = random.randint(start, len(target_route))
            target_route[position:position] = block
            _append_candidate(plan, current, current_signature, current_coverage,
                              seen_signatures, results)
    return results


def generate_block_exchange_neighbors(current: Chromosome, max_neighbors: int,
                                      deadline: float,
                                      seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Sample feasible inter- or intra-route block exchanges without a cost filter."""
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)
    attempts = max_neighbors * 12

    for _ in range(attempts):
        if _deadline_reached(deadline, results, max_neighbors) or len(units) < 2:
            break
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
            if len(left_nodes) != len(left_indices) or len(right_nodes) != len(right_indices):
                continue
            left_position = _adjusted_index(left.start_index, left_indices)
            right_position = _adjusted_index(right.start_index, right_indices)
            left_route[left_position:left_position] = right_nodes
            right_route[right_position:right_position] = left_nodes
        _append_candidate(plan, current, current_signature, current_coverage,
                          seen_signatures, results)
    return results


def generate_two_opt_neighbors(current: Chromosome, max_neighbors: int,
                               deadline: float,
                               seen_signatures: Set[SolutionSignature]) -> List[Chromosome]:
    """Reverse complete, contiguous PDG blocks without partial-pair loss."""
    results: List[Chromosome] = []
    current_signature = _cached_signature(current)
    current_coverage = _solution_coverage(current.solution)
    units = _extract_pdg_units(current.solution, current.id_to_vehicle)
    runs_by_vehicle = {
        vehicle_id: _contiguous_outer_block_runs(units, vehicle_id)
        for vehicle_id in current.solution
    }
    vehicle_ids = [
        vehicle_id for vehicle_id, runs in runs_by_vehicle.items() if runs
    ]
    attempts = max_neighbors * 16

    for _ in range(attempts):
        if _deadline_reached(deadline, results, max_neighbors) or not vehicle_ids:
            break
        vehicle_id = random.choice(vehicle_ids)
        run = random.choice(runs_by_vehicle[vehicle_id])
        first_index, last_index = sorted(random.sample(range(len(run)), 2))
        first_start = run[first_index][0]
        last_end = run[last_index][1]
        plan = copy.deepcopy(current.solution)
        route = plan[vehicle_id]
        reversed_blocks: List[Node] = []
        for start, end in reversed(run[first_index:last_index + 1]):
            reversed_blocks.extend(route[start:end + 1])
        route[first_start:last_end + 1] = reversed_blocks
        _append_candidate(plan, current, current_signature, current_coverage,
                          seen_signatures, results)
    return results


def generate_neighbors(current: Chromosome, limit_time: float,
                       deadline: Optional[float] = None) -> List[Chromosome]:
    """Generate bounded feasible TS neighbours, including worsening solutions."""
    generators = (
        generate_pdg_relocate_neighbors,
        generate_pdg_exchange_neighbors,
        generate_block_relocate_neighbors,
        generate_block_exchange_neighbors,
        generate_two_opt_neighbors,
    )
    overall_deadline = deadline or (time.time() + limit_time * len(generators))
    seen_signatures: Set[SolutionSignature] = set()
    neighbors: List[Chromosome] = []

    for index, generator in enumerate(generators):
        if time.time() >= overall_deadline or config.is_timeout():
            break
        remaining_generators = len(generators) - index
        remaining_time = max(0.0, overall_deadline - time.time())
        operator_deadline = time.time() + min(
            limit_time, remaining_time / max(1, remaining_generators)
        )
        neighbors.extend(generator(
            current, config.TS_NEIGHBORS_PER_OPERATOR, operator_deadline,
            seen_signatures,
        ))
    return neighbors


def _search_deadline() -> float:
    """Return the tighter of the TS budget and simulator safety deadline."""
    simulator_deadline = (
        config.BEGIN_TIME + config.ALGO_TIME_LIMIT - _OUTPUT_RESERVE_SECONDS
    )
    return min(simulator_deadline, time.time() + config.TS_SEARCH_TIME_LIMIT)


def MOEAD_TS(Base_vehicleid_to_plan: Dict[str, List[Node]],
                route_map: Dict[Tuple, Tuple],
                id_to_vehicle: Dict[str, Vehicle],
                id_to_factory: Dict[str, Factory],
                id_to_unlocated_items: Dict[str, OrderItem],
                new_order_itemIDs: List[str]) -> Optional[Chromosome]:
    """Run bounded classical TS for one dynamic dispatch decision.

    This retains the classical tabu list, aspiration, and best-admissible
    neighbour selection (including worsening moves). It intentionally omits
    diversification because DPDP invokes TS again after each state update.
    """
    if not new_order_itemIDs:
        return None

    if config.BEGIN_TIME == 0:
        config.set_begin_time()
    config.set_random_seed()
    start_time = time.time()
    search_deadline = _search_deadline()

    try:
        # Khởi tạo giống AGVNS: chèn đơn hàng mới bằng cheapest insertion (CI)
        # thay cho worse_dispatch_new_orders. TS chỉ cần 1 lời giải nên dùng
        # thẳng lời giải CI làm điểm khởi đầu, không cần population như GA.
        initial_plan = copy.deepcopy(Base_vehicleid_to_plan)
        worse_dispatch_new_orders(
            initial_plan,
            id_to_factory,
            route_map,
            id_to_vehicle,
            id_to_unlocated_items,
            new_order_itemIDs,
        )
        initial = Chromosome(initial_plan, route_map, id_to_vehicle)
    except Exception:
        # Fallback: return a Chromosome from the base plan itself
        return None

    current = initial
    best_solution = copy.deepcopy(current.solution)
    best_cost = _cached_fitness(current)
    tabu_fifo = deque()
    tabu_signatures: Set[SolutionSignature] = set()
    add_tabu_signature(_cached_signature(current), tabu_fifo,
                       tabu_signatures, config.TS_TABU_LIST_SIZE)

    iteration = 0
    stagnation = 0
    total_aspirations = 0
    print("[TS-Tabu] Init: seed={}, cost={:.2f}, tabu_size={}, budget={:.2f}s, "
          "max_iters={}".format(
        config.TS_RANDOM_SEED, best_cost, config.TS_TABU_LIST_SIZE,
        max(0.0, search_deadline - start_time), config.TS_MAX_ITERATIONS,
    ))

    while (iteration < config.TS_MAX_ITERATIONS and
           time.time() < search_deadline and not config.is_timeout()):
        iteration += 1
        neighbors = generate_neighbors(current, config.TS_OPERATOR_TIME_LIMIT,
                                       search_deadline)
        chosen, signature, tabu_rejections, aspirations = select_admissible_solution(
            neighbors, tabu_signatures, best_cost
        )
        total_aspirations += aspirations

        if chosen is None:
            stagnation += 1
        else:
            current = chosen
            add_tabu_signature(signature, tabu_fifo, tabu_signatures,
                               config.TS_TABU_LIST_SIZE)
            current_cost = _cached_fitness(current)
            if current_cost < best_cost:
                best_solution = copy.deepcopy(current.solution)
                best_cost = current_cost
                stagnation = 0
            else:
                stagnation += 1

        if stagnation >= config.TS_STAGNATION_LIMIT:
            print("[TS-Tabu] Stop at iter={}: stagnated for {} iterations".format(
                iteration, config.TS_STAGNATION_LIMIT
            ))
            break

        if iteration == 1 or iteration % 10 == 0:
            print(
                "[TS-Tabu] iter={} current={:.2f} best={:.2f} neighbors={} "
                "tabu_rejected={} aspiration={} stuck={} tabu_size={} remaining={:.1f}s".format(
                    iteration, _cached_fitness(current), best_cost, len(neighbors), tabu_rejections,
                    aspirations, stagnation, len(tabu_fifo),
                    max(0.0, search_deadline - time.time()),
                )
            )

    elapsed = time.time() - start_time
    print("[TS-Tabu] DONE: iters={}, best={:.2f}, aspirations={}, time={:.2f}s".format(
        iteration, best_cost, total_aspirations, elapsed
    ))
    return Chromosome(best_solution, route_map, id_to_vehicle)
