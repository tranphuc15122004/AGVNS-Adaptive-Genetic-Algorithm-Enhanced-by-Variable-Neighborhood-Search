import copy
import math
import random
import time

from algorithm.Object import Chromosome, Factory, Node, OrderItem, Vehicle
from algorithm.engine import (
    _restore_canonical_route_after, cost_of_a_route, get_route_after,
    isFeasible, merge_node, repair_restored_lifo_routes, total_cost,
)
import algorithm.engine as engine
import algorithm.Test_algorithm.MOEAD_TS as moead_ts_operators
import algorithm.Test_algorithm.moead_core as moead_core
import algorithm.Test_algorithm.moead_objectives as moead_objectives
from algorithm.Test_algorithm.moead_core import (
    DispatchUnit,
    _insert_unit_best,
    build_neighborhoods,
    run_moead_ts,
    tabu_search,
    uniform_weights,
)
from algorithm.Test_algorithm.moead_objectives import (
    EvaluationContext,
    Objectives,
    canonicalize_solution,
    evaluate_solution,
    tchebycheff,
    validate_solution,
)
import algorithm.algorithm_config as config


def _fixture():
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(("A", "B", "C", "D"))
    }
    route_map = {
        (source, target): (1.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    vehicle.set_cur_position_info("A", 0, 0, 0)
    item = OrderItem(
        "I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 50, 1, 1, 1
    )
    return factories, route_map, {"V_1": vehicle}, item


def test_paper_weights_and_neighborhood():
    weights = uniform_weights(6)
    assert weights == [
        (0.0, 1.0), (0.2, 0.8), (0.4, 0.6),
        (0.6, 0.4), (0.8, 0.19999999999999996), (1.0, 0.0),
    ]
    neighborhoods = build_neighborhoods(weights, 2)
    assert len(neighborhoods) == 6
    assert all(len(neighborhood) == 2 for neighborhood in neighborhoods)
    assert all(index in neighborhood for index, neighborhood in enumerate(neighborhoods))


def test_tchebycheff_uses_separate_objectives():
    objectives = Objectives(10.0, 4.0)
    assert tchebycheff(objectives, (0.5, 0.5), (0.0, 0.0)) == 5.0
    assert objectives.tc == config.Delta * 10.0 + 4.0


def test_moead_ts_inserts_and_returns_complete_pair(monkeypatch):
    factories, route_map, vehicles, item = _fixture()
    monkeypatch.setattr(config, "MOEAD_MAX_GENERATIONS", 2)
    monkeypatch.setattr(config, "MOEAD_TS_MAX_ITERATIONS", 2)
    monkeypatch.setattr(config, "MOEAD_TS_TABU_LIST_SIZE", 4)
    config.set_begin_time()
    config.set_random_seed(0)

    result = run_moead_ts(
        {"V_1": []}, route_map, vehicles, factories,
        {item.id: item}, [item.id]
    )

    assert result is not None
    route = result.solution["V_1"]
    assert [(node.id, [x.id for x in node.pickup_item_list],
             [x.id for x in node.delivery_item_list]) for node in route] == [
        ("B", ["I-1"], []), ("C", [], ["I-1"])
    ]
    assert math.isfinite(result._moead_tc)
    assert result._moead_tc == evaluate_solution(result.solution, EvaluationContext(
        route_map, vehicles, factories, {item.id: item}
    )).tc
    assert math.isfinite(result.fitness)


def test_evaluator_averages_distance_over_all_vehicles():
    factories, route_map, vehicles, item = _fixture()
    second = Vehicle("V_2", "G_2", 24, 15, [])
    second.set_cur_position_info("A", 0, 0, 0)
    vehicles["V_2"] = second
    solution = {
        "V_1": [Node("B", [], [item]), Node("C", [item], [])],
        "V_2": [],
    }
    context = EvaluationContext(route_map, vehicles, factories, {item.id: item})
    objectives = evaluate_solution(solution, context)
    assert objectives.average_distance == 1.0


def test_evaluator_uses_the_shared_engine_for_f1_f2_and_total_cost():
    factories, route_map, vehicles, item = _fixture()
    solution = {
        "V_1": [Node("B", [], [item]), Node("C", [item], [])],
    }
    context = EvaluationContext(route_map, vehicles, factories, {item.id: item})
    objectives = evaluate_solution(solution, context)
    normalized = canonicalize_solution(solution, vehicles)
    vehicle = vehicles["V_1"]

    weighted_f1 = cost_of_a_route(
        normalized["V_1"], vehicle, vehicles, route_map, normalized,
        mode="overtime",
    )
    f2 = cost_of_a_route(
        normalized["V_1"], vehicle, vehicles, route_map, normalized,
        mode="distance",
    )
    f1, f2_from_total, scalar = total_cost(
        vehicles, route_map, normalized, mode="components",
    )

    # All three values must originate from the same full-fleet total-cost
    # evaluation. The per-route function is only a parity oracle here.
    assert f1 == weighted_f1 / config.Delta
    assert f2_from_total == f2
    assert objectives.tardiness == f1
    assert objectives.average_distance == f2_from_total
    assert objectives.tc == scalar
    assert scalar == total_cost(vehicles, route_map, normalized)


def test_evaluator_requests_all_components_from_one_total_cost_call(monkeypatch):
    factories, route_map, vehicles, item = _fixture()
    context = EvaluationContext(route_map, vehicles, factories, {item.id: item})
    calls = []

    def total_with_components(_vehicles, _route_map, _plan, mode="total"):
        calls.append(mode)
        return 12.0, 3.0, 36.0

    monkeypatch.setattr(moead_objectives, "total_cost", total_with_components)
    objectives = moead_objectives.evaluate_solution(
        {"V_1": [Node("B", [], [item]), Node("C", [item], [])]},
        context, validate=False,
    )

    assert calls == ["components"]
    assert objectives == Objectives(12.0, 3.0, 36.0)


def test_route_evaluator_delegates_to_one_full_total_cost_call(monkeypatch):
    factories, route_map, vehicles, item = _fixture()
    plan = {"V_1": [Node("B", [], [item]), Node("C", [item], [])]}
    calls = []

    def total_with_components(_vehicles, _route_map, _plan, mode="total"):
        calls.append(mode)
        return 5.0, 7.0, 17.0

    monkeypatch.setattr(engine, "total_cost", total_with_components)
    value = cost_of_a_route(
        plan["V_1"], vehicles["V_1"], vehicles, route_map, plan,
        mode="distance",
    )

    assert calls == ["components"]
    assert value == 7.0


def test_evaluator_matches_the_consecutive_factory_nodes_sent_to_simulator():
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(("A", "B", "C"))
    }
    route_map = {
        (source, target): (1.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    vehicle.set_cur_position_info("A", 0, 0, 0)
    first = OrderItem("I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 2500, 1, 1, 1)
    second = OrderItem("I-2", "PALLET", "O-2", 1.0, "B", "C", 0, 2500, 1, 1, 1)
    unmerged = {
        "V_1": [
            Node("B", [], [first]),
            Node("B", [], [second]),
            Node("C", [second, first], []),
        ]
    }
    merged = {
        "V_1": [
            Node("B", [], [first, second]),
            Node("C", [second, first], []),
        ]
    }
    context = EvaluationContext(route_map, {"V_1": vehicle}, factories,
                                {first.id: first, second.id: second})

    assert len(canonicalize_solution(unmerged)["V_1"]) == 2
    assert evaluate_solution(unmerged, context) == evaluate_solution(merged, context)


def test_locked_destination_does_not_bypass_capacity_or_lifo_validation():
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(("A", "B", "C", "D", "E", "F"))
    }
    route_map = {
        (source, target): (1.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    destination = Node("B", [], [])
    vehicle = Vehicle("V_1", "G_1", 24, 1, [], destination)
    vehicle.set_cur_position_info("A", 0, 0, 0)
    first = OrderItem("I-1", "PALLET", "O-1", 1.0, "C", "F", 0, 1000, 1, 1, 1)
    second = OrderItem("I-2", "PALLET", "O-2", 1.0, "D", "E", 0, 1000, 1, 1, 1)
    solution = {
        "V_1": [
            destination,
            Node("C", [], [first]),
            Node("D", [], [second]),
            Node("E", [second], []),
            Node("F", [first], []),
        ]
    }
    context = EvaluationContext(route_map, {"V_1": vehicle}, factories,
                                {first.id: first, second.id: second})

    assert not validate_solution(solution, context)


def test_ci_checks_the_true_best_position_beyond_the_old_scan_cap(monkeypatch):
    factories = {name: Factory(name, 0.0, 0.0, 6) for name in ("B", "C")}
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    vehicle.set_cur_position_info("B", 0, 0, 0)
    item = OrderItem("I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    context = EvaluationContext({}, {"V_1": vehicle}, factories, {item.id: item})
    base_plan = {"V_1": [Node("X{}".format(index), [], []) for index in range(21)]}
    unit = DispatchUnit((item.id,), (item,))

    def always_feasible(*_args):
        return True

    def position_score(plan, _context, validate=False):
        route = plan["V_1"]
        pickup_index = next(index for index, node in enumerate(route) if node.id == "B")
        delivery_index = next(index for index, node in enumerate(route) if node.id == "C")
        return Objectives(0.0, 0.0 if (pickup_index, delivery_index) == (18, 21) else 1.0)

    monkeypatch.setattr(moead_core, "isFeasible", always_feasible)
    monkeypatch.setattr(moead_core, "evaluate_solution", position_score)
    config.set_begin_time()
    result = _insert_unit_best(base_plan, unit, context, None, None,
                               time.time() + 1.0, use_tc=True)

    assert result is not None
    route = result["V_1"]
    assert next(index for index, node in enumerate(route) if node.id == "B") == 18
    assert next(index for index, node in enumerate(route) if node.id == "C") == 21


def test_couple_exchange_generates_a_feasible_intra_route_neighbor():
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(("A", "B", "C", "D", "E"))
    }
    route_map = {
        (source, target): (1.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    vehicle.set_cur_position_info("A", 0, 0, 0)
    first = OrderItem("I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    second = OrderItem("I-2", "PALLET", "O-2", 1.0, "D", "E", 0, 1000, 1, 1, 1)
    solution = {
        "V_1": [
            Node("B", [], [first]), Node("C", [first], []),
            Node("D", [], [second]), Node("E", [second], []),
        ]
    }
    chromosome = Chromosome(solution, route_map, {"V_1": vehicle})
    context = EvaluationContext(route_map, {"V_1": vehicle}, factories,
                                {first.id: first, second.id: second})
    previous_context = moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT
    moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = context
    random.seed(0)
    try:
        neighbors = moead_ts_operators.generate_pdg_exchange_neighbors(
            chromosome, 1, time.time() + 1.0, set()
        )
    finally:
        moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = previous_context

    assert len(neighbors) == 1
    pickup_ids = [
        node.pickup_item_list[0].id
        for node in neighbors[0].solution["V_1"]
        if node.pickup_item_list
    ]
    assert pickup_ids == ["I-2", "I-1"]


def _single_order_relocation_fixture():
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(("A", "B", "C", "D", "E"))
    }
    route_map = {
        (source, target): (10.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    route_map[("A", "B")] = (100.0, 100)
    route_map[("D", "B")] = (5.0, 5)
    route_map[("E", "B")] = (1.0, 1)
    route_map[("B", "C")] = (1.0, 1)

    vehicles = {}
    for vehicle_id, factory_id in (
            ("V_1", "A"), ("V_2", "D"), ("V_3", "E")):
        vehicle = Vehicle(vehicle_id, "G_" + vehicle_id, 24, 15, [])
        vehicle.set_cur_position_info(factory_id, 0, 0, 0)
        vehicles[vehicle_id] = vehicle

    item = OrderItem(
        "I-1", "PALLET", "O-1", 1.0, "B", "C",
        0, 100000, 1, 1, 1,
    )
    solution = {
        "V_1": [Node("B", [], [item]), Node("C", [item], [])],
        "V_2": [],
        "V_3": [],
    }
    context = EvaluationContext(
        route_map, vehicles, factories, {item.id: item}
    )
    return Chromosome(solution, route_map, vehicles), context


def test_relocate_operators_return_the_best_move_from_the_full_neighborhood():
    chromosome, context = _single_order_relocation_fixture()
    previous_context = moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT
    moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = context
    try:
        for generator in (
                moead_ts_operators.generate_pdg_relocate_neighbors,
                moead_ts_operators.generate_block_relocate_neighbors):
            neighbors = generator(
                chromosome, 1, time.time() + 1.0, set()
            )
            assert len(neighbors) == 1
            assert not neighbors[0].solution["V_1"]
            assert not neighbors[0].solution["V_2"]
            assert [node.id for node in neighbors[0].solution["V_3"]] == [
                "B", "C"
            ]
    finally:
        moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = previous_context


def test_exchange_operators_return_the_best_pair_from_the_full_neighborhood():
    factory_ids = ("A", "B", "C", "D", "E", "F", "G")
    factories = {
        name: Factory(name, float(index), 0.0, 6)
        for index, name in enumerate(factory_ids)
    }
    route_map = {
        (source, target): (50.0, 10)
        for source in factories
        for target in factories
        if source != target
    }
    desired_route = ("F", "G", "D", "E", "B", "C")
    for source, target in zip(("A",) + desired_route, desired_route):
        route_map[(source, target)] = (1.0, 1)

    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    vehicle.set_cur_position_info("A", 0, 0, 0)
    items = [
        OrderItem(
            "I-{}".format(index), "PALLET", "O-{}".format(index),
            1.0, pickup, delivery, 0, 100000, 1, 1, 1,
        )
        for index, (pickup, delivery) in enumerate(
            (("B", "C"), ("D", "E"), ("F", "G")), start=1
        )
    ]
    solution = {
        "V_1": [
            node
            for item in items
            for node in (
                Node(item.pickup_factory_id, [], [item]),
                Node(item.delivery_factory_id, [item], []),
            )
        ]
    }
    chromosome = Chromosome(solution, route_map, {"V_1": vehicle})
    context = EvaluationContext(
        route_map, {"V_1": vehicle}, factories,
        {item.id: item for item in items},
    )
    previous_context = moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT
    moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = context
    try:
        for generator in (
                moead_ts_operators.generate_pdg_exchange_neighbors,
                moead_ts_operators.generate_block_exchange_neighbors):
            neighbors = generator(
                chromosome, 1, time.time() + 1.0, set()
            )
            assert len(neighbors) == 1
            assert tuple(
                node.id for node in neighbors[0].solution["V_1"]
            ) == desired_route
    finally:
        moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = previous_context


def test_tabu_search_samples_single_moves_from_all_four_operators(monkeypatch):
    chromosome, context = _single_order_relocation_fixture()
    monkeypatch.setattr(config, "MOEAD_TS_MAX_ITERATIONS", 1)
    monkeypatch.setattr(config, "MOEAD_TS_NEIGHBOR_THRESHOLD", 4)
    calls = []
    operator_names = (
        "pdg_exchange", "block_exchange", "pdg_relocate", "block_relocate",
    )

    def make_sampler(name):
        def sampler(current, deadline):
            calls.append(name)
            return None
        return sampler

    for name in operator_names:
        monkeypatch.setattr(
            moead_ts_operators,
            "sample_{}_move".format(name),
            make_sampler(name),
        )
    selected_operators = iter(operator_names)
    monkeypatch.setattr(
        moead_core.random, "choice", lambda _operators: next(selected_operators)
    )
    config.set_begin_time()

    result = tabu_search(chromosome, context, time.time() + 1.0)

    assert calls == list(operator_names)
    assert get_route_after(result.solution, {}) == get_route_after(chromosome.solution, {})


def test_tabu_search_tabus_the_applied_move(monkeypatch):
    chromosome, context = _single_order_relocation_fixture()
    monkeypatch.setattr(config, "MOEAD_TS_MAX_ITERATIONS", 2)
    monkeypatch.setattr(config, "MOEAD_TS_NEIGHBOR_THRESHOLD", 1)
    monkeypatch.setattr(config, "MOEAD_TS_TABU_LIST_SIZE", 4)

    item = chromosome.solution["V_1"][0].pickup_item_list[0]

    def improving_relocate(current, deadline):
        plan = copy.deepcopy(current.solution)
        plan["V_1"] = []
        plan["V_2"] = []
        plan["V_3"] = [
            Node("B", [], [item]), Node("C", [item], []),
        ]
        candidate = Chromosome(plan, current.route_map, current.id_to_vehicle)
        return candidate, ("pdg_relocate", ("I-1",), "V_3", 0, 1)

    monkeypatch.setattr(
        moead_ts_operators, "sample_pdg_relocate_move", improving_relocate
    )
    monkeypatch.setattr(
        moead_core.random, "choice",
        lambda _operators: "pdg_relocate",
    )
    config.set_begin_time()

    result = tabu_search(chromosome, context, time.time() + 1.0)

    # First outer iteration applies the sampled relocate; the move key is
    # tabued so the second iteration cannot re-apply the same move.
    assert result.solution["V_1"] == []
    assert [node.id for node in result.solution["V_3"]] == ["B", "C"]
    assert result._moead_tc < chromosome.fitness


def test_archive_round_trip_preserves_cross_order_lifo_sequence():
    factories = {name: Factory(name, 0.0, 0.0, 6) for name in ("B", "C")}
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    first = OrderItem("100-1", "PALLET", "100", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    second = OrderItem("200-1", "PALLET", "200", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    plan = {
        "V_1": [
            Node("B", [], [first, second]),
            Node("C", [second, first], []),
        ]
    }
    assert isFeasible(plan["V_1"], [], 15)

    archive = get_route_after(plan, {})
    restored = {"V_1": []}
    assert _restore_canonical_route_after(
        archive, restored, factories, {first.id: first, second.id: second}, [], []
    )
    assert [item.id for item in restored["V_1"][0].pickup_item_list] == [
        "100-1", "200-1"
    ]
    assert [item.id for item in restored["V_1"][1].delivery_item_list] == [
        "200-1", "100-1"
    ]
    assert isFeasible(restored["V_1"], [], 15)


def test_legacy_sorted_delivery_archive_is_repaired_from_the_stack():
    first = OrderItem("100-1", "PALLET", "100", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    second = OrderItem("200-1", "PALLET", "200", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    plan = {
        "V_1": [
            Node("B", [], [first, second]),
            Node("C", [first, second], []),
        ]
    }
    assert not isFeasible(plan["V_1"], [], 15)
    assert repair_restored_lifo_routes(plan, {"V_1": vehicle})
    assert [item.id for item in plan["V_1"][1].delivery_item_list] == [
        "200-1", "100-1"
    ]
    assert isFeasible(plan["V_1"], [], 15)


def test_destination_actions_are_immutable_and_same_factory_work_is_separate():
    factories = {name: Factory(name, 0.0, 0.0, 6) for name in ("A", "B", "C")}
    route_map = {(a, b): (1.0, 1) for a in factories for b in factories if a != b}
    committed = OrderItem("I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    extra = OrderItem("I-2", "PALLET", "O-2", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    destination = Node("B", [], [committed], 20, 0)
    vehicle = Vehicle("V_1", "G_1", 24, 15, [], destination)
    vehicle.set_cur_position_info("A", 0, 0, 0)
    context = EvaluationContext(
        route_map, {"V_1": vehicle}, factories,
        {committed.id: committed, extra.id: extra},
    )
    changed_destination = {
        "V_1": [Node("B", [], [extra]), Node("C", [extra], [])]
    }
    assert not validate_solution(changed_destination, context)

    plan = {
        "V_1": [
            Node("B", [], [extra]), Node("C", [extra], []),
            Node("C", [committed], []),
        ]
    }
    moead_core._ensure_destination_prefix(plan, {"V_1": vehicle})
    assert [item.id for item in plan["V_1"][0].pickup_item_list] == ["I-1"]
    assert [item.id for item in plan["V_1"][1].pickup_item_list] == ["I-2"]
    merge_node({"V_1": vehicle}, plan)
    assert len(plan["V_1"]) == 3
    assert validate_solution(plan, context)


def test_no_new_order_returns_a_validated_restored_candidate():
    factories, route_map, vehicles, item = _fixture()
    plan = {"V_1": [Node("B", [], [item]), Node("C", [item], [])]}
    config.set_begin_time()
    result = run_moead_ts(plan, route_map, vehicles, factories, {}, [])
    assert result is not None
    assert validate_solution(result.solution, result._moead_context)


def test_combined_node_is_expanded_before_local_search_and_can_move():
    factories = {name: Factory(name, 0.0, 0.0, 6) for name in ("A", "B", "C", "D")}
    route_map = {(a, b): (1.0, 1) for a in factories for b in factories if a != b}
    first = OrderItem("I-1", "PALLET", "O-1", 1.0, "B", "C", 0, 1000, 1, 1, 1)
    second = OrderItem("I-2", "PALLET", "O-2", 1.0, "C", "D", 0, 1000, 1, 1, 1)
    first_vehicle = Vehicle("V_1", "G_1", 24, 15, [])
    first_vehicle.set_cur_position_info("A", 0, 0, 0)
    second_vehicle = Vehicle("V_2", "G_2", 24, 15, [])
    second_vehicle.set_cur_position_info("A", 0, 0, 0)
    vehicles = {"V_1": first_vehicle, "V_2": second_vehicle}
    solution = {
        "V_1": [
            Node("B", [], [first]), Node("C", [first], [second]),
            Node("D", [second], []),
        ],
        "V_2": [],
    }
    context = EvaluationContext(
        route_map, vehicles, factories, {first.id: first, second.id: second}
    )
    assert validate_solution(solution, context)
    moead_core._expand_plan_for_local_search(solution, vehicles)
    assert all(not (node.pickup_item_list and node.delivery_item_list)
               for node in solution["V_1"])
    chromosome = Chromosome(solution, route_map, vehicles)
    previous_context = moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT
    moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = context
    config.set_begin_time()
    try:
        neighbors = moead_ts_operators.generate_pdg_relocate_neighbors(
            chromosome, 1, time.time() + 1.0, set()
        )
    finally:
        moead_ts_operators._ACTIVE_OBJECTIVE_CONTEXT = previous_context
    assert neighbors
    assert all(validate_solution(neighbor.solution, context) for neighbor in neighbors)


def test_safe_fallback_prevents_empty_population_failure(monkeypatch):
    factories, route_map, vehicles, item = _fixture()
    monkeypatch.setattr(config, "MOEAD_MAX_GENERATIONS", 0)
    monkeypatch.setattr(moead_core, "initialize_population", lambda *_args: [])
    config.set_begin_time()
    result = run_moead_ts(
        {"V_1": []}, route_map, vehicles, factories, {item.id: item}, [item.id]
    )
    assert result is not None
    assert validate_solution(result.solution, result._moead_context)
