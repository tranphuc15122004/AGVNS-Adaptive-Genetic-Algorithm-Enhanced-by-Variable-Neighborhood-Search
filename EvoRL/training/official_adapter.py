"""Serialization-isolated adapter for ``src.common.InputInfo`` snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Tuple

from algorithm.evorl.dto import EpochState, RouteNode, VehicleState, factory_to_dto, item_to_dto, node_to_dto


class RouteMapAdapter(Mapping):
    """Expose the official ``src.common.route.Map`` through ``Mapping.get``."""

    def __init__(self, route_map: Any):
        self.route_map = route_map

    def __getitem__(self, key):
        start, end = key
        if not start or not end:
            return (0.0, 0.0)
        distance = self.route_map.calculate_distance_between_factories(start, end)
        travel_time = self.route_map.calculate_transport_time_between_factories(start, end)
        return float(distance), float(travel_time)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def get(self, key, default=None):
        try:
            return self[key]
        except Exception:
            return default


class OfficialInputAdapter:
    """Copy simulator objects into DTOs; policy code never receives aliases."""

    @staticmethod
    def snapshot(input_info: Any, *, epoch: int = 0, current_time: int = 0) -> EpochState:
        all_items = {}
        all_items.update({
            str(item_id): item_to_dto(item)
            for item_id, item in (getattr(input_info, "id_to_unallocated_order_item", {}) or {}).items()
        })
        all_items.update({
            str(item_id): item_to_dto(item)
            for item_id, item in (getattr(input_info, "id_to_ongoing_order_item", {}) or {}).items()
        })
        vehicles = {}
        for vehicle_id, vehicle in (getattr(input_info, "id_to_vehicle", {}) or {}).items():
            try:
                carrying = tuple(str(item.id) for item in vehicle.get_loading_sequence())
            except Exception:
                carrying = ()
            destination = getattr(vehicle, "destination", None)
            vehicles[str(vehicle_id)] = VehicleState(
                vehicle_id=str(vehicle_id),
                capacity=float(vehicle.board_capacity),
                current_factory_id=str(getattr(vehicle, "cur_factory_id", "") or ""),
                carrying_item_ids=carrying,
                destination=node_to_dto(destination) if destination is not None else None,
                planned_route=tuple(node_to_dto(node) for node in (getattr(vehicle, "planned_route", []) or [])),
            )
        source_factories = getattr(input_info, "id_to_factory", {}) or {}
        factories = {
            str(factory_id): factory_to_dto(factory_id, factory)
            for factory_id, factory in source_factories.items()
        }
        return EpochState(
            epoch=epoch,
            current_time=current_time,
            items=dict(all_items),
            vehicles=vehicles,
            factories=dict(factories),
            route_map=RouteMapAdapter(getattr(input_info, "route_map", {})),
        )
