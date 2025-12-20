from typing import List, Optional
from algorithm.Object import *

class Vehicle:
    def __init__(self, id: str, gps_id: str, operation_time: int, board_capacity: int, carrying_items: List['OrderItem'], des: Node = None):
        self.id = id
        self.gps_id = gps_id
        self.cur_factory_id = None
        self.gps_update_time = 0
        self.operation_time = operation_time
        self.board_capacity = board_capacity
        self.left_capacity = 0.0
        self.arrive_time_at_current_factory = 0
        self.leave_time_at_current_factory = 0
        self.carrying_items = carrying_items
        self.planned_route = []
        self.des = des

    def __str__(self):
        return f"Vehicle {self.id} at {self.cur_factory_id} with {len(self.carrying_items)} items"

    def set_cur_position_info(self, cur_factory_id: str, update_time: int, arrive_time_at_current_factory: int, leave_time_at_current_factory: int):
        self.cur_factory_id = cur_factory_id
        self.gps_update_time = update_time
        if cur_factory_id:
            self.arrive_time_at_current_factory = arrive_time_at_current_factory
            self.leave_time_at_current_factory = leave_time_at_current_factory
        else:
            self.arrive_time_at_current_factory = 0
            self.leave_time_at_current_factory = 0
