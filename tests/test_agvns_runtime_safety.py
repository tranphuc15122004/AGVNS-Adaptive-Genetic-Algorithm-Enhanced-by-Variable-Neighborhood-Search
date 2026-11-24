import importlib.util
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "AGVNS"))

import algorithm.algorithm_config as config
import algorithm.Test_algorithm.GAVND7 as gavnd7


class _FakeChromosome:
    def __init__(self, fitness):
        self.fitness = fitness
        self.solution = {}


def test_gavnd7_keeps_incumbent_when_divergence_filter_is_empty(monkeypatch):
    incumbent = _FakeChromosome(10.0)
    worse_candidate = _FakeChromosome(20.0)

    monkeypatch.setattr(
        gavnd7,
        "new_generate_random_chromosome",
        lambda *args: ([incumbent], {}),
    )
    monkeypatch.setattr(
        gavnd7,
        "remove_similar_individuals",
        lambda population, threshold: [worse_candidate],
    )
    monkeypatch.setattr(config, "NUMBER_OF_GENERATION", 0)
    monkeypatch.setattr(config, "addDelta", 0.0)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(gavnd7, "adaptive_LS_stategy", lambda *args: False)

    result = gavnd7.GAVND_7({}, {}, {}, {0: {}, 1: {}}, {})

    assert result.fitness == pytest.approx(10.0)
    assert result._fitness_at_timeout == pytest.approx(10.0)


def test_gavnd7_divergence_phase_uses_global_algorithm_deadline(monkeypatch):
    incumbent = _FakeChromosome(10.0)
    improving_candidate = _FakeChromosome(9.0)
    adaptive_calls = []

    monkeypatch.setattr(
        gavnd7,
        "new_generate_random_chromosome",
        lambda *args: ([incumbent], {}),
    )
    monkeypatch.setattr(
        gavnd7,
        "remove_similar_individuals",
        lambda population, threshold: [improving_candidate],
    )
    monkeypatch.setattr(config, "NUMBER_OF_GENERATION", 0)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "addDelta", 0.0)
    monkeypatch.setattr(
        gavnd7,
        "adaptive_LS_stategy",
        lambda *args: adaptive_calls.append(True),
    )

    gavnd7.GAVND_7({}, {}, {}, {0: {}, 1: {}}, {})

    assert adaptive_calls == [True]


def test_gavnd7_adaptive_ls_uses_unbounded_operator_budget(monkeypatch):
    captured_limits = []
    individual = SimpleNamespace(
        solution={},
        id_to_vehicle={},
        route_map={},
        improved_LS_map={
            "PDPairExchange": 0,
            "BlockExchange": 0,
            "BlockRelocate": 0,
            "mPDG": 0,
        },
    )

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(gavnd7, "total_cost", lambda *args: 0.0)
    monkeypatch.setattr(
        gavnd7,
        "get_adaptive_order",
        lambda *args: ["PDPairExchange", "BlockExchange", "BlockRelocate", "mPDG"],
    )

    def _capture_limit(*args):
        captured_limits.append(args[3])
        return False

    monkeypatch.setattr(gavnd7, "new_inter_couple_exchange", _capture_limit)
    monkeypatch.setattr(gavnd7, "new_block_exchange", _capture_limit)
    monkeypatch.setattr(gavnd7, "new_block_relocate", _capture_limit)
    monkeypatch.setattr(gavnd7, "new_multi_pd_group_relocate", _capture_limit)

    gavnd7.adaptive_LS_stategy(individual, {}, False)

    assert captured_limits == [float("inf")] * 4


def test_initial_population_uses_configured_perturbation(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    calls = []

    class _FakeNode:
        pass

    class _FakeChromosome:
        def __init__(self, *args):
            self.fitness = 0.0

    monkeypatch.setattr(
        new_engine,
        "disturbance_opt",
        lambda *args: calls.append(args[-1]) or object(),
    )
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(new_engine, "Chromosome", _FakeChromosome)
    monkeypatch.setattr(config, "PERTURBATION_RATE", 0.25)

    node = _FakeNode()
    unongoing = {
        0: {"vehicle,0": node, "vehicle,1": node},
        1: {"vehicle,2": node, "vehicle,3": node},
    }

    new_engine.new_generate_random_chromosome(
        {}, {}, {}, unongoing, {}, quantity=1
    )

    assert calls == [0.25]


def test_dispatch_node_pair_returns_without_work_when_deadline_expired():
    import algorithm.engine as engine

    class _FakeNode:
        id = "factory"
        pickup_item_list = []
        delivery_item_list = []

    result = engine.dispatch_nodePair(
        [_FakeNode(), _FakeNode()], {}, {}, {}, deadline=time.monotonic() - 1
    )

    assert result == (False, "", 0, 1, [])


def test_random_dispatch_uses_constant_time_fallback_after_deadline(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    import algorithm.engine as engine

    item = SimpleNamespace(id="deadline-item", demand=1.0)
    pickup = SimpleNamespace(pickup_item_list=[item], delivery_item_list=[])
    delivery = SimpleNamespace(pickup_item_list=[], delivery_item_list=[item])
    vehicle = SimpleNamespace(des=None, carrying_items=[], board_capacity=10.0)
    plans = {"v1": []}
    feasibility_calls = []

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(
        engine,
        "isFeasible",
        lambda *args, **kwargs: feasibility_calls.append(True) or True,
    )

    result = new_engine.random_dispatch_nodePair(
        [pickup, delivery],
        {"v1": vehicle},
        plans,
        deadline=time.monotonic() - 1,
    )

    assert result is True
    assert feasibility_calls == [True]
    assert plans["v1"] == [pickup, delivery]


def test_dispatch_ci_never_inserts_before_committed_destination(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Node, OrderItem

    committed = OrderItem(
        id="committed-1",
        order_id="committed",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    new_item = OrderItem(
        id="new-1",
        order_id="new",
        pickup_factory_id="F1",
        delivery_factory_id="F3",
        demand=1.0,
    )
    destination = Node("F1", [], [committed])
    committed_delivery = Node("F2", [committed], [])
    pickup = Node("F1", [], [new_item])
    delivery = Node("F3", [new_item], [])
    vehicle = SimpleNamespace(des=destination, carrying_items=[], board_capacity=10.0)
    plans = {"V_1": [destination, committed_delivery]}

    monkeypatch.setattr(new_engine, "create_Pickup_Delivery_nodes", lambda *args: [pickup, delivery])
    monkeypatch.setattr(
        new_engine,
        "dispatch_nodePair",
        lambda *args, **kwargs: (False, "V_1", 0, 1, []),
    )
    monkeypatch.setattr(config, "is_timeout", lambda: False)

    new_engine._dispatch_new_orders_impl(
        plans,
        {"F1": object(), "F3": object()},
        {},
        {"V_1": vehicle},
        {"new-1": new_item},
        ["new-1"],
        deadline=None,
    )

    assert plans["V_1"] == [destination, committed_delivery, pickup, delivery]


def test_dispatch_node_pair_returns_insert_position_after_destination(monkeypatch):
    import algorithm.engine as engine
    from algorithm.Object import Node

    destination = Node("F1", [], [])
    route = [destination] + [Node(f"F{index}", [], []) for index in range(2, 9)]
    vehicle = SimpleNamespace(des=destination)

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(engine, "cost_of_a_route", lambda *args, **kwargs: 1.0)

    pickup = Node("F2", [], [])
    delivery = Node("F3", [], [])
    result = engine.dispatch_nodePair(
        [pickup, delivery],
        {"V_1": vehicle},
        {"V_1": route},
        {},
    )

    assert result[1] == "V_1"
    assert result[2] >= 1
    assert result[3] > result[2]


def test_dispatch_repairs_destination_after_exhaustive_ci_replacement(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Node, OrderItem

    committed = OrderItem(
        id="committed-2",
        order_id="committed-2",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    new_item = OrderItem(
        id="new-2",
        order_id="new-2",
        pickup_factory_id="F1",
        delivery_factory_id="F3",
        demand=1.0,
    )
    destination = Node("F1", [], [committed])
    committed_delivery = Node("F2", [committed], [])
    pickup = Node("F1", [], [new_item])
    delivery = Node("F3", [new_item], [])
    vehicle = SimpleNamespace(des=destination, carrying_items=[], board_capacity=10.0)
    plans = {"V_1": [destination, committed_delivery]}

    monkeypatch.setattr(new_engine, "create_Pickup_Delivery_nodes", lambda *args: [pickup, delivery])
    monkeypatch.setattr(
        new_engine,
        "dispatch_nodePair",
        lambda *args, **kwargs: (True, "V_1", 0, 1, [pickup, delivery]),
    )
    monkeypatch.setattr(config, "is_timeout", lambda: False)

    new_engine._dispatch_new_orders_impl(
        plans,
        {"F1": object(), "F3": object()},
        {},
        {"V_1": vehicle},
        {"new-2": new_item},
        ["new-2"],
        deadline=None,
    )

    assert plans["V_1"] == [destination, committed_delivery, pickup, delivery]


def test_is_feasible_returns_true_for_valid_route():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    item = OrderItem(
        id="feasible-1",
        order_id="feasible",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
    )

    route = [
        Node("F1", [], [item]),
        Node("F2", [item], []),
    ]

    assert engine.isFeasible(route, [], 10.0) is True


def test_is_feasible_rejects_capacity_overflow():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    item_a = OrderItem(
        id="capacity-1",
        order_id="capacity",
        pickup_factory_id="F1",
        delivery_factory_id="F4",
        demand=1.0,
    )
    item_b = OrderItem(
        id="capacity-2",
        order_id="capacity",
        pickup_factory_id="F2",
        delivery_factory_id="F3",
        demand=1.0,
    )

    route = [
        Node("F1", [], [item_a]),
        Node("F2", [], [item_b]),
        Node("F3", [item_b], []),
        Node("F4", [item_a], []),
    ]

    assert engine.isFeasible(route, [], 1.0) is False


def test_subprocess_timeout_terminates_process_group(monkeypatch):
    import src.utils.json_tools as json_tools

    calls = {}

    class _FakeProcess:
        pid = 1234

        def communicate(self, timeout=None):
            calls["communicate_timeout"] = timeout
            if not calls.get("timed_out"):
                calls["timed_out"] = True
                raise subprocess.TimeoutExpired("python3 main_algorithm.py", timeout)
            return b"", b""

        def poll(self):
            return -15 if calls.get("wait") or calls.get("killed") else None

        def wait(self, timeout=None):
            calls["wait"] = timeout
            return -15

        def kill(self):
            calls["killed"] = True

    def fake_popen(*args, **kwargs):
        calls["popen_args"] = args
        calls["popen_kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(json_tools.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        json_tools.os,
        "killpg",
        lambda pid, signal: calls.setdefault("killpg", (pid, signal)),
        raising=False,
    )
    monkeypatch.setattr(json_tools.Configs, "MAX_RUNTIME_OF_ALGORITHM", 1)

    elapsed, message = json_tools.subprocess_function("python3 main_algorithm.py")

    assert elapsed is None
    assert message == "Timeout"
    assert calls["popen_kwargs"].get("shell") is not True
    assert calls["popen_kwargs"]["start_new_session"] is True
    assert calls["popen_kwargs"]["cwd"] == json_tools.Configs.root_folder_path
    assert calls["killpg"][0] == 1234


def test_main_records_system_exit_as_failed_runtime_stat(monkeypatch):
    main_path = pathlib.Path(__file__).parents[1] / "AGVNS" / "main.py"
    main_spec = importlib.util.spec_from_file_location("agvns_runner_main", main_path)
    agvns_main = importlib.util.module_from_spec(main_spec)
    main_spec.loader.exec_module(agvns_main)

    created_stats = []

    class _FakeRuntimeStats:
        csv_path = "runtime.csv"
        json_path = "runtime.json"

        def __init__(self, *args, **kwargs):
            self.records = []
            created_stats.append(self)

        def start_instance(self, instance):
            return "started"

        def record(self, instance, **kwargs):
            self.records.append((instance, kwargs))

    def fail_simulation(*args):
        raise SystemExit(-1)

    monkeypatch.setattr(
        agvns_main,
        "_parse_args",
        lambda: SimpleNamespace(
            stats_file="runtime.csv",
            seed=7,
            data_dir=None,
            instances="1",
            cpu=None,
        ),
    )
    monkeypatch.setattr(agvns_main, "_configure_runtime", lambda args: None)
    monkeypatch.setattr(agvns_main, "_get_test_instances", lambda: [1])
    monkeypatch.setattr(agvns_main, "RuntimeStats", _FakeRuntimeStats)
    monkeypatch.setattr(agvns_main, "simulate", fail_simulation)
    monkeypatch.setattr(agvns_main, "ini_logger", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agvns_main, "remove_file_handler_of_logging", lambda *args: None
    )

    with pytest.raises(SystemExit) as exc_info:
        agvns_main.main()

    assert exc_info.value.code == 1
    assert created_stats[0].records[0][0] == "instance_1"
    assert created_stats[0].records[0][1]["status"] == "FAILED"


def test_simulator_does_not_report_infeasible_dispatch_as_success(monkeypatch):
    import src.simulator.simulate_environment as simulate_environment

    environment = simulate_environment.SimulateEnvironment.__new__(
        simulate_environment.SimulateEnvironment
    )
    environment.pre_time = 0
    environment.time_interval = 600
    environment.time_to_dispatch_result = {}
    environment.id_to_vehicle = {}
    environment.id_to_order = {}
    environment.update_input = lambda: object()
    environment.dispatch = lambda _input: (0, object())

    monkeypatch.setattr(
        simulate_environment.Checker,
        "check_dispatch_result",
        lambda *args: False,
    )

    with pytest.raises(RuntimeError, match="infeasible"):
        environment.run()


def test_new_dispatch_rolls_back_partial_ci_failure_and_uses_emergency_fallback(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    item = SimpleNamespace(id="item-1", order_id="order-1", demand=1.0)
    pickup = SimpleNamespace(
        id="pickup", pickup_item_list=[item], delivery_item_list=[]
    )
    delivery = SimpleNamespace(
        id="delivery", pickup_item_list=[], delivery_item_list=[item]
    )
    vehicle = SimpleNamespace(board_capacity=10.0, des=None, carrying_items=[])
    plans = {"v1": []}

    monkeypatch.setattr(
        new_engine,
        "create_Pickup_Delivery_nodes",
        lambda items, factories: [pickup, delivery],
    )
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    def broken_ci(node_list, vehicles, current_plans, route_map, **kwargs):
        current_plans["v1"].append(node_list[0])
        raise RuntimeError("synthetic CI failure")

    def emergency_fallback(node_list, vehicles, current_plans, deadline=None):
        current_plans["v1"].extend(node_list[:2])
        return True

    monkeypatch.setattr(new_engine, "dispatch_nodePair", broken_ci)
    monkeypatch.setattr(new_engine, "random_dispatch_nodePair", emergency_fallback)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {"pickup": object(), "delivery": object()},
        {},
        {"v1": vehicle},
        {"item-1": item},
        ["item-1"],
    )

    assert result is False
    assert [node.id for node in plans["v1"]] == ["pickup", "delivery"]


def test_new_dispatch_reports_missing_item_after_all_fallbacks_without_raising(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    item = SimpleNamespace(id="item-2", order_id="order-2", demand=1.0)
    vehicle = SimpleNamespace(board_capacity=10.0, des=None, carrying_items=[])
    plans = {"v1": []}

    monkeypatch.setattr(new_engine, "create_Pickup_Delivery_nodes", lambda *args: [])
    monkeypatch.setattr(new_engine, "random_dispatch_nodePair", lambda *args, **kwargs: False)
    monkeypatch.setattr(config, "is_timeout", lambda: True)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 0.0)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {},
        {},
        {"v1": vehicle},
        {"item-2": item},
        ["item-2"],
    )

    assert result is False
    assert plans == {"v1": []}


def test_algorithm_main_does_not_pass_local_dispatch_deadline(monkeypatch):
    main_path = pathlib.Path(__file__).parents[1] / "AGVNS" / "algorithm" / "main.py"
    main_spec = importlib.util.spec_from_file_location("agvns_algorithm_main_deadline", main_path)
    agvns_algorithm_main = importlib.util.module_from_spec(main_spec)
    main_spec.loader.exec_module(agvns_algorithm_main)

    captured = {}

    class _FakeChromosome:
        def __init__(self, solution, *args):
            self.solution = solution
            self.fitness = 0.0

    monkeypatch.setattr(agvns_algorithm_main, "_assert_valid_dispatch_plan", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main.Config, "set_begin_time", lambda: None)
    monkeypatch.setattr(agvns_algorithm_main.Config, "get_remaining_time", lambda: 42.0)
    monkeypatch.setattr(agvns_algorithm_main, "Input", lambda: ({}, {}, {}, {}, {}, {}))
    monkeypatch.setattr(agvns_algorithm_main, "deal_old_solution_file", lambda *args: None)
    monkeypatch.setattr(
        agvns_algorithm_main,
        "restore_scene_with_single_node",
        lambda *args: ["item-1"],
    )

    def capture_dispatch(*args, **kwargs):
        captured["deadline"] = kwargs.get("deadline")
        return True

    monkeypatch.setattr(agvns_algorithm_main, "new_dispatch_new_orders", capture_dispatch)
    monkeypatch.setattr(agvns_algorithm_main, "get_UnongoingSuperNode", lambda *args: ({}, {}))
    monkeypatch.setattr(agvns_algorithm_main, "Chromosome", _FakeChromosome)
    monkeypatch.setattr(agvns_algorithm_main, "GAVND_7", lambda *args: _FakeChromosome({}))
    monkeypatch.setattr(agvns_algorithm_main, "gold_algorithm_LS", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "get_route_after", lambda *args: "")
    monkeypatch.setattr(agvns_algorithm_main, "total_cost", lambda *args: 0.0)
    monkeypatch.setattr(agvns_algorithm_main, "update_solution_json", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "merge_node", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "get_output_solution", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "write_destination_json_to_file", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "write_route_json_to_file", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main, "append_current_solution", lambda *args: None)
    monkeypatch.setattr(agvns_algorithm_main.Config, "DELAY_DISPATCH", False)

    agvns_algorithm_main.main()

    assert captured["deadline"] is None


def test_gold_local_search_uses_unbounded_operator_budget(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    captured_limits = []
    individual = SimpleNamespace(solution={}, id_to_vehicle={}, route_map={})

    def unbounded_operator(*args):
        captured_limits.append(args[3])
        return False

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(new_engine, "total_cost", lambda *args: 0.0)
    monkeypatch.setattr(new_engine, "new_inter_couple_exchange", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_block_exchange", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_block_relocate", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_multi_pd_group_relocate", unbounded_operator)

    new_engine.gold_algorithm_LS(individual, False)

    assert captured_limits == [float("inf")] * 4


def test_gold_local_search_ignores_legacy_final_deadline(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    captured_limits = []
    individual = SimpleNamespace(solution={}, id_to_vehicle={}, route_map={})

    def unbounded_operator(*args):
        captured_limits.append(args[3])
        return False

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "FINAL_LS_TIME_LIMIT", 0.0, raising=False)
    monkeypatch.setattr(new_engine, "total_cost", lambda *args: 0.0)
    monkeypatch.setattr(new_engine, "new_inter_couple_exchange", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_block_exchange", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_block_relocate", unbounded_operator)
    monkeypatch.setattr(new_engine, "new_multi_pd_group_relocate", unbounded_operator)

    new_engine.gold_algorithm_LS(individual, False)

    assert captured_limits == [float("inf")] * 4


def test_local_deadline_does_not_override_global_clock(monkeypatch):
    monkeypatch.setattr(config, "BEGIN_MONOTONIC", time.monotonic())
    monkeypatch.setattr(config, "LOCAL_DEADLINE", time.monotonic() - 1.0, raising=False)

    assert config.is_timeout() is False


def test_total_cost_ignores_expired_local_deadline(monkeypatch):
    import algorithm.engine as engine

    vehicle = SimpleNamespace(
        cur_factory_id="F1",
        leave_time_at_current_factory=0,
        gps_update_time=0,
        des=None,
        board_capacity=10.0,
    )
    monkeypatch.setattr(config, "BEGIN_MONOTONIC", time.monotonic())
    monkeypatch.setattr(config, "LOCAL_DEADLINE", time.monotonic() - 1.0, raising=False)

    assert engine.total_cost({"V_1": vehicle}, {}, {"V_1": []}) != float("inf")


def test_single_vehicle_cost_ignores_expired_local_deadline(monkeypatch):
    import algorithm.engine as engine

    vehicle = SimpleNamespace(
        cur_factory_id="F1",
        leave_time_at_current_factory=0,
        gps_update_time=0,
        des=None,
        board_capacity=10.0,
    )
    monkeypatch.setattr(config, "BEGIN_MONOTONIC", time.monotonic())
    monkeypatch.setattr(config, "LOCAL_DEADLINE", time.monotonic() - 1.0, raising=False)
    node = SimpleNamespace(id="F1", pickup_item_list=[], delivery_item_list=[], service_time=0)

    assert engine.single_vehicle_cost([node], vehicle, {}) != float("inf")


def test_new_dispatch_restores_partial_pair_before_emergency_retry(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    item = SimpleNamespace(id="item-3", order_id="order-3", demand=1.0)
    pickup = SimpleNamespace(
        id="pickup", pickup_item_list=[item], delivery_item_list=[]
    )
    delivery = SimpleNamespace(
        id="delivery", pickup_item_list=[], delivery_item_list=[item]
    )
    vehicle = SimpleNamespace(board_capacity=10.0, des=None, carrying_items=[])
    plans = {"v1": []}

    monkeypatch.setattr(new_engine, "create_Pickup_Delivery_nodes", lambda *args: [pickup, delivery])
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    def partial_ci(node_list, vehicles, current_plans, route_map, **kwargs):
        current_plans["v1"].append(node_list[0])
        return False, "", 0, 1, []

    monkeypatch.setattr(new_engine, "dispatch_nodePair", partial_ci)
    monkeypatch.setattr(new_engine, "random_dispatch_nodePair", lambda *args, **kwargs: False)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {"pickup": object(), "delivery": object()},
        {},
        {"v1": vehicle},
        {"item-3": item},
        ["item-3"],
    )

    assert result is False
    assert [node.id for node in plans["v1"]] == ["pickup", "delivery"]


def test_new_dispatch_replaces_stale_requested_pairs_in_restored_route(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, Node, OrderItem

    item = OrderItem(
        id="stale-route-item",
        order_id="stale-route-order",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    plans = {
        "v1": [
            Node("F1", [], [item]),
            Node("F2", [item], []),
            Node("F1", [], [item]),
            Node("F2", [item], []),
        ]
    }
    vehicle = SimpleNamespace(
        board_capacity=10.0,
        des=None,
        carrying_items=[],
    )

    def dispatch_once(vehicleid_to_plan, *args, **kwargs):
        vehicleid_to_plan["v1"].extend([
            Node("F1", [], [item]),
            Node("F2", [item], []),
        ])
        return True

    monkeypatch.setattr(new_engine, "_dispatch_new_orders_impl", dispatch_once)
    monkeypatch.setattr(new_engine, "random_dispatch_nodePair", lambda *args, **kwargs: False)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {
            "F1": Factory("F1", 1.0, 1.0, 1),
            "F2": Factory("F2", 2.0, 2.0, 1),
        },
        {},
        {"v1": vehicle},
        {item.id: item},
        [item.id],
        strict=True,
    )

    pickup_count = sum(
        entry.id == item.id
        for route in plans.values()
        for node in route
        for entry in node.pickup_item_list
    )
    delivery_count = sum(
        entry.id == item.id
        for route in plans.values()
        for node in route
        for entry in node.delivery_item_list
    )
    assert result is True
    assert (pickup_count, delivery_count) == (1, 1)


def test_new_dispatch_rejects_pair_on_different_routes_or_wrong_order(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    item = SimpleNamespace(id="item-4", order_id="order-4", demand=1.0)
    pickup = SimpleNamespace(
        id="pickup", pickup_item_list=[item], delivery_item_list=[]
    )
    delivery = SimpleNamespace(
        id="delivery", pickup_item_list=[], delivery_item_list=[item]
    )
    vehicle = SimpleNamespace(board_capacity=10.0, des=None, carrying_items=[])
    plans = {"v1": []}

    monkeypatch.setattr(new_engine, "create_Pickup_Delivery_nodes", lambda *args: [pickup, delivery])
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)
    monkeypatch.setattr(
        new_engine,
        "dispatch_nodePair",
        lambda *args, **kwargs: (True, "v1", 0, 1, [delivery, pickup]),
    )

    result = new_engine.new_dispatch_new_orders(
        plans,
        {"pickup": object(), "delivery": object()},
        {},
        {"v1": vehicle},
        {"item-4": item},
        ["item-4"],
    )

    assert result is False
    assert [node.id for node in plans["v1"]] == ["pickup", "delivery"]


def test_restore_scene_seeds_committed_destination_prefix(monkeypatch, tmp_path):
    import algorithm.engine as engine
    from algorithm.Object import Factory, Node, OrderItem, Vehicle

    monkeypatch.setattr(engine, "input_directory", str(tmp_path))
    item = OrderItem(
        id="destination-1",
        order_id="destination",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    destination = Node("F1", [], [item], arrive_time=100, leave_time=110)
    vehicle = Vehicle("V_1", "G_1", 24, 10.0, [], destination)
    vehicle.set_cur_position_info("F0", 0, 0, 0)

    plans = {}
    new_ids = engine.restore_scene_with_single_node(
        plans,
        {},
        {item.id: item},
        {vehicle.id: vehicle},
        {
            "F0": Factory("F0", 0.0, 0.0, 1),
            "F1": Factory("F1", 1.0, 1.0, 1),
            "F2": Factory("F2", 2.0, 2.0, 1),
        },
        {item.id: item},
    )

    assert new_ids == [item.id]
    assert plans[vehicle.id][0].id == destination.id
    assert [order_item.id for order_item in plans[vehicle.id][0].pickup_item_list] == [item.id]



def test_restore_scene_trims_unloaded_deliveries_from_committed_destination():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    items = {
        "order-%d" % suffix: OrderItem(
            id="order-%d" % suffix,
            order_id="order",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        )
        for suffix in range(1, 6)
    }
    committed_item = items["order-5"]
    destination = Node("F2", [committed_item], [], arrive_time=10, leave_time=20)
    vehicle = SimpleNamespace(carrying_items=[committed_item], des=destination)
    serialized_head = Node("F2", list(reversed(list(items.values()))), [])

    requeued = set()
    restored = engine._reconcile_restored_route(
        "V_11",
        vehicle,
        [serialized_head],
        set(),
        {"order-1", "order-2", "order-3", "order-4"},
        requeued,
    )

    assert [item.id for item in restored[0].delivery_item_list] == [committed_item.id]
    assert requeued == {"order-1", "order-2", "order-3", "order-4"}
    assert engine.isFeasible(restored, vehicle.carrying_items, capacity=5.0)



def test_restore_scene_drops_unloaded_delivery_tail_at_committed_factory():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    committed_item = OrderItem(
        id="committed-1",
        order_id="committed",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    stale_items = [
        OrderItem(
            id="stale-%d" % suffix,
            order_id="stale",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        )
        for suffix in range(1, 5)
    ]
    destination = Node("F2", [committed_item], [], arrive_time=10, leave_time=20)
    vehicle = SimpleNamespace(carrying_items=[committed_item], des=destination)
    saved_tail = Node("F2", list(reversed(stale_items)), [])

    requeued = set()
    restored = engine._reconcile_restored_route(
        "V_11",
        vehicle,
        [saved_tail],
        set(),
        {item.id for item in stale_items},
        requeued,
    )

    assert len(restored) == 1
    assert [item.id for item in restored[0].delivery_item_list] == [committed_item.id]
    assert requeued == {item.id for item in stale_items}
    assert engine.isFeasible(restored, vehicle.carrying_items, capacity=5.0)


def test_restore_scene_removes_stale_destination_actions_from_route_tail():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    item = OrderItem(
        id="destination-stale-1",
        order_id="destination-stale",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    destination = Node("F1", [], [item])
    stale_same_factory = Node("F1", [], [])
    stale_tail = Node("F1", [], [item])
    unrelated = Node("F3", [], [])
    plans = {"v1": [stale_same_factory, stale_tail, unrelated]}
    vehicle = SimpleNamespace(des=destination)

    engine._ensure_destination_prefix(plans, {"v1": vehicle})

    assert len(plans["v1"]) == 2
    assert plans["v1"][0].pickup_item_list[0].id == item.id
    assert plans["v1"][1].id == "F3"
    assert not plans["v1"][1].pickup_item_list


def test_new_dispatch_handles_item_already_picked_at_destination(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, Node, OrderItem

    item = OrderItem(
        id="destination-2",
        order_id="destination",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    destination = Node("F1", [], [item])
    vehicle = SimpleNamespace(
        board_capacity=10.0,
        des=destination,
        carrying_items=[],
        cur_factory_id="F0",
    )
    plans = {"v1": [destination]}
    calls = []

    def fake_impl(*args, **kwargs):
        calls.append(args[5])
        return True

    monkeypatch.setattr(new_engine, "_dispatch_new_orders_impl", fake_impl)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {
            "F1": Factory("F1", 1.0, 1.0, 1),
            "F2": Factory("F2", 2.0, 2.0, 1),
        },
        {},
        {"v1": vehicle},
        {item.id: item},
        [item.id],
    )

    assert result is False
    assert calls == [[]]
    assert [node.id for node in plans["v1"]] == ["F1", "F2"]
    assert plans["v1"][0].pickup_item_list[0].id == item.id
    assert plans["v1"][1].delivery_item_list[0].id == item.id


def test_new_dispatch_splits_oversized_order_on_timeout(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, OrderItem

    items = [
        OrderItem(
            id="timeout-block-1",
            order_id="timeout-block",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        ),
        OrderItem(
            id="timeout-block-2",
            order_id="timeout-block",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        ),
    ]
    vehicle = SimpleNamespace(board_capacity=1.0, des=None, carrying_items=[])
    plans = {"v1": []}
    calls = []

    def timeout_random(node_list, vehicles, current_plans, deadline=None):
        calls.append(len(node_list[0].pickup_item_list))
        current_plans["v1"].extend(node_list)
        return True

    monkeypatch.setattr(new_engine, "random_dispatch_nodePair", timeout_random)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {
            "F1": Factory("F1", 0.0, 0.0, 1),
            "F2": Factory("F2", 1.0, 1.0, 1),
        },
        {},
        {"v1": vehicle},
        {item.id: item for item in items},
        [item.id for item in items],
        deadline=time.monotonic() - 1,
    )

    assert result is False
    assert calls == []
    assert len(plans["v1"]) == 4


def test_sensitivity_runner_records_outer_worker_timeout(monkeypatch, tmp_path):
    runner_path = (
        pathlib.Path(__file__).parents[1]
        / "AGVNS"
        / "experiments"
        / "agvns_parameter_sensitivity"
        / "run_screening.py"
    )
    spec = importlib.util.spec_from_file_location(
        "agvns_sensitivity_runner_safety", runner_path
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    class _FakeProcess:
        pid = 321
        returncode = None

        def poll(self):
            return None if self.returncode is None else self.returncode

    process = _FakeProcess()
    log_path = tmp_path / "worker.log"
    log_path.write_text("", encoding="utf-8")
    job = {
        "configuration_id": 1,
        "instance_id": 57,
        "repetition": 1,
        "seed": 57001,
    }
    worker = {
        "job": job,
        "workspace": tmp_path,
        "log_path": log_path,
        "process": process,
        "log_handle": log_path.open("r+", encoding="utf-8"),
        "core": 0,
        "started_monotonic": time.monotonic() - 10,
    }
    results = []

    monkeypatch.setattr(runner, "launch", lambda *args, **kwargs: worker)
    monkeypatch.setattr(
        runner,
        "terminate_worker",
        lambda current: setattr(current["process"], "returncode", -9),
    )
    monkeypatch.setattr(runner, "append_result", lambda _run_dir, result: results.append(result))
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    runner.run_jobs(
        SimpleNamespace(
            workers=1,
            resume=False,
            job_timeout_seconds=0.01,
            python=sys.executable,
        ),
        tmp_path,
        [job],
        [0],
    )

    assert len(results) == 1
    assert results[0]["status"] == "FAILED"
    assert "outer job wall-time exceeded" in results[0]["error"]


def test_new_dispatch_delivers_destination_pickups_in_reverse_loading_order(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, Node, OrderItem

    items = [
        OrderItem(
            id="destination-order-1",
            order_id="destination-order",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        ),
        OrderItem(
            id="destination-order-2",
            order_id="destination-order",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        ),
        OrderItem(
            id="destination-order-3",
            order_id="destination-order",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        ),
    ]
    destination = Node("F1", [], items)
    vehicle = SimpleNamespace(board_capacity=10.0, des=destination, carrying_items=[])
    plans = {"v1": [destination]}

    monkeypatch.setattr(new_engine, "_dispatch_new_orders_impl", lambda *args, **kwargs: True)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "get_remaining_time", lambda: 60.0)

    result = new_engine.new_dispatch_new_orders(
        plans,
        {
            "F1": Factory("F1", 1.0, 1.0, 1),
            "F2": Factory("F2", 2.0, 2.0, 1),
        },
        {},
        {"v1": vehicle},
        {item.id: item for item in items},
        [item.id for item in items],
    )

    assert result is False
    assert [item.id for item in plans["v1"][1].delivery_item_list] == [items[2].id]
    assert [item.id for item in plans["v1"][2].delivery_item_list] == [items[1].id]
    assert [item.id for item in plans["v1"][3].delivery_item_list] == [items[0].id]


def test_validate_dispatch_plan_catches_destination_and_pair_corruption():
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, Node, OrderItem

    item = OrderItem(
        id="validate-1",
        order_id="validate",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    destination = Node("F0", [], [])
    vehicle = SimpleNamespace(
        board_capacity=10.0,
        des=destination,
        carrying_items=[],
    )
    pickup = Node("F1", [], [item])
    delivery = Node("F2", [item], [])

    errors = new_engine.validate_dispatch_plan(
        {"v1": [pickup, delivery]},
        {"v1": vehicle},
        [item.id],
        {
            "F0": Factory("F0", 0.0, 0.0, 1),
            "F1": Factory("F1", 1.0, 1.0, 1),
            "F2": Factory("F2", 2.0, 2.0, 1),
        },
    )

    assert any("destination" in error for error in errors)


def test_validate_dispatch_plan_rejects_undelivered_cargo_before_simulator():
    import algorithm.Test_algorithm.new_engine as new_engine
    from algorithm.Object import Factory, Node, OrderItem

    carrying_item = OrderItem(
        id="carry-over-1",
        order_id="carry-over",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    destination = Node("F0", [], [])
    vehicle = SimpleNamespace(
        board_capacity=10.0,
        des=destination,
        carrying_items=[carrying_item],
    )

    errors = new_engine.validate_dispatch_plan(
        {"v1": [destination]},
        {"v1": vehicle},
        [],
        {"F0": Factory("F0", 0.0, 0.0, 1)},
    )

    assert any("FILO/capacity" in error for error in errors)


def test_restore_scene_skips_one_invalid_legacy_node_and_keeps_valid_nodes(monkeypatch, tmp_path):
    import algorithm.engine as engine
    from algorithm.Object import Factory, OrderItem

    solution_path = tmp_path / "solution.json"
    solution_path.write_text(
        json.dumps(
            {
                "no": 1,
                "route_after": "V_1:[d2_missing-1 p1_known-1]",
                "onvehicle_order_items": "",
                "unallocated_order_items": "",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "input_directory", str(tmp_path))

    known_item = OrderItem(
        id="known-1",
        order_id="known",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    new_item = OrderItem(
        id="new-1",
        order_id="new",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    plans = {}
    new_ids = engine.restore_scene_with_single_node(
        plans,
        {},
        {"new-1": new_item},
        {"V_1": object()},
        {"F1": Factory("F1", 0.0, 0.0, 1), "F2": Factory("F2", 1.0, 1.0, 1)},
        {"known-1": known_item, "new-1": new_item},
    )

    assert new_ids == ["new-1"]
    assert [node.id for node in plans["V_1"]] == ["F1"]


def test_restore_scene_falls_back_to_all_unallocated_when_solution_is_invalid(monkeypatch, tmp_path):
    import algorithm.engine as engine
    from algorithm.Object import Factory, OrderItem

    (tmp_path / "solution.json").write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(engine, "input_directory", str(tmp_path))
    item = OrderItem(
        id="fallback-1",
        order_id="fallback",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )

    new_ids = engine.restore_scene_with_single_node(
        {},
        {},
        {item.id: item},
        {"V_1": object()},
        {
            "F1": Factory("F1", 0.0, 0.0, 1),
            "F2": Factory("F2", 1.0, 1.0, 1),
        },
        {item.id: item},
    )

    assert new_ids == [item.id]


def test_restore_scene_requeues_unallocated_orphan_delivery(monkeypatch, tmp_path):
    import algorithm.engine as engine
    from algorithm.Object import Factory, OrderItem

    (tmp_path / "solution.json").write_text(
        json.dumps(
            {
                "no": 1,
                "route_after": "V_1:[d1_orphan-1]",
                "onvehicle_order_items": "",
                "unallocated_order_items": "orphan-1",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "input_directory", str(tmp_path))

    item = OrderItem(
        id="orphan-1",
        order_id="orphan",
        pickup_factory_id="F1",
        delivery_factory_id="F2",
        demand=1.0,
    )
    plans = {}
    new_ids = engine.restore_scene_with_single_node(
        plans,
        {},
        {item.id: item},
        {"V_1": SimpleNamespace(des=None)},
        {
            "F1": Factory("F1", 0.0, 0.0, 1),
            "F2": Factory("F2", 1.0, 1.0, 1),
        },
        {item.id: item},
    )

    assert new_ids == [item.id]
    assert plans["V_1"] == []


def test_solution_route_round_trip_preserves_noncontiguous_delivery_item_ids(
        monkeypatch, tmp_path):
    import algorithm.engine as engine
    from algorithm.Object import Factory, Node, OrderItem

    item_ids = ["order-1", "order-10"] + ["order-%d" % i for i in range(2, 10)]
    items = [
        OrderItem(
            id=item_id,
            order_id="order",
            pickup_factory_id="F1",
            delivery_factory_id="F2",
            demand=1.0,
        )
        for item_id in item_ids
    ]
    vehicle = SimpleNamespace(
        des=None,
        carrying_items=[],
        board_capacity=20.0,
        gps_update_time=0,
    )
    plans = {
        "V_1": [
            Node("F1", [], items),
            Node("F2", list(reversed(items)), []),
        ]
    }
    monkeypatch.setattr(engine, "input_directory", str(tmp_path))

    engine.update_solution_json(
        {}, {item.id: item for item in items}, {"V_1": vehicle},
        plans, {}, {}, used_time=0.0,
    )

    persisted_solution = json.loads((tmp_path / "solution.json").read_text())
    restored_plans = {}
    restored_ids = engine.restore_scene_with_single_node(
        restored_plans,
        {},
        {item.id: item for item in items},
        {"V_1": vehicle},
        {
            "F1": Factory("F1", 0.0, 0.0, 1),
            "F2": Factory("F2", 1.0, 1.0, 1),
        },
        {item.id: item for item in items},
    )

    assert restored_ids == []
    assert len(restored_plans["V_1"]) == 2
    assert [item.id for item in restored_plans["V_1"][0].pickup_item_list] == item_ids
    assert [item.id for item in restored_plans["V_1"][1].delivery_item_list] == list(
        reversed(item_ids)
    )


def test_main_captures_cheapest_insertion_fitness_before_running_ga(monkeypatch, capsys):
    import importlib
    import math

    algorithm_main = importlib.import_module("algorithm.main")
    state = {"timed_out": False}

    class _FakeChromosome:
        def __init__(self, solution, route_map, id_to_vehicle):
            self.solution = solution

        @property
        def fitness(self):
            return math.inf if state["timed_out"] else 12.5

    monkeypatch.setattr(algorithm_main.Config, "set_begin_time", lambda: None)
    monkeypatch.setattr(algorithm_main.Config, "BEGIN_TIME", time.time())
    monkeypatch.setattr(algorithm_main.Config, "DELAY_DISPATCH", False)
    monkeypatch.setattr(algorithm_main, "Input", lambda: ({}, {}, {}, {}, {}, {}))
    monkeypatch.setattr(algorithm_main, "deal_old_solution_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "restore_scene_with_single_node", lambda *args: [])
    monkeypatch.setattr(algorithm_main, "new_dispatch_new_orders", lambda *args, **kwargs: None)
    monkeypatch.setattr(algorithm_main, "_assert_valid_dispatch_plan", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_UnongoingSuperNode", lambda *args: ({}, {}))
    monkeypatch.setattr(algorithm_main, "Chromosome", _FakeChromosome)

    def _run_ga(*args):
        state["timed_out"] = True
        return _FakeChromosome({}, {}, {})

    monkeypatch.setattr(algorithm_main, "GAVND_7", _run_ga)
    monkeypatch.setattr(algorithm_main, "get_route_after", lambda *args: "routes")
    monkeypatch.setattr(algorithm_main, "total_cost", lambda *args: math.inf)
    monkeypatch.setattr(algorithm_main, "update_solution_json", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "merge_node", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_output_solution", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_destination_json_to_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_route_json_to_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "append_current_solution", lambda *args: None)

    algorithm_main.main()

    assert "The fitness value before EA: 12.5" in capsys.readouterr().out



def test_search_stops_at_570_but_finalization_uses_simulator_safety_window(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(config.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(config, "BEGIN_MONOTONIC", 1000.0)
    monkeypatch.setattr(config, "ALGO_TIME_LIMIT", 570.0)
    monkeypatch.setattr(config, "SIMULATOR_HARD_TIMEOUT_SECONDS", 6000.0, raising=False)
    monkeypatch.setattr(config, "FINALIZATION_MODE", False, raising=False)

    clock["now"] = 1570.0
    assert config.is_timeout() is True

    config.begin_finalization()

    assert config.is_timeout() is False
    assert config.get_remaining_time() == pytest.approx(5430.0)

    clock["now"] = 7000.0
    assert config.is_timeout() is True
    assert config.get_remaining_time() == 0.0


def test_main_selects_finite_ga_incumbent_checkpoint_after_search_deadline(
    monkeypatch, capsys
):
    import importlib
    import math

    algorithm_main = importlib.import_module("algorithm.main")
    state = {"finalizing": False, "ga_score_reads": 0}

    class _FakeChromosome:
        def __init__(self, solution, route_map, id_to_vehicle):
            self.solution = solution
            self._fitness = 12.5 if solution.get("V_1") == ["ci"] else math.inf
            if solution.get("V_1") == ["ga"]:
                self._fitness_at_timeout = 9.5

        @property
        def fitness(self):
            if self.solution.get("V_1") == ["ga"]:
                state["ga_score_reads"] += 1
                return math.inf
            if not state["finalizing"]:
                return math.inf
            return 12.5

    monkeypatch.setattr(algorithm_main.Config, "set_begin_time", lambda: None)
    monkeypatch.setattr(algorithm_main.Config, "BEGIN_TIME", time.time())
    monkeypatch.setattr(
        algorithm_main.Config,
        "begin_finalization",
        lambda: state.update(finalizing=True),
        raising=False,
    )
    monkeypatch.setattr(algorithm_main.Config, "DELAY_DISPATCH", False)
    monkeypatch.setattr(algorithm_main, "Input", lambda: ({}, {}, {"V_1": object()}, {}, {}, {}))
    monkeypatch.setattr(algorithm_main, "deal_old_solution_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "restore_scene_with_single_node", lambda *args: [])
    monkeypatch.setattr(
        algorithm_main,
        "new_dispatch_new_orders",
        lambda plans, *args, **kwargs: plans.update({"V_1": ["ci"]}),
    )
    monkeypatch.setattr(algorithm_main, "_assert_valid_dispatch_plan", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_UnongoingSuperNode", lambda *args: ({}, {}))
    monkeypatch.setattr(algorithm_main, "Chromosome", _FakeChromosome)
    def _run_ga(*args):
        assert not state["finalizing"]
        return _FakeChromosome({"V_1": ["ga"]}, {}, {})

    monkeypatch.setattr(algorithm_main, "GAVND_7", _run_ga)
    monkeypatch.setattr(
        algorithm_main,
        "get_route_after",
        lambda plan, *args: ",".join(plan.get("V_1", [])),
    )
    monkeypatch.setattr(algorithm_main, "update_solution_json", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "merge_node", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_output_solution", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_destination_json_to_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_route_json_to_file", lambda *args: None)
    archived_fitness = []
    monkeypatch.setattr(
        algorithm_main,
        "append_current_solution",
        lambda fitness, *args: archived_fitness.append(fitness),
    )

    algorithm_main.main()

    output = capsys.readouterr().out
    assert archived_fitness == [9.5]
    assert state["ga_score_reads"] == 0
    assert "The fitness value after EA: 9.5" in output
    assert "The solution initialized by Cheapest Insertion:\nci" in output
    assert "Selected feasible GA solution" in output

def test_adaptive_ls_logs_last_finite_cost_after_timeout(monkeypatch, capsys):
    calls = []
    individual = SimpleNamespace(
        solution={},
        id_to_vehicle={},
        route_map={},
        improved_LS_map={
            "PDPairExchange": 0,
            "BlockExchange": 0,
            "BlockRelocate": 0,
            "mPDG": 0,
        },
    )

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(
        gavnd7,
        "total_cost",
        lambda *args: calls.append(True) or (12.5 if len(calls) == 1 else float("inf")),
    )
    monkeypatch.setattr(
        gavnd7,
        "get_adaptive_order",
        lambda *args: ["PDPairExchange", "BlockExchange", "BlockRelocate", "mPDG"],
    )
    monkeypatch.setattr(gavnd7, "new_inter_couple_exchange", lambda *args: False)
    monkeypatch.setattr(gavnd7, "new_block_exchange", lambda *args: False)
    monkeypatch.setattr(gavnd7, "new_block_relocate", lambda *args: False)
    monkeypatch.setattr(gavnd7, "new_multi_pd_group_relocate", lambda *args: False)

    gavnd7.adaptive_LS_stategy(individual, {}, False)

    assert "Cost:12.50" in capsys.readouterr().out
    assert len(calls) == 1


def test_total_cost_reuses_known_finite_score_after_algorithm_deadline(monkeypatch):
    import math

    import algorithm.engine as engine
    from algorithm.Object import Node

    deadline = {"expired": False}
    monkeypatch.setattr(engine.config, "is_timeout", lambda: deadline["expired"])
    plan = {"V_1": [Node("F1", [], [])]}
    route_map = {}
    vehicles = {
        "V_1": SimpleNamespace(
            cur_factory_id="F1",
            leave_time_at_current_factory=0,
            gps_update_time=0,
            des=None,
        )
    }

    known_score = engine.total_cost(vehicles, route_map, plan)
    assert known_score == pytest.approx(0.0)

    deadline["expired"] = True
    assert engine.total_cost(vehicles, route_map, plan) == pytest.approx(known_score)
    plan["V_1"].append(Node("F2", [], []))
    assert math.isinf(engine.total_cost(vehicles, route_map, plan))


def test_total_cost_reuses_score_of_previously_scored_mutation_after_deadline(monkeypatch):
    import algorithm.engine as engine
    from algorithm.Object import Node

    deadline = {"expired": False}
    monkeypatch.setattr(engine.config, "is_timeout", lambda: deadline["expired"])
    route_map = {("F1", "F2"): (10.0, 100)}
    vehicles = {
        "V_1": SimpleNamespace(
            cur_factory_id="F1",
            leave_time_at_current_factory=0,
            gps_update_time=0,
            des=None,
        )
    }
    first_node = Node("F1", [], [])
    second_node = Node("F2", [], [])
    candidate_plan = {"V_1": [first_node, second_node]}

    candidate_score = engine.total_cost(vehicles, route_map, candidate_plan)
    assert candidate_score == pytest.approx(10.0)

    accepted_plan = {"V_1": [first_node, second_node]}
    deadline["expired"] = True
    assert engine.total_cost(vehicles, route_map, accepted_plan) == pytest.approx(candidate_score)


def test_main_keeps_ci_solution_when_ga_returns_worse_fitness(monkeypatch, capsys):
    import importlib

    algorithm_main = importlib.import_module("algorithm.main")

    class _ScoredChromosome:
        def __init__(self, solution, route_map, id_to_vehicle):
            self.solution = solution

        @property
        def fitness(self):
            route = self.solution.get("V_1", [])
            return 12.5 if route == ["ci"] else 12.6

    monkeypatch.setattr(algorithm_main.Config, "set_begin_time", lambda: None)
    monkeypatch.setattr(algorithm_main.Config, "BEGIN_TIME", time.time())
    monkeypatch.setattr(algorithm_main.Config, "DELAY_DISPATCH", False)
    monkeypatch.setattr(algorithm_main, "Input", lambda: ({}, {}, {"V_1": object()}, {}, {}, {}))
    monkeypatch.setattr(algorithm_main, "deal_old_solution_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "restore_scene_with_single_node", lambda *args: [])
    monkeypatch.setattr(
        algorithm_main,
        "new_dispatch_new_orders",
        lambda plans, *args, **kwargs: plans.update({"V_1": ["ci"]}),
    )
    monkeypatch.setattr(algorithm_main, "_assert_valid_dispatch_plan", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_UnongoingSuperNode", lambda *args: ({}, {}))
    monkeypatch.setattr(algorithm_main, "Chromosome", _ScoredChromosome)
    monkeypatch.setattr(
        algorithm_main,
        "GAVND_7",
        lambda *args: _ScoredChromosome({"V_1": ["ga"]}, {}, {}),
    )
    monkeypatch.setattr(
        algorithm_main,
        "get_route_after",
        lambda plan, *args: ",".join(plan.get("V_1", [])),
    )
    monkeypatch.setattr(algorithm_main, "update_solution_json", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "merge_node", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "get_output_solution", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_destination_json_to_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "write_route_json_to_file", lambda *args: None)
    monkeypatch.setattr(algorithm_main, "append_current_solution", lambda *args: None)

    algorithm_main.main()

    output = capsys.readouterr().out
    assert "The fitness value before EA: 12.5" in output
    assert "The fitness value after EA: 12.5" in output
    assert "The solution initialized by Cheapest Insertion:\nci" in output
    assert "Selected feasible GA solution" not in output


def test_gavnd7_treats_fractional_fitness_gain_as_an_improvement(monkeypatch):
    class _FakeChromosome:
        def __init__(self, score_or_solution, *args):
            if isinstance(score_or_solution, dict):
                self.solution = score_or_solution
                self._fitness = self.solution["V_1"][0]
            else:
                self._fitness = score_or_solution
                self.solution = {"V_1": [score_or_solution]}
            self.improved_LS_map = {
                "PDPairExchange": 0,
                "BlockExchange": 0,
                "BlockRelocate": 0,
                "mPDG": 0,
            }

        @property
        def fitness(self):
            return self._fitness

    incumbent = _FakeChromosome(10.8)
    second = _FakeChromosome(11.0)
    child_scores = iter([10.7, 10.75] + [10.76, 10.77] * 7)
    crossover_calls = []

    monkeypatch.setattr(config, "BEGIN_TIME", time.time())
    monkeypatch.setattr(config, "NUMBER_OF_GENERATION", 8)
    monkeypatch.setattr(config, "POPULATION_SIZE", 2)
    monkeypatch.setattr(config, "MUTATION_RATE", 0.0)
    monkeypatch.setattr(config, "CROSSOVER_TYPE_RATIO", 1.0)
    monkeypatch.setattr(config, "addDelta", 0.0)
    monkeypatch.setattr(config, "is_timeout", lambda: False)
    monkeypatch.setattr(config, "applied_experiment_config", lambda: {
        "configuration_id": 1,
        "threshold_orders": 40,
        "population_size": 2,
        "perturbation_rate": 0.5,
        "mutation_rate": 0.25,
        "random_seed": 1,
    })
    monkeypatch.setattr(gavnd7, "adaptive_local_configs", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        gavnd7,
        "new_generate_random_chromosome",
        lambda *args: ([incumbent, second], {}),
    )
    monkeypatch.setattr(gavnd7, "Chromosome", _FakeChromosome)

    def _new_child(*args):
        crossover_calls.append(True)
        return _FakeChromosome(next(child_scores))

    monkeypatch.setattr(gavnd7, "new_crossver2", _new_child)
    monkeypatch.setattr(gavnd7, "randon_1_LS", lambda *args: None)
    monkeypatch.setattr(gavnd7, "remove_similar_individuals", lambda population, threshold: population)
    monkeypatch.setattr(gavnd7, "adaptive_LS_stategy", lambda *args: None)

    result = gavnd7.GAVND_7({}, {}, {}, {0: {}, 1: {}}, {})

    assert len(crossover_calls) == 10
    assert result.fitness == pytest.approx(10.7)



def test_is_feasible_rejects_missing_route_nodes_without_crashing():
    import algorithm.engine as engine

    assert not engine.isFeasible([None], [], 10.0)


def test_legacy_route_parser_recovers_noncontiguous_factory_groups():
    import algorithm.engine as engine
    from algorithm.Object import Factory, Node, OrderItem

    items = {}
    for suffix in range(1, 18):
        item_id = "legacy-order-%d" % suffix
        items[item_id] = OrderItem(
            id=item_id,
            order_id="legacy-order",
            pickup_factory_id="F2",
            delivery_factory_id="F2",
            demand=1.0,
        )
    expected_factory_items = sorted(
        item_id for item_id in items if item_id not in {
            "legacy-order-8", "legacy-order-9",
        }
    )
    vehicle = SimpleNamespace(
        carrying_items=[items[item_id] for item_id in expected_factory_items],
        des=Node(
            "F2", [items[item_id] for item_id in reversed(expected_factory_items)], [],
        ),
    )
    factories = {"F2": Factory("F2", 2.0, 2.0, 1)}

    pickup = engine._parse_legacy_route_node(
        "p15_legacy-order-1", factories, items, vehicle=vehicle
    )
    delivery = engine._parse_legacy_route_node(
        "d15_legacy-order-7", factories, items, vehicle=vehicle
    )

    assert [item.id for item in pickup.pickup_item_list] == expected_factory_items
    assert [item.id for item in delivery.delivery_item_list] == list(
        reversed(expected_factory_items)
    )



def test_dispatch_node_pair_skips_route_with_unpaired_existing_pickup(monkeypatch):
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    old_item = OrderItem(
        id="old-item", order_id="old-order", pickup_factory_id="F1",
        delivery_factory_id="F2", demand=1.0,
    )
    new_item = OrderItem(
        id="new-item", order_id="new-order", pickup_factory_id="F1",
        delivery_factory_id="F3", demand=1.0,
    )
    vehicle = SimpleNamespace(
        des=None, board_capacity=10.0, carrying_items=[], gps_update_time=0,
    )
    plans = {"v1": [Node("F1", [], [old_item])]}
    new_pair = [Node("F1", [], [new_item]), Node("F3", [new_item], [])]

    monkeypatch.setattr(config, "is_timeout", lambda: False)
    def reject_none_nodes(route, *args, **kwargs):
        assert all(node is not None for node in route)
        return 1.0
    monkeypatch.setattr(engine, "cost_of_a_route", reject_none_nodes)

    result = engine.dispatch_nodePair(new_pair, {"v1": vehicle}, plans, {})

    assert result[1] == ""



def test_deal_old_solution_uses_configured_worker_data_dir(monkeypatch, tmp_path):
    import datetime
    import os
    from types import SimpleNamespace
    import algorithm.engine as engine

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 29, 12, 0, 0)

    initial_time = int(FixedDateTime(2026, 9, 29, 0, 0, 0).timestamp())
    expected_path = os.path.join(str(tmp_path), "solution.json")
    removed_paths = []
    fake_os = SimpleNamespace(
        path=SimpleNamespace(
            join=os.path.join,
            exists=lambda path: path == expected_path,
        ),
        remove=removed_paths.append,
    )
    monkeypatch.setattr(engine, "datetime", FixedDateTime)
    monkeypatch.setattr(engine, "os", fake_os)
    monkeypatch.setattr(engine, "input_directory", str(tmp_path))

    engine.deal_old_solution_file({
        "V_1": SimpleNamespace(gps_update_time=initial_time + 600, des=None)
    })

    assert removed_paths == [expected_path]


def test_initial_population_stops_at_global_algorithm_deadline(monkeypatch):
    import algorithm.Test_algorithm.new_engine as new_engine

    calls = []
    class _FakeChromosome:
        def __init__(self, solution, *args):
            self.solution = solution
            self.fitness = 0.0

    node = SimpleNamespace()
    pairs = {
        0: {"v1,0": node, "v1,1": node},
        1: {"v1,2": node, "v1,3": node},
    }
    monkeypatch.setattr(config, "is_timeout", lambda: True)
    monkeypatch.setattr(new_engine, "Chromosome", _FakeChromosome)
    monkeypatch.setattr(
        new_engine,
        "disturbance_opt",
        lambda *args: calls.append(True) or object(),
    )

    population, pdg_map = new_engine.new_generate_random_chromosome(
        {}, {}, {}, pairs, {}, quantity=2
    )

    assert calls == []
    assert population is None
    assert pdg_map is None


def test_disturbance_opt_stops_before_copying_after_global_deadline(monkeypatch):
    import algorithm.Test_algorithm.new_LS as new_ls

    calls = []
    monkeypatch.setattr(config, "is_timeout", lambda: True)
    monkeypatch.setattr(
        new_ls,
        "get_UnongoingSuperNode",
        lambda *args: calls.append(True) or ({}, {}),
    )

    result = new_ls.disturbance_opt({}, {}, {}, relocate_rate=0.5)

    assert result is None
    assert calls == []



def test_epoch_log_records_nonfinite_fitness_as_unavailable(monkeypatch, tmp_path):
    import json
    import math
    import algorithm.epoch_plan_log as epoch_plan_log

    monkeypatch.setattr(epoch_plan_log, "_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(epoch_plan_log, "_STATE_FILE", str(tmp_path / "_run_state.json"))

    epoch_plan_log.append_epoch_solution(1, "0000-0010", math.inf, "[]")

    state = json.loads((tmp_path / "_run_state.json").read_text(encoding="utf-8"))
    log_path = tmp_path / ("epoch_plans_%s.jsonl" % state["run_id"])
    record = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert record["tc"] is None



def test_nonfinite_fitness_is_reported_as_unavailable_after_deadline(monkeypatch):
    import algorithm.main as algorithm_main

    monkeypatch.setattr(algorithm_main.Config, "is_timeout", lambda: True)

    assert algorithm_main._fitness_display(float("inf")) == (
        "unavailable (algorithm budget exhausted)"
    )



def test_log_rotation_ignores_file_removed_by_another_worker(monkeypatch, tmp_path):
    import os
    from src.utils import log_utils

    for name in ("a.log", "b.log", "c.log"):
        (tmp_path / name).write_text("log", encoding="utf-8")

    real_remove = os.remove

    def raced_remove(path):
        if os.path.basename(path) == "a.log":
            raise FileNotFoundError(path)
        real_remove(path)

    monkeypatch.setattr(log_utils.os, "remove", raced_remove)

    log_utils.delete_files(str(tmp_path), max_num=2)



def test_merge_node_keeps_pickup_before_same_factory_delivery():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    item = OrderItem(
        id="same-factory-1",
        order_id="same-factory",
        pickup_factory_id="F1",
        delivery_factory_id="F1",
        demand=1.0,
    )
    vehicle = SimpleNamespace(carrying_items=[], board_capacity=15.0)
    plans = {
        "V_1": [
            Node("F1", [], [item]),
            Node("F1", [item], []),
        ]
    }

    assert engine.isFeasible(plans["V_1"], vehicle.carrying_items, vehicle.board_capacity)

    engine.merge_node({"V_1": vehicle}, plans)

    assert len(plans["V_1"]) == 2
    assert engine.isFeasible(plans["V_1"], vehicle.carrying_items, vehicle.board_capacity)



def test_ensure_destination_prefix_removes_duplicate_committed_delivery():
    import algorithm.engine as engine
    from algorithm.Object import Node, OrderItem

    item = OrderItem(
        id="committed-delivery-1",
        order_id="committed-delivery",
        pickup_factory_id="F0",
        delivery_factory_id="F1",
        demand=1.0,
    )
    destination = Node("F1", [item], [])
    vehicle = SimpleNamespace(des=destination)
    plans = {
        "V_1": [
            Node("F1", [item], []),
            Node("F1", [item], []),
            Node("F2", [], []),
        ]
    }

    engine._ensure_destination_prefix(plans, {"V_1": vehicle})

    assert len(plans["V_1"]) == 2
    assert [entry.id for entry in plans["V_1"][0].delivery_item_list] == [item.id]
    assert plans["V_1"][1].id == "F2"


def test_output_plan_validation_includes_destination_and_returned_route():
    import pytest
    import algorithm.main as algorithm_main
    from algorithm.Object import Node, OrderItem

    item = OrderItem(
        id="duplicate-delivery-1",
        order_id="duplicate-delivery",
        pickup_factory_id="F0",
        delivery_factory_id="F1",
        demand=1.0,
    )
    destination = Node("F1", [item], [])
    vehicle = SimpleNamespace(
        des=destination,
        carrying_items=[item],
        board_capacity=15.0,
    )

    with pytest.raises(RuntimeError, match="FILO/capacity"):
        algorithm_main._assert_valid_output_plan(
            {"V_1": [Node("F1", [item], [])]},
            {"V_1": destination},
            {"V_1": vehicle},
            [],
            {"F1": object()},
        )
