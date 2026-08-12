"""Leakage-safe synthetic DPDP episodes built only from a route graph.

The generator never reads ICAPS order rows.  A caller may provide the static
route map/factory metadata as environment context; all order streams,
deadlines and release times are sampled from the supplied generator seed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from algorithm.evorl.atomic import chunk_items, mutable_item_ids
from algorithm.evorl.cost import projected_cost
from algorithm.evorl.dto import AtomicOrder, EpochState, RouteNode, VehicleState


@dataclass(frozen=True)
class SyntheticConfig:
    num_factories: int = 20
    num_vehicles: int = 5
    orders_per_episode: int = 50
    capacity: float = 15.0
    horizon_steps: int = 144
    epoch_seconds: int = 600
    max_items_per_order: int = 8
    max_order_demand: float = 30.0
    deadline_min_steps: int = 6
    deadline_max_steps: int = 48


class SyntheticDPDPEpisode:
    """A deterministic, dynamic order stream over a fixed factory graph."""

    def __init__(self, config: SyntheticConfig = SyntheticConfig(), *, seed: int = 0,
                 factories: Mapping[str, Any] | None = None,
                 route_map: Mapping[Tuple[str, str], Tuple[float, float]] | None = None):
        self.config = config
        self.seed = int(seed)
        self.rng = random.Random(seed)
        self.start_time = 0
        self.factories = dict(factories) if factories else self._make_factories()
        self.route_map = dict(route_map) if route_map else self._make_routes()
        self.items = self._make_orders()
        self.state = self._initial_state()

    def reset(self, *, seed: int | None = None) -> EpochState:
        if seed is not None:
            self.__init__(self.config, seed=int(seed), factories=self.factories, route_map=self.route_map)
        else:
            self.state = self._initial_state()
        return self.state

    def available_at(self, state: EpochState | None = None) -> List[AtomicOrder]:
        state = state or self.state
        covered = set()
        for vehicle in state.vehicles.values():
            for node in vehicle.planned_route:
                covered.update(node.pickup_item_ids)
                covered.update(node.delivery_item_ids)
            if vehicle.destination:
                covered.update(vehicle.destination.pickup_item_ids)
                covered.update(vehicle.destination.delivery_item_ids)
        generated = [item for item in self.items.values()
                     if int(item["creation_time"]) <= state.current_time and item["id"] not in covered]
        return chunk_items(generated, capacity=self.config.capacity)

    def advance(self, state: EpochState, *, elapsed_seconds: int | None = None) -> EpochState:
        next_time = state.current_time + int(elapsed_seconds or self.config.epoch_seconds)
        next_state = replace(state, epoch=state.epoch + 1, current_time=next_time)
        self.state = next_state
        return next_state

    def terminal(self, state: EpochState) -> bool:
        return state.epoch >= self.config.horizon_steps and not self.available_at(state)

    def score(self, state: EpochState) -> float:
        return projected_cost(
            {key: value.planned_route for key, value in state.vehicles.items()},
            state.vehicles, state.route_map, state.items, current_time=state.current_time,
        ).benchmark_cost

    def _initial_state(self) -> EpochState:
        vehicles = {
            f"V_{index + 1}": VehicleState(
                vehicle_id=f"V_{index + 1}", capacity=self.config.capacity,
                current_factory_id=sorted(self.factories)[index % len(self.factories)],
            )
            for index in range(self.config.num_vehicles)
        }
        return EpochState(0, self.start_time, self.items, vehicles, self.factories, self.route_map)

    def _make_factories(self) -> Dict[str, Dict[str, float]]:
        factories = {}
        for index in range(self.config.num_factories):
            angle = 2.0 * math.pi * index / max(1, self.config.num_factories)
            factories[f"F_{index + 1}"] = {
                "id": f"F_{index + 1}", "lng": 50.0 + 40.0 * math.cos(angle),
                "lat": 50.0 + 40.0 * math.sin(angle), "dock_num": 6,
            }
        return factories

    def _make_routes(self) -> Dict[Tuple[str, str], Tuple[float, float]]:
        result = {}
        for left, left_data in self.factories.items():
            for right, right_data in self.factories.items():
                distance = math.hypot(left_data["lng"] - right_data["lng"], left_data["lat"] - right_data["lat"])
                result[(left, right)] = (distance, int(distance * 60.0))
        return result

    def _make_orders(self) -> Dict[str, Dict[str, Any]]:
        factory_ids = sorted(self.factories)
        items: Dict[str, Dict[str, Any]] = {}
        for order_index in range(self.config.orders_per_episode):
            order_id = f"S{self.seed:06d}-O{order_index:05d}"
            pickup, delivery = self.rng.sample(factory_ids, 2)
            item_count = self.rng.randint(1, self.config.max_items_per_order)
            remaining = self.rng.uniform(1.0, self.config.max_order_demand)
            demands = []
            for index in range(item_count - 1):
                maximum = min(1.0, remaining - 0.25 * (item_count - index - 1))
                demand = self.rng.choice([0.25, 0.5, 1.0]) if maximum >= 0.25 else 0.25
                demand = min(demand, maximum)
                demands.append(demand)
                remaining -= demand
            demands.append(max(0.25, min(1.0, remaining)))
            creation = self.rng.randrange(self.config.horizon_steps) * self.config.epoch_seconds
            deadline = creation + self.rng.randint(self.config.deadline_min_steps, self.config.deadline_max_steps) * self.config.epoch_seconds
            for item_index, demand in enumerate(demands):
                item_id = f"{order_id}-{item_index + 1}"
                items[item_id] = {
                    "id": item_id, "type": "PALLET", "order_id": order_id,
                    "demand": float(demand), "pickup_factory_id": pickup,
                    "delivery_factory_id": delivery, "creation_time": creation,
                    "committed_completion_time": deadline, "load_time": int(demand * 240),
                    "unload_time": int(demand * 240), "delivery_state": 1,
                }
        return items
