"""Shared-policy observation and action-mask construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from algorithm.evorl.cost import _edge, full_route_for_vehicle
from algorithm.evorl.dto import AtomicOrder, EpochState, item_attr
from algorithm.evorl.planner import TransactionalPlanner


@dataclass(frozen=True)
class CandidateAction:
    atomic_id: str
    vehicle_id: str


@dataclass(frozen=True)
class CandidateObservation:
    actions: Tuple[CandidateAction, ...]
    features: Tuple[Tuple[float, ...], ...]
    mask: Tuple[bool, ...]


class ObservationBuilder:
    """Build fixed-width numerical features for a shared policy."""

    # The first 16 fields preserve the original contract; the final eight
    # expose route, dock, fleet, and backlog context required by ICAPS.
    feature_dim = 24

    def __init__(self, planner: TransactionalPlanner | None = None):
        self.planner = planner or TransactionalPlanner()

    def build(self, state: EpochState, atomic: AtomicOrder) -> CandidateObservation:
        actions: List[CandidateAction] = []
        features: List[Tuple[float, ...]] = []
        mask: List[bool] = []
        remaining_ids = self._remaining_item_ids(state)
        fleet_capacity = sum(float(vehicle.capacity) for vehicle in state.vehicles.values())
        fleet_load = sum(
            float(item_attr(state.items.get(item_id), "demand", 0.0) or 0.0)
            for vehicle in state.vehicles.values()
            for item_id in vehicle.carrying_item_ids
            if item_id in state.items
        )
        fleet_utilization = fleet_load / max(1.0, fleet_capacity)
        for vehicle_id in sorted(state.vehicles):
            vehicle = state.vehicles[vehicle_id]
            current = vehicle.current_factory_id
            if not current and vehicle.destination is not None:
                # The official simulator uses an empty current factory while
                # a vehicle is in transit; its committed destination is the
                # only valid location feature available to the solver.
                current = vehicle.destination.factory_id
            feasible = self._cheap_feasible(state, atomic, vehicle_id)
            pickup_distance, pickup_time = _edge(state.route_map, current, atomic.pickup_factory_id)
            delivery_distance, delivery_time = _edge(
                state.route_map, atomic.pickup_factory_id, atomic.delivery_factory_id,
            )
            estimated_delta = pickup_distance + delivery_distance
            full_route = full_route_for_vehicle(vehicle, vehicle.planned_route)
            route_distance = 0.0
            route_time = 0.0
            route_previous = current
            for route_node in full_route:
                edge_distance, edge_time = _edge(state.route_map, route_previous, route_node.factory_id)
                route_distance += edge_distance
                route_time += edge_time
                route_previous = route_node.factory_id
            pickup_factory = state.factories.get(atomic.pickup_factory_id)
            delivery_factory = state.factories.get(atomic.delivery_factory_id)
            pickup_dock = float(item_attr(pickup_factory, "dock_num", 0) or 0)
            delivery_dock = float(item_attr(delivery_factory, "dock_num", 0) or 0)
            route_load = sum(float(item_attr(state.items.get(item_id), "demand", 0.0) or 0.0)
                             for item_id in vehicle.carrying_item_ids if item_id in state.items)
            features.append((
                float(atomic.demand / max(1.0, vehicle.capacity)),
                float(atomic.committed_completion_time - state.current_time) / 3600.0,
                float(pickup_distance) / 100.0,
                float(pickup_time) / 3600.0,
                float(vehicle.capacity - route_load) / max(1.0, vehicle.capacity),
                float(len(vehicle.planned_route)) / 100.0,
                float(len(vehicle.carrying_item_ids)) / max(1.0, vehicle.capacity),
                float(current == atomic.pickup_factory_id),
                float(current == atomic.delivery_factory_id),
                float(estimated_delta) / 100.0,
                float(state.epoch) / 144.0,
                float(state.current_time % 86400) / 86400.0,
                float(len(vehicle.committed_prefix)) / 100.0,
                float(vehicle.destination is not None),
                float(atomic.creation_time - state.current_time) / 86400.0,
                float(atomic.demand / max(1.0, vehicle.capacity)),
                float(delivery_distance) / 100.0,
                float(delivery_time) / 3600.0,
                float(route_distance) / 100.0,
                float(route_time) / 3600.0,
                pickup_dock / 6.0,
                delivery_dock / 6.0,
                fleet_utilization,
                float(len(remaining_ids)) / 1000.0,
            ))
            actions.append(CandidateAction(atomic.atomic_id, vehicle_id))
            mask.append(bool(feasible))
        if not any(mask) and actions:
            # The caller must fail/retain the prior solution; never silently
            # convert an invalid action into DEFER in v1.
            mask = [False] * len(mask)
        return CandidateObservation(tuple(actions), tuple(features), tuple(mask))

    def _cheap_feasible(self, state: EpochState, atomic: AtomicOrder, vehicle_id: str) -> bool:
        """Return the exact planner-feasible mask without cost projection."""

        return self.planner.can_insert(state, atomic, vehicle_id)

    @staticmethod
    def _remaining_item_ids(state: EpochState) -> Tuple[str, ...]:
        covered = set()
        for vehicle in state.vehicles.values():
            covered.update(vehicle.carrying_item_ids)
            if vehicle.destination is not None:
                covered.update(vehicle.destination.pickup_item_ids)
                covered.update(vehicle.destination.delivery_item_ids)
            for node in vehicle.planned_route:
                covered.update(node.pickup_item_ids)
                covered.update(node.delivery_item_ids)
        return tuple(sorted(
            item_id for item_id, item in state.items.items()
            if item_id not in covered and int(item_attr(item, "delivery_state", 1) or 1) <= 1
        ))
