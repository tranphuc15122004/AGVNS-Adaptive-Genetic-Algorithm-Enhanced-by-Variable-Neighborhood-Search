"""Inference-time EvoRL dispatcher used by the existing subprocess entrypoint."""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence, Optional
import os
import time
from pathlib import Path

from .atomic import mutable_item_ids
from .legacy_adapter import dispatch_atomic_legacy
from .legacy_adapter import build_epoch_state, apply_epoch_state
from .atomic import chunk_items
from .planner import TransactionalPlanner
from .validator import SolutionValidator
from training.trace import append_trace, stable_digest


def dispatch_mutable_orders(
    plans: Dict[str, List[object]],
    vehicles: Mapping[str, object],
    all_items: Mapping[str, object],
    factories: Mapping[str, object],
    route_map: Mapping,
    *,
    generated_item_ids: Sequence[str] | None = None,
    policy_checkpoint: Optional[str] = None,
    device: str = "cpu",
    current_time: int = 0,
    epoch: int = 0,
    time_budget_seconds: float | None = None,
) -> List[str]:
    """Allocate every unpicked/unplanned generated item exactly once.

    DEFER is not a learned action.  If a route is infeasible and the
    compatibility flag is enabled, the item remains pending and the previous
    valid plan is emitted for this epoch; expired items are still rejected by
    the official simulator.
    """

    started = time.perf_counter()
    deadline = (
        time.monotonic() + float(time_budget_seconds)
        if time_budget_seconds is not None and float(time_budget_seconds) > 0
        else None
    )
    candidate_ids = mutable_item_ids(
        generated_item_ids if generated_item_ids is not None else all_items.keys(),
        vehicles,
        plans,
    )
    # Recompute coverage after the canonical restore as a final duplicate
    # guard.  This catches stale legacy ``unallocated_order_items`` metadata
    # when a route was accepted in the previous epoch but the item has not yet
    # been physically picked up.
    restored = build_epoch_state(
        plans, vehicles, all_items, factories, route_map,
        epoch=epoch, current_time=current_time,
    )
    covered = set()
    for vehicle in restored.vehicles.values():
        covered.update(vehicle.carrying_item_ids)
        if vehicle.destination is not None:
            covered.update(vehicle.destination.pickup_item_ids)
            covered.update(vehicle.destination.delivery_item_ids)
        for node in vehicle.planned_route:
            covered.update(node.pickup_item_ids)
            covered.update(node.delivery_item_ids)
    candidate_ids = [item_id for item_id in candidate_ids if item_id not in covered]
    all_candidate_ids = list(candidate_ids)
    dispatch_telemetry = {}
    if candidate_ids:
        if policy_checkpoint:
            accepted_ids = _dispatch_with_policy(
                plans, vehicles, all_items, factories, route_map, candidate_ids,
                policy_checkpoint, device=device, epoch=epoch, current_time=current_time,
                deadline=deadline, telemetry=dispatch_telemetry,
            )
        else:
            try:
                dispatch_atomic_legacy(
                    plans, vehicles, all_items, factories, route_map, candidate_ids,
                    epoch=epoch, current_time=current_time,
                )
                accepted_ids = list(candidate_ids)
            except ValueError:
                if not _allow_defer():
                    raise
                # Leave the generated item in the simulator's unallocated
                # stream.  It will be reconsidered from the complete pending
                # set next epoch instead of disappearing via a ``new_order``
                # diff.
                accepted_ids = []
        candidate_ids = accepted_ids
    else:
        # Even a no-new-order tick must round-trip the restored scene through
        # the canonical boundary.  Historical solution files can contain the
        # committed destination twice or with a stale delivery ordering;
        # returning the raw ``plans`` would make Checker reject an otherwise
        # valid no-op dispatch.
        apply_epoch_state(restored, plans, all_items, factories)
    # One final canonical validation protects the official boundary even on a
    # no-op epoch.  Any failure is surfaced to strict callers instead of being
    # silently converted into an invalid JSON dispatch.
    final_state = build_epoch_state(
        plans, vehicles, all_items, factories, route_map,
        epoch=epoch, current_time=current_time,
    )
    expected = set()
    destinations = {}
    for vehicle_id, vehicle in final_state.vehicles.items():
        destinations[vehicle_id] = vehicle.destination
        expected.update(vehicle.carrying_item_ids)
        if vehicle.destination is not None:
            expected.update(vehicle.destination.pickup_item_ids)
            expected.update(vehicle.destination.delivery_item_ids)
        for node in vehicle.planned_route:
            expected.update(node.pickup_item_ids)
            expected.update(node.delivery_item_ids)
    report = SolutionValidator().validate(
        {key: value.planned_route for key, value in final_state.vehicles.items()},
        final_state.vehicles, final_state.items,
        expected_item_ids=expected, destinations=destinations,
    )
    if not report.valid:
        raise ValueError("canonical dispatch validation failed: " + "; ".join(report.errors))
    route_snapshot = {
        vehicle_id: {
            "destination": _trace_node(vehicle.destination),
            "route": [_trace_node(node) for node in vehicle.planned_route],
            "carrying": list(vehicle.carrying_item_ids),
        }
        for vehicle_id, vehicle in sorted(final_state.vehicles.items())
    }
    append_trace({
        "schema_version": 1,
        "episode_id": os.environ.get("EVORL_EPISODE_ID", ""),
        "epoch": int(epoch),
        "current_time": int(current_time),
        "candidate_item_ids": list(all_candidate_ids),
        "accepted_item_ids": list(candidate_ids),
        "deferred_item_ids": [item_id for item_id in all_candidate_ids if item_id not in set(candidate_ids)],
        "route_hash": stable_digest(route_snapshot),
        "route_snapshot": route_snapshot,
        "checker_precondition": True,
        "validator_errors": list(report.errors),
        "strict_checkpoint": os.environ.get("EVORL_REQUIRE_CHECKPOINT") == "1",
        "execution_mode": dispatch_telemetry.get("execution_mode"),
        "online_ga": bool(dispatch_telemetry.get("online_ga", False)),
        "ga_epochs": list(dispatch_telemetry.get("ga_epochs", ())),
        "wall_seconds": time.perf_counter() - started,
    })
    return candidate_ids


def _trace_node(node):
    if node is None:
        return None
    return {
        "factory_id": str(node.factory_id),
        "pickup_item_ids": list(node.pickup_item_ids),
        "delivery_item_ids": list(node.delivery_item_ids),
        "arrive_time": int(node.arrive_time),
        "leave_time": int(node.leave_time),
    }


def _dispatch_with_policy(plans, vehicles, all_items, factories, route_map, candidate_ids,
                          checkpoint_path: str, *, device: str, epoch: int,
                          current_time: int, deadline: float | None = None,
                          telemetry: dict | None = None) -> None:
    """Run RPPO and, in paper mode, the online GA execution stage.

    ``EvoRL-ICAPS`` remains an explicit policy-only ablation.  The
    ``EvoRL-paper-repro`` contract follows Algorithm 1: RPPO creates the seed
    phenotype, GA evolves it, and the better phenotype under the paper
    evaluator is executed at the simulator boundary.
    """
    import torch
    from training.observation import ObservationBuilder
    from training.rppo import RPPOPolicy

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    from training.reproduction import load_assumptions
    assumptions = load_assumptions()
    expected_assumptions = checkpoint.get("assumptions_sha256")
    if os.environ.get("EVORL_REQUIRE_CHECKPOINT") == "1" and not expected_assumptions:
        raise ValueError("strict EvoRL evaluation requires an assumptions fingerprint")
    if expected_assumptions and expected_assumptions != assumptions.source_sha256:
        raise ValueError(
            "checkpoint assumptions do not match the current EvoRL-paper manifest"
        )
    if os.environ.get("EVORL_REQUIRE_CHECKPOINT") == "1":
        from training.observation import ObservationBuilder
        from training.reproduction import validate_checkpoint_manifest
        validate_checkpoint_manifest(
            checkpoint,
            protocol=os.environ.get("EVORL_PROTOCOL", "benchmark_heldout"),
            assumptions_sha256=assumptions.source_sha256,
            expected_input_dim=ObservationBuilder.feature_dim,
            execution_mode=os.environ.get("EVORL_EXECUTION_MODE", "EvoRL-paper-repro"),
        )
    policy = RPPOPolicy(
        checkpoint["input_dim"], checkpoint.get("hidden_dim", 128),
        recurrent=bool(checkpoint.get("recurrent", True)),
    )
    target_device = device if device == "cpu" or torch.cuda.is_available() else "cpu"
    policy.to(target_device)
    policy.load_state_dict(checkpoint["model"])
    policy.eval()
    execution_mode = os.environ.get("EVORL_EXECUTION_MODE", "EvoRL-paper-repro")
    online_ga = execution_mode == "EvoRL-paper-repro"
    ga_teacher = None
    if online_ga:
        # Prefer the GA contract stored with the checkpoint. Environment
        # overrides are useful only for bounded debug runs.
        from algorithm import algorithm_config as algorithm_config
        from training.ga import GAConfig, PaperEvolutionaryTeacher
        resolved_ga = checkpoint.get("resolved_config", {}).get("ga", {})
        population_size = int(os.environ.get(
            "EVORL_GA_POPULATION",
            resolved_ga.get("population_size", algorithm_config.POPULATION_SIZE),
        ))
        generations = int(os.environ.get(
            "EVORL_GA_GENERATIONS",
            resolved_ga.get("generations", algorithm_config.NUMBER_OF_GENERATION),
        ))
        ga_time_limit = float(os.environ.get(
            "EVORL_GA_TIME_LIMIT",
            resolved_ga.get("time_limit_seconds", algorithm_config.EVORL_GA_TIME_LIMIT),
        ))
        ga_seed = int(os.environ.get("EVORL_RANDOM_SEED", checkpoint.get("seed", 0)))
        ga_teacher = PaperEvolutionaryTeacher(
            GAConfig(
                population_size=max(1, population_size),
                generations=max(0, generations),
                time_limit_seconds=max(0.001, ga_time_limit),
                seed=ga_seed,
            ),
            planner=TransactionalPlanner(),
        )
    from training.session import AlgorithmSessionState, HiddenStateSidecar
    fingerprint = HiddenStateSidecar.fingerprint(Path(checkpoint_path).read_bytes())
    episode_id = os.environ.get("EVORL_EPISODE_ID") or os.path.basename(os.environ.get("MA_DATA_INTERACTION_DIR", "episode"))
    sidecar_path = os.environ.get("EVORL_HIDDEN_SIDECAR")
    if not sidecar_path:
        from src.conf.configs import Configs
        sidecar_root = os.environ.get(
            "MA_DATA_INTERACTION_DIR",
            Configs.algorithm_data_interaction_folder_path,
        )
        sidecar_path = os.path.join(sidecar_root, "evorl_hidden_state.json")
    solution_path = os.path.join(os.environ.get("MA_DATA_INTERACTION_DIR", "."), "solution.json")
    if epoch == 0 and not os.path.exists(solution_path) and os.path.exists(sidecar_path):
        # A fresh simulator episode may reuse a data directory.  A sidecar
        # from a previous interrupted run must not seed its first action.
        try:
            os.remove(sidecar_path)
        except OSError:
            pass
    sidecar = HiddenStateSidecar(sidecar_path)
    session = AlgorithmSessionState(episode_id, fingerprint, epoch=epoch, current_time=current_time)
    retry = os.environ.get("EVORL_RETRY_EPOCH", "0") == "1"
    state = build_epoch_state(
        plans, vehicles, all_items, factories, route_map,
        epoch=epoch, current_time=current_time,
    )
    input_route_snapshot = {
        vehicle_id: {
            "destination": _trace_node(vehicle.destination),
            "route": [_trace_node(node) for node in vehicle.planned_route],
            "carrying": list(vehicle.carrying_item_ids),
        }
        for vehicle_id, vehicle in sorted(state.vehicles.items())
    }
    input_route_hash = stable_digest(input_route_snapshot)
    hidden_payload = sidecar.load(
        episode_id=episode_id, model_fingerprint=fingerprint,
        epoch=epoch, current_time=current_time, retry=retry,
        route_hash=input_route_hash,
    )
    hidden = None
    if hidden_payload is not None:
        hidden = torch.tensor(hidden_payload, dtype=torch.float32, device=target_device)
        if hidden.ndim == 2:
            hidden = hidden.unsqueeze(0)
    planner = TransactionalPlanner()
    builder = ObservationBuilder(planner)
    hidden_before = hidden
    accepted_ids = []
    ga_trace = []
    source_state = state
    policy_state = state
    processed_atomics = []
    policy_assignments = []
    atomics = chunk_items(
        [all_items[item_id] for item_id in candidate_ids],
        capacity=_capacity(vehicles),
    )
    for atomic in atomics:
        if deadline is not None and time.monotonic() >= deadline:
            if not _allow_defer():
                raise TimeoutError("EvoRL dispatch exceeded the simulator epoch budget")
            break
        observation = builder.build(policy_state, atomic)
        features = torch.tensor(observation.features, dtype=torch.float32, device=target_device).unsqueeze(0)
        mask = torch.tensor(observation.mask, dtype=torch.bool, device=target_device).unsqueeze(0)
        if not bool(mask.any()):
            if not _allow_defer():
                raise ValueError(f"no feasible policy action for {atomic.atomic_id}")
            continue
        with torch.no_grad():
            action, _, _, _, hidden = policy.act(features, mask, hidden, deterministic=True)
        selected_vehicle = observation.actions[int(action.item())].vehicle_id
        result = planner.probe(
            policy_state, atomic, selected_vehicle=selected_vehicle, deadline=deadline,
        )
        if not result.ok:
            if not _allow_defer():
                raise ValueError(result.reason)
            continue
        policy_state = planner.apply(policy_state, result)
        processed_atomics.append(atomic)
        policy_assignments.append(selected_vehicle)

    if online_ga and ga_teacher is not None and processed_atomics:
        from training.ga import FleetGenome, GAConfig, PaperEvolutionaryTeacher
        from training.paper_evaluator import evaluate_paper_fitness
        from algorithm.evorl.cost import projected_cost

        policy_genome = FleetGenome.from_assignment(
            processed_atomics, tuple(sorted(vehicles)), policy_assignments,
        )
        remaining = (
            max(0.001, deadline - time.monotonic())
            if deadline is not None else ga_teacher.config.time_limit_seconds
        )
        base = ga_teacher.config
        bounded_teacher = PaperEvolutionaryTeacher(
            GAConfig(
                population_size=base.population_size,
                generations=base.generations,
                elite_size=base.elite_size,
                tournament_size=base.tournament_size,
                crossover_probability=base.crossover_probability,
                mutation_probability=base.mutation_probability,
                time_limit_seconds=min(base.time_limit_seconds, remaining),
                seed=base.seed,
                selection=base.selection,
                crossover_min=base.crossover_min,
                mutation_min=base.mutation_min,
            ),
            planner=ga_teacher.planner,
        )
        ga_result = bounded_teacher.optimize(
            source_state, processed_atomics,
            seed_genome=policy_genome, seed_state=policy_state,
        )
        policy_fitness = evaluate_paper_fitness(policy_state).utility
        if ga_result.fitness > policy_fitness:
            state = ga_result.state
            executed_source = "ga"
        else:
            state = policy_state
            executed_source = "policy"
        policy_cost = projected_cost(
            {key: value.planned_route for key, value in policy_state.vehicles.items()},
            policy_state.vehicles, policy_state.route_map, policy_state.items,
            current_time=policy_state.current_time,
        )
        ga_trace.append({
            "atomic_ids": [atomic.atomic_id for atomic in processed_atomics],
            "policy_fitness": float(policy_fitness),
            "ga_fitness": float(ga_result.fitness),
            "policy_cost": float(policy_cost.benchmark_cost),
            "ga_cost": float(ga_result.cost),
            "executed_source": executed_source,
            "ga_evaluated": int(ga_result.evaluated),
            "ga_generations_completed": int(ga_result.generations_completed),
        })
        accepted_ids.extend(
            item_id for atomic in processed_atomics for item_id in atomic.item_ids
        )
    else:
        state = policy_state
        accepted_ids.extend(
            item_id for atomic in processed_atomics for item_id in atomic.item_ids
        )
    if telemetry is not None:
        telemetry.update({
            "execution_mode": execution_mode,
            "online_ga": bool(online_ga),
            "ga_epochs": ga_trace,
        })
    apply_epoch_state(state, plans, all_items, factories)
    if hidden is not None:
        session.hidden_state = hidden
        session.route_snapshot = {
            vehicle_id: {
                "destination": _trace_node(vehicle.destination),
                "route": [_trace_node(node) for node in vehicle.planned_route],
                "carrying": list(vehicle.carrying_item_ids),
            }
            for vehicle_id, vehicle in sorted(state.vehicles.items())
        }
        session.metadata["input_route_hash"] = input_route_hash
        sidecar.save(session, hidden_before, hidden)
    return accepted_ids


def _allow_defer() -> bool:
    # A strict checkpoint run is a correctness gate.  Silently leaving an
    # item pending would let an invalid policy appear to have completed an
    # epoch; the official simulator must observe the failure instead.
    if os.environ.get("EVORL_REQUIRE_CHECKPOINT") == "1":
        return False
    return os.environ.get("EVORL_ALLOW_DEFER", "1") == "1"


def _capacity(vehicles):
    capacities = {float(getattr(vehicle, "board_capacity", 15) or 15) for vehicle in vehicles.values()}
    if len(capacities) > 1:
        raise ValueError(f"ICAPS mode requires uniform capacity, got {sorted(capacities)}")
    return next(iter(capacities), 15.0)
