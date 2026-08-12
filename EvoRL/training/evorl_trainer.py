"""Paper-like GA-in-the-loop orchestration for one dispatch epoch."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Sequence
import time

import torch
from torch.distributions import Categorical

from algorithm.evorl.dto import AtomicOrder, EpochState
from algorithm.evorl.cost import projected_cost
from algorithm.evorl.dto import InsertionResult
from algorithm.evorl.planner import TransactionalPlanner
from .ga import FleetGenome, GAConfig, PaperEvolutionaryTeacher, PaperGAResult
from .observation import ObservationBuilder
from .paper_evaluator import evaluate_paper_fitness
from .rppo import RPPOPolicy, RolloutBuffer, RPPOTrainer, Transition
from .reward import RewardBreakdown, compose_reward


@dataclass(frozen=True)
class EpochTrainingResult:
    state: EpochState
    ga_result: PaperGAResult
    policy_action_indices: tuple[int, ...]
    collaborative_loss: float
    ppo_metrics: dict
    reward: RewardBreakdown
    policy_cost: float
    ga_cost: float
    trace: dict


class EvoRLTrainer:
    """Execute one paper-inspired epoch under an explicit execution contract.

    ``EvoRL-ICAPS`` is the policy-only deployment ablation.  The
    ``EvoRL-paper-repro`` contract follows Algorithm 1: it compares the policy
    phenotype H with the best GA phenotype eta using the paper evaluator and
    executes the better one.  GA phenotypes are still kept in a separate
    teacher buffer; an environment transition caused by eta is never silently
    relabelled as an ordinary on-policy PPO transition.
    """

    def __init__(self, policy: RPPOPolicy, *, device: str = "cpu", planner: TransactionalPlanner | None = None,
                 ga_config: GAConfig | None = None, rppo_config: Dict | None = None,
                 execution_mode: str = "EvoRL-paper-repro"):
        if execution_mode not in {"EvoRL-ICAPS", "EvoRL-paper-repro"}:
            raise ValueError(f"unknown EvoRL execution mode: {execution_mode}")
        self.execution_mode = execution_mode
        self.planner = planner or TransactionalPlanner()
        self.observation_builder = ObservationBuilder(self.planner)
        self.teacher = PaperEvolutionaryTeacher(config=ga_config or GAConfig(), planner=self.planner)
        self.rppo = RPPOTrainer(policy, device=device, **(rppo_config or {}))
        self.hidden = None
        self.rollout_buffer = RolloutBuffer()
        self.collaborative_buffer: List[Transition] = []
        self._pending_policy_transitions: List[Transition] = []
        self.episode_trace: List[dict] = []

    def reset_hidden(self) -> None:
        self.hidden = None

    def train_epoch(
        self,
        state: EpochState,
        atomics: Sequence[AtomicOrder],
        *,
        update: bool = True,
    ) -> EpochTrainingResult:
        if not atomics:
            raise ValueError("train_epoch requires at least one atomic order")
        policy_state = state
        buffer = RolloutBuffer()
        policy_actions: List[int] = []
        ga_transitions: List[Transition] = []
        policy_transitions: List[Transition] = []
        policy_assignments: List[int] = []
        policy_features = []
        policy_masks = []
        policy_log_probs = []
        policy_values = []
        policy_hidden_before = []
        policy_hidden_after = []
        policy_micro_rewards: List[float] = []
        vehicle_ids = sorted(state.vehicles)
        # A GA candidate has its own order permutation.  Its teacher labels
        # must therefore be replayed from the same macro-state with a hidden
        # prefix corresponding to that permutation, rather than borrowing a
        # hidden state from the policy's differently ordered prefix.
        epoch_hidden_before = self.hidden.detach().clone() if self.hidden is not None else None
        for atomic in atomics:
            observation = self.observation_builder.build(policy_state, atomic)
            features = torch.tensor(
                observation.features, dtype=torch.float32, device=self.rppo.device,
            ).unsqueeze(0)
            mask = torch.tensor(
                observation.mask, dtype=torch.bool, device=self.rppo.device,
            ).unsqueeze(0)
            if not bool(mask.any()):
                raise ValueError(f"no feasible action for {atomic.atomic_id}")
            hidden_before = self.hidden.detach().clone() if self.hidden is not None else None
            action, log_prob, _, value, self.hidden = self.rppo.policy.act(features, mask, self.hidden)
            if self.hidden is not None:
                self.hidden = self.hidden.detach()
            policy_index = int(action.item())
            policy_actions.append(policy_index)
            policy_features.append(features.detach())
            policy_masks.append(mask.detach())
            policy_log_probs.append(log_prob.detach())
            policy_values.append(float(value.item()))
            policy_hidden_before.append(hidden_before)
            policy_hidden_after.append(self.hidden.detach().clone() if self.hidden is not None else None)
            selected_vehicle = observation.actions[policy_index].vehicle_id
            insertion = self.planner.probe(policy_state, atomic, selected_vehicle=selected_vehicle)
            if not insertion.ok:
                raise ValueError(insertion.reason)
            policy_state = self.planner.apply(policy_state, insertion)
            policy_assignments.append(vehicle_ids.index(selected_vehicle))
            # This is a potential difference inside one simulator epoch.  It
            # is replaced/adjusted by the actual official reward after the
            # macro dispatch, but keeps credit assignment directional for
            # synthetic and pre-advance training paths.
            policy_micro_rewards.append(-float(insertion.delta_cost))

        policy_vehicle_assignments = tuple(vehicle_ids[index] for index in policy_assignments)
        policy_genome = FleetGenome(
            tuple(atomic.atomic_id for atomic in atomics), policy_vehicle_assignments,
        )
        ga_result = self.teacher.optimize(
            state, atomics, seed_genome=policy_genome, seed_state=policy_state,
        )
        before_cost = projected_cost(
            {key: value.planned_route for key, value in state.vehicles.items()},
            state.vehicles, state.route_map, state.items, current_time=state.current_time,
        )
        policy_cost = projected_cost(
            {key: value.planned_route for key, value in policy_state.vehicles.items()},
            policy_state.vehicles, policy_state.route_map, policy_state.items, current_time=state.current_time,
        )
        policy_fitness = evaluate_paper_fitness(policy_state).utility
        if self.execution_mode == "EvoRL-ICAPS":
            # Explicit policy-only ablation used to measure the contribution
            # of online GA execution.  The primary paper reproduction below
            # uses the Eq. (33) comparison instead.
            executed_state = policy_state
            executed_source = "policy"
        elif ga_result.fitness > policy_fitness:
            # Algorithm 1, line 19 / Eq. (33): execute the best phenotype,
            # not the GA winner unconditionally.  The strict comparison keeps
            # the policy phenotype on ties and makes runs deterministic.
            executed_state = ga_result.state
            executed_source = "ga"
        else:
            executed_state = policy_state
            executed_source = "policy"
        executed_cost = projected_cost(
            {key: value.planned_route for key, value in executed_state.vehicles.items()},
            executed_state.vehicles, executed_state.route_map, executed_state.items,
            current_time=state.current_time,
        )
        reward = compose_reward(
            before_cost, executed_cost,
        )
        for atomic_index, atomic in enumerate(atomics):
            features = policy_features[atomic_index]
            mask = policy_masks[atomic_index]
            action = torch.tensor(
                [policy_actions[atomic_index]],
                dtype=torch.long,
                device=self.rppo.device,
            )
            # In the paper-reproduction mode the environment may execute eta.
            # H is on-policy only when it is the selected phenotype; otherwise
            # retain it as auditable pseudo/offline data.
            policy_transitions.append(Transition(
                features, mask, action, policy_log_probs[atomic_index],
                reward=policy_micro_rewards[atomic_index], done=False,
                value=policy_values[atomic_index],
                behavior_tag=("policy" if (self.execution_mode == "EvoRL-ICAPS"
                                             or executed_source == "policy")
                              else "paper_pseudo_transition"),
                hidden_before=policy_hidden_before[atomic_index],
                hidden_after=policy_hidden_after[atomic_index],
                discount=(self.rppo.gamma if atomic_index == len(atomics) - 1 else 1.0),
            ))
        # Replay each evaluated GA phenotype through its own deterministic
        # planner prefix.  This makes the Eq. (34)-style feedback auditable:
        # every stored action was feasible in the exact state in which it is
        # labelled, and recurrent context follows the GA order permutation.
        atomic_by_id = {atomic.atomic_id: atomic for atomic in atomics}
        denominator = max(1e-9, abs(policy_cost.benchmark_cost) + 1e-9)
        executed_ga_transitions: List[Transition] = []
        replay_deadline = time.monotonic() + max(
            0.1, float(self.teacher.config.time_limit_seconds),
        )
        for candidate_genome, candidate_cost in zip(
            ga_result.population, ga_result.population_costs,
        ):
            if time.monotonic() >= replay_deadline:
                break
            candidate_state = state
            candidate_hidden = (
                epoch_hidden_before.detach().clone()
                if epoch_hidden_before is not None else None
            )
            candidate_transitions: List[Transition] = []
            replayable = True
            assignments = dict(zip(candidate_genome.order, candidate_genome.vehicle_assignment))
            for atomic_id in candidate_genome.order:
                atomic = atomic_by_id.get(atomic_id)
                ga_vehicle = assignments.get(atomic_id)
                if atomic is None or ga_vehicle not in vehicle_ids:
                    replayable = False
                    break
                candidate_observation = self.observation_builder.build(candidate_state, atomic)
                candidate_features = torch.tensor(
                    candidate_observation.features, dtype=torch.float32,
                    device=self.rppo.device,
                ).unsqueeze(0)
                candidate_mask = torch.tensor(
                    candidate_observation.mask, dtype=torch.bool,
                    device=self.rppo.device,
                ).unsqueeze(0)
                ga_action_index = vehicle_ids.index(ga_vehicle)
                if not bool(candidate_mask[0, ga_action_index].item()):
                    replayable = False
                    break
                ga_action = torch.tensor(
                    [ga_action_index],
                    dtype=torch.long,
                    device=self.rppo.device,
                )
                with torch.no_grad():
                    old_logits, old_value, next_hidden = self.rppo.policy(
                        candidate_features, candidate_mask, candidate_hidden,
                    )
                    ga_old_log_prob = Categorical(logits=old_logits).log_prob(ga_action)
                insertion = self.planner.probe(
                    candidate_state, atomic, selected_vehicle=ga_vehicle,
                    deadline=replay_deadline,
                )
                if not insertion.ok:
                    replayable = False
                    break
                candidate_transitions.append(Transition(
                    candidate_features.detach(), candidate_mask.detach(), ga_action,
                    ga_old_log_prob.detach(), reward=0.0, done=False,
                    value=float(old_value.item()), behavior_tag="ga",
                    hidden_before=(candidate_hidden.detach().clone()
                                  if candidate_hidden is not None else None),
                ))
                candidate_state = self.planner.apply(candidate_state, insertion)
                candidate_hidden = (
                    next_hidden.detach() if next_hidden is not None else None
                )
            if not replayable:
                continue
            ga_advantage = max(
                0.0, policy_cost.benchmark_cost - float(candidate_cost),
            ) / denominator
            confidence = min(1.0, ga_advantage / 0.05) if ga_advantage > 0 else 0.0
            for transition in candidate_transitions:
                transition.reward = ga_advantage
                transition.confidence = confidence
                transition.teacher_advantage = ga_advantage
            if (self.execution_mode == "EvoRL-paper-repro"
                    and executed_source == "ga"
                    and candidate_genome == ga_result.genome):
                # Algorithm 1 executes Xi and updates the policy from that
                # transition.  The replayed GA winner already contains the
                # correct action mask, old log-probabilities, and recurrent
                # prefix, so promote it to the PPO buffer instead of treating
                # the environment transition as offline-only.
                executed_ga_transitions = candidate_transitions
            else:
                ga_transitions.extend(candidate_transitions)

        if (self.execution_mode == "EvoRL-paper-repro"
                and executed_source == "ga"
                and not executed_ga_transitions):
            raise RuntimeError(
                "the GA phenotype selected for execution could not be replayed "
                "into an RPPO transition"
            )
        execution_transitions = policy_transitions
        if (self.execution_mode == "EvoRL-paper-repro"
                and executed_source == "ga"
                and executed_ga_transitions):
            execution_transitions = executed_ga_transitions
            # H remains useful as an explicitly labelled pseudo transition,
            # but must not receive the next state/reward caused by Xi.
            if not update:
                self.rollout_buffer.offline.extend(policy_transitions)
        for transition in execution_transitions:
            buffer.add(transition)
        if update:
            ppo_metrics = self.rppo.update(buffer, epochs=4, minibatch_size=512)
            collaborative_loss = self.rppo.collaborative_ga_update(ga_transitions)
        else:
            self.rollout_buffer.policy.extend(execution_transitions)
            self.collaborative_buffer.extend(ga_transitions)
            self._pending_policy_transitions = execution_transitions
            ppo_metrics = {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
            collaborative_loss = 0.0
        trace = {
            "epoch": int(state.epoch),
            "execution_mode": self.execution_mode,
            "current_time": int(state.current_time),
            "atomic_ids": [atomic.atomic_id for atomic in atomics],
            "policy_assignments": list(policy_vehicle_assignments),
            "before_cost": asdict(before_cost),
            "policy_projected_cost": asdict(policy_cost),
            "executed_cost": asdict(executed_cost),
            "policy_cost": float(policy_cost.benchmark_cost),
            "policy_fitness": float(policy_fitness),
            "ga_cost": float(ga_result.cost),
            "ga_fitness": float(ga_result.fitness),
            "executed_source": executed_source,
            "ga_evaluated": int(ga_result.evaluated),
            "ga_generations_completed": int(ga_result.generations_completed),
            "ga_population": [
                {"order": list(genome.order), "vehicle_assignment": list(genome.vehicle_assignment),
                 "cost": float(cost), "fitness": float(fitness)}
                for genome, cost, fitness in zip(
                    ga_result.population, ga_result.population_costs,
                    ga_result.population_fitnesses or (0.0,) * len(ga_result.population),
                )
            ],
            "reward": asdict(reward),
            "ppo": dict(ppo_metrics),
            "collaborative_loss": float(collaborative_loss),
        }
        self.episode_trace.append(trace)
        return EpochTrainingResult(
            executed_state, ga_result, tuple(policy_actions), collaborative_loss,
            ppo_metrics, reward, policy_cost.benchmark_cost, ga_result.cost, trace,
        )

    def record_environment_reward(self, reward: float, *, done: bool = False) -> None:
        """Replace projected reward with the reward observed after Xi executes."""

        if not self._pending_policy_transitions:
            if done and self.rollout_buffer.policy:
                # A terminal simulator advance can happen on a no-new-order
                # tick.  Attach its official potential correction to the last
                # policy action so the episode still telescopes to terminal
                # score without inventing a no-op PPO action.
                last = self.rollout_buffer.policy[-1]
                last.reward += float(reward)
                last.done = True
                return
            if done:
                # An empty official episode can terminate before any order is
                # generated.  There is no policy action to credit, but this
                # is a valid terminal transition rather than a bookkeeping
                # error.
                return
            raise RuntimeError("no pending policy transitions")
        previous_total = sum(float(item.reward) for item in self._pending_policy_transitions[:-1])
        # Preserve the macro transition total while retaining potential-based
        # micro credit for earlier assignments in the same epoch.
        last = self._pending_policy_transitions[-1]
        last.reward = float(reward) - previous_total
        for transition in self._pending_policy_transitions[:-1]:
            transition.done = False
        last.done = bool(done)
        self._pending_policy_transitions = []

    def finish_episode(self) -> dict:
        """Apply PPO and collaborative updates after an official episode."""

        # A terminal simulator step can contain no newly generated orders.
        # Mark the most recent actual transition terminal in that case so GAE
        # cannot bootstrap across episode boundaries.
        if self.rollout_buffer.policy and not any(item.done for item in self.rollout_buffer.policy):
            self.rollout_buffer.policy[-1].done = True
        offline_transition_count = len(self.rollout_buffer.offline)
        metrics = self.rppo.update(self.rollout_buffer, epochs=4, minibatch_size=512)
        self.rollout_buffer.offline.clear()
        collaborative_loss = self.rppo.collaborative_ga_update(self.collaborative_buffer)
        self.collaborative_buffer.clear()
        trace = list(self.episode_trace)
        self.episode_trace.clear()
        return {
            **metrics, "collaborative_loss": collaborative_loss,
            "offline_transition_count": offline_transition_count,
            "trace": trace,
        }
