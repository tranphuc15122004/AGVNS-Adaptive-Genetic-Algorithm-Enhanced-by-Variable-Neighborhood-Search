from typing import List, Optional
from algorithm.Object import *


class VehicleInfo:
    def __init__(self, id: str, operation_time: int, capacity: int, gps_id: str, update_time: int,
                cur_factory_id: str, arrive_time_at_current_factory: int, leave_time_at_current_factory: int,
                carrying_items_list: List[str], destination: 'Destination'):
        self.id = id
        self.operation_time = operation_time
        self.capacity = capacity
        self.gps_id = gps_id
        self.update_time = update_time
        self.cur_factory_id = cur_factory_id
        self.arrive_time_at_current_factory = arrive_time_at_current_factory
        self.leave_time_at_current_factory = leave_time_at_current_factory
        self.carrying_items_list = carrying_items_list
        self.destination = destination
