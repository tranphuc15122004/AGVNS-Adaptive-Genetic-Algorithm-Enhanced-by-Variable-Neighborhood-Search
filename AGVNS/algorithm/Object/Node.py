from typing import List, Optional
from algorithm.Object import *


class Node:
    def __init__(self):
        from .Orderitem import OrderItem
        
        
    def __init__(self, factory_id: str, delivery_item_list: List['OrderItem'], pickup_item_list: List['OrderItem'],
                arrive_time: Optional[int] = None, leave_time: Optional[int] = None,
                lng: float = 0.0, lat: float = 0.0):
        self.id = factory_id
        self.delivery_item_list = delivery_item_list
        self.pickup_item_list = pickup_item_list
        self.arrive_time = arrive_time if arrive_time is not None else 0
        self.leave_time = leave_time if leave_time is not None else 0
        self.lng = lng
        self.lat = lat
    
    @property
    def service_time(self) -> int:
        return self.__calculate_service_time()
        
    def __str__(self):
        return (f"Node {self.id}:\n"
                f"  Delivery Items: {len(self.delivery_item_list)}\n"
                f"  Pickup Items: {len(self.pickup_item_list)}\n"
                f"  Arrive Time: {self.arrive_time}\n"
                f"  Leave Time: {self.leave_time}\n"
                f"  Location: ({self.lat}, {self.lng})\n"
                f"  Service Time: {self.service_time}")

    def __calculate_service_time(self) -> int:
        # Tính toán thời gian phục vụ
        loading_time = 0
        unloading_time = 0
        for item in self.pickup_item_list:
            loading_time += item.load_time 
        
        for item in self.delivery_item_list:
            unloading_time += item.unload_time
        return loading_time + unloading_time

