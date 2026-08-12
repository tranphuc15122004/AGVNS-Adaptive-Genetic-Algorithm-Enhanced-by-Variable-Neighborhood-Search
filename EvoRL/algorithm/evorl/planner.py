"""Transactional candidate probing and application for atomic orders."""

from __future__ import annotations

from dataclasses import replace
from math import inf
import time
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .cost import projected_cost
from .dto import AtomicOrder, EpochState, InsertionResult, RouteNode, VehicleState, item_attr
from .validator import SolutionValidator


class TransactionalPlanner:
    """Plan one atomic order without mutating the caller's state."""

    def __init__(self, validator: Optional[SolutionValidator] = None):
        self.validator = validator or SolutionValidator()

    @staticmethod
    def _candidate_routes(base: Sequence[RouteNode], pickup: RouteNode,
                          delivery: RouteNode):
        """Yield a deterministic cheap candidate before exhaustive insertion.

        Large ICAPS instances can contain thousands of already planned nodes.
        Scanning every ``(pickup_position, delivery_position)`` pair for every
        atomic order makes the 570-second simulator budget unusable.  Appending
        a pickup/delivery pair is always a legal insertion candidate when the
        route prefix is feasible; callers stop after validating it.  If that
        fast candidate is rejected (for example by LIFO/capacity), the complete
        insertion space is still searched, so feasibility is never lost merely
        because of the optimization.
        """
        original = list(base)
        append_route = TransactionalPlanner._canonicalize_route(original + [pickup, delivery])
        yield len(original), len(original) + 1, append_route
        for i in range(len(original) + 1):
            for j in range(i + 1, len(original) + 2):
                if i == len(original) and j == len(original) + 1:
                    continue
                route = TransactionalPlanner._canonicalize_route(
                    original[:i] + [pickup] + original[i:j - 1]
                    + [delivery] + original[j - 1:]
                )
                yield i, j, route

    @staticmethod
    def _canonicalize_route(nodes: Sequence[RouteNode]) -> Tuple[RouteNode, ...]:
        """Merge adjacent mutable nodes at one factory.

        The official JSON boundary has one node per consecutive factory.  The
        planner can naturally produce ``delivery@F`` followed by
        ``pickup@F`` when two atomic assignments meet at the same factory;
        retaining both nodes makes in-process and subprocess phenotypes differ
        even though the dispatch is semantically identical.  Canonicalizing
        here keeps the shared decoder and the legacy ``merge_node`` contract
        identical.  The committed destination is not part of
        ``planned_route`` and is therefore never merged into this suffix.
        """
        merged = []
        for node in nodes:
            if merged and merged[-1].factory_id == node.factory_id:
                previous = merged[-1]
                # A fresh same-factory pickup followed by its delivery must
                # remain two operations: the official Checker services a
                # node as delivery-then-pickup, so merging would attempt the
                # delivery before the item has been loaded.  The same guard
                # covers a previously picked item delivered in the next
                # duplicate node.
                previous_pickups = set(previous.pickup_item_ids)
                node_pickups = set(node.pickup_item_ids)
                node_deliveries = set(node.delivery_item_ids)
                if (previous_pickups & node_deliveries) or (node_pickups & node_deliveries):
                    merged.append(node)
                    continue
                merged[-1] = RouteNode(
                    factory_id=previous.factory_id,
                    pickup_item_ids=previous.pickup_item_ids + node.pickup_item_ids,
                    delivery_item_ids=previous.delivery_item_ids + node.delivery_item_ids,
                    arrive_time=previous.arrive_time,
                    leave_time=previous.leave_time,
                )
            else:
                merged.append(node)
        return tuple(merged)

    def probe(
        self,
        state: EpochState,
        atomic: AtomicOrder,
        *,
        selected_vehicle: Optional[str] = None,
        top_k: Optional[int] = None,
        deadline: Optional[float] = None,
    ) -> InsertionResult:
        vehicle_ids = [selected_vehicle] if selected_vehicle is not None else sorted(state.vehicles)
        if selected_vehicle is not None and selected_vehicle not in state.vehicles:
            return InsertionResult(False, reason=f"unknown vehicle: {selected_vehicle}")
        candidates = []
        pickup = RouteNode(atomic.pickup_factory_id, atomic.item_ids, ())
        delivery = RouteNode(atomic.delivery_factory_id, (), tuple(reversed(atomic.item_ids)))
        for vehicle_id in vehicle_ids:
            if deadline is not None and time.monotonic() >= deadline:
                break
            vehicle = state.vehicles[vehicle_id]
            base = list(vehicle.planned_route)
            append_ok = False
            for i, j, route in self._candidate_routes(base, pickup, delivery):
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    candidate_vehicles = dict(state.vehicles)
                    candidate_vehicles[vehicle_id] = replace(vehicle, planned_route=route)
                    candidate_routes = {vehicle_id: route}
                    candidate_all_routes = {key: value.planned_route for key, value in candidate_vehicles.items()}
                    local_expected = set()
                    # The selected vehicle may already carry an item or have
                    # a committed destination.  Those IDs belong to the
                    # immutable prefix and must be part of the local
                    # validation universe; otherwise a valid insertion is
                    # rejected as an "unexpected" pre-existing item.
                    local_expected.update(str(item_id) for item_id in vehicle.carrying_item_ids)
                    if vehicle.destination is not None:
                        local_expected.update(vehicle.destination.pickup_item_ids)
                        local_expected.update(vehicle.destination.delivery_item_ids)
                    for node in route:
                        local_expected.update(node.pickup_item_ids)
                        local_expected.update(node.delivery_item_ids)
                    report = self.validator.validate(
                        candidate_routes,
                        {vehicle_id: candidate_vehicles[vehicle_id]},
                        state.items,
                        expected_item_ids=local_expected,
                        destinations={vehicle_id: candidate_vehicles[vehicle_id].destination},
                    )
                    if not report.valid:
                        continue
                    if not self._order_split_allowed(state, atomic, vehicle_id):
                        continue
                    before = projected_cost(
                        {key: value.planned_route for key, value in state.vehicles.items()},
                        state.vehicles, state.route_map, state.items, current_time=state.current_time,
                    )
                    after = projected_cost(
                        candidate_all_routes, candidate_vehicles, state.route_map, state.items,
                        current_time=state.current_time,
                    )
                    candidates.append(InsertionResult(
                        True, vehicle_id, i, j, route, "", after.benchmark_cost - before.benchmark_cost,
                    ))
                    # The fast append candidate is a valid phenotype.  Do not
                    # spend O(n^2) probing an already large route; exhaustive
                    # search remains available whenever append is infeasible.
                    if i == len(base) and j == len(base) + 1:
                        append_ok = True
                        break
            if append_ok:
                continue
        candidates.sort(key=lambda result: (result.delta_cost, result.vehicle_id or "", result.pickup_position or 0, result.delivery_position or 0))
        if not candidates:
            return InsertionResult(False, reason=f"no feasible insertion for {atomic.atomic_id}")
        return candidates[0]

    def can_insert(self, state: EpochState, atomic: AtomicOrder, vehicle_id: str) -> bool:
        """Check the exact insertion mask without calculating projected cost.

        The policy mask must not advertise an action that ``probe`` will
        reject (for example, a vehicle with a committed destination and a
        carrying stack).  This short-circuiting validator keeps the mask
        exact while avoiding the O(n) cost projection for every candidate.
        """

        if vehicle_id not in state.vehicles:
            return False
        if not self._order_split_allowed(state, atomic, vehicle_id):
            return False
        vehicle = state.vehicles[vehicle_id]
        if atomic.demand > vehicle.capacity + 1e-8:
            return False
        base = list(vehicle.planned_route)
        pickup = RouteNode(atomic.pickup_factory_id, atomic.item_ids, ())
        delivery = RouteNode(atomic.delivery_factory_id, (), tuple(reversed(atomic.item_ids)))
        for i, j, route in self._candidate_routes(base, pickup, delivery):
                candidate_vehicle = replace(vehicle, planned_route=route)
                expected = set(str(item_id) for item_id in candidate_vehicle.carrying_item_ids)
                if candidate_vehicle.destination is not None:
                    expected.update(candidate_vehicle.destination.pickup_item_ids)
                    expected.update(candidate_vehicle.destination.delivery_item_ids)
                for node in route:
                    expected.update(node.pickup_item_ids)
                    expected.update(node.delivery_item_ids)
                report = self.validator.validate(
                    {vehicle_id: route}, {vehicle_id: candidate_vehicle}, state.items,
                    expected_item_ids=expected,
                    destinations={vehicle_id: candidate_vehicle.destination},
                )
                if report.valid:
                    return True
        return False

    @staticmethod
    def _order_split_allowed(state: EpochState, atomic: AtomicOrder, selected_vehicle: str) -> bool:
        """Keep fitting original orders on one vehicle; allow large chunks to split."""
        order_items = [item for item in state.items.values()
                       if str(item_attr(item, "order_id", "")) == atomic.order_id]
        order_item_ids = {str(item_attr(item, "id", "")) for item in order_items}
        total_demand = sum(float(item_attr(item, "demand", 0.0) or 0.0) for item in order_items)
        if total_demand <= state.vehicles[selected_vehicle].capacity + 1e-8:
            for vehicle_id, vehicle in state.vehicles.items():
                if vehicle_id == selected_vehicle:
                    continue
                existing_ids = set(vehicle.carrying_item_ids)
                if vehicle.destination is not None:
                    existing_ids.update(vehicle.destination.pickup_item_ids)
                    existing_ids.update(vehicle.destination.delivery_item_ids)
                for node in vehicle.planned_route:
                    existing_ids.update(node.pickup_item_ids)
                    existing_ids.update(node.delivery_item_ids)
                if existing_ids & order_item_ids:
                    return False
        return True

    def apply(self, state: EpochState, result: InsertionResult) -> EpochState:
        if not result.ok or result.vehicle_id is None:
            raise ValueError(result.reason or "cannot apply failed insertion")
        vehicle = state.vehicles[result.vehicle_id]
        updated = replace(vehicle, planned_route=tuple(result.route))
        vehicles = dict(state.vehicles)
        vehicles[result.vehicle_id] = updated
        return replace(state, vehicles=vehicles)

    def dispatch(self, state: EpochState, atomics: Sequence[AtomicOrder]) -> EpochState:
        current = state
        for atomic in atomics:
            result = self.probe(current, atomic)
            if not result.ok:
                raise ValueError(result.reason)
            current = self.apply(current, result)
        return current

    def decode_assignments(
        self,
        state: EpochState,
        atomics: Sequence[AtomicOrder],
        vehicle_assignments: Mapping[str, str],
        *,
        order: Optional[Sequence[str]] = None,
        deadline: Optional[float] = None,
    ) -> Optional[EpochState]:
        """Decode a fleet assignment through the canonical insertion planner.

        This is the single phenotype contract shared by policy rollouts, the
        GA teacher, and subprocess inference.  A genome may choose an order
        sequence, but it may not bypass feasibility checks or use a second
        route-construction implementation.
        """

        atomic_by_id = {atomic.atomic_id: atomic for atomic in atomics}
        sequence = tuple(order or (atomic.atomic_id for atomic in atomics))
        if set(sequence) != set(atomic_by_id) or len(sequence) != len(atomic_by_id):
            return None
        current = state
        for atomic_id in sequence:
            vehicle_id = vehicle_assignments.get(atomic_id)
            if vehicle_id is None:
                return None
            result = self.probe(
                current, atomic_by_id[atomic_id],
                selected_vehicle=str(vehicle_id), deadline=deadline,
            )
            if not result.ok:
                return None
            current = self.apply(current, result)
        report = self.validator.validate(
            {key: value.planned_route for key, value in current.vehicles.items()},
            current.vehicles,
            current.items,
            destinations={key: value.destination for key, value in current.vehicles.items()},
        )
        return current if report.valid else None

    @staticmethod
    def _expected_ids(state: EpochState, atomic: AtomicOrder):
        expected = set()
        for vehicle in state.vehicles.values():
            if vehicle.destination:
                expected.update(vehicle.destination.pickup_item_ids)
                expected.update(vehicle.destination.delivery_item_ids)
            for node in vehicle.planned_route:
                expected.update(node.pickup_item_ids)
                expected.update(node.delivery_item_ids)
        expected.update(atomic.item_ids)
        return expected
