import os
import tempfile
import unittest
from unittest.mock import patch

import torch

from algorithm.Object import Factory, Node, OrderItem, Vehicle
from algorithm.evorl.atomic import chunk_items, mutable_item_ids
from algorithm.evorl.cost import CostBreakdown, projected_cost
from algorithm.evorl.dto import EpochState, ItemState, RouteNode, VehicleState
from algorithm.evorl.planner import TransactionalPlanner
from algorithm.evorl.validator import SolutionValidator
from training.session import AlgorithmSessionState, HiddenStateSidecar
from training.observation import ObservationBuilder
from training.runtime import RuntimeParity
from training.env import TrainingDPDPEnv
from algorithm.evorl.legacy_adapter import build_epoch_state
from algorithm.engine import merge_node
from training.synthetic import SyntheticConfig, SyntheticDPDPEpisode
from training.ga import FleetGenome, GAConfig, PaperEvolutionaryTeacher
from training.evorl_trainer import EvoRLTrainer
from training.rppo import RPPOPolicy
from training.reproduction import load_assumptions, split_instances, validate_training_instances
from training.reproduction import validate_checkpoint_manifest
from training.reward import compose_reward
from training.official_parity import _node_snapshot
from algorithm.evorl.dispatch import _allow_defer
from training.evaluate import _trace_diagnostics
from src.common.stack import Stack
from src.common.dispatch_result import DispatchResult
from src.common.order import Order
from src.common.node import Node as OfficialNode
from src.utils.checker import Checker


def item(item_id, order_id="O-1", demand=1, pickup="F1", delivery="F2", deadline=100):
    return OrderItem(item_id, "PALLET", order_id, demand, pickup, delivery, 0, deadline, 1, 1)


class EvoRLDomainTests(unittest.TestCase):
    def test_atomic_chunking_is_stable_and_exact(self):
        values = [item("O-1-2", demand=8), item("O-1-1", demand=7), item("O-1-3", demand=1)]
        chunks = chunk_items(values, capacity=15)
        self.assertEqual([chunk.item_ids for chunk in chunks], [("O-1-1", "O-1-2"), ("O-1-3",)])
        self.assertEqual(set(x for chunk in chunks for x in chunk.item_ids), {"O-1-1", "O-1-2", "O-1-3"})

    def test_validator_accepts_lifo_route_and_rejects_factory_mismatch(self):
        values = {x.id: x for x in [item("O-1-1"), item("O-1-2")]}
        routes = {"V_1": [RouteNode("F1", ("O-1-1", "O-1-2")), RouteNode("F2", (), ("O-1-2", "O-1-1"))]}
        vehicle = Vehicle("V_1", "gps", 24, 15, [])
        report = SolutionValidator().validate(routes, {"V_1": vehicle}, values, expected_item_ids=values)
        self.assertTrue(report.valid, report.errors)
        bad = {"V_1": [RouteNode("F9", ("O-1-1",), ())]}
        self.assertFalse(SolutionValidator().validate(bad, {"V_1": vehicle}, values).valid)

    def test_projected_cost_counts_multi_item_order_once(self):
        values = {x.id: x for x in [item("O-1-1", deadline=0), item("O-1-2", deadline=0)]}
        routes = {"V_1": [RouteNode("F1", ("O-1-1", "O-1-2")), RouteNode("F2", (), ("O-1-2", "O-1-1"))]}
        vehicle = Vehicle("V_1", "gps", 24, 15, [])
        vehicle.cur_factory_id = "F1"
        cost = projected_cost(routes, {"V_1": vehicle}, {("F1", "F2"): (10, 10)}, values)
        self.assertAlmostEqual(cost.distance, 10.0)
        # One order-level penalty, not one penalty per item.
        self.assertEqual(cost.overtime_seconds, 13.0)

    def test_projected_cost_reads_canonical_current_and_carrying_fields(self):
        values = {"O-1-1": ItemState("O-1-1", "PALLET", "O-1", 1.0, "F1", "F2", committed_completion_time=0)}
        vehicle = VehicleState("V_1", 15, "F1", carrying_item_ids=(), planned_route=(RouteNode("F2", (), ("O-1-1",)),))
        cost = projected_cost(
            {"V_1": vehicle.planned_route}, {"V_1": vehicle},
            {("F1", "F2"): (10.0, 10.0)}, values,
        )
        self.assertEqual(cost.distance, 10.0)

    def test_projected_cost_includes_committed_destination_once(self):
        value = ItemState("O-1-1", "PALLET", "O-1", 1.0, "F2", "F3", committed_completion_time=100)
        destination = RouteNode("F2")
        vehicle = VehicleState(
            "V_1", 15, "F1", destination=destination,
            planned_route=(RouteNode("F3", (), ("O-1-1",)),),
        )
        cost = projected_cost(
            {"V_1": vehicle.planned_route}, {"V_1": vehicle},
            {("F1", "F2"): (5.0, 5.0), ("F2", "F3"): (7.0, 7.0)},
            {value.id: value},
        )
        self.assertEqual(cost.distance, 12.0)

    def test_terminal_reward_replaces_projected_suffix(self):
        before = CostBreakdown(benchmark_cost=100.0)
        after = CostBreakdown(benchmark_cost=10.0)
        reward = compose_reward(before, after, terminal=True, terminal_score=40.0)
        self.assertEqual(reward.intrinsic, 60.0)
        self.assertEqual(reward.final, 0.0)
        self.assertEqual(reward.total, 60.0)
        self.assertEqual(reward.terminal_score, 40.0)

    def test_deadline_equality_has_zero_overtime(self):
        value = item("O-1-1", deadline=11)
        vehicle = Vehicle("V_1", "gps", 24, 15, [])
        vehicle.cur_factory_id = "F1"
        cost = projected_cost(
            {"V_1": [RouteNode("F1", (value.id,)), RouteNode("F2", (), (value.id,))]},
            {"V_1": vehicle}, {("F1", "F2"): (10.0, 10.0)}, {value.id: value},
        )
        self.assertEqual(cost.overtime_seconds, 0.0)

    def test_planner_is_transactional(self):
        values = {"O-1-1": item("O-1-1")}
        state = EpochState(
            0, 0, values,
            {"V_1": VehicleState("V_1", 15, "F1")},
            route_map={("F1", "F2"): (10, 10)},
        )
        result = TransactionalPlanner().probe(state, chunk_items(values.values())[0])
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(state.vehicles["V_1"].planned_route, ())
        updated = TransactionalPlanner().apply(state, result)
        self.assertEqual(len(updated.vehicles["V_1"].planned_route), 2)

    def test_common_decoder_merges_adjacent_mutable_factory_nodes(self):
        route = TransactionalPlanner._canonicalize_route((
            RouteNode("F2", (), ("old",)),
            RouteNode("F2", ("new",), ()),
        ))
        self.assertEqual(len(route), 1)
        self.assertEqual(route[0].factory_id, "F2")
        self.assertEqual(route[0].pickup_item_ids, ("new",))
        self.assertEqual(route[0].delivery_item_ids, ("old",))

    def test_same_factory_pickup_delivery_keeps_operation_order(self):
        values = {"O-1-1": item("O-1-1", pickup="F2", delivery="F2")}
        state = EpochState(
            0, 0, values,
            {"V_1": VehicleState("V_1", 15, "F1")},
            route_map={("F1", "F2"): (10, 10), ("F2", "F2"): (0, 0)},
        )
        result = TransactionalPlanner().probe(state, chunk_items(values.values())[0])
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(len(result.route), 2)
        self.assertEqual(result.route[0].pickup_item_ids, ("O-1-1",))
        self.assertEqual(result.route[1].delivery_item_ids, ("O-1-1",))

    def test_mutable_ids_include_unplanned_items(self):
        values = [item("O-1-1"), item("O-1-2")]
        vehicle = Vehicle("V_1", "gps", 24, 15, [values[0]])
        vehicle.cur_factory_id = "F1"
        self.assertEqual(mutable_item_ids([x.id for x in values], {"V_1": vehicle}, {"V_1": []}), ["O-1-2"])

    def test_sidecar_resets_for_mismatched_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            sidecar = HiddenStateSidecar(os.path.join(directory, "hidden.json"))
            session = AlgorithmSessionState("episode-a", "model-a", epoch=2, current_time=1200)
            sidecar.save(session, [0], [1])
            self.assertEqual(sidecar.load(episode_id="episode-a", model_fingerprint="model-a"), [1])
            self.assertIsNone(sidecar.load(episode_id="episode-b", model_fingerprint="model-a"))

    def test_sidecar_retry_restores_pre_step_hidden_state(self):
        with tempfile.TemporaryDirectory() as directory:
            sidecar = HiddenStateSidecar(os.path.join(directory, "hidden.json"))
            session = AlgorithmSessionState("episode-a", "model-a", epoch=4, current_time=2400)
            session.metadata["input_route_hash"] = "route-a"
            sidecar.save(session, [1, 2], [3, 4])
            self.assertEqual(
                sidecar.load(
                    episode_id="episode-a", model_fingerprint="model-a",
                    epoch=4, current_time=2400, retry=True,
                    route_hash="route-a",
                ),
                [1, 2],
            )
            self.assertIsNone(sidecar.load(
                episode_id="episode-a", model_fingerprint="model-a",
                epoch=4, current_time=2400, retry=True, route_hash="route-b",
            ))
            self.assertEqual(
                sidecar.load(
                    episode_id="episode-a", model_fingerprint="model-a",
                    epoch=5, current_time=3000,
                ),
                [3, 4],
            )

    def test_observation_has_shared_masked_candidate_space(self):
        values = {"O-1-1": item("O-1-1")}
        state = EpochState(
            0, 0, values,
            {"V_2": VehicleState("V_2", 15, "F1"), "V_1": VehicleState("V_1", 15, "F1")},
            route_map={("F1", "F2"): (10, 10)},
        )
        observation = ObservationBuilder().build(state, chunk_items(values.values())[0])
        self.assertEqual([action.vehicle_id for action in observation.actions], ["V_1", "V_2"])
        self.assertEqual(len(observation.features[0]), ObservationBuilder.feature_dim)
        self.assertEqual(observation.mask, (True, True))

    def test_policy_logits_are_vehicle_permutation_equivariant(self):
        policy = RPPOPolicy(ObservationBuilder.feature_dim, recurrent=False)
        features = torch.randn(1, 2, ObservationBuilder.feature_dim)
        mask = torch.tensor([[True, True]])
        with torch.no_grad():
            logits, _, _ = policy(features, mask)
            swapped, _, _ = policy(features[:, [1, 0]], mask[:, [1, 0]])
        self.assertTrue(torch.allclose(logits[:, [1, 0]], swapped, atol=1e-6))

    def test_runtime_parity_reports_epoch_mismatch(self):
        parity = RuntimeParity(
            lambda state, action: {"state": state + action, "route_snapshot": state + action},
            lambda state, action: {"state": state + action, "route_snapshot": state + action + 1},
        )
        result = parity.compare(0, [1, 1])
        self.assertFalse(result.equal)
        self.assertEqual(result.differing_epochs, (0, 1))

    def test_runtime_parity_compares_official_trace_fields(self):
        left = [{"epoch": 0, "current_time": 600, "route_hash": "a", "checker_precondition": True}]
        right = [{"epoch": 0, "current_time": 600, "route_hash": "b", "checker_precondition": True}]
        result = RuntimeParity.compare_traces(left, right)
        self.assertFalse(result.equal)
        self.assertEqual(result.differing_epochs, (0,))
        self.assertIn("route_hash", result.details["0"]["fields"])

    def test_official_parity_snapshot_preserves_legacy_node_items(self):
        class LegacyNode:
            id = "F2"
            pickup_items = [item("O-1-1")]
            delivery_items = []

        snapshot = _node_snapshot(LegacyNode())
        self.assertEqual(snapshot["factory_id"], "F2")
        self.assertEqual(snapshot["pickup_item_ids"], ("O-1-1",))

    def test_synthetic_episode_is_seeded_and_releases_orders_dynamically(self):
        config = SyntheticConfig(num_factories=4, num_vehicles=2, orders_per_episode=4, horizon_steps=1)
        first = SyntheticDPDPEpisode(config, seed=7)
        second = SyntheticDPDPEpisode(config, seed=7)
        self.assertEqual(first.items, second.items)
        state = first.reset()
        self.assertEqual(state.current_time, 0)
        for _ in range(3):
            state = first.advance(state)
        self.assertGreaterEqual(len(first.available_at(state)), 0)

    def test_full_epoch_trainer_uses_one_ga_result_for_all_atomics(self):
        config = SyntheticConfig(num_factories=4, num_vehicles=2, orders_per_episode=4, horizon_steps=1)
        episode = SyntheticDPDPEpisode(config, seed=11)
        state = episode.reset()
        atomics = episode.available_at(state)
        trainer = EvoRLTrainer(
            RPPOPolicy(ObservationBuilder.feature_dim),
            ga_config=GAConfig(population_size=2, generations=1, time_limit_seconds=0.2),
        )
        result = trainer.train_epoch(state, atomics)
        self.assertEqual(len(result.policy_action_indices), len(atomics))
        self.assertEqual(len(result.ga_result.genome.order), len(atomics))
        self.assertIsInstance(result.ga_cost, float)

    def test_ga_teacher_is_not_used_as_on_policy_environment_transition(self):
        config = SyntheticConfig(num_factories=4, num_vehicles=2, orders_per_episode=4, horizon_steps=1)
        episode = SyntheticDPDPEpisode(config, seed=17)
        state = episode.reset()
        atomics = episode.available_at(state)
        trainer = EvoRLTrainer(
            RPPOPolicy(ObservationBuilder.feature_dim),
            ga_config=GAConfig(population_size=2, generations=1, time_limit_seconds=0.2),
            execution_mode="EvoRL-ICAPS",
        )
        result = trainer.train_epoch(state, atomics, update=False)
        self.assertTrue(trainer.rollout_buffer.policy)
        self.assertTrue(all(item.behavior_tag == "policy" for item in trainer.rollout_buffer.policy))
        self.assertTrue(all(item.behavior_tag == "ga" for item in trainer.collaborative_buffer))
        self.assertEqual(len(result.policy_action_indices), len(atomics))
        self.assertTrue(all(bool(t.mask[0, int(t.action.item())]) for t in trainer.collaborative_buffer))

    def test_paper_repro_mode_tags_ga_executed_transition_separately(self):
        config = SyntheticConfig(num_factories=4, num_vehicles=2, orders_per_episode=4, horizon_steps=1)
        episode = SyntheticDPDPEpisode(config, seed=19)
        state = episode.reset()
        atomics = episode.available_at(state)
        trainer = EvoRLTrainer(
            RPPOPolicy(ObservationBuilder.feature_dim),
            ga_config=GAConfig(population_size=2, generations=0, time_limit_seconds=0.2),
            execution_mode="EvoRL-paper-repro",
        )
        result = trainer.train_epoch(state, atomics, update=False)
        self.assertEqual(result.trace["execution_mode"], "EvoRL-paper-repro")
        # The selected phenotype must enter the PPO buffer so the paper mode
        # receives an actual environment transition.  If GA wins, the RPPO
        # seed remains separately auditable as pseudo/offline data.
        self.assertTrue(trainer.rollout_buffer.policy)
        if result.trace["executed_source"] == "ga":
            # Xi is the executed phenotype, so its replayed transitions are
            # on-policy for this macro-step even though their action source is
            # the GA teacher.  H remains separately auditable offline data.
            self.assertTrue(all(item.behavior_tag == "ga"
                                for item in trainer.rollout_buffer.policy))
            self.assertTrue(trainer.rollout_buffer.offline)
            self.assertTrue(all(item.behavior_tag == "paper_pseudo_transition"
                                for item in trainer.rollout_buffer.offline))
        else:
            self.assertTrue(all(item.behavior_tag == "policy"
                                for item in trainer.rollout_buffer.policy))

    def test_paper_fleet_genome_preserves_route_strings_and_exact_ids(self):
        genome = FleetGenome(("A", "B", "C"), ("V_2", "V_1", "V_2"))
        self.assertEqual(genome.routes, {"V_1": ("B",), "V_2": ("A", "C")})

    def test_pmx_crossover_terminates_and_preserves_permutation(self):
        teacher = PaperEvolutionaryTeacher()
        left = FleetGenome(("A", "B", "C", "D"), ("V_1", "V_1", "V_2", "V_2"))
        right = FleetGenome(("B", "A", "D", "C"), ("V_2", "V_1", "V_2", "V_1"))
        child = teacher._pmx(left, right, __import__("random").Random(0))
        self.assertEqual(set(child.order), set(left.order))
        self.assertEqual(len(child.order), len(set(child.order)))
        self.assertEqual(len(child.vehicle_assignment), len(child.order))

    def test_paper_assumptions_and_heldout_split_are_versioned(self):
        assumptions = load_assumptions()
        self.assertEqual(assumptions.name, "EvoRL-paper")
        split = split_instances(protocol="benchmark_heldout")
        self.assertEqual(set(split["train"]) & set(split["test"]), set())
        self.assertEqual(set(split["train"]) | set(split["validation"]) | set(split["test"]), set(range(1, 65)))

    def test_heldout_training_rejects_validation_and_test_ids(self):
        with self.assertRaises(ValueError):
            validate_training_instances("benchmark_heldout", (6,))
        with self.assertRaises(ValueError):
            validate_training_instances("benchmark_heldout", (7,))
        self.assertEqual(validate_training_instances("benchmark_heldout", (1, 2)), (1, 2))

    def test_item_state_is_immutable_snapshot_value(self):
        value = ItemState("I-1", "PALLET", "O-1", 1.0, "F1", "F2")
        with self.assertRaises(AttributeError):
            value.demand = 2.0

    def test_validator_can_enforce_empty_terminal_stack(self):
        value = item("O-1-1")
        vehicle = VehicleState("V_1", 15, "F1", carrying_item_ids=(value.id,))
        routes = {"V_1": ()}
        values = {value.id: value}
        self.assertTrue(SolutionValidator().validate(routes, {"V_1": vehicle}, values).valid)
        strict = SolutionValidator().validate(
            routes, {"V_1": vehicle}, values, require_empty_stack=True,
        )
        self.assertFalse(strict.valid)

    def test_validator_counts_carrying_items_in_expected_coverage(self):
        value = item("O-1-1")
        vehicle = VehicleState("V_1", 15, "F1", carrying_item_ids=(value.id,))
        report = SolutionValidator().validate(
            {"V_1": ()}, {"V_1": vehicle}, {value.id: value},
            expected_item_ids=(value.id,),
        )
        self.assertTrue(report.valid, report.errors)

    def test_canonical_route_fixture_matches_official_checker(self):
        value = item("O-1-1", pickup="F1", delivery="F2")
        order = Order("O-1", {"PALLET": 1}, 1, 0, 100, 1, 1, "F2", "F1")
        order.item_list = [value]
        vehicle = Vehicle("V_1", "gps", 24, 15, Stack())
        vehicle.cur_factory_id = "F1"
        vehicle.destination = None
        destination = OfficialNode("F1", 0.0, 0.0, [value], [])
        route = OfficialNode("F2", 0.0, 0.0, [], [value])
        dispatch = DispatchResult({"V_1": destination}, {"V_1": [route]})
        self.assertTrue(Checker.check_dispatch_result(dispatch, {"V_1": vehicle}, {"O-1": order}))
        bad_route = OfficialNode("F9", 0.0, 0.0, [], [value])
        bad = DispatchResult({"V_1": destination}, {"V_1": [bad_route]})
        self.assertFalse(Checker.check_dispatch_result(bad, {"V_1": vehicle}, {"O-1": order}))

    def test_strict_dispatch_never_hides_deferred_items(self):
        with patch.dict(os.environ, {"EVORL_REQUIRE_CHECKPOINT": "1", "EVORL_ALLOW_DEFER": "1"}):
            self.assertFalse(_allow_defer())
        with patch.dict(os.environ, {"EVORL_REQUIRE_CHECKPOINT": "0", "EVORL_ALLOW_DEFER": "1"}):
            self.assertTrue(_allow_defer())

    def test_strict_trace_diagnostics_reject_defer_and_budget_overrun(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trace.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"epoch": 0, "checker_precondition": true, "deferred_item_ids": ["I-1"], "wall_seconds": 571}\n')
            report = _trace_diagnostics(__import__("pathlib").Path(path))
            reasons = {entry["reason"] for entry in report["trace_invalid"]}
            self.assertEqual(report["trace_epochs"], 1)
            self.assertEqual(report["trace_max_wall_seconds"], 571.0)
            self.assertEqual(reasons, {"deferred", "epoch_timeout"})

    def test_strict_checkpoint_manifest_rejects_smoke_checkpoint(self):
        with self.assertRaises(ValueError):
            validate_checkpoint_manifest(
                {"model": {}, "input_dim": ObservationBuilder.feature_dim},
                protocol="benchmark_heldout",
                expected_input_dim=ObservationBuilder.feature_dim,
            )

    def test_simulator_seed_reaches_algorithm_process(self):
        class DummyEnvironment:
            total_score = 0.0

            def run(self):
                return None

        import src.simulator.simulate_api as simulate_api
        previous = os.environ.get("EVORL_RANDOM_SEED")
        try:
            with patch.object(simulate_api, "__initialize", return_value=DummyEnvironment()):
                simulate_api.simulate("factory.csv", "route.csv", "instance_1", simulator_seed=37)
            self.assertEqual(os.environ.get("EVORL_RANDOM_SEED"), "37")
        finally:
            if previous is None:
                os.environ.pop("EVORL_RANDOM_SEED", None)
            else:
                os.environ["EVORL_RANDOM_SEED"] = previous

    def test_training_env_observe_is_pure_and_terminal_observation_is_cached(self):
        calls = {"observe": 0, "advance": 0}

        def observe(session):
            calls["observe"] += 1
            return {"epoch": session.epoch}

        def dispatch(session, action):
            return {"action": action}

        def advance(session, info):
            calls["advance"] += 1
            return True, {"reward": 3.0}

        env = TrainingDPDPEnv(observe, dispatch, advance)
        self.assertEqual(env.reset(), {"epoch": 0})
        before = calls.copy()
        self.assertEqual(env.observe(), {"epoch": 0})
        self.assertEqual(calls, before)
        result = env.step("x")
        self.assertTrue(result.done)
        self.assertEqual(result.observation, {"epoch": 1})
        self.assertEqual(calls["advance"], 1)
        self.assertEqual(env.observe(), {"epoch": 1})
        self.assertEqual(calls["advance"], 1)

    def test_legacy_boundary_returns_immutable_item_snapshot(self):
        value = item("O-1-1")
        factory = Factory("F1", 1.0, 2.0, 1)
        vehicle = Vehicle("V_1", "gps", 24, 15, [])
        state = build_epoch_state(
            {"V_1": []}, {"V_1": vehicle}, {value.id: value},
            {"F1": factory}, {("F1", "F1"): (0.0, 0.0)},
        )
        self.assertIsInstance(state.items[value.id], ItemState)
        with self.assertRaises(AttributeError):
            state.items[value.id].demand = 99.0

    def test_legacy_boundary_removes_duplicate_committed_pickup(self):
        value = item("O-1-1", pickup="F1", delivery="F2")
        destination = Node("F1", [], [value])
        vehicle = Vehicle("V_1", "gps", 24, 15, [], destination)
        vehicle.cur_factory_id = ""
        plans = {"V_1": [Node("F1", [], [value]), Node("F2", [value], [])]}
        state = build_epoch_state(
            plans, {"V_1": vehicle}, {value.id: value},
            {"F1": Factory("F1", 1.0, 2.0, 1), "F2": Factory("F2", 2.0, 3.0, 1)},
            {("F1", "F2"): (10.0, 10.0)},
        )
        self.assertEqual(state.vehicles["V_1"].destination.pickup_item_ids, (value.id,))
        self.assertEqual(state.vehicles["V_1"].planned_route[0].delivery_item_ids, (value.id,))
        self.assertEqual(len(state.vehicles["V_1"].planned_route), 1)

    def test_merge_does_not_mutate_committed_destination(self):
        locked_item = item("O-1-1", pickup="F1", delivery="F2")
        suffix_item = item("O-2-1", order_id="O-2", pickup="F1", delivery="F3")
        destination = Node("F1", [], [locked_item])
        mutable_suffix = Node("F1", [], [suffix_item])
        vehicle = Vehicle("V_1", "gps", 24, 15, [], destination)
        plans = {"V_1": [destination, mutable_suffix, Node("F3", [suffix_item], [])]}
        merge_node({"V_1": vehicle}, plans)
        self.assertEqual(plans["V_1"][0].pickup_item_list, [locked_item])
        self.assertEqual(plans["V_1"][1].pickup_item_list, [suffix_item])


if __name__ == "__main__":
    unittest.main()
