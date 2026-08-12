"""Bridge between canonical DTOs and the legacy algorithm objects."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from .atomic import chunk_items
from .dto import EpochState, RouteNode, VehicleState, factory_to_dto, item_to_dto
from .planner import TransactionalPlanner


def build_epoch_state(
    plans: Mapping[str, Sequence[Any]],
    vehicles: Mapping[str, Any],
    items: Mapping[str, Any],
    factories: Mapping[str, Any],
    route_map: Mapping,
    *,
    epoch: int = 0,
    current_time: int = 0,
) -> EpochState:
    # The subprocess path owns the mutable simulator objects.  Keep the
    # canonical solver state just as isolated as the in-process training
    # adapter: policies/GA probes must never receive an OrderItem/Factory
    # alias that can mutate the simulator before Checker validation.
    item_snapshot = {
        str(item_id): item_to_dto(item)
        for item_id, item in (items or {}).items()
    }
    factory_snapshot = {
        str(factory_id): factory_to_dto(factory_id, factory)
        for factory_id, factory in (factories or {}).items()
    }
    vehicle_states = {}
    for vehicle_id, vehicle in vehicles.items():
        carrying = getattr(vehicle, "carrying_items", ())
        if hasattr(carrying, "items"):
            carrying = list(carrying.items)
        destination = getattr(vehicle, "des", None)
        dto_destination = _node_to_dto(destination) if destination is not None else None
        dto_route = [_node_to_dto(node) for node in (plans.get(vehicle_id) or ())]
        # Historical solution.json files may contain the committed destination
        # both in ``vehicle.des`` and at route index zero.  Keep one copy so
        # the validator does not report a false LIFO/duplicate violation.
        if dto_destination is not None and dto_route:
            # Depending on whether the previous subprocess wrote destination
            # and route files before/after merging, the committed destination
            # can occur at index 0 *or* at the tail of the restored route.
            # Remove exactly one identical copy; retaining it would make the
            # next dispatch deliver the same stack twice and can exceed
            # capacity after boundary merging.
            for index, route_node in enumerate(dto_route):
                if (route_node.factory_id == dto_destination.factory_id and
                        route_node.pickup_item_ids == dto_destination.pickup_item_ids and
                        route_node.delivery_item_ids == dto_destination.delivery_item_ids):
                    dto_route = dto_route[:index] + dto_route[index + 1:]
                    break
        # Some historical restore paths expose the committed destination in
        # ``vehicle.des`` while also leaving its pickup/delivery nodes in the
        # route list.  Those node entries must not be emitted a second time.
        # Pickup and delivery IDs are handled separately: a destination pickup
        # still needs its future delivery suffix, whereas a destination
        # delivery is already committed.
        locked_delivery_ids = set()
        locked_pickup_ids = set()
        if dto_destination is not None:
            # A destination pickup is not yet on the vehicle; its future
            # delivery node must remain in the route suffix.  Destination
            # deliveries, by contrast, are already committed and are often
            # duplicated in historical route files.
            locked_delivery_ids.update(dto_destination.delivery_item_ids)
            locked_pickup_ids.update(dto_destination.pickup_item_ids)
        if locked_delivery_ids or locked_pickup_ids:
            normalized_route = []
            for route_node in dto_route:
                normalized = RouteNode(
                    route_node.factory_id,
                    tuple(
                        item_id for item_id in route_node.pickup_item_ids
                        if item_id not in locked_delivery_ids and item_id not in locked_pickup_ids
                    ),
                    tuple(item_id for item_id in route_node.delivery_item_ids
                          if item_id not in locked_delivery_ids),
                    route_node.arrive_time, route_node.leave_time,
                )
                if normalized.pickup_item_ids or normalized.delivery_item_ids:
                    normalized_route.append(normalized)
            dto_route = normalized_route
        vehicle_states[vehicle_id] = VehicleState(
            vehicle_id=str(vehicle_id),
            capacity=float(getattr(vehicle, "board_capacity", 15) or 15),
            current_factory_id=str(getattr(vehicle, "cur_factory_id", "") or ""),
            carrying_item_ids=tuple(str(getattr(item, "id", item)) for item in (carrying or ())),
            destination=dto_destination,
            planned_route=tuple(dto_route),
        )
    return EpochState(
        epoch, current_time, item_snapshot, vehicle_states, factory_snapshot,
        _RouteMapAdapter(route_map),
    )


def apply_epoch_state(
    state: EpochState,
    plans: Dict[str, List[Any]],
    items: Mapping[str, Any],
    factories: Mapping[str, Any],
) -> None:
    """Apply a new plan atomically at the algorithm boundary."""

    from algorithm.Object import Node

    converted: Dict[str, List[Any]] = {}
    for vehicle_id, vehicle in state.vehicles.items():
        route = []
        if vehicle.destination is not None:
            destination = vehicle.destination
            factory = factories.get(destination.factory_id)
            if factory is None:
                raise ValueError(f"unknown destination factory {destination.factory_id}")
            route.append(Node(
                factory_id=destination.factory_id,
                delivery_item_list=[items[item_id] for item_id in destination.delivery_item_ids if item_id in items],
                pickup_item_list=[items[item_id] for item_id in destination.pickup_item_ids if item_id in items],
                arrive_time=destination.arrive_time,
                leave_time=destination.leave_time,
                lng=float(getattr(factory, "lng", 0.0)),
                lat=float(getattr(factory, "lat", 0.0)),
            ))
        for node in vehicle.planned_route:
            factory = factories.get(node.factory_id)
            if factory is None:
                raise ValueError(f"unknown factory {node.factory_id}")
            pickups = [items[item_id] for item_id in node.pickup_item_ids if item_id in items]
            deliveries = [items[item_id] for item_id in node.delivery_item_ids if item_id in items]
            route.append(Node(
                factory_id=node.factory_id,
                delivery_item_list=deliveries,
                pickup_item_list=pickups,
                arrive_time=node.arrive_time,
                leave_time=node.leave_time,
                lng=float(getattr(factory, "lng", 0.0)),
                lat=float(getattr(factory, "lat", 0.0)),
            ))
        converted[vehicle_id] = route
    plans.clear()
    plans.update(converted)


def dispatch_atomic_legacy(
    plans: Dict[str, List[Any]],
    vehicles: Mapping[str, Any],
    items: Mapping[str, Any],
    factories: Mapping[str, Any],
    route_map: Mapping,
    item_ids: Sequence[str],
    *,
    epoch: int = 0,
    current_time: int = 0,
) -> EpochState:
    mutable = [items[item_id] for item_id in item_ids if item_id in items]
    if not mutable:
        return build_epoch_state(plans, vehicles, items, factories, route_map, epoch=epoch, current_time=current_time)
    state = build_epoch_state(plans, vehicles, items, factories, route_map, epoch=epoch, current_time=current_time)
    atomics = chunk_items(mutable, capacity=_uniform_capacity(vehicles))
    next_state = TransactionalPlanner().dispatch(state, atomics)
    apply_epoch_state(next_state, plans, items, factories)
    return next_state


def _uniform_capacity(vehicles: Mapping[str, Any]) -> float:
    capacities = {float(getattr(vehicle, "board_capacity", 15) or 15) for vehicle in vehicles.values()}
    if not capacities:
        return 15.0
    if len(capacities) != 1:
        raise ValueError(f"ICAPS mode requires uniform capacity, got {sorted(capacities)}")
    return next(iter(capacities))


class _RouteMapAdapter(Mapping):
    """Expose legacy route-map methods through the canonical mapping API."""

    def __init__(self, route_map: Any):
        self.route_map = route_map

    def __getitem__(self, key):
        start, end = key
        if not start or not end:
            return 0.0, 0.0
        if hasattr(self.route_map, "calculate_distance_between_factories"):
            return (
                float(self.route_map.calculate_distance_between_factories(start, end)),
                float(self.route_map.calculate_transport_time_between_factories(start, end)),
            )
        if isinstance(self.route_map, Mapping):
            value = self.route_map.get((start, end))
            if value is None:
                value = self.route_map.get((end, start))
            if value is not None:
                if isinstance(value, Mapping):
                    return float(value.get("distance", 0.0)), float(value.get("time", 0.0))
                return float(value[0]), float(value[1])
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, TypeError, ValueError, AttributeError):
            return default


def _node_to_dto(node: Any) -> RouteNode:
    pickups = getattr(node, "pickup_item_list", getattr(node, "pickup_items", ())) or ()
    deliveries = getattr(node, "delivery_item_list", getattr(node, "delivery_items", ())) or ()
    return RouteNode(
        factory_id=str(getattr(node, "id", "")),
        pickup_item_ids=tuple(str(getattr(item, "id", item)) for item in pickups),
        delivery_item_ids=tuple(str(getattr(item, "id", item)) for item in deliveries),
        arrive_time=int(getattr(node, "arrive_time", 0) or 0),
        leave_time=int(getattr(node, "leave_time", 0) or 0),
    )
