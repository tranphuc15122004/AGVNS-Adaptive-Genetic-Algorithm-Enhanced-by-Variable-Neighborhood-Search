from typing import List

class Destination:
    def __init__(self, factory_id: str, delivery_item_list: List[str], pickup_item_list: List[str],
                arrive_time: int, leave_time: int):
        self.factory_id = factory_id
        self.delivery_item_list = delivery_item_list
        self.pickup_item_list = pickup_item_list
        self.arrive_time = arrive_time
        self.leave_time = leave_time

    def __str__(self):
        return (f"Destination(factory_id={self.factory_id}, "
                f"delivery_item_list={self.delivery_item_list}, "
                f"pickup_item_list={self.pickup_item_list}, "
                f"arrive_time={self.arrive_time}, "
                f"leave_time={self.leave_time})")