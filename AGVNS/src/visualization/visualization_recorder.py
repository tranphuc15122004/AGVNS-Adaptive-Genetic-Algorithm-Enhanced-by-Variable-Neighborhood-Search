# Copyright (C) 2025. Trajectory Visualization Module for DPDP Simulator
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE

import datetime
import json
import os
import sys

from src.utils.logging_engine import logger


class VisualizationRecorder(object):
    """
    Records the state of the simulation at each epoch for later visualization.
    Can operate in two modes:
      1. RECORD mode: saves JSON snapshots of each epoch to disk (lightweight).
      2. RENDER mode: generates Folium HTML maps (requires folium).
    """

    def __init__(self, output_dir: str = None, record_mode: str = "json"):
        """
        :param output_dir: Directory to save visualization output.
                           Default: ./visualization_output/
        :param record_mode: "json" (lightweight, recommended during simulation)
                            or "folium" (generate HTML maps inline, slower)
        """
        self.output_dir = output_dir or os.path.join(os.getcwd(), "visualization_output")
        self.record_mode = record_mode

        # Snapshots stored in memory (also saved to disk in JSON mode)
        self.epoch_snapshots = []

        # Factory data (loaded once)
        self.id_to_factory = {}
        self.route_map = None

        # Tracks unique vehicles for consistent coloring
        self.vehicle_colors = {}

        # Last known positions of vehicles for trajectory interpolation
        self.last_vehicle_state = {}

        if record_mode == "folium":
            try:
                import folium
                self.folium = folium
            except ImportError:
                logger.error("folium is required for RENDER mode. Install it with: pip install folium")
                sys.exit(1)

    def set_factory_data(self, id_to_factory: dict, route_map):
        """Store factory and route data for later visualization."""
        self.id_to_factory = id_to_factory
        self.route_map = route_map

    def record_epoch(self, cur_time: int, id_to_vehicle: dict,
                     id_to_generated_order_item: dict,
                     id_to_ongoing_order_item: dict,
                     id_to_completed_order_item: dict,
                     vehicle_simulator=None):
        """
        Record the full simulation state at the current epoch.

        Args:
            cur_time: Current simulation time (unix timestamp)
            id_to_vehicle: All vehicles with their current state
            id_to_generated_order_item: Unallocated order items
            id_to_ongoing_order_item: Ongoing order items
            id_to_completed_order_item: Completed order items
            vehicle_simulator: Optional VehicleSimulator instance for
                               detailed node-level trajectory info
        """
        snapshot = {
            "epoch_time": cur_time,
            "epoch_datetime": datetime.datetime.fromtimestamp(cur_time).strftime('%Y-%m-%d %H:%M:%S'),
            "epoch_index": len(self.epoch_snapshots),
            "vehicles": self._record_vehicles(id_to_vehicle, cur_time, vehicle_simulator),
            "orders": {
                "unallocated": len(id_to_generated_order_item),
                "ongoing": len(id_to_ongoing_order_item),
                "completed": len(id_to_completed_order_item),
            },
            "order_items": {
                "unallocated": self._record_order_items(id_to_generated_order_item),
                "ongoing": self._record_order_items(id_to_ongoing_order_item),
                "completed": self._record_order_items(id_to_completed_order_item),
            }
        }

        self.epoch_snapshots.append(snapshot)

        if self.record_mode == "json":
            self._save_json_snapshot(snapshot)

        logger.info(f"[Visualization] Epoch {snapshot['epoch_index']} recorded: "
                    f"{snapshot['orders']}")

    def _record_vehicles(self, id_to_vehicle: dict, cur_time: int, vehicle_simulator=None):
        """Extract vehicle state information for the snapshot."""
        vehicles_data = []

        for vehicle_id, vehicle in id_to_vehicle.items():
            # Compute interpolated position if vehicle is en route
            position = self._get_vehicle_position(vehicle, cur_time, vehicle_simulator)

            # ── Extract planned route nodes (for backward compat) ──
            planned_nodes = []
            if vehicle.destination is not None:
                planned_nodes.append({
                    "factory_id": vehicle.destination.id,
                    "lng": vehicle.destination.lng,
                    "lat": vehicle.destination.lat,
                    "arrive_time": vehicle.destination.arrive_time,
                    "leave_time": vehicle.destination.leave_time,
                    "is_destination": True
                })
            for node in vehicle.planned_route:
                factory = self.id_to_factory.get(node.id)
                planned_nodes.append({
                    "factory_id": node.id,
                    "lng": node.lng,
                    "lat": node.lat,
                    "arrive_time": node.arrive_time,
                    "leave_time": node.leave_time,
                    "is_destination": False
                })

            # ── Build full trajectory (node list with times + coordinates) ──
            full_trajectory = self._build_full_trajectory(vehicle, cur_time, vehicle_simulator)

            # ── Extract events (pickup/delivery) at each node ──
            events = self._extract_events(vehicle, cur_time, vehicle_simulator)

            # Carrying items info
            carrying_item_ids = []
            carrying_items_copy = []
            while not vehicle.carrying_items.is_empty():
                item = vehicle.carrying_items.pop()
                carrying_item_ids.append(item.id)
                carrying_items_copy.append(item)
            # Restore stack
            for item in reversed(carrying_items_copy):
                vehicle.carrying_items.push(item)

            vehicle_data = {
                "id": vehicle_id,
                "capacity": vehicle.board_capacity,
                "operation_time": vehicle.operation_time,
                "cur_factory_id": vehicle.cur_factory_id if len(vehicle.cur_factory_id) > 0 else None,
                "position": position,
                "destination": {
                    "factory_id": vehicle.destination.id,
                    "lng": vehicle.destination.lng,
                    "lat": vehicle.destination.lat,
                    "arrive_time": vehicle.destination.arrive_time,
                    "leave_time": vehicle.destination.leave_time
                } if vehicle.destination is not None else None,
                "planned_route_nodes": planned_nodes,
                "trajectory": full_trajectory,
                "events": events,
                "carrying_item_count": len(carrying_item_ids),
                "carrying_item_ids": carrying_item_ids,
                "status": self._get_vehicle_status(vehicle, cur_time)
            }

            # Update last known state for trajectory tracking
            self.last_vehicle_state[vehicle_id] = {
                "cur_factory_id": vehicle.cur_factory_id,
                "destination": vehicle.destination,
                "planned_route": vehicle.planned_route,
                "update_time": cur_time
            }

            vehicles_data.append(vehicle_data)

        return vehicles_data

    def _build_full_trajectory(self, vehicle, cur_time: int, vehicle_simulator=None):
        """
        Build the complete trajectory (node list) for a vehicle.
        Uses the VehicleSimulator's node list if available, otherwise
        constructs from current factory + destination + planned route.
        Returns a list of dicts with:
            factory_id, lng, lat, arrive_time, leave_time, is_past
        """
        trajectory = []

        # Strategy: get node list from VehicleSimulator (most accurate)
        node_list = None
        if vehicle_simulator is not None:
            try:
                node_list = vehicle_simulator.get_node_list_of_vehicle(vehicle)
            except Exception:
                pass

        if node_list and len(node_list) > 0:
            for node in node_list:
                factory = self.id_to_factory.get(node.id)
                if factory:
                    trajectory.append({
                        "factory_id": node.id,
                        "lng": factory.lng,
                        "lat": factory.lat,
                        "arrive_time": node.arr_time,
                        "leave_time": node.leave_time,
                        "status": self._classify_node_status(node, cur_time)
                    })
        else:
            # Fallback: build from vehicle state
            # Current factory
            if len(vehicle.cur_factory_id) > 0:
                factory = self.id_to_factory.get(vehicle.cur_factory_id)
                if factory:
                    trajectory.append({
                        "factory_id": vehicle.cur_factory_id,
                        "lng": factory.lng,
                        "lat": factory.lat,
                        "arrive_time": vehicle.arrive_time_at_current_factory,
                        "leave_time": vehicle.leave_time_at_current_factory,
                        "status": "past" if vehicle.leave_time_at_current_factory <= cur_time else "current"
                    })

            # Destination
            if vehicle.destination is not None:
                factory = self.id_to_factory.get(vehicle.destination.id)
                if factory:
                    trajectory.append({
                        "factory_id": vehicle.destination.id,
                        "lng": factory.lng,
                        "lat": factory.lat,
                        "arrive_time": vehicle.destination.arrive_time,
                        "leave_time": vehicle.destination.leave_time,
                        "status": "future"
                    })

                # Planned route
                for node in vehicle.planned_route:
                    factory = self.id_to_factory.get(node.id)
                    if factory:
                        trajectory.append({
                            "factory_id": node.id,
                            "lng": factory.lng,
                            "lat": factory.lat,
                            "arrive_time": node.arrive_time,
                            "leave_time": node.leave_time,
                            "status": "future"
                        })

        return trajectory

    @staticmethod
    def _classify_node_status(node, cur_time: int):
        """Classify a trajectory node as past, current, or future."""
        if node.leave_time <= cur_time:
            return "past"
        elif node.arr_time <= cur_time < node.leave_time:
            return "current"
        else:
            return "future"

    def _extract_events(self, vehicle, cur_time: int, vehicle_simulator=None):
        """
        Extract pickup and delivery events from the vehicle's planned route nodes.
        Returns a list of events with:
            type: "pickup" or "delivery"
            item_id: the item involved
            factory_id: where it happens
            time: when it happens (arrive_time = moment of event)
            lng, lat: coordinates
        """
        events = []

        # Collect all nodes that have events
        all_nodes = []

        if vehicle.destination is not None:
            all_nodes.append(vehicle.destination)

        for node in vehicle.planned_route:
            all_nodes.append(node)

        for node in all_nodes:
            factory = self.id_to_factory.get(node.id)
            f_lng = factory.lng if factory else 0
            f_lat = factory.lat if factory else 0

            # Delivery events happen at arrive_time (unload)
            for item in node.delivery_items:
                events.append({
                    "type": "delivery",
                    "item_id": item.id,
                    "item_type": item.type,
                    "factory_id": node.id,
                    "lng": f_lng,
                    "lat": f_lat,
                    "time": node.arrive_time,
                    "vehicle_id": vehicle.id
                })

            # Pickup events happen after delivery, before leave_time
            for item in node.pickup_items:
                events.append({
                    "type": "pickup",
                    "item_id": item.id,
                    "item_type": item.type,
                    "factory_id": node.id,
                    "lng": f_lng,
                    "lat": f_lat,
                    "time": node.arrive_time + 1,  # slightly after arrival
                    "vehicle_id": vehicle.id
                })

        # Sort by time
        events.sort(key=lambda e: e["time"])
        return events

    def _get_vehicle_position(self, vehicle, cur_time: int, vehicle_simulator=None):
        """
        Get the interpolated geographic position of a vehicle.
        If the vehicle is at a factory, return the factory coordinates.
        If en route, interpolate between the last factory and the next factory.
        """
        # Case 1: Vehicle is at a factory
        if len(vehicle.cur_factory_id) > 0:
            factory = self.id_to_factory.get(vehicle.cur_factory_id)
            if factory:
                return {
                    "lng": factory.lng,
                    "lat": factory.lat,
                    "factory_id": vehicle.cur_factory_id,
                    "status": "at_factory"
                }

        # Case 2: Vehicle has a destination (en route or heading somewhere)
        if vehicle.destination is not None:
            # Use node list from vehicle simulator if available
            if vehicle_simulator is not None:
                node_list = vehicle_simulator.get_node_list_of_vehicle(vehicle)
                # Find where the vehicle is between nodes
                for i in range(len(node_list) - 1):
                    curr_node = node_list[i]
                    next_node = node_list[i + 1]
                    if curr_node.arr_time <= cur_time <= next_node.leave_time:
                        # Interpolate position
                        if cur_time <= curr_node.leave_time:
                            # Still at curr_node
                            factory = self.id_to_factory.get(curr_node.id)
                            if factory:
                                return {
                                    "lng": factory.lng,
                                    "lat": factory.lat,
                                    "factory_id": curr_node.id,
                                    "status": "at_factory"
                                }
                        else:
                            # En route from curr_node to next_node
                            total_time = next_node.arr_time - curr_node.leave_time
                            if total_time > 0:
                                ratio = (cur_time - curr_node.leave_time) / total_time
                            else:
                                ratio = 0
                            start_factory = self.id_to_factory.get(curr_node.id)
                            end_factory = self.id_to_factory.get(next_node.id)
                            if start_factory and end_factory:
                                return {
                                    "lng": start_factory.lng + ratio * (end_factory.lng - start_factory.lng),
                                    "lat": start_factory.lat + ratio * (end_factory.lat - start_factory.lat),
                                    "from_factory": curr_node.id,
                                    "to_factory": next_node.id,
                                    "status": "en_route",
                                    "progress": ratio
                                }

            # Fallback: use destination info
            dest_factory = self.id_to_factory.get(vehicle.destination.id)
            cur_factory = self.id_to_factory.get(vehicle.cur_factory_id) if len(vehicle.cur_factory_id) > 0 else None

            if cur_factory and dest_factory:
                # Interpolate based on times
                total_time = vehicle.destination.arrive_time - vehicle.leave_time_at_current_factory
                if total_time > 0:
                    ratio = (cur_time - vehicle.leave_time_at_current_factory) / total_time
                    ratio = max(0, min(1, ratio))
                else:
                    ratio = 0
                return {
                    "lng": cur_factory.lng + ratio * (dest_factory.lng - cur_factory.lng),
                    "lat": cur_factory.lat + ratio * (dest_factory.lat - cur_factory.lat),
                    "from_factory": vehicle.cur_factory_id,
                    "to_factory": vehicle.destination.id,
                    "status": "en_route",
                    "progress": ratio
                }
            else:
                # Unknown position, use destination
                return {
                    "lng": dest_factory.lng if dest_factory else 0,
                    "lat": dest_factory.lat if dest_factory else 0,
                    "factory_id": vehicle.destination.id,
                    "status": "unknown"
                }

        # Case 3: No destination, no factory (error state)
        return {
            "lng": 0,
            "lat": 0,
            "status": "idle"
        }

    @staticmethod
    def _get_vehicle_status(vehicle, cur_time: int):
        """Determine the operational status of a vehicle."""
        if len(vehicle.cur_factory_id) > 0:
            if vehicle.leave_time_at_current_factory > cur_time:
                return "loading_unloading"
            elif vehicle.destination is not None:
                return "idle_at_factory"
            else:
                return "parked"
        elif vehicle.destination is not None:
            return "en_route"
        return "unknown"

    @staticmethod
    def _record_order_items(order_items_dict: dict):
        """Extract key info from order items for the snapshot."""
        items = []
        for item_id, item in order_items_dict.items():
            items.append({
                "id": item.id,
                "type": item.type,
                "demand": item.demand,
                "pickup_factory_id": item.pickup_factory_id,
                "delivery_factory_id": item.delivery_factory_id,
                "creation_time": item.creation_time,
                "committed_completion_time": item.committed_completion_time,
                "delivery_state": item.delivery_state
            })
        return items

    def _save_json_snapshot(self, snapshot: dict):
        """Save a single epoch snapshot as JSON into epochs/ subfolder."""
        epochs_dir = os.path.join(self.output_dir, "epochs")
        os.makedirs(epochs_dir, exist_ok=True)
        epoch_idx = snapshot["epoch_index"]
        file_path = os.path.join(epochs_dir, f"epoch_{epoch_idx:04d}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            # Convert datetime objects to string for JSON serialization
            json.dump(snapshot, f, indent=2, default=str)
        logger.info(f"[Visualization] Saved snapshot to {file_path}")

    def save_summary_json(self):
        """Save all snapshots into a single summary JSON file."""
        os.makedirs(self.output_dir, exist_ok=True)
        file_path = os.path.join(self.output_dir, "epoch_summary.json")
        summary = {
            "total_epochs": len(self.epoch_snapshots),
            "factory_count": len(self.id_to_factory),
            "factory_data": [
                {"id": fid, "lng": f.lng, "lat": f.lat, "dock_num": f.dock_num}
                for fid, f in self.id_to_factory.items()
            ],
            "epochs": self.epoch_snapshots
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"[Visualization] Summary saved to {file_path}")
        return file_path

    # ──────────────────────────────────────────────
    # FOLIUM RENDERING METHODS
    # ──────────────────────────────────────────────

    def render_epoch_map(self, snapshot: dict, output_path: str = None):
        """
        Generate a Folium HTML map for a single epoch snapshot.
        Only available in 'folium' record mode.
        """
        if self.record_mode != "folium":
            logger.warning("Folium rendering requires record_mode='folium'")
            return

        folium = self.folium
        from folium.plugins import MarkerCluster

        # Compute map center from factory data
        lats = [f.lat for f in self.id_to_factory.values()]
        lngs = [f.lng for f in self.id_to_factory.values()]
        center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]

        m = folium.Map(location=center, zoom_start=11, tiles='CartoDB positron',
                       attr='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>')

        # ── Add factories ──
        for fid, factory in self.id_to_factory.items():
            folium.CircleMarker(
                location=[factory.lat, factory.lng],
                radius=5,
                color='gray',
                fill=True,
                fill_color='gray',
                fill_opacity=0.6,
                popup=f"Factory: {fid[:12]}...<br>Docks: {factory.dock_num}"
            ).add_to(m)

        # ── Add vehicles ──
        for vdata in snapshot["vehicles"]:
            pos = vdata["position"]
            vehicle_id = vdata["id"]

            if pos["status"] == "en_route":
                color = 'green'
                icon_type = 'arrow-right'
            elif pos["status"] == "loading_unloading":
                color = 'orange'
                icon_type = 'time'
            elif pos["status"] == "parked" or pos["status"] == "idle_at_factory":
                color = 'blue'
                icon_type = 'pause'
            else:
                color = 'red'
                icon_type = 'question'

            popup_parts = [
                f"<b>Vehicle:</b> {vehicle_id}",
                f"<b>Status:</b> {pos['status']}",
                f"<b>Capacity:</b> {vdata['capacity']}",
                f"<b>Items onboard:</b> {vdata['carrying_item_count']}",
            ]

            if pos.get("from_factory"):
                popup_parts.append(f"<b>From:</b> {pos['from_factory'][:12]}...")
            if pos.get("to_factory"):
                popup_parts.append(f"<b>To:</b> {pos['to_factory'][:12]}...")
            if pos.get("progress") is not None:
                popup_parts.append(f"<b>Progress:</b> {pos['progress'] * 100:.1f}%")

            folium.Marker(
                location=[pos['lat'], pos['lng']],
                popup="<br>".join(popup_parts),
                icon=folium.Icon(color=color, icon=icon_type, prefix='fa'),
            ).add_to(m)

            # ── Draw planned route ──
            route_nodes = vdata.get("planned_route_nodes", [])
            if route_nodes:
                route_coords = [[pos['lat'], pos['lng']]]
                for rnode in route_nodes:
                    route_coords.append([rnode['lat'], rnode['lng']])
                folium.PolyLine(
                    locations=route_coords,
                    weight=2,
                    color=color,
                    opacity=0.5,
                    dash_array='5, 5'
                ).add_to(m)

        # ── Add order summary ──
        orders = snapshot["orders"]
        summary_text = (
            f"<div style='position: fixed; top: 10px; right: 10px; z-index: 9999; "
            f"background: white; padding: 8px; border-radius: 5px; font-size: 12px; "
            f"box-shadow: 0 0 5px rgba(0,0,0,0.3);'>"
            f"<b>Epoch {snapshot['epoch_index']}</b><br>"
            f"{snapshot['epoch_datetime']}<br>"
            f"📦 Unallocated: {orders['unallocated']}<br>"
            f"🚚 Ongoing: {orders['ongoing']}<br>"
            f"✅ Completed: {orders['completed']}"
            f"</div>"
        )
        m.get_root().html.add_child(folium.Element(summary_text))

        if output_path:
            m.save(output_path)
        return m

    def render_all_epochs(self, output_dir: str = None):
        """Render all recorded epochs as individual HTML maps."""
        if not self.epoch_snapshots:
            logger.warning("No snapshots to render")
            return

        out_dir = output_dir or os.path.join(self.output_dir, "maps")
        os.makedirs(out_dir, exist_ok=True)

        for snap in self.epoch_snapshots:
            path = os.path.join(out_dir, f"epoch_{snap['epoch_index']:04d}.html")
            self.render_epoch_map(snap, output_path=path)

        logger.info(f"[Visualization] All epoch maps saved to {out_dir}")
        return out_dir
