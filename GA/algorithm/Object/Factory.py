class Factory:
    def __init__(self, factory_id: str, lng: float, lat: float, dock_num: int):
        self.factory_id = factory_id
        self.lng = lng
        self.lat = lat
        self.dock_num = dock_num

    def __str__(self):
        return f"Factory {self.factory_id} at ({self.lng}, {self.lat}) with {self.dock_num} docks"