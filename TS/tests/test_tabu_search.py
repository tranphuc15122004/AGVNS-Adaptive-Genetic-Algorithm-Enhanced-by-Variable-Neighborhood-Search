"""Focused unit tests for solution-based Tabu Search.

Run from ``TS`` with ``python3 -m unittest tests.test_tabu_search``.
"""

import copy
import hashlib
import json
import random
import time
import unittest
from collections import deque
from pathlib import Path

import algorithm.algorithm_config as config
from algorithm.In_and_Out import Input
from algorithm.engine import (
    _restore_canonical_route_after,
    get_route_after,
    isFeasible,
    restore_scene_with_single_node,
)
from algorithm.Object import Chromosome, Node
from algorithm.Test_algorithm import new_LS, tabu_search
from algorithm.Test_algorithm.new_LS import (
    new_block_exchange,
    new_block_relocate,
    new_inter_couple_exchange,
    new_multi_pd_group_relocate,
    new_two_opt,
)
from algorithm.Test_algorithm.new_engine import worse_dispatch_new_orders
from algorithm.Test_algorithm.tabu_search import (
    _changed_vehicle_ids,
    _ensure_destination_prefix,
    _has_destination_prefix,
    _is_feasible_solution,
    _solution_coverage,
    add_tabu_signature,
    generate_block_relocate_neighbors,
    generate_neighbors,
    generate_pdg_relocate_neighbors,
    select_admissible_solution,
    solution_signature,
)
from src.conf.configs import Configs


class _Candidate:
    def __init__(self, solution, fitness):
        self.solution = solution
        self.fitness = fitness


class TabuMemoryTests(unittest.TestCase):
    def test_seed_configuration_restarts_random_stream(self):
        config.set_random_seed(19)
        first = [random.random() for _ in range(4)]
        config.set_random_seed(19)
        second = [random.random() for _ in range(4)]
        self.assertEqual(first, second)

    def test_fifo_memory_evicts_the_oldest_solution_signature(self):
        first, second, third = b"first", b"second", b"third"
        fifo = deque()
        tabu_signatures = set()

        add_tabu_signature(first, fifo, tabu_signatures, 2)
        add_tabu_signature(second, fifo, tabu_signatures, 2)
        add_tabu_signature(third, fifo, tabu_signatures, 2)

        self.assertEqual(list(fifo), [second, third])
        self.assertNotIn(first, tabu_signatures)
        self.assertEqual(tabu_signatures, {second, third})

    def test_classical_tabu_has_no_diversification_phase(self):
        self.assertFalse(hasattr(tabu_search, "_diversify"))


class SolutionSelectionTests(unittest.TestCase):
    @staticmethod
    def _solution(label):
        node = type("Node", (), {
            "id": label,
            "pickup_item_list": [],
            "delivery_item_list": [],
        })()
        return {"V_1": [node]}

    def test_signature_is_stable_and_route_sensitive(self):
        first = {"V_2": self._solution("F_2")["V_1"],
                 "V_1": self._solution("F_1")["V_1"]}
        same_routes_different_mapping_order = {"V_1": first["V_1"],
                                               "V_2": first["V_2"]}
        different = self._solution("F_2")

        self.assertEqual(solution_signature(first),
                         solution_signature(same_routes_different_mapping_order))
        self.assertNotEqual(solution_signature(first), solution_signature(different))

    def test_canonical_route_after_and_tabu_digest_include_all_route_data(self):
        def node(factory_id, pickup_ids, delivery_ids):
            return type("Node", (), {
                "id": factory_id,
                "pickup_item_list": [type("Item", (), {"id": item_id})()
                                     for item_id in pickup_ids],
                "delivery_item_list": [type("Item", (), {"id": item_id})()
                                      for item_id in delivery_ids],
            })()

        solution = {
            "V_100": [node(
                "F_100", ["p-10", "p-2", "p-1"], ["d-2", "d-1", "d-10"],
            )],
            "V_2": [node("F_2", ["p-3"], []), node("F_3", [], ["d-3"])],
            "V_1": [],
        }

        route_after = get_route_after(solution, {})
        self.assertEqual(json.loads(route_after), [
            ["V_1", []],
            ["V_2", [["F_2", ["p-3"], []], ["F_3", [], ["d-3"]]]],
            ["V_100", [["F_100", ["p-1", "p-2", "p-10"],
                        ["d-10", "d-2", "d-1"]]]],
        ])
        self.assertEqual(
            solution_signature(solution),
            hashlib.blake2b(route_after.encode("utf-8"), digest_size=16).digest(),
        )

    def test_canonical_route_after_round_trips_through_restore(self):
        factory = type("Factory", (), {"lng": 106.0, "lat": 10.0})()
        pickup = type("Item", (), {"id": "p-1"})()
        delivery = type("Item", (), {"id": "d-1"})()
        source = {
            "V_1": [],
            "V_2": [Node("F_2", [delivery], [pickup], None, None, 106.0, 10.0)],
        }
        serialized = get_route_after(source, {})
        restored = {"V_1": [], "V_2": []}

        self.assertTrue(_restore_canonical_route_after(
            serialized,
            restored,
            {"F_2": factory},
            {"p-1": pickup, "d-1": delivery},
            [],
            [],
        ))
        self.assertEqual(get_route_after(restored, {}), serialized)

    def test_restored_multi_item_delivery_keeps_filo_order(self):
        factory = type("Factory", (), {"lng": 106.0, "lat": 10.0})()
        first = type("Item", (), {"id": "order-1", "demand": 1.0})()
        second = type("Item", (), {"id": "order-2", "demand": 1.0})()
        source = {
            "V_1": [
                Node("F_pick", [], [first, second], None, None, 106.0, 10.0),
                Node("F_delivery", [second, first], [], None, None, 106.0, 10.0),
            ],
        }
        restored = {"V_1": []}

        self.assertTrue(_restore_canonical_route_after(
            get_route_after(source, {}),
            restored,
            {"F_pick": factory, "F_delivery": factory},
            {"order-1": first, "order-2": second},
            [],
            [],
        ))
        self.assertTrue(isFeasible(restored["V_1"], [], 10.0))

    def test_selection_uses_lowest_cost_non_tabu_solution(self):
        expensive = _Candidate(self._solution("F_1"), 20.0)
        best = _Candidate(self._solution("F_2"), 10.0)

        chosen, _, rejected, aspirations = select_admissible_solution(
            [expensive, best], set(), 5.0
        )

        self.assertIs(chosen, best)
        self.assertEqual(rejected, 0)
        self.assertEqual(aspirations, 0)

    def test_selection_accepts_a_worsening_non_tabu_solution(self):
        worse_than_current = _Candidate(self._solution("F_1"), 12.0)
        even_worse = _Candidate(self._solution("F_2"), 18.0)

        chosen, _, rejected, aspirations = select_admissible_solution(
            [even_worse, worse_than_current], set(), 10.0
        )

        self.assertIs(chosen, worse_than_current)
        self.assertEqual(rejected, 0)
        self.assertEqual(aspirations, 0)

    def test_aspiration_allows_tabu_solution_only_for_new_global_best(self):
        tabu_candidate = _Candidate(self._solution("F_1"), 4.0)
        ordinary = _Candidate(self._solution("F_2"), 6.0)
        tabu = {solution_signature(tabu_candidate.solution)}

        chosen, _, rejected, aspirations = select_admissible_solution(
            [ordinary, tabu_candidate], tabu, 5.0
        )

        self.assertIs(chosen, tabu_candidate)
        self.assertEqual(rejected, 0)
        self.assertEqual(aspirations, 1)

    def test_non_improving_tabu_solution_is_rejected(self):
        tabu_candidate = _Candidate(self._solution("F_1"), 5.0)
        ordinary = _Candidate(self._solution("F_2"), 6.0)
        tabu = {solution_signature(tabu_candidate.solution)}

        chosen, _, rejected, aspirations = select_admissible_solution(
            [tabu_candidate, ordinary], tabu, 5.0
        )

        self.assertIs(chosen, ordinary)
        self.assertEqual(rejected, 1)
        self.assertEqual(aspirations, 0)


class LocalSearchNeighborTests(unittest.TestCase):
    def setUp(self):
        self.original_data_dir = Configs.algorithm_data_interaction_folder_path
        self.original_begin_time = config.BEGIN_TIME
        config.set_random_seed(0)
        config.set_begin_time()
        fixture = Path(__file__).resolve().parents[1] / "algorithm" / "data_interaction_runs" / "test_tabu"
        Configs.configure_algorithm_data_dir(str(fixture))
        (self.factories, self.route_map, self.vehicles, self.unlocated,
         ongoing, all_orders) = Input()
        self.plan = {}
        new_items = restore_scene_with_single_node(
            self.plan, ongoing, self.unlocated, self.vehicles,
            self.factories, all_orders,
        )
        worse_dispatch_new_orders(
            self.plan, self.factories, self.route_map, self.vehicles,
            self.unlocated, [item for item in new_items if item],
        )
        self.current = Chromosome(self.plan, self.route_map, self.vehicles)

    def tearDown(self):
        Configs.configure_algorithm_data_dir(self.original_data_dir)
        config.BEGIN_TIME = self.original_begin_time

    def test_public_ls_use_in_place_bool_contract(self):
        operators = (
            new_multi_pd_group_relocate,
            new_inter_couple_exchange,
            new_block_relocate,
            new_block_exchange,
            new_two_opt,
        )
        for operator in operators:
            candidate = copy.deepcopy(self.plan)
            result = operator(candidate, self.vehicles, self.route_map, 0.2,
                              is_limited=True)
            self.assertIsInstance(result, bool)

    def test_generate_neighbors_keeps_source_unchanged_and_feasible(self):
        before = solution_signature(self.current.solution)
        neighbors = generate_neighbors(self.current, 0.2)

        self.assertEqual(solution_signature(self.current.solution), before)
        self.assertLessEqual(len(neighbors), config.TS_NEIGHBORS_PER_OPERATOR * 5)
        self.assertEqual(len({solution_signature(candidate.solution)
                              for candidate in neighbors}), len(neighbors))
        for candidate in neighbors:
            self.assertNotEqual(solution_signature(candidate.solution), before)
            self.assertEqual(_solution_coverage(candidate.solution),
                             _solution_coverage(self.current.solution))
            self.assertTrue(_is_feasible_solution(
                candidate, _changed_vehicle_ids(self.current.solution, candidate.solution)
            ))

    def test_destination_prefix_is_materialized_for_an_empty_dynamic_route(self):
        plan = {"V_1": []}
        vehicle = copy.deepcopy(self.vehicles["V_1"])
        vehicle.des = Node("fixed_destination", [], [], None, None)

        _ensure_destination_prefix(plan, {"V_1": vehicle})

        self.assertTrue(_has_destination_prefix(plan, {"V_1": vehicle}))
        self.assertEqual(plan["V_1"][0].id, "fixed_destination")

    def test_relocators_skip_a_missing_destination_prefix_without_crashing(self):
        plan = copy.deepcopy(self.plan)
        vehicles = copy.deepcopy(self.vehicles)
        source_id = next(vehicle_id for vehicle_id, route in plan.items() if route)
        target_id = next(vehicle_id for vehicle_id, route in plan.items()
                         if not route and vehicle_id != source_id)
        vehicles[target_id].des = Node("fixed_destination", [], [], None, None)
        current = Chromosome(plan, self.route_map, vehicles)
        before = solution_signature(current.solution)

        for generator in (generate_pdg_relocate_neighbors,
                          generate_block_relocate_neighbors):
            neighbors = generator(current, 4, time.time() + 1.0, set())
            self.assertTrue(all(
                target_id not in _changed_vehicle_ids(
                    current.solution, candidate.solution
                )
                for candidate in neighbors
            ))
            self.assertEqual(solution_signature(current.solution), before)

    def test_move_candidate_layer_has_been_removed(self):
        self.assertFalse(hasattr(new_LS, "NeighborhoodMove"))
        self.assertFalse(hasattr(new_LS, "_ts_collect_pdg_relocate"))


if __name__ == "__main__":
    unittest.main()
