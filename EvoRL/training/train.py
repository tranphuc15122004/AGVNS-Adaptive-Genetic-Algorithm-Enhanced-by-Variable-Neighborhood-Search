"""CPU/T4-safe RPPO training entrypoint.

The module trains against a supplied ``TrainingDPDPEnv`` in applications.  A
small deterministic candidate environment is provided for smoke tests and CI
so installation can be verified without running all 64 simulator instances.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import torch

from algorithm.evorl.planner import TransactionalPlanner
from algorithm.evorl.atomic import chunk_items, mutable_item_ids
from algorithm.evorl.dto import item_attr
from .ga import GAConfig
from .observation import ObservationBuilder
from .rppo import RPPOPolicy, RPPOTrainer, RolloutBuffer, Transition
from .synthetic import SyntheticConfig, SyntheticDPDPEpisode
from .evorl_trainer import EvoRLTrainer
from .official_env import OfficialDPDPEnv
from .reproduction import (
    load_assumptions, split_instances, validate_checkpoint_manifest,
    validate_training_instances,
)


def _sha256_file(path: str | Path) -> str | None:
    """Return a stable input fingerprint, or ``None`` for an unavailable file."""

    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _atomic_torch_save(payload: Mapping[str, Any], destination: str | Path) -> None:
    """Write a checkpoint atomically so an interrupted train cannot corrupt it."""

    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    torch.save(dict(payload), temporary)
    os.replace(temporary, target)


def _latest_checkpoint_path(output: str | Path) -> Path:
    target = Path(output)
    return target.with_name(target.stem + ".latest" + target.suffix)


def _runtime_provenance(configs: Any, *, protocol: str, execution_mode: str) -> dict[str, Any]:
    """Capture enough runtime/input identity to audit a baseline checkpoint."""

    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "code_revision": os.environ.get("EVORL_CODE_REVISION", "unknown"),
        "factory_info_sha256": _sha256_file(configs.factory_info_file_path),
        "route_info_sha256": _sha256_file(configs.route_info_file_path),
        "protocol": protocol,
        "execution_mode": execution_mode,
    }


def _load_training_checkpoint(path: Optional[str], policy: RPPOPolicy, trainer: EvoRLTrainer, *, assumptions_hash: str) -> tuple[int, list]:
    """Restore model/optimizer/RNG state for an exact continuation."""

    if not path:
        return 0, []
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    saved_hash = checkpoint.get("assumptions_sha256")
    if saved_hash and saved_hash != assumptions_hash:
        raise ValueError("checkpoint assumptions do not match paper_assumptions.yaml")
    policy.load_state_dict(checkpoint["model"])
    optimizer_state = checkpoint.get("optimizer")
    if optimizer_state:
        trainer.rppo.load_state_dict(optimizer_state)
    if checkpoint.get("python_random_state") is not None:
        random.setstate(checkpoint["python_random_state"])
    if checkpoint.get("torch_random_state") is not None:
        torch.set_rng_state(checkpoint["torch_random_state"])
    if checkpoint.get("numpy_random_state") is not None:
        np.random.set_state(checkpoint["numpy_random_state"])
    if checkpoint.get("cuda_random_state") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(checkpoint["cuda_random_state"])
    return int(checkpoint.get("episode", 0)), list(checkpoint.get("history", []))


def train_smoke(*, updates: int, seed: int, device: str, output: str, input_dim: int = 16, candidates: int = 8):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    policy = RPPOPolicy(input_dim=input_dim, hidden_dim=128, recurrent=True)
    trainer = RPPOTrainer(policy, device=device)
    buffer = RolloutBuffer()
    target_device = trainer.device
    for _ in range(max(1, updates)):
        for _ in range(32):
            features = torch.randn(1, candidates, input_dim, device=target_device)
            mask = torch.ones(1, candidates, dtype=torch.bool, device=target_device)
            action, log_prob, _, value, _ = policy.act(features, mask)
            reward = float(-features[0, action.item(), 0].item())
            buffer.add(Transition(features, mask, action, log_prob.detach(), reward, False, float(value.item())))
        trainer.update(buffer, epochs=4, minibatch_size=32)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": policy.state_dict(), "input_dim": input_dim, "hidden_dim": 128, "recurrent": True, "seed": seed}, destination)
    return destination


def _rollout_policy(policy, episode: SyntheticDPDPEpisode, *, seed: int, device: str) -> float:
    """Evaluate one synthetic order stream without GA or parameter updates."""
    state = episode.reset(seed=seed)
    planner = TransactionalPlanner()
    builder = ObservationBuilder(planner)
    target_device = device if device == "cpu" or torch.cuda.is_available() else "cpu"
    hidden = None
    while not episode.terminal(state):
        for atomic in episode.available_at(state):
            observation = builder.build(state, atomic)
            features = torch.tensor(observation.features, dtype=torch.float32, device=target_device).unsqueeze(0)
            mask = torch.tensor(observation.mask, dtype=torch.bool, device=target_device).unsqueeze(0)
            if not bool(mask.any()):
                continue
            with torch.no_grad():
                action, _, _, _, hidden = policy.act(features, mask, hidden, deterministic=True)
            selected = observation.actions[int(action.item())].vehicle_id
            result = planner.probe(state, atomic, selected_vehicle=selected)
            if result.ok:
                state = planner.apply(state, result)
        state = episode.advance(state)
    return episode.score(state)


def train_synthetic(*, episodes: int, validation_episodes: int, seed: int, device: str,
                    output: str, config: SyntheticConfig, ga_config: GAConfig) -> dict:
    """Train on independent generated DPDP streams and retain best validation checkpoint."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    resolved_ga_config = ga_config or GAConfig(seed=seed)
    policy = RPPOPolicy(input_dim=ObservationBuilder.feature_dim, hidden_dim=128, recurrent=True)
    trainer = EvoRLTrainer(policy, device=device, ga_config=ga_config)
    best_score = float("inf")
    best_episode = 0
    history = []
    for episode_index in range(max(1, episodes)):
        episode = SyntheticDPDPEpisode(config, seed=seed + episode_index)
        state = episode.reset()
        trainer.reset_hidden()
        while not episode.terminal(state):
            atomics = episode.available_at(state)
            if atomics:
                result = trainer.train_epoch(state, atomics)
                state = result.state
            state = episode.advance(state)
        validation_scores = []
        for validation_index in range(max(1, validation_episodes)):
            validation_episode = SyntheticDPDPEpisode(config, seed=10_000 + seed + episode_index * 100 + validation_index)
            validation_scores.append(_rollout_policy(policy, validation_episode, seed=validation_episode.seed, device=device))
        validation_score = sum(validation_scores) / len(validation_scores)
        history.append({"episode": episode_index + 1, "validation_score": validation_score})
        if validation_score < best_score:
            best_score = validation_score
            best_episode = episode_index + 1
            destination = Path(output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model": policy.state_dict(), "input_dim": ObservationBuilder.feature_dim,
                "hidden_dim": 128, "recurrent": True, "seed": seed, "best_episode": best_episode,
                "validation_score": best_score, "synthetic_config": config.__dict__,
            }, destination)
    return {"best_episode": best_episode, "best_validation_score": best_score, "history": history, "checkpoint": output}


def _official_atomics(state, *, capacity: float = 15.0):
    """Build the paper dispatch set from the immutable official snapshot."""

    candidate_ids = mutable_item_ids(state.items.keys(), state.vehicles, {
        key: value.planned_route for key, value in state.vehicles.items()
    }, destinations={key: value.destination for key, value in state.vehicles.items()})
    candidates = [
        state.items[item_id] for item_id in candidate_ids
        if int(item_attr(state.items[item_id], "delivery_state", 1) or 1) <= 1
    ]
    return chunk_items(candidates, capacity=capacity)


def _rollout_official_policy(policy: RPPOPolicy, *, instance_id: int,
                             simulator_seed: int, device: str,
                             execution_mode: str = "EvoRL-paper-repro",
                             ga_config: GAConfig | None = None) -> float:
    """Greedy official validation using the selected execution contract."""

    from src.conf.configs import Configs

    env = OfficialDPDPEnv(
        Configs.factory_info_file, Configs.route_info_file,
        f"instance_{int(instance_id)}", simulator_seed=int(simulator_seed),
    )
    state = env.reset()
    planner = TransactionalPlanner()
    builder = ObservationBuilder(planner)
    from .ga import FleetGenome, PaperEvolutionaryTeacher
    from .paper_evaluator import evaluate_paper_fitness
    ga_teacher = PaperEvolutionaryTeacher(
        config=ga_config or GAConfig(seed=simulator_seed), planner=planner,
    ) if execution_mode == "EvoRL-paper-repro" else None
    target_device = device if device == "cpu" or torch.cuda.is_available() else "cpu"
    hidden = None
    was_training = policy.training
    policy.eval()
    try:
        while not env.done:
            source_state = state
            dispatch_state = state
            policy_assignments = []
            processed_atomics = []
            for atomic in _official_atomics(state):
                observation = builder.build(dispatch_state, atomic)
                features = torch.tensor(
                    observation.features, dtype=torch.float32,
                    device=target_device,
                ).unsqueeze(0)
                mask = torch.tensor(
                    observation.mask, dtype=torch.bool,
                    device=target_device,
                ).unsqueeze(0)
                if not bool(mask.any()):
                    raise ValueError(
                        f"validation has no feasible action for {atomic.atomic_id}"
                    )
                with torch.no_grad():
                    action, _, _, _, hidden = policy.act(
                        features, mask, hidden, deterministic=True,
                    )
                selected_vehicle = observation.actions[int(action.item())].vehicle_id
                insertion = planner.probe(
                    dispatch_state, atomic, selected_vehicle=selected_vehicle,
                )
                if not insertion.ok:
                    raise ValueError(insertion.reason)
                dispatch_state = planner.apply(dispatch_state, insertion)
                policy_assignments.append(selected_vehicle)
                processed_atomics.append(atomic)
            if ga_teacher is not None and processed_atomics:
                policy_genome = FleetGenome.from_assignment(
                    processed_atomics, tuple(sorted(state.vehicles)), policy_assignments,
                )
                ga_result = ga_teacher.optimize(
                    source_state, processed_atomics,
                    seed_genome=policy_genome, seed_state=dispatch_state,
                )
                if ga_result.fitness > evaluate_paper_fitness(dispatch_state).utility:
                    dispatch_state = ga_result.state
            step = env.step(dispatch_state)
            state = step.observation
        return float(env.finalize())
    finally:
        if was_training:
            policy.train()


def train_official(
    *,
    episodes: int,
    seed: int,
    device: str,
    output: str,
    protocol: str = "benchmark_heldout",
    instances: tuple[int, ...] | None = None,
    ga_config: GAConfig | None = None,
    resume: str | None = None,
    latest_output: str | None = None,
    validation_every: int = 1,
    execution_mode: str = "EvoRL-paper-repro",
) -> dict:
    """Train the primary paper-faithful EvoRL policy on fresh official episodes.

    The wall-clock time spent by GA is not passed to the simulator; every
    ``OfficialDPDPEnv.step`` advances exactly one 10-minute interval.
    """

    from src.conf.configs import Configs

    best_destination = Path(output)
    latest_destination = Path(latest_output) if latest_output else _latest_checkpoint_path(output)
    assumptions = load_assumptions()
    split = split_instances(protocol=protocol)
    train_instances = validate_training_instances(
        protocol,
        tuple(instances) if instances is not None else split["train"],
    )
    if not train_instances:
        raise ValueError("official training requires at least one instance")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    resolved_ga_config = ga_config or GAConfig(seed=seed)
    policy = RPPOPolicy(input_dim=ObservationBuilder.feature_dim, hidden_dim=int(assumptions.ppo.get("hidden_dim", 128)), recurrent=True)
    ppo = assumptions.ppo
    trainer = EvoRLTrainer(
        policy, device=device, ga_config=resolved_ga_config,
        execution_mode=execution_mode,
        rppo_config={
            "lr": float(ppo.get("learning_rate", 3e-4)),
            "clip": float(ppo.get("clip_epsilon", 0.2)),
            "gamma": float(ppo.get("gamma", 0.99)),
            "gae_lambda": float(ppo.get("gae_lambda", 0.95)),
            "value_coef": float(ppo.get("value_coefficient", 0.5)),
            "entropy_coef": float(ppo.get("entropy_coefficient", 0.01)),
            "tbptt_steps": int(ppo.get("tbptt_steps", 16)),
        },
    )
    provenance = _runtime_provenance(
        Configs, protocol=protocol, execution_mode=execution_mode,
    )
    if resume:
        resume_payload = torch.load(resume, map_location="cpu", weights_only=False)
        validate_checkpoint_manifest(
            resume_payload, protocol=protocol,
            assumptions_sha256=assumptions.source_sha256,
            expected_input_dim=ObservationBuilder.feature_dim,
            execution_mode=execution_mode,
        )
    start_episode, history = _load_training_checkpoint(
        resume, policy, trainer, assumptions_hash=assumptions.source_sha256,
    )
    best_validation = float("inf")
    best_episode = None
    if history:
        previous_validation = [
            row.get("validation_score") for row in history
            if row.get("validation_score") is not None
        ]
        if previous_validation:
            best_validation = min(float(value) for value in previous_validation)
            best_episode = next(
                int(row.get("episode", 0)) for row in history
                if row.get("validation_score") == best_validation
            )
    for episode_offset in range(max(1, int(episodes))):
        episode_index = start_episode + episode_offset
        instance_id = train_instances[episode_index % len(train_instances)]
        env = OfficialDPDPEnv(
            Configs.factory_info_file, Configs.route_info_file,
            f"instance_{instance_id}", simulator_seed=seed + episode_index,
        )
        state = env.reset()
        trainer.reset_hidden()
        epoch_scores = []
        while not env.done:
            atomics = _official_atomics(state)
            if atomics:
                result = trainer.train_epoch(state, atomics, update=False)
                dispatch_state = result.state
            else:
                # No new order at this tick: preserve the accepted route and
                # still let the official simulator advance exactly once.
                dispatch_state = state
            step = env.step(dispatch_state)
            if atomics:
                result.trace["environment_reward"] = {
                    "intrinsic": float(step.reward.intrinsic),
                    "feasibility": float(step.reward.feasibility),
                    "collaborative": float(step.reward.collaborative),
                    "final": float(step.reward.final),
                    "total": float(step.reward.total),
                }
                result.trace["environment_done"] = bool(step.done)
                result.trace["official_score_after_step"] = step.info.get("official_score")
            # A terminal no-new-order tick still carries the final official
            # potential correction; attach it to the last policy transition
            # rather than creating a fictitious no-op action.
            if atomics or step.done:
                trainer.record_environment_reward(step.reward.total, done=step.done)
            epoch_scores.append(float(step.info.get("official_score") or 0.0))
            state = step.observation
        metrics = trainer.finish_episode()
        score = env.finalize()
        history.append({
            "episode": episode_index + 1, "instance": instance_id,
            "simulator_seed": seed + episode_index, "score": score, **metrics,
        })
        validation_score = None
        if validation_every and (episode_index + 1) % max(1, int(validation_every)) == 0:
            validation_ids = tuple(split["validation"])
            if validation_ids:
                # Use one fixed held-out case for comparable checkpoint
                # selection.  The release campaign evaluates every validation
                # and test case explicitly; rotating different-scale scores
                # would make ``best`` meaningless.
                validation_id = validation_ids[0]
                validation_values = [_rollout_official_policy(
                    policy, instance_id=validation_id,
                    simulator_seed=seed + 100_000 + episode_index,
                    device=device, execution_mode=execution_mode,
                    ga_config=resolved_ga_config,
                )]
                validation_score = sum(validation_values) / len(validation_values)
                history[-1]["validation_score"] = validation_score
                is_best = validation_score < best_validation
                if is_best:
                    best_validation = validation_score
                    best_episode = episode_index + 1
            else:
                is_best = True
        else:
            # With validation disabled this is an explicitly last-checkpoint
            # run; the manifest records that no model selection occurred.
            is_best = validation_every == 0
        if validation_every and split["validation"] and validation_score is None:
            is_best = False
        checkpoint_payload = {
            "model": policy.state_dict(), "input_dim": ObservationBuilder.feature_dim,
            "hidden_dim": policy.hidden_dim, "recurrent": policy.recurrent, "seed": seed,
            "episode": episode_index + 1, "instance": instance_id,
            "protocol": protocol, "assumptions_sha256": assumptions.source_sha256,
            "history": history, "optimizer": trainer.rppo.state_dict(),
            "resolved_config": {
                "mode": "official",
                "execution_mode": execution_mode,
                "protocol": protocol,
                "train_instances": list(train_instances),
                "validation_instances": list(split["validation"]),
                "ga": asdict(resolved_ga_config),
                "rppo": dict(ppo),
                "device": str(trainer.rppo.device),
                "validation_every": int(validation_every),
                "best_episode": best_episode,
                "best_validation_score": None if best_validation == float("inf") else best_validation,
                "best_output": str(best_destination),
                "latest_output": str(latest_destination),
            },
            "provenance": provenance,
            "checkpoint_kind": "latest",
            "python_random_state": random.getstate(),
            "torch_random_state": torch.get_rng_state(),
            "numpy_random_state": np.random.get_state(),
            "cuda_random_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
        }
        # ``latest`` is a resumable journal and is written after every
        # completed episode, including episodes that fail validation.  The
        # selected ``best`` artifact remains stable for evaluation.
        _atomic_torch_save(checkpoint_payload, latest_destination)
        if is_best or not best_destination.exists():
            _atomic_torch_save(
                dict(checkpoint_payload, checkpoint_kind="best"),
                best_destination,
            )
    return {
        "checkpoint": output, "protocol": protocol, "history": history,
        "best_episode": best_episode,
        "best_validation_score": None if best_validation == float("inf") else best_validation,
        "latest_checkpoint": str(latest_destination),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train EvoRL RPPO (CPU or CUDA/T4)")
    parser.add_argument(
        "--mode", default="official", choices=("synthetic", "official"),
        help="official is the safe baseline default; synthetic is CI/smoke only",
    )
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--updates", type=int, default=None, help="legacy alias for --episodes")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--validation-episodes", type=int, default=2)
    parser.add_argument("--orders", type=int, default=50)
    parser.add_argument("--vehicles", type=int, default=5)
    parser.add_argument("--horizon-steps", type=int, default=144)
    parser.add_argument("--ga-population", type=int, default=None)
    parser.add_argument("--ga-generations", type=int, default=None)
    parser.add_argument("--ga-time-limit", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default="checkpoints/evorl_rppo.pt")
    parser.add_argument("--resume", default=None, help="resume official training from a checkpoint")
    parser.add_argument(
        "--latest-output", default=None,
        help="resumable latest checkpoint path (default: <output stem>.latest.pt)",
    )
    parser.add_argument(
        "--validation-every", type=int, default=1,
        help="run official held-out validation every N training episodes (0 disables selection)",
    )
    parser.add_argument(
        "--execution-mode", default="EvoRL-paper-repro",
        choices=("EvoRL-ICAPS", "EvoRL-paper-repro"),
        help="primary on-policy adaptation or explicitly tagged paper GA-execution ablation",
    )
    parser.add_argument("--protocol", default="benchmark_heldout", choices=("benchmark_heldout", "paper_transductive"))
    parser.add_argument("--instances", default="", help="official training instance IDs/ranges")
    args = parser.parse_args(argv)
    episodes = args.updates if args.updates is not None else args.episodes
    if args.mode == "official":
        selected = []
        if args.instances:
            for part in args.instances.split(","):
                if "-" in part:
                    start, end = (int(value) for value in part.split("-", 1))
                    selected.extend(range(start, end + 1))
                else:
                    selected.append(int(part))
        result = train_official(
            episodes=episodes, seed=args.seed, device=args.device, output=args.output,
            protocol=args.protocol, instances=tuple(selected) or None,
            ga_config=GAConfig(
                population_size=(args.ga_population if args.ga_population is not None else int(load_assumptions().values.get("population_size", 20))),
                generations=(args.ga_generations if args.ga_generations is not None else int(load_assumptions().values.get("ga_generations", 20))),
                time_limit_seconds=args.ga_time_limit,
                seed=args.seed,
            ),
            resume=args.resume,
            latest_output=args.latest_output,
            validation_every=args.validation_every,
            execution_mode=args.execution_mode,
        )
        print(result)
        return
    config = SyntheticConfig(orders_per_episode=args.orders, num_vehicles=args.vehicles, horizon_steps=args.horizon_steps)
    ga_config = GAConfig(
        population_size=args.ga_population if args.ga_population is not None else 8,
        generations=args.ga_generations if args.ga_generations is not None else 4,
        time_limit_seconds=args.ga_time_limit, seed=args.seed,
    )
    result = train_synthetic(
        episodes=episodes, validation_episodes=args.validation_episodes, seed=args.seed,
        device=args.device, output=args.output, config=config, ga_config=ga_config,
    )
    print(result)


if __name__ == "__main__":
    main()
