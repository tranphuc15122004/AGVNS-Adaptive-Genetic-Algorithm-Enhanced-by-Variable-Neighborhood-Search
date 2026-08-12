"""Small state-machine wrapper that keeps observation pure and advancement single-shot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .session import AlgorithmSessionState


@dataclass(frozen=True)
class StepResult:
    observation: Any
    reward: float
    done: bool
    info: Mapping[str, Any]


class TrainingDPDPEnv:
    """Adapter around the official simulator or a deterministic test backend.

    ``observe_fn`` must be pure.  ``dispatch_fn`` performs one dispatch only;
    ``advance_fn`` is called exactly once per ``step`` after dispatch.
    """

    def __init__(
        self,
        observe_fn: Callable[[AlgorithmSessionState], Any],
        dispatch_fn: Callable[[AlgorithmSessionState, Any], Mapping[str, Any]],
        advance_fn: Callable[[AlgorithmSessionState, Mapping[str, Any]], tuple[bool, Mapping[str, Any]]],
        *,
        epoch_seconds: int = 600,
        episode_id: str = "episode-0",
        model_fingerprint: str = "",
    ):
        self.observe_fn = observe_fn
        self.dispatch_fn = dispatch_fn
        self.advance_fn = advance_fn
        self.epoch_seconds = int(epoch_seconds)
        self.session = AlgorithmSessionState(episode_id, model_fingerprint)
        self._last_observation = None
        self._phase = "NEW"

    def reset(self, *, episode_id: Optional[str] = None) -> Any:
        self.session.reset(episode_id=episode_id or self.session.episode_id)
        self._last_observation = self.observe_fn(self.session)
        self._phase = "AWAITING_ACTION"
        return self._last_observation

    def observe(self) -> Any:
        if self._phase == "TERMINAL":
            return self._last_observation
        if self._last_observation is None:
            self._last_observation = self.observe_fn(self.session)
        return self._last_observation

    def step(self, action: Any) -> StepResult:
        if self._phase == "NEW":
            self.reset()
        if self._phase == "TERMINAL":
            raise RuntimeError("cannot step a terminal training episode")
        before = self.observe()
        dispatch_info = self.dispatch_fn(self.session, action)
        done, advance_info = self.advance_fn(self.session, dispatch_info)
        # ``advance_fn`` computes the official transition but does not advance
        # this session object.  The wrapper owns exactly one logical tick.
        self.session.advance(elapsed_seconds=self.epoch_seconds, route_snapshot=advance_info.get("route_snapshot"))
        self._phase = "TERMINAL" if done else "AWAITING_ACTION"
        # A terminal transition still has a well-defined post-advance
        # observation.  Cache it so repeated ``observe`` calls remain pure and
        # do not accidentally execute another simulator tick.
        self._last_observation = self.observe_fn(self.session)
        reward = float(advance_info.get("reward", 0.0))
        info = {"before": before, **dict(dispatch_info), **dict(advance_info)}
        return StepResult(self._last_observation, reward, done, info)
