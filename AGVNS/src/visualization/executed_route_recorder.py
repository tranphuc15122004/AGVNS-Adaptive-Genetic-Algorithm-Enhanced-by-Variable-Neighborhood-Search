# Copyright (C) 2025. Executed Route Recorder for DPDP Simulator
#
# Records the ACTUAL executed route of each vehicle across the entire 24h simulation.
# Captures only nodes that have been fully completed (leave_time ≤ cur_time, set by simpy).
# Post-processes to compute carrying_items state after each node via replay.

import copy
import datetime
import json
import os
import sys

from src.utils.logging_engine import logger


class ExecutedRouteRecorder(object):
    """
    Records the actual executed route of each vehicle — only nodes that were
    truly completed (leave_time set by simpy and ≤ cur_time).

    Key design:
      - Hooked after VehicleSimulator.parse_simulation_result() — nodes still
        have simpy-set arrive/leave times, planned_route not yet cleared.
      - Only records nodes from vehicle.destination + vehicle.planned_route
        (these are Node objects with full delivery/pickup item info).
      - Dedup via (vehicle_id, factory_id, arrive_time) to prevent double-recording.
      - carrying_after is computed via replay after simulation ends (because
        VehicleSimulator modifies the vehicle's stack in-place).

    Usage:
        recorder = ExecutedRouteRecorder(output_dir)
        recorder.capture_initial_state(id_to_vehicle)          # once at start
        # ... each epoch, after parse_simulation_result:
        recorder.record_epoch(id_to_vehicle, cur_time)
        # ... after simulation:
        recorder.record_final(id_to_vehicle)                    # capture remaining
        recorder.finalize()                                     # compute carrying_after
        recorder.save(instance_name)                            # write JSON
    """

    def __init__(self, output_dir: str = None):
        """
        :param output_dir: Root directory for output (e.g. visualization_output).
                           Output will be saved to <output_dir>/<instance>/executed_routes.json
        """
        self.output_dir = output_dir or os.path.join(os.getcwd(), "visualization_output")

        # ── Per-vehicle executed nodes (in execution order) ──
        # { vehicle_id: [ executed_node_dict, ... ] }
        self.vehicle_nodes = {}

        # ── Dedup set to prevent recording the same node twice ──
        # Each entry: (vehicle_id, factory_id, arrive_time)
        self._recorded = set()

        # ── Initial carrying items for each vehicle (captured once at start) ──
        # { vehicle_id: [item_id, ...] }  — bottom-to-top order (loading order)
        self._initial_carrying = {}

        # ── Factory coordinates for visualization ──
        self._factory_data = []  # [{"id": ..., "lng": ..., "lat": ..., "dock_num": ...}]

    # ──────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def set_factory_data(self, id_to_factory: dict):
        """
        Store factory coordinates for inclusion in output JSON.
        Call once at initialization, before save().

        :param id_to_factory: dict of factory_id -> Factory
        """
        self._factory_data = []
        for factory_id, factory in id_to_factory.items():
            self._factory_data.append({
                "id": factory_id,
                "lng": factory.lng,
                "lat": factory.lat,
                "dock_num": getattr(factory, "dock_num", 0),
            })
        logger.info(f"[ExecutedRoute] Factory data stored for {len(self._factory_data)} factories.")

    def capture_initial_state(self, id_to_vehicle: dict):
        """
        Capture initial carrying_items for all vehicles.
        Must be called ONCE at simulation start, before any epochs run.
        The captured state is used later by finalize() to replay and compute
        carrying_after for each executed node.

        :param id_to_vehicle: dict of vehicle_id -> Vehicle
        """
        for vehicle_id, vehicle in id_to_vehicle.items():
            items = []
            temp = []
            # Pop all items from stack to read them
            while not vehicle.carrying_items.is_empty():
                item = vehicle.carrying_items.pop()
                temp.append(item)
            # Restore stack (push in reverse order)
            for item in reversed(temp):
                vehicle.carrying_items.push(item)
            # temp order: top-first (last-loaded first)
            # reversed(temp): bottom-first (first-loaded first) = loading order
            items = [item.id for item in reversed(temp)]
            self._initial_carrying[vehicle_id] = items

        logger.info(f"[ExecutedRoute] Initial state captured for {len(id_to_vehicle)} vehicles.")

    def record_epoch(self, id_to_vehicle: dict, cur_time: int):
        """
        Record nodes completed in this epoch.
        Call AFTER vehicle_simulator.parse_simulation_result(), BEFORE
        update_status_of_vehicles() clears planned_route.

        :param id_to_vehicle: dict of vehicle_id -> Vehicle (with intact destination + planned_route)
        :param cur_time: current epoch time (unix timestamp)
        """
        total_checked = 0
        total_recorded = 0
        for vehicle_id, vehicle in id_to_vehicle.items():
            if vehicle_id not in self.vehicle_nodes:
                self.vehicle_nodes[vehicle_id] = []

            # Check destination (committed next node)
            if vehicle.destination is not None:
                total_checked += 1
                if self._try_record_node(vehicle_id, vehicle.destination, cur_time):
                    total_recorded += 1

            # Check planned_route nodes
            for node in vehicle.planned_route:
                total_checked += 1
                if self._try_record_node(vehicle_id, node, cur_time):
                    total_recorded += 1

        if total_checked > 0:
            logger.debug(f"[ExecutedRoute] Epoch record: checked {total_checked} nodes, "
                        f"recorded {total_recorded} new (cur_time={cur_time})")

    def record_final(self, id_to_vehicle: dict):
        """
        Record all remaining completed nodes after the final simulation.
        Uses sys.maxsize as cur_time to capture everything.

        :param id_to_vehicle: dict of vehicle_id -> Vehicle
        """
        self.record_epoch(id_to_vehicle, sys.maxsize)
        logger.info(f"[ExecutedRoute] Final recording complete.")

    def finalize(self):
        """
        Compute carrying_after for each executed node by replaying the
        pickup/delivery sequence from the initial state.

        This must be called AFTER all record_epoch/record_final calls,
        and BEFORE save().
        """
        for vehicle_id, nodes in self.vehicle_nodes.items():
            # Start with initial carrying items (loading order = bottom-first)
            carrying = list(self._initial_carrying.get(vehicle_id, []))

            for node in nodes:
                # ── Process deliveries (LIFO unload) ──
                # delivery_items are in unload order: [0] first out, [-1] last out
                # Each pop removes the top (last element) of the stack
                # In a valid LIFO route, the popped item should match the delivery item
                for delivery_item in node.get("delivery_items", []):
                    if carrying:
                        popped = carrying.pop()
                        # Verify LIFO: the item being delivered should be on top
                        if popped != delivery_item["item_id"]:
                            logger.warning(
                                f"[ExecutedRoute] LIFO mismatch for vehicle {vehicle_id} "
                                f"at {node['factory_id']}: expected to deliver "
                                f"{delivery_item['item_id']} but top of stack is {popped}"
                            )
                    else:
                        logger.warning(
                            f"[ExecutedRoute] Empty stack for vehicle {vehicle_id} "
                            f"at {node['factory_id']} when trying to deliver "
                            f"{delivery_item['item_id']}"
                        )
                        carrying.append(delivery_item["item_id"])  # Put it back for consistency

                # ── Process pickups (LIFO load) ──
                # pickup_items are in load order: [0] first in (goes to bottom),
                # [-1] last in (becomes top)
                for item in node.get("pickup_items", []):
                    carrying.append(item["item_id"])

                # ── Snapshot state after this node ──
                node["carrying_after"] = list(carrying)

        logger.info(f"[ExecutedRoute] Finalized carrying_after for {len(self.vehicle_nodes)} vehicles.")

    def save(self, instance_name: str) -> str:
        """
        Save executed routes to JSON file.

        :param instance_name: e.g. "instance_1"
        :return: path to the saved file
        """
        output_dir = os.path.join(self.output_dir, instance_name)
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "executed_routes.json")

        # Build output structure
        vehicles_output = {}
        total_nodes_all = 0
        for vehicle_id, nodes in self.vehicle_nodes.items():
            vehicles_output[vehicle_id] = {
                "executed_nodes": nodes,
                "total_nodes": len(nodes),
            }
            total_nodes_all += len(nodes)

        output = {
            "instance": instance_name,
            "generated_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_executed_nodes": total_nodes_all,
            "vehicle_count": len(self.vehicle_nodes),
            "factory_data": self._factory_data,
            "vehicles": vehicles_output,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"[ExecutedRoute] Saved {total_nodes_all} executed nodes "
                    f"across {len(self.vehicle_nodes)} vehicles to {output_path}")
        return output_path

    def get_vehicle_route(self, vehicle_id: str) -> list:
        """Get the executed route for a specific vehicle (after finalize)."""
        return self.vehicle_nodes.get(vehicle_id, [])

    # ──────────────────────────────────────────────────────────────────
    #  INTERNAL
    # ──────────────────────────────────────────────────────────────────

    def _try_record_node(self, vehicle_id: str, node, cur_time: int) -> bool:
        """
        Record a single node if:
          1. It has been simulated (leave_time > 0, set by simpy)
          2. It is fully completed (leave_time ≤ cur_time)
          3. It has NOT been recorded before (dedup check)
        
        Returns True if the node was newly recorded, False otherwise.
        """
        # Not yet simulated by simpy (leave_time is still default 0)
        if node.leave_time <= 0:
            return False

        # Dedup: same vehicle at same factory at same arrival time = same visit
        dedup_key = (vehicle_id, node.id, node.arrive_time)
        if dedup_key in self._recorded:
            return False

        # Only record fully completed nodes
        if node.leave_time <= cur_time:
            # Extract delivery items
            delivery_items = []
            for item in node.delivery_items:
                delivery_items.append({
                    "item_id": item.id,
                    "order_id": getattr(item, "order_id", ""),
                    "type": getattr(item, "type", ""),
                    "demand": getattr(item, "demand", 0),
                })

            # Extract pickup items
            pickup_items = []
            for item in node.pickup_items:
                pickup_items.append({
                    "item_id": item.id,
                    "order_id": getattr(item, "order_id", ""),
                    "type": getattr(item, "type", ""),
                    "demand": getattr(item, "demand", 0),
                })

            executed_node = {
                "factory_id": node.id,
                "arrive_time": node.arrive_time,
                "leave_time": node.leave_time,
                "service_time": node.service_time,
                "delivery_items": delivery_items,
                "pickup_items": pickup_items,
                # carrying_after will be filled by finalize()
            }

            if vehicle_id not in self.vehicle_nodes:
                self.vehicle_nodes[vehicle_id] = []
            self.vehicle_nodes[vehicle_id].append(executed_node)
            self._recorded.add(dedup_key)
            return True
        
        return False
