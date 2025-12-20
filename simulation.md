## Introduction 

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Directory Structure of the Simulator**

```
dpdp_competition
	│  main.py  Main program of the simulator
	│  main_algorithm.py  Main program of the algorithm
	│  readme.md  Documentation
	│  
	│─algorithm  Folder containing algorithm code
	│  │  algorithm_demo.py  Algorithm example code
	│  │  
	│  └─data_interaction  Folder for algorithm-simulator data interaction
	│      
	├─benchmark  Test dataset
	│
	└─src Folder containing simulator code
		├─common  Common classes
		│      dispatch_result.py
		│      factory.py
		│      input_info.py
		│      node.py
		│      order.py
		│      route.py
		│      stack.py
		│      vehicle.py
		│      
		├─conf  Configuration files
		│      configs.py
		│      
		├─simulator  Simulator
		│      history.py
		│      simulate_api.py
		│      simulate_environment.py
		│      vehicle_simulator.py
		│      
		└─utils  Utility tools
		       checker.py
		       evaluator.py
		       input_utils.py
		       json_tools.py
		       logging_engine.py
		       log_utils.py
		       tools.py
```



**Run the Simulator**

```
# cd dpdp_competition
python main.py
```



## Requirements

* python >= 3.6
* simpy



## Quick Start
### Interaction Between Algorithm and Simulator

Firstly, the simulator reads the selected test instance which can be modified in Configs.py. Then, the simulator performs simulation at a fixed interval of 10 minutes until all orders in the instance are completed.

In each round of simulation, the simulator outputs the vehicle and order data required by the algorithm to the algorithm/data_interaction folder in JSON format. Next, it calls the main program of the algorithm prefixed with "main_algorithm", e.g. main_algorithm.py, main_algorithm.java, etc. When the algorithm runs, it starts to read JSON files, dispatch orders, output the dispatch result to the algorithm/data_interaction folder in JSON format and print string "SUCCESS" to the console as the flag for the simulator to determine whether the algorithm has successfully returned. If the successful returned flag of the algorithm is obtained, the simulator will read the output JSON files and perform verification. After passing the verification, it continues the simulation.

The running time of the algorithm is limited to 10 minutes. If the algorithm times out, the simulator will exit.

Note: The paths of folders and files mentioned above are illustrated in the Introduction section.



### Main Process (from Algorithm Perspective)

+ [Read the input JSON files](#read-the-input-json-files)
+ [Dispatch orders](#dispatch-orders) 
+ [Output required JSON files](#output-required-json-files) 




### Read the Input JSON Files

The simulator outputs the latest vehicle information in "vehicle_info.json", order items to be allocated in "unallocated_order_items.json" and ongoing order items in "ongoing_order_items.json". The details of these files are as follows.

Three concepts are explained here:

1. Item: the smallest indivisible unit in an order. For example, if an order contains 2 standard pallets and 1 small pallet, there are 3 corresponding items.
2. Item status: 0 means initialization; 1 means the item has been generated; 2 means the item has been loaded; 3 means the item has been delivered.
3. Order status: the minimum value of the statuses of all items in the order. For example, if an order contains two items, item 1 of 1 small pallet and item 2 of 1 box, and item 1 has status 3 while item 2 has status 2, then the order status is 2.



+ **vehicle_info.json**

  Example: 

```
[
  {
    "id": "V_1",
    "operation_time": 24,
    "capacity": 15,
    "gps_id": "G_1",
    "update_time": 1621471200.0,
    "cur_factory_id": "f6faef4b36e743328800b961aced4a2c",
    "arrive_time_at_current_factory": 1621471008.0,
    "leave_time_at_current_factory": 1621473288.0,
    "carrying_items": [
      "2218470047-1",
      "2218470047-2"
    ],
    "destination": {
      "factory_id": "b6dd694ae05541dba369a2a759d2c2b9",
      "delivery_item_list": [
        "2218470047-2",
        "2218470047-1"
      ],
      "pickup_item_list": [],
      "arrive_time": 1621473396.0,
      "leave_time": 1621475676.0
    }
  },
  {
    "id": "V_2",
    "operation_time": 24,
    "capacity": 15,
    "gps_id": "G_2",
    "update_time": 1621471200.0,
    "cur_factory_id": "5e2e9efa5ade4984bb18af66028bc0c8",
    "arrive_time_at_current_factory": 1621464180.0,
    "leave_time_at_current_factory": 1621470600.0,
    "carrying_items": [],
    "destination": null
  },
  ...
]
```

| Column                         | Description                                                  | Type              |
| ------------------------------ | ------------------------------------------------------------ | ----------------- |
| id                             | Vehicle ID (license plate)                                   | str               |
| operation_time                 | Operation time of the vehicle (unit: hour)                   | int               |
| capacity                       | Capacity of the vehicle (unit: standard pallet)              | int               |
| update_time                    | Update time of the current position and status of the vehicle (unit: unix timestamp) | int               |
| cur_factory_id                 | The factory ID where the vehicle is currently located; empty string if not at any factory | str               |
| arrive_time_at_current_factory | The time when the vehicle arrives at the current factory (unit: unix timestamp) | int               |
| leave_time_at_current_factory  | The time when the vehicle leaves the current factory (unit: unix timestamp) | int               |
| carrying_items                 | List of items loaded on the vehicle in loading order          | [str1, str2, ...] |
| destination                    | Current destination of the vehicle (once determined, cannot be changed until arrival). Null if the vehicle is parked | dict or null      |

Notes: if vehicle v is at factory f1 with destination f2, then the route plan {f3, f2} violates the destination invariant constraint, while {f2, f3} does not.



+ **unallocated_order_items.json**
  Example：

```
[
  {
    "id": "1436011625-1",
    "type": "HALF_PALLET",
    "order_id": "1436011625",
    "demand": 0.5,
    "pickup_factory_id": "7b84670cf4164cccba22ebb17a2c290a",
    "delivery_factory_id": "7fb0acc4e2634440ba26a7ebc0040dc2",
    "creation_time": 1621406161,
    "committed_completion_time": 1621420561,
    "load_time": 120,
    "unload_time": 120,
    "delivery_state": 1
  },
  {
    "id": "1446161669-1",
    "type": "PALLET",
    "order_id": "1446161669",
    "demand": 1,
    "pickup_factory_id": "2445d4bd004c457d95957d6ecf77f759",
    "delivery_factory_id": "9f1a09c368584eba9e7f10a53d55caae",
    "creation_time": 1621406776,
    "committed_completion_time": 1621421176,
    "load_time": 240,
    "unload_time": 240,
    "delivery_state": 1
  },
```

| Column                    | Description                                                  | Type   |
| ------------------------- | ------------------------------------------------------------ | ------ |
| id                        | Item ID                                                      | str    |
| type                      | Pallet type (e.g., standard pallet, small pallet, box)      | str    |
| order_id                  | Order ID                                                     | str    |
| demand                    | Total standard pallet amount (as a fraction)                 | double |
| pickup_factory_id         | Pickup factory ID                                            | str    |
| delivery_factory_id       | Delivery factory ID                                          | str    |
| creation_time             | Order creation time (unit: unix timestamp)                   | int    |
| committed_completion_time | Order promised completion time (unit: unix timestamp)        | int    |
| load_time                 | Item loading time (unit: second)                             | int    |
| unload_time               | Item unloading time (unit: second)                           | int    |
| delivery_state            | Item status: 0 initialization; 1 generated; 2 loaded; 3 delivered | int    |



+ **ongoing_order_items.json**
  Example：

```
[
  {
    "id": "0003480001-1",
    "type": "HALF_PALLET",
    "order_id": "0003480001",
    "demand": 0.5,
    "pickup_factory_id": "2445d4bd004c457d95957d6ecf77f759",
    "delivery_factory_id": "b6dd694ae05541dba369a2a759d2c2b9",
    "creation_time": 1621267428,
    "committed_completion_time": 1621281828,
    "load_time": 120,
    "unload_time": 120,
    "delivery_state": 2
  },
  {
    "id": "0012230002-1",
    "type": "PALLET",
    "order_id": "0012230002",
    "demand": 1,
    "pickup_factory_id": "2445d4bd004c457d95957d6ecf77f759",
    "delivery_factory_id": "9f1a09c368584eba9e7f10a53d55caae",
    "creation_time": 1621267943,
    "committed_completion_time": 1621282343,
    "load_time": 240,
    "unload_time": 240,
    "delivery_state": 2
  },
  ...
]

```




### Dispatch Orders

1. When vehicle v arrives at factory f, the pickup and delivery list of v at f will be generated immediately. The vehicle can only be loaded and unloaded according to this list. Items in the pickup/delivery list of v at f can only be changed before the list is generated.
2. An item can be reallocated to a different vehicle as long as it has not appeared on any pickup/delivery list.
3. Since the input contains items belonging to orders, the algorithm must respect the order non-splitting constraint: if an entire order does not exceed the vehicle's capacity (vehicles are homogeneous), the order cannot be split.
4. The algorithm can control when an order is released. For example, if order A is generated at time t1, the algorithm can delay allocation until t2 where t2 <= t1 + 4h. Note: if an order has been generated for more than 4 hours but has not been dispatched, the simulator will exit.
5. The distance and time required by the algorithm must be obtained only from the distance and time matrix between factories in the benchmark. Do not calculate distance based on latitude/longitude. If vehicle v is in transit, it must have a destination factory f, and the simulator will provide the estimated arrival time at f. The algorithm can then plan the route of v based on this destination.
6. Suppose the simulator sends the latest vehicle status to the algorithm at time t1, and the algorithm returns the dispatch result at time t2. If the algorithm takes too long to run, the vehicle status may change significantly during [t1, t2], causing the dispatch result to become inconsistent with the actual situation. For this reason, the algorithm's runtime is currently limited to 10 minutes.



### Output Required JSON Files

The algorithm needs to output two JSON files: "output_destination.json" and "output_route.json". Details are as follows.

+ **output_destination.json**

  Example

```
{
  "V_1": {
    "factory_id": "2445d4bd004c457d95957d6ecf77f759",
    "lng": 116.5841,
    "lat": 40.2869,
    "delivery_item_list": [],
    "pickup_item_list": [
      "0003480001-1"
    ],
    "arrive_time": 1621445928.0,
    "leave_time": 0
  },
  "V_2": {
    "factory_id": "9f1a09c368584eba9e7f10a53d55caae",
    "lng": 116.6309,
    "lat": 40.2304,
    "delivery_item_list": [
      "0013570003-1"
    ],
    "pickup_item_list": [],
    "arrive_time": 1621443624.0,
    "leave_time": 0
  },
  "V_3": null,
  ...
} 
```



+ **output_route.json**

  Example

```
{
  "V_1": [
    {
      "factory_id": "b6dd694ae05541dba369a2a759d2c2b9",
      "lng": 116.6264,
      "lat": 40.2253,
      "delivery_item_list": [
        "0003480001-1"
      ],
      "pickup_item_list": [],
      "arrive_time": 0,
      "leave_time": 0
    },
    {
      "factory_id": "2445d4bd004c457d95957d6ecf77f759",
      "lng": 116.5841,
      "lat": 40.2869,
      "delivery_item_list": [],
      "pickup_item_list": [
        "0012230002-1"
      ],
      "arrive_time": 0,
      "leave_time": 0
    },
    {
      "factory_id": "9f1a09c368584eba9e7f10a53d55caae",
      "lng": 116.6309,
      "lat": 40.2304,
      "delivery_item_list": [
        "0012230002-1"
      ],
      "pickup_item_list": [],
      "arrive_time": 0,
      "leave_time": 0
    }
  ],
  "V_2": [
    {
      "factory_id": "2445d4bd004c457d95957d6ecf77f759",
      "lng": 116.5841,
      "lat": 40.2869,
      "delivery_item_list": [],
      "pickup_item_list": [
        "0033520004-1",
        "0033520004-2",
        "0033520004-3"
      ],
      "arrive_time": 0,
      "leave_time": 0
    },
    {
      "factory_id": "b6dd694ae05541dba369a2a759d2c2b9",
      "lng": 116.6264,
      "lat": 40.2253,
      "delivery_item_list": [
        "0033520004-3",
        "0033520004-2",
        "0033520004-1"
      ],
      "pickup_item_list": [],
      "arrive_time": 0,
      "leave_time": 0
    }
  ],
  "V_3": [],
  ...
}
```

| Column             | Description                                                  | Type              |
| ------------------ | ------------------------------------------------------------ | ----------------- |
| factory_id         | Factory ID (node)                                            | str               |
| lng                | Longitude of the corresponding factory                       | double            |
| lat                | Latitude of the corresponding factory                        | double            |
| delivery_item_list | List of items to be unloaded from the vehicle (unloading order: delivery_item_list[0], delivery_item_list[1], ...) | [str1, str2, ...] |
| pickup_item_list   | List of items to be loaded onto the vehicle (loading order: pickup_item_list[0], pickup_item_list[1], ...) | [str3, str4, ...] |
| arrive_time        | Time to reach the node (unit: unix timestamp)                | int               |
| leave_time         | Time to leave the node (unit: unix timestamp)                | int               |




## Submission

**To be continued**

After the online submission platform of HUAWEI CLOUD competition opens, we will complete the submission process documentation as soon as possible.



## License

The MIT License (MIT)
