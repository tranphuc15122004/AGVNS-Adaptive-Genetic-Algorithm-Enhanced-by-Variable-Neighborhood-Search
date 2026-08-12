"""In-process driver for the official ICAPS simulator.

This module deliberately calls the same simulator primitives used by the
competition loop.  It never hands simulator-owned ``InputInfo`` objects to the
policy; snapshots cross the immutable DTO boundary in
``OfficialInputAdapter``.  Subprocess execution remains available for final
benchmarking through ``training.evaluate``.
"""

from __future__ import annotations

import copy
import math
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from algorithm.evorl.cost import projected_cost
from algorithm.evorl.dto import EpochState, RouteNode
from src.common.dispatch_result import DispatchResult
from src.common.node import Node
from src.utils.checker import Checker
from src.utils.evaluator import Evaluator
from src.simulator.simulate_api import initialize_environment

from .official_adapter import OfficialInputAdapter
from .reward import RewardBreakdown, compose_reward
from .trace import append_trace, stable_digest


class OfficialEnvironmentError(RuntimeError):
    """Raised when a strict in-process dispatch violates ICAPS semantics."""


@dataclass(frozen=True)
class OfficialStep:
    observation: EpochState
    reward: RewardBreakdown
    done: bool
    info: Mapping[str, Any]


class OfficialDPDPEnv:
    """Reset/observe/step state machine around ``SimulateEnvironment``."""

    def __init__(
        self,
        factory_info_file: str,
        route_info_file: str,
        instance: str,
        *,
        simulator_seed: int = 0,
        strict: bool = True,
        trace_path: str | None = None,
    ):
        self.factory_info_file = factory_info_file
        self.route_info_file = route_info_file
        self.instance = instance
        self.simulator_seed = int(simulator_seed)
        self.strict = bool(strict)
        self.simulator = None
        self.input_info = None
        self.observation: Optional[EpochState] = None
        self.done = False
        self.epoch = 0
        self.score: Optional[float] = None
        self._accepted_state: Optional[EpochState] = None
        self.trace_path = trace_path

    def reset(self) -> EpochState:
        self.simulator = initialize_environment(
            self.factory_info_file, self.route_info_file, self.instance,
            simulator_seed=self.simulator_seed,
        )
        if self.simulator is None:
            raise OfficialEnvironmentError(f"could not initialize ICAPS instance {self.instance}")
        self.input_info = None
        self.observation = None
        self.done = False
        self.score = None
        self._accepted_state = None
        self.epoch = 0
        self._advance_to_next_decision(first=True)
        assert self.observation is not None
        return self.observation

    def observe(self) -> EpochState:
        if self.observation is None:
            return self.reset()
        return self.observation

    def step(self, state_or_dispatch: EpochState | DispatchResult) -> OfficialStep:
        if self.simulator is None or self.observation is None:
            raise OfficialEnvironmentError("reset() must be called before step()")
        if self.done:
            raise OfficialEnvironmentError("cannot step a terminal ICAPS episode")
        before = self.observation
        started = time.perf_counter()
        dispatch_result = (
            state_or_dispatch if isinstance(state_or_dispatch, DispatchResult)
            else self._to_dispatch_result(state_or_dispatch)
        )
        if not isinstance(state_or_dispatch, DispatchResult):
            self._accepted_state = self._normalize_dispatch_state(state_or_dispatch)
        if not Checker.check_dispatch_result(
            dispatch_result, self.simulator.id_to_vehicle, self.simulator.id_to_order,
        ):
            raise OfficialEnvironmentError(f"official Checker rejected epoch {self.epoch}")
        self.simulator.deliver_control_command_to_vehicles(dispatch_result)
        if self.simulator.complete_the_dispatch_of_all_orders():
            self._finalize()
        else:
            if self.simulator.ignore_allocating_timeout_orders(dispatch_result):
                raise OfficialEnvironmentError("an expired generated item was not dispatched")
            self._advance_to_next_decision(first=False)
        after = self.observation or before
        before_cost = self._projected_cost(before)
        after_cost = self._projected_cost(after)
        reward = compose_reward(
            before_cost,
            after_cost,
            terminal=self.done,
            terminal_score=self.score if self.done else None,
        )
        route_snapshot = self._trace_snapshot(self._accepted_state or before)
        append_trace({
            "schema_version": 1,
            "episode_id": self.instance,
            "epoch": max(0, self.epoch - 1),
            "current_time": int(before.current_time),
            "route_hash": stable_digest(route_snapshot),
            "route_snapshot": route_snapshot,
            "checker_precondition": True,
            "official_score": self.score,
            "reward_total": float(reward.total),
            "wall_seconds": time.perf_counter() - started,
        }, self.trace_path)
        return OfficialStep(
            observation=after,
            reward=reward,
            done=self.done,
            info={
                "epoch": self.epoch,
                "official_score": self.score,
                "official_terminal_score": self.score if self.done else None,
                "before_projected_cost": before_cost.benchmark_cost,
                "after_projected_cost": after_cost.benchmark_cost,
            },
        )

    def finalize(self) -> float:
        if self.simulator is None:
            raise OfficialEnvironmentError("reset() must be called before finalize()")
        if not self.done:
            self._finalize()
        assert self.score is not None
        return self.score

    def _advance_to_next_decision(self, *, first: bool) -> None:
        assert self.simulator is not None
        if not first:
            # ``elapsed=0`` is intentional: training/GA wall-clock time must
            # not change the simulator's ten-minute decision interval.
            self.simulator.pre_time = self.simulator.cur_time
        self.simulator.cur_time = self.simulator.pre_time + (
            0 // self.simulator.time_interval + 1
        ) * self.simulator.time_interval
        self.input_info = self.simulator.update_input()
        snapshot = OfficialInputAdapter.snapshot(
            self.input_info, epoch=self.epoch, current_time=self.simulator.cur_time,
        )
        self.observation = self._restore_route_suffix(snapshot)
        self.epoch += 1

    def _finalize(self) -> None:
        assert self.simulator is not None
        self.simulator.simulate_the_left_ongoing_orders_of_vehicles(self.simulator.id_to_vehicle)
        self.score = float(Evaluator.calculate_total_score(
            self.simulator.history, self.simulator.route_map, len(self.simulator.id_to_vehicle),
        ))
        if self.strict and (not math.isfinite(self.score) or self.score >= float(sys.maxsize)):
            raise OfficialEnvironmentError("official terminal evaluator returned an invalid score")
        self.done = True

    def _projected_cost(self, state: EpochState):
        return projected_cost(
            {key: value.planned_route for key, value in state.vehicles.items()},
            state.vehicles, state.route_map, state.items,
            current_time=state.current_time,
        )

    def _to_dispatch_result(self, state: EpochState) -> DispatchResult:
        if set(state.vehicles) != set(self.simulator.id_to_vehicle):
            raise OfficialEnvironmentError("dispatch state does not contain every official vehicle")
        destinations = {}
        planned_routes = {}
        for vehicle_id, vehicle_state in state.vehicles.items():
            route_nodes = list(vehicle_state.planned_route)
            destination = vehicle_state.destination
            # Official ``DispatchResult`` separates the next node from the
            # remaining route.  Canonical planning keeps a newly constructed
            # route in ``planned_route`` until this boundary, so promote its
            # first node when no destination is already committed.
            if destination is None and route_nodes:
                destination, route_nodes = route_nodes[0], route_nodes[1:]
            destinations[vehicle_id] = self._to_node(destination)
            planned_routes[vehicle_id] = [self._to_node(node) for node in route_nodes]
        return DispatchResult(destinations, planned_routes)

    def _normalize_dispatch_state(self, state: EpochState) -> EpochState:
        """Represent the official destination/route split in canonical form."""

        vehicles = {}
        for vehicle_id, vehicle in state.vehicles.items():
            route = list(vehicle.planned_route)
            destination = vehicle.destination
            if destination is None and route:
                destination, route = route[0], route[1:]
            vehicles[vehicle_id] = type(vehicle)(
                vehicle_id=vehicle.vehicle_id, capacity=vehicle.capacity,
                current_factory_id=vehicle.current_factory_id,
                carrying_item_ids=vehicle.carrying_item_ids,
                destination=destination, committed_prefix=vehicle.committed_prefix,
                planned_route=tuple(route),
            )
        return EpochState(state.epoch, state.current_time, state.items, vehicles, state.factories, state.route_map)

    def _restore_route_suffix(self, snapshot: EpochState) -> EpochState:
        """Restore route suffix lost when the simulator clears planned_route."""

        if self._accepted_state is None:
            return snapshot
        accepted = self._accepted_state
        vehicles = dict(snapshot.vehicles)
        for vehicle_id, current in snapshot.vehicles.items():
            previous = accepted.vehicles.get(vehicle_id)
            if previous is None:
                continue
            accepted_full = list(previous.planned_route)
            if previous.destination is not None:
                accepted_full.insert(0, previous.destination)
            if current.destination is None:
                continue
            current_key = self._node_key(current.destination)
            match = next((index for index, node in enumerate(accepted_full) if self._node_key(node) == current_key), None)
            if match is None:
                continue
            vehicles[vehicle_id] = type(current)(
                vehicle_id=current.vehicle_id, capacity=current.capacity,
                current_factory_id=current.current_factory_id,
                carrying_item_ids=current.carrying_item_ids,
                destination=current.destination,
                committed_prefix=current.committed_prefix,
                planned_route=tuple(accepted_full[match + 1:]),
            )
        return EpochState(snapshot.epoch, snapshot.current_time, snapshot.items, vehicles, snapshot.factories, snapshot.route_map)

    @staticmethod
    def _node_key(node: RouteNode):
        return (node.factory_id, tuple(node.pickup_item_ids), tuple(node.delivery_item_ids))

    @staticmethod
    def _trace_snapshot(state: EpochState):
        return {
            vehicle_id: {
                "destination": OfficialDPDPEnv._trace_node(vehicle.destination),
                "route": [OfficialDPDPEnv._trace_node(node) for node in vehicle.planned_route],
                "carrying": list(vehicle.carrying_item_ids),
            }
            for vehicle_id, vehicle in sorted(state.vehicles.items())
        }

    @staticmethod
    def _trace_node(node: Optional[RouteNode]):
        if node is None:
            return None
        return {
            "factory_id": node.factory_id,
            "pickup_item_ids": list(node.pickup_item_ids),
            "delivery_item_ids": list(node.delivery_item_ids),
            "arrive_time": int(node.arrive_time),
            "leave_time": int(node.leave_time),
        }

    def _to_node(self, node: Optional[RouteNode]):
        if node is None:
            return None
        factory = self.simulator.id_to_factory.get(node.factory_id)
        if factory is None:
            raise OfficialEnvironmentError(f"unknown factory {node.factory_id}")
        items = self.simulator.id_to_order_item
        pickup = [items[item_id] for item_id in node.pickup_item_ids if item_id in items]
        delivery = [items[item_id] for item_id in node.delivery_item_ids if item_id in items]
        return Node(
            node.factory_id, float(factory.lng), float(factory.lat), pickup, delivery,
            int(node.arrive_time), int(node.leave_time),
        )
