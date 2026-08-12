"""RPPO implementation with masked candidate actions and GA feedback isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

try:  # Torch is optional for domain-only/subprocess deployments.
    import torch
    from torch import Tensor, nn
    from torch.distributions import Categorical
except ImportError:  # pragma: no cover
    torch = None
    Tensor = object
    nn = object
    Categorical = None


def _require_torch():
    if torch is None:
        raise RuntimeError("RPPO requires PyTorch; install torch for training")


class RPPOPolicy(nn.Module if torch is not None else object):
    """Shared actor/critic for all ICAPS scales.

    Candidate features are padded to the batch maximum.  Invalid candidates
    are masked before sampling, so the policy never emits an unknown vehicle
    or position action.
    """

    def __init__(self, input_dim: int, hidden_dim: int = 128, recurrent: bool = True):
        _require_torch()
        super().__init__()
        self.input_dim = int(input_dim)
        self.hidden_dim = int(hidden_dim)
        self.recurrent = bool(recurrent)
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.Tanh())
        self.gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True) if recurrent else None
        self.actor = nn.Linear(hidden_dim, 1)
        self.critic = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1))

    def forward(self, candidate_features: Tensor, action_mask: Tensor, hidden: Optional[Tensor] = None):
        encoded = self.encoder(candidate_features)
        if self.gru is not None:
            # The candidate axis is an action set, not a temporal sequence.
            # Recurrent context therefore advances once per micro-action and
            # is broadcast over candidates; treating vehicles as a GRU
            # sequence would make logits depend on input vehicle ordering.
            pooled_input = encoded.masked_fill(~action_mask.unsqueeze(-1).bool(), 0.0).sum(1)
            denom_input = action_mask.sum(1, keepdim=True).clamp_min(1).to(encoded.dtype)
            context, next_hidden = self.gru((pooled_input / denom_input).unsqueeze(1), hidden)
            encoded = encoded + context[:, -1:, :]
        else:
            next_hidden = hidden
        logits = self.actor(encoded).squeeze(-1)
        logits = logits.masked_fill(~action_mask.bool(), torch.finfo(logits.dtype).min)
        pooled = encoded.masked_fill(~action_mask.unsqueeze(-1).bool(), 0.0).sum(1)
        denom = action_mask.sum(1, keepdim=True).clamp_min(1).to(encoded.dtype)
        value = self.critic(pooled / denom).squeeze(-1)
        return logits, value, next_hidden

    def act(self, candidate_features: Tensor, action_mask: Tensor, hidden: Optional[Tensor] = None, deterministic: bool = False):
        logits, value, next_hidden = self(candidate_features, action_mask, hidden)
        distribution = Categorical(logits=logits)
        action = logits.argmax(-1) if deterministic else distribution.sample()
        return action, distribution.log_prob(action), distribution.entropy(), value, next_hidden


@dataclass
class Transition:
    features: Tensor
    mask: Tensor
    action: Tensor
    old_log_prob: Tensor
    reward: float
    done: bool
    value: float
    behavior_tag: str = "policy"
    confidence: float = 1.0
    hidden_before: Optional[Tensor] = None
    hidden_after: Optional[Tensor] = None
    teacher_advantage: float = 0.0
    discount: float = 0.99


class RolloutBuffer:
    """On-policy buffer; GA samples are deliberately stored separately."""

    def __init__(self):
        self.policy: List[Transition] = []
        self.ga: List[Transition] = []
        self.offline: List[Transition] = []

    def add(self, transition: Transition) -> None:
        if transition.behavior_tag == "ga":
            self.ga.append(transition)
        elif transition.behavior_tag == "policy":
            self.policy.append(transition)
        else:
            self.offline.append(transition)

    def clear(self) -> None:
        self.policy.clear()
        self.ga.clear()
        self.offline.clear()


class RPPOTrainer:
    def __init__(self, policy: RPPOPolicy, *, lr: float = 3e-4, clip: float = 0.2,
                 gamma: float = 0.99, gae_lambda: float = 0.95,
                 value_coef: float = 0.5, entropy_coef: float = 0.01,
                 device: str = "cpu", tbptt_steps: int = 16):
        _require_torch()
        requested_device = str(device).lower()
        if requested_device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was explicitly requested for RPPO training, but no usable "
                "CUDA device is available. Check the NVIDIA driver/container "
                "runtime instead of silently falling back to CPU."
            )
        self.device = torch.device(device)
        self.policy = policy.to(self.device)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        self.clip = clip
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.tbptt_steps = max(1, int(tbptt_steps))

    def state_dict(self) -> Dict[str, object]:
        """Return optimizer/config state needed for deterministic resumption."""

        return {
            "optimizer": self.optimizer.state_dict(),
            "clip": self.clip,
            "gamma": self.gamma,
            "gae_lambda": self.gae_lambda,
            "value_coef": self.value_coef,
            "entropy_coef": self.entropy_coef,
            "tbptt_steps": self.tbptt_steps,
        }

    def load_state_dict(self, payload: Dict[str, object]) -> None:
        """Restore optimizer state without replacing the policy module."""

        optimizer = payload.get("optimizer")
        if optimizer:
            self.optimizer.load_state_dict(optimizer)
            for state in self.optimizer.state.values():
                for key, value in list(state.items()):
                    if torch is not None and torch.is_tensor(value):
                        state[key] = value.to(self.device)
        for name in ("clip", "gamma", "gae_lambda", "value_coef", "entropy_coef"):
            if name in payload:
                setattr(self, name, float(payload[name]))
        if "tbptt_steps" in payload:
            self.tbptt_steps = max(1, int(payload["tbptt_steps"]))

    def update(self, buffer: RolloutBuffer, *, epochs: int = 4, minibatch_size: int = 512) -> Dict[str, float]:
        if not buffer.policy:
            return {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
        transitions = buffer.policy
        rewards = torch.tensor([x.reward for x in transitions], dtype=torch.float32, device=self.device)
        dones = torch.tensor([x.done for x in transitions], dtype=torch.float32, device=self.device)
        values = torch.tensor([x.value for x in transitions], dtype=torch.float32, device=self.device)
        discounts = torch.tensor([x.discount for x in transitions], dtype=torch.float32, device=self.device)
        advantages = self._gae(rewards, dones, values, discounts)
        returns = advantages + values
        indices = torch.arange(len(transitions), device=self.device)
        metrics = {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
        count = 0
        for _ in range(epochs):
            sequence_size = self.tbptt_steps if self.policy.recurrent else minibatch_size
            chunk_size = min(minibatch_size, sequence_size)
            for start in range(0, len(transitions), chunk_size):
                batch_idx = indices[start:start + chunk_size].tolist()
                self.optimizer.zero_grad(set_to_none=True)
                losses = []
                entropies = []
                values_new = []
                running_hidden = None
                for offset, idx in enumerate(batch_idx):
                    transition = transitions[idx]
                    features = transition.features.to(self.device)
                    mask = transition.mask.to(self.device)
                    action = transition.action.to(self.device)
                    # Keep the recurrent graph through a contiguous truncated
                    # sequence.  The previous implementation detached every
                    # micro-action and therefore trained a gated feed-forward
                    # policy despite exposing a GRU at inference time.
                    hidden = transition.hidden_before if offset == 0 else running_hidden
                    if hidden is not None:
                        hidden = hidden.to(self.device)
                    logits, value, running_hidden = self.policy(features, mask, hidden)
                    dist = Categorical(logits=logits)
                    log_prob = dist.log_prob(action)
                    ratio = torch.exp(log_prob - transition.old_log_prob.to(self.device))
                    adv = advantages[idx].detach()
                    losses.append(-torch.minimum(ratio * adv, torch.clamp(ratio, 1 - self.clip, 1 + self.clip) * adv))
                    entropies.append(dist.entropy())
                    values_new.append(value.squeeze())
                policy_loss = torch.stack(losses).mean()
                value_loss = 0.5 * (torch.stack(values_new) - returns[batch_idx]).pow(2).mean()
                entropy = torch.stack(entropies).mean()
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), 0.5)
                self.optimizer.step()
                for key, value_item in (("loss", loss), ("policy_loss", policy_loss), ("value_loss", value_loss), ("entropy", entropy)):
                    metrics[key] += float(value_item.detach().cpu())
                count += 1
        if count:
            metrics = {key: value / count for key, value in metrics.items()}
        buffer.clear()
        return metrics

    def collaborative_ga_update(self, transitions: Sequence[Transition], *, weight: float = 0.1) -> float:
        """Small confidence-weighted supervised/KL update for GA winners.

        This is intentionally separate from PPO's on-policy ratio update.
        """
        if not transitions:
            return 0.0
        self.optimizer.zero_grad(set_to_none=True)
        losses = []
        for transition in transitions:
            hidden = transition.hidden_before
            if hidden is not None:
                hidden = hidden.to(self.device)
            logits, _, _ = self.policy(transition.features.to(self.device), transition.mask.to(self.device), hidden)
            distribution = Categorical(logits=logits)
            action = transition.action.to(self.device)
            log_prob = distribution.log_prob(action)
            old_log_prob = transition.old_log_prob.to(self.device)
            ratio = torch.exp(log_prob - old_log_prob)
            advantage = float(transition.teacher_advantage)
            if advantage == 0.0:
                advantage = float(transition.confidence)
            advantage_tensor = torch.as_tensor(advantage, dtype=log_prob.dtype, device=self.device)
            clipped = torch.clamp(ratio, 1 - self.clip, 1 + self.clip) * advantage_tensor
            surrogate = torch.minimum(ratio * advantage_tensor, clipped)
            # Eq. (34) contains a KL trust-region term.  The old log-prob is
            # the only distributional quantity available in a transition, so
            # this per-action KL proxy is deterministic and auditable.
            kl_proxy = old_log_prob - log_prob
            losses.append(float(transition.confidence) * (-surrogate + 0.01 * kl_proxy))
        loss = weight * torch.stack(losses).mean()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), 0.5)
        self.optimizer.step()
        return float(loss.detach().cpu())

    def _gae(self, rewards: Tensor, dones: Tensor, values: Tensor, discounts: Optional[Tensor] = None) -> Tensor:
        if discounts is None:
            discounts = torch.full_like(rewards, self.gamma)
        advantages = torch.zeros_like(rewards)
        gae = torch.tensor(0.0, device=self.device)
        next_value = torch.tensor(0.0, device=self.device)
        for index in reversed(range(len(rewards))):
            discount = discounts[index]
            delta = rewards[index] + discount * next_value * (1 - dones[index]) - values[index]
            gae = delta + discount * self.gae_lambda * (1 - dones[index]) * gae
            advantages[index] = gae
            next_value = values[index]
        if advantages.numel() <= 1:
            return advantages - advantages.mean()
        return (advantages - advantages.mean()) / (advantages.std(unbiased=False).clamp_min(1e-8))
