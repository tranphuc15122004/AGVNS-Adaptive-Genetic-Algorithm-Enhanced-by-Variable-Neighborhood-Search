"""
Quick unit test for ExecutedRouteRecorder — validates core logic in isolation.
"""
import sys, os, tempfile, json

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.visualization.executed_route_recorder import ExecutedRouteRecorder


class MockItem:
    def __init__(self, iid, oid, itype, demand):
        self.id = iid; self.order_id = oid; self.type = itype; self.demand = demand

class MockNode:
    def __init__(self, fid, arr, lv, deliveries, pickups, svc=100):
        self.id = fid; self.arrive_time = arr; self.leave_time = lv
        self.service_time = svc
        self.delivery_items = deliveries; self.pickup_items = pickups

class MockStack:
    def __init__(self, items):
        self.items = list(items)
    def is_empty(self): return len(self.items) == 0
    def pop(self): return self.items.pop()
    def push(self, item): self.items.append(item)

class MockVehicle:
    def __init__(self, vid, carrying=None):
        self.id = vid
        self.destination = None
        self.planned_route = []
        self.carrying_items = MockStack(carrying or [])


def test_basic():
    """Test basic recording, carrying_after computation, and dedup."""
    tmpdir = tempfile.mkdtemp()
    recorder = ExecutedRouteRecorder(output_dir=tmpdir)

    # Create items
    item_a = MockItem('I_A', 'O_1', 'PALLET', 1.0)
    item_b = MockItem('I_B', 'O_2', 'BOX', 0.5)
    item_c = MockItem('I_C', 'O_3', 'PALLET', 1.0)

    # Create vehicles: V1 carries A initially (A loaded first → bottom of stack)
    # V2 empty
    v1 = MockVehicle('V_1', carrying=[item_a])
    v2 = MockVehicle('V_2', carrying=[])
    id_to_vehicle = {'V_1': v1, 'V_2': v2}
    recorder.capture_initial_state(id_to_vehicle)

    # Epoch 1: V1 at F_5 picks up B (B loaded on top of A → stack: [A, B])
    #           V2 at F_3 picks up C (stack: [C])
    node_v1 = MockNode('F_5', 1000, 1100, [], [item_b])
    node_v2 = MockNode('F_3', 1000, 1100, [], [item_c])
    v1.destination = node_v1
    v2.destination = node_v2

    recorder.record_epoch(id_to_vehicle, cur_time=1200)

    # Epoch 2: V1 at F_8 delivers B first (LIFO: B is on top), then picks up nothing
    #           V2 at F_8 delivers C (top), then picks up A
    node_v1b = MockNode('F_8', 1200, 1300, [item_b], [])   # Deliver B (was on top)
    node_v2b = MockNode('F_8', 1200, 1300, [item_c], [item_a])  # Deliver C, pickup A
    v1.destination = node_v1b
    v2.destination = node_v2b

    recorder.record_epoch(id_to_vehicle, cur_time=1400)

    # Finalize and save
    recorder.finalize()
    path = recorder.save('test_instance')

    with open(path) as f:
        data = json.load(f)

    print('=== VERIFICATION ===')
    for vid, vdata in data['vehicles'].items():
        print(f"\nVehicle {vid}: {vdata['total_nodes']} nodes")
        for i, node in enumerate(vdata['executed_nodes']):
            print(f"  Node {i}: {node['factory_id']} "
                  f"del={[d['item_id'] for d in node['delivery_items']]} "
                  f"pup={[p['item_id'] for p in node['pickup_items']]} "
                  f"carrying={node['carrying_after']}")

    # Assertions
    v1_nodes = data['vehicles']['V_1']['executed_nodes']
    # V1: Node 0 pickup B → [A, B]; Node 1 deliver B (top) → [A]
    assert v1_nodes[0]['carrying_after'] == ['I_A', 'I_B'], \
        f"V1 node 0 FAIL: {v1_nodes[0]['carrying_after']} != ['I_A', 'I_B']"
    assert v1_nodes[1]['carrying_after'] == ['I_A'], \
        f"V1 node 1 FAIL: {v1_nodes[1]['carrying_after']} != ['I_A']"

    v2_nodes = data['vehicles']['V_2']['executed_nodes']
    # V2: Node 0 pickup C → [C]; Node 1 deliver C → [], pickup A → [A]
    assert v2_nodes[0]['carrying_after'] == ['I_C'], \
        f"V2 node 0 FAIL: {v2_nodes[0]['carrying_after']} != ['I_C']"
    assert v2_nodes[1]['carrying_after'] == ['I_A'], \
        f"V2 node 1 FAIL: {v2_nodes[1]['carrying_after']} != ['I_A']"

    print("\n✅ Basic flow: PASSED")
    return recorder, id_to_vehicle


def test_dedup():
    """Test that recording the same node twice does not create duplicates."""
    tmpdir = tempfile.mkdtemp()
    recorder = ExecutedRouteRecorder(output_dir=tmpdir)

    item = MockItem('I_X', 'O_X', 'BOX', 0.5)
    v = MockVehicle('V_test', carrying=[])
    id_to_vehicle = {'V_test': v}
    recorder.capture_initial_state(id_to_vehicle)

    node = MockNode('F_1', 100, 200, [], [item])
    v.destination = node

    # Record same epoch twice
    recorder.record_epoch(id_to_vehicle, cur_time=300)
    recorder.record_epoch(id_to_vehicle, cur_time=300)  # should be dedup'd
    recorder.finalize()
    path = recorder.save('test_dedup')

    with open(path) as f:
        data = json.load(f)
    assert data['vehicles']['V_test']['total_nodes'] == 1, \
        f"Dedup FAIL: got {data['vehicles']['V_test']['total_nodes']} nodes"
    print("✅ Dedup: PASSED")


def test_not_completed():
    """Test that nodes still in progress (arrive_time <= cur_time < leave_time) are NOT recorded."""
    tmpdir = tempfile.mkdtemp()
    recorder = ExecutedRouteRecorder(output_dir=tmpdir)

    item = MockItem('I_Y', 'O_Y', 'PALLET', 1.0)
    v = MockVehicle('V_progress', carrying=[])
    id_to_vehicle = {'V_progress': v}
    recorder.capture_initial_state(id_to_vehicle)

    # Node in progress: arrived at 500, leaves at 800, cur_time = 600
    node = MockNode('F_5', 500, 800, [], [item])
    v.destination = node

    recorder.record_epoch(id_to_vehicle, cur_time=600)
    recorder.finalize()
    path = recorder.save('test_progress')

    with open(path) as f:
        data = json.load(f)
    assert data['vehicles']['V_progress']['total_nodes'] == 0, \
        "Progress FAIL: in-progress node was recorded!"
    print("✅ Not-completed filter: PASSED")


def test_future_node():
    """Test that future nodes (arrive_time > cur_time) are NOT recorded."""
    tmpdir = tempfile.mkdtemp()
    recorder = ExecutedRouteRecorder(output_dir=tmpdir)

    item = MockItem('I_Z', 'O_Z', 'BOX', 0.5)
    v = MockVehicle('V_future', carrying=[])
    id_to_vehicle = {'V_future': v}
    recorder.capture_initial_state(id_to_vehicle)

    # Future node
    node = MockNode('F_9', 2000, 2100, [], [item])
    v.destination = node

    recorder.record_epoch(id_to_vehicle, cur_time=1000)
    recorder.finalize()
    path = recorder.save('test_future')

    with open(path) as f:
        data = json.load(f)
    assert data['vehicles']['V_future']['total_nodes'] == 0, \
        "Future FAIL: future node was recorded!"
    print("✅ Future-node filter: PASSED")


def test_not_simulated():
    """Test that nodes without simpy-set times (leave_time=0) are NOT recorded."""
    tmpdir = tempfile.mkdtemp()
    recorder = ExecutedRouteRecorder(output_dir=tmpdir)

    item = MockItem('I_W', 'O_W', 'PALLET', 1.0)
    v = MockVehicle('V_nosim', carrying=[])
    id_to_vehicle = {'V_nosim': v}
    recorder.capture_initial_state(id_to_vehicle)

    # Node with leave_time=0 (not yet simulated by simpy)
    node = MockNode('F_3', 0, 0, [], [item])
    v.destination = node

    recorder.record_epoch(id_to_vehicle, cur_time=999999)
    recorder.finalize()
    path = recorder.save('test_nosim')

    with open(path) as f:
        data = json.load(f)
    assert data['vehicles']['V_nosim']['total_nodes'] == 0, \
        "No-sim FAIL: unsimulated node was recorded!"
    print("✅ Not-simulated filter: PASSED")


if __name__ == '__main__':
    print("=" * 60)
    print("ExecutedRouteRecorder Unit Tests")
    print("=" * 60)

    test_basic()
    test_dedup()
    test_not_completed()
    test_future_node()
    test_not_simulated()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✅")
    print("=" * 60)
