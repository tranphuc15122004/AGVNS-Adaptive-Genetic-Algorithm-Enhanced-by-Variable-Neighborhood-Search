"""Paper-aligned reward components with explicit maximize-reward signs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from algorithm.evorl.cost import CostBreakdown


@dataclass(frozen=True)
class RewardConfig:
    intrinsic_weight: float = 1.0
    feasibility_penalty: float = 1000.0
    collaborative_weight: float = 1.0
    final_weight: float = 1.0


@dataclass(frozen=True)
class RewardBreakdown:
    intrinsic: float
    feasibility: float
    collaborative: float
    final: float
    total: float
    terminal_score: Optional[float] = None


def compose_reward(
    before: CostBreakdown,
    after: CostBreakdown,
    *,
    ga_cost: Optional[float] = None,
    seed_cost: Optional[float] = None,
    invalid: bool = False,
    terminal: bool = False,
    terminal_score: Optional[float] = None,
    config: RewardConfig = RewardConfig(),
) -> RewardBreakdown:
    """Return a reward with an explicit terminal objective boundary.

    For non-terminal transitions the benchmark component is the potential
    difference ``J_before - J_after``.  At terminal, the official Evaluator
    score replaces the projected suffix rather than being added to it.  This
    prevents the common error of double-counting the terminal objective.
    """

    if terminal_score is not None:
        intrinsic = before.benchmark_cost - float(terminal_score)
    else:
        intrinsic = before.benchmark_cost - after.benchmark_cost
    feasibility = -config.feasibility_penalty if invalid else 0.0
    # ``ga_cost`` is the executed candidate cost.  The paper's collaborative
    # signal is positive when GA improves the RL seed, so callers provide the
    # seed explicitly.  The old two-argument form remains compatible and uses
    # the before-cost as its seed.
    reference_cost = before.benchmark_cost if seed_cost is None else float(seed_cost)
    collaborative = 0.0 if ga_cost is None else reference_cost - float(ga_cost)
    # The terminal score is already included in the potential difference above.
    # Keep ``final`` as a separately logged component for paper-style reward
    # experiments, but do not add it in the official ICAPS reward path.
    final = 0.0
    total = (
        config.intrinsic_weight * intrinsic
        + feasibility
        + config.collaborative_weight * collaborative
        + config.final_weight * final
    )
    return RewardBreakdown(intrinsic, feasibility, collaborative, final, total, terminal_score)
