"""Independent solution invariants for algorithm and simulator routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from .dto import RouteNode, item_attr


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    errors: Tuple[str, ...] = ()

    def raise_if_invalid(self) -> None:
        if not self.valid:
            raise ValueError("invalid solution: " + "; ".join(self.errors))


class SolutionValidator:
    """Validate a candidate against the DPDP route contract.

    The validator accepts both canonical :class:`RouteNode` values and the
    legacy ``algorithm.Object.Node`` values, allowing it to guard the existing
    JSON boundary without changing simulator classes.
    """

    def validate(
        self,
        routes: Mapping[str, Sequence[Any]],
        vehicles: Mapping[str, Any],
        items: Mapping[str, Any] | Iterable[Any],
        *,
        expected_item_ids: Optional[Iterable[str]] = None,
        destinations: Optional[Mapping[str, Any]] = None,
        committed_prefix: Optional[Mapping[str, Sequence[Any]]] = None,
        require_empty_stack: bool = False,
    ) -> ValidationReport:
        errors = []
        item_map = items if isinstance(items, Mapping) else {str(item_attr(x, "id")): x for x in items}
        # ``seen`` counts route occurrences only.  Carrying items are the
        # initial stack and therefore legitimately appear again at delivery.
        seen: Set[str] = set()
        order_to_vehicles: Dict[str, Set[str]] = {}
        order_demands: Dict[str, float] = {}
        expected = set(str(x) for x in expected_item_ids) if expected_item_ids is not None else None

        if set(routes) != set(vehicles):
            missing = sorted(set(vehicles) - set(routes))
            extra = sorted(set(routes) - set(vehicles))
            if missing:
                errors.append(f"missing vehicle routes: {missing}")
            if extra:
                errors.append(f"unknown vehicle routes: {extra}")

        for vehicle_id, vehicle in vehicles.items():
            route = list(routes.get(vehicle_id, ()))
            destination = (destinations or {}).get(vehicle_id)
            if destination is None:
                destination = getattr(vehicle, "des", None)
            full_route = ([destination] if destination is not None else []) + route
            errors.extend(self._validate_vehicle(
                vehicle_id, vehicle, full_route, item_map, seen,
                require_empty_stack=require_empty_stack,
            ))
            for item_id in self._route_item_ids(vehicle, full_route):
                data = item_map.get(item_id)
                if data is None:
                    continue
                order_id = str(item_attr(data, "order_id", ""))
                order_to_vehicles.setdefault(order_id, set()).add(vehicle_id)
                order_demands.setdefault(order_id, 0.0)
                order_demands[order_id] += float(item_attr(data, "demand", 0.0) or 0.0)
            if committed_prefix and not self._has_prefix(committed_prefix.get(vehicle_id, ()), full_route):
                errors.append(f"vehicle {vehicle_id}: committed prefix changed")

        if expected is not None:
            missing = sorted(expected - seen)
            duplicate = sorted(seen - expected)
            if missing:
                errors.append(f"missing route items: {missing[:10]}")
            if duplicate:
                errors.append(f"unexpected route items: {duplicate[:10]}")
        capacities = [float(getattr(vehicle, "board_capacity", getattr(vehicle, "capacity", 0)) or 0) for vehicle in vehicles.values()]
        capacity = min(capacities) if capacities else 0.0
        for order_id, vehicle_ids in order_to_vehicles.items():
            if len(vehicle_ids) > 1 and order_demands.get(order_id, 0.0) <= capacity + 1e-8:
                errors.append(f"order {order_id}: split across vehicles despite fitting capacity")
        return ValidationReport(not errors, tuple(errors))

    @staticmethod
    def _route_item_ids(vehicle: Any, route: Sequence[Any]) -> Set[str]:
        carrying = getattr(vehicle, "carrying_items", ())
        if hasattr(vehicle, "carrying_item_ids"):
            carrying = getattr(vehicle, "carrying_item_ids")
        result = {str(getattr(item, "id", item)) for item in (carrying or ())}
        for node in route:
            for attr in ("pickup_item_list", "pickup_items", "pickup_item_ids", "delivery_item_list", "delivery_items", "delivery_item_ids"):
                values = getattr(node, attr, ()) or ()
                result.update(str(getattr(item, "id", item)) for item in values)
        return result

    def _validate_vehicle(
        self,
        vehicle_id: str,
        vehicle: Any,
        route: Sequence[Any],
        item_map: Mapping[str, Any],
        seen: Set[str],
        *,
        require_empty_stack: bool = False,
    ):
        errors = []
        capacity = float(getattr(vehicle, "board_capacity", getattr(vehicle, "capacity", 0)) or 0)
        carrying = getattr(vehicle, "carrying_items", ())
        if hasattr(vehicle, "carrying_item_ids"):
            carrying = list(getattr(vehicle, "carrying_item_ids") or ())
        if hasattr(carrying, "items"):
            carrying = list(carrying.items)
        stack = [str(getattr(x, "id", x)) for x in (carrying or ())]
        load = sum(float(item_attr(item_map.get(str(getattr(x, "id", x)), x), "demand", 0) or 0)
                   for x in (carrying or ()))
        if load > capacity + 1e-8:
            errors.append(f"vehicle {vehicle_id}: carrying capacity exceeded")
        if len(stack) != len(set(stack)):
            errors.append(f"vehicle {vehicle_id}: duplicate carrying item")

        # Items already on the vehicle are part of the accepted coverage
        # universe even though they do not occur as a pickup in the mutable
        # suffix.  Omitting them made a strict expected-item check report a
        # false "missing route item" for a perfectly valid in-transit plan.
        # Keep them in ``seen`` so coverage and split-order checks agree with
        # the official Checker, which starts from the carrying stack.
        seen.update(stack)

        for node in route:
            factory_id = str(getattr(node, "id", getattr(node, "factory_id", "")))
            deliveries = getattr(node, "delivery_item_list", None)
            if deliveries is None:
                deliveries = getattr(node, "delivery_items", ())
            pickups = getattr(node, "pickup_item_list", None)
            if pickups is None:
                pickups = getattr(node, "pickup_items", ())
            if hasattr(node, "delivery_item_ids"):
                deliveries = getattr(node, "delivery_item_ids")
            if hasattr(node, "pickup_item_ids"):
                pickups = getattr(node, "pickup_item_ids")
            deliveries = list(deliveries or ())
            pickups = list(pickups or ())
            for item in deliveries:
                item_id = str(getattr(item, "id", item))
                data = item_map.get(item_id, item)
                if str(item_attr(data, "delivery_factory_id", "")) != factory_id:
                    errors.append(f"item {item_id}: delivery factory mismatch")
                if not stack or stack[-1] != item_id:
                    errors.append(f"vehicle {vehicle_id}: LIFO violation delivering {item_id}")
                else:
                    stack.pop()
                load -= float(item_attr(data, "demand", 0) or 0)
                # A delivery normally follows the item's pickup, so seeing
                # the same ID here is expected; a second delivery is rejected
                # by the stack check above.
                seen.add(item_id)
            for item in pickups:
                item_id = str(getattr(item, "id", item))
                data = item_map.get(item_id, item)
                if str(item_attr(data, "pickup_factory_id", "")) != factory_id:
                    errors.append(f"item {item_id}: pickup factory mismatch")
                load += float(item_attr(data, "demand", 0) or 0)
                if load > capacity + 1e-8:
                    errors.append(f"vehicle {vehicle_id}: capacity exceeded at {factory_id}")
                stack.append(item_id)
                if item_id in seen:
                    errors.append(f"duplicate route item {item_id}")
                seen.add(item_id)
        if require_empty_stack and stack:
            errors.append(f"vehicle {vehicle_id}: terminal carrying stack is not empty")
        return errors

    @staticmethod
    def _has_prefix(prefix: Sequence[Any], route: Sequence[Any]) -> bool:
        if len(prefix) > len(route):
            return False
        for left, right in zip(prefix, route):
            left_id = str(getattr(left, "id", getattr(left, "factory_id", "")))
            right_id = str(getattr(right, "id", getattr(right, "factory_id", "")))
            if left_id != right_id:
                return False
            for attr in ("pickup_item_list", "pickup_items", "delivery_item_list", "delivery_items"):
                l = getattr(left, attr, None)
                r = getattr(right, attr, None)
                if l is not None:
                    l_ids = [str(getattr(x, "id", x)) for x in l]
                    r_ids = [str(getattr(x, "id", x)) for x in (r or ())]
                    if l_ids != r_ids:
                        return False
        return True
