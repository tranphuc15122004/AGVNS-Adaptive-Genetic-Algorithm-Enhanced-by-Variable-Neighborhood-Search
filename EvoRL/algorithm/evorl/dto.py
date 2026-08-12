"""Immutable, serialization-safe domain types used by EvoRL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ItemState:
    """Immutable item snapshot used by the in-process training boundary.

    The official simulator owns mutable ``OrderItem`` instances.  Keeping a
    small primitive copy here prevents an encoder/GA probe from changing the
    simulator before the official Checker sees the dispatch result.
    """

    id: str
    type: str
    order_id: str
    demand: float
    pickup_factory_id: str
    delivery_factory_id: str
    creation_time: int = 0
    committed_completion_time: int = 0
    load_time: int = 0
    unload_time: int = 0
    delivery_state: int = 1


@dataclass(frozen=True)
class FactoryState:
    """Immutable factory metadata used by the encoder/evaluator."""

    factory_id: str
    lng: float = 0.0
    lat: float = 0.0
    dock_num: int = 0


@dataclass(frozen=True)
class AtomicOrder:
    """A capacity-feasible group of items from one original order."""

    atomic_id: str
    order_id: str
    item_ids: Tuple[str, ...]
    demand: float
    pickup_factory_id: str
    delivery_factory_id: str
    committed_completion_time: int = 0
    creation_time: int = 0


@dataclass(frozen=True)
class RouteNode:
    factory_id: str
    pickup_item_ids: Tuple[str, ...] = ()
    delivery_item_ids: Tuple[str, ...] = ()
    arrive_time: int = 0
    leave_time: int = 0


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    capacity: float
    current_factory_id: str
    carrying_item_ids: Tuple[str, ...] = ()
    destination: Optional[RouteNode] = None
    committed_prefix: Tuple[RouteNode, ...] = ()
    planned_route: Tuple[RouteNode, ...] = ()


@dataclass(frozen=True)
class EpochState:
    epoch: int
    current_time: int
    items: Mapping[str, Any]
    vehicles: Mapping[str, VehicleState]
    factories: Mapping[str, Any] = field(default_factory=dict)
    route_map: Mapping[Tuple[str, str], Tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class InsertionResult:
    ok: bool
    vehicle_id: Optional[str] = None
    pickup_position: Optional[int] = None
    delivery_position: Optional[int] = None
    route: Tuple[RouteNode, ...] = ()
    reason: str = ""
    delta_cost: float = 0.0


def item_attr(item: Any, name: str, default: Any = None) -> Any:
    """Read an attribute from either a legacy DTO or a JSON-like mapping."""

    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def item_to_dto(item: Any) -> ItemState:
    """Copy an official/legacy order item into an immutable primitive DTO."""

    return ItemState(
        id=str(item_attr(item, "id", "")),
        type=str(item_attr(item, "type", item_attr(item, "item_type", "")) or ""),
        order_id=str(item_attr(item, "order_id", "")),
        demand=float(item_attr(item, "demand", 0.0) or 0.0),
        pickup_factory_id=str(item_attr(item, "pickup_factory_id", "")),
        delivery_factory_id=str(item_attr(item, "delivery_factory_id", "")),
        creation_time=int(item_attr(item, "creation_time", 0) or 0),
        committed_completion_time=int(item_attr(item, "committed_completion_time", 0) or 0),
        load_time=int(item_attr(item, "load_time", 0) or 0),
        unload_time=int(item_attr(item, "unload_time", 0) or 0),
        delivery_state=int(item_attr(item, "delivery_state", 1) or 1),
    )


def factory_to_dto(factory_id: str, factory: Any) -> FactoryState:
    """Copy official factory metadata without retaining simulator aliases."""

    return FactoryState(
        factory_id=str(factory_id),
        lng=float(item_attr(factory, "lng", item_attr(factory, "longitude", 0.0)) or 0.0),
        lat=float(item_attr(factory, "lat", item_attr(factory, "latitude", 0.0)) or 0.0),
        dock_num=int(item_attr(factory, "dock_num", item_attr(factory, "port_num", 0)) or 0),
    )


def node_to_dto(node: Any) -> RouteNode:
    """Convert a legacy algorithm Node or simulator Node to a pure DTO."""

    if isinstance(node, Mapping):
        return RouteNode(
            factory_id=str(node.get("factory_id", node.get("id", ""))),
            pickup_item_ids=tuple(str(x) for x in node.get("pickup_item_ids", node.get("pickup_items", ())) or ()),
            delivery_item_ids=tuple(str(x) for x in node.get("delivery_item_ids", node.get("delivery_items", ())) or ()),
            arrive_time=int(node.get("arrive_time", 0) or 0),
            leave_time=int(node.get("leave_time", 0) or 0),
        )
    pickups = getattr(node, "pickup_item_list", None)
    if pickups is None:
        pickups = getattr(node, "pickup_items", ())
    deliveries = getattr(node, "delivery_item_list", None)
    if deliveries is None:
        deliveries = getattr(node, "delivery_items", ())
    return RouteNode(
        factory_id=str(getattr(node, "id", "")),
        pickup_item_ids=tuple(str(getattr(x, "id", x)) for x in (pickups or ())),
        delivery_item_ids=tuple(str(getattr(x, "id", x)) for x in (deliveries or ())),
        arrive_time=int(getattr(node, "arrive_time", 0) or 0),
        leave_time=int(getattr(node, "leave_time", 0) or 0),
    )
