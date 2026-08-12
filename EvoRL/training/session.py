"""Deterministic episode/session state shared by in-process and subprocess modes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional


@dataclass
class AlgorithmSessionState:
    episode_id: str
    model_fingerprint: str = ""
    epoch: int = 0
    current_time: int = 0
    hidden_state: Any = None
    route_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def reset(self, *, episode_id: Optional[str] = None, model_fingerprint: Optional[str] = None) -> None:
        if episode_id is not None:
            self.episode_id = episode_id
        if model_fingerprint is not None:
            self.model_fingerprint = model_fingerprint
        self.epoch = 0
        self.current_time = 0
        self.hidden_state = None
        self.route_snapshot = {}
        self.metadata = {}

    def observe(self, builder: Callable[["AlgorithmSessionState"], Any]) -> Any:
        """Build an observation without advancing or mutating simulator state."""

        return builder(self)

    def advance(self, *, elapsed_seconds: int, route_snapshot: Optional[Mapping[str, Any]] = None) -> None:
        self.current_time += int(elapsed_seconds)
        self.epoch += 1
        if route_snapshot is not None:
            self.route_snapshot = dict(route_snapshot)


class HiddenStateSidecar:
    """Atomic, retry-safe hidden-state persistence for subprocess execution."""

    schema_version = 1

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    @staticmethod
    def fingerprint(model_bytes: bytes) -> str:
        return hashlib.sha256(model_bytes).hexdigest()[:16]

    def save(self, session: AlgorithmSessionState, hidden_before: Any, hidden_after: Any) -> None:
        payload = {
            "schema_version": self.schema_version,
            "episode_id": session.episode_id,
            "episode_key": session.episode_id,
            "model_fingerprint": session.model_fingerprint,
            "epoch": session.epoch,
            "hidden_before": _json_safe(hidden_before),
            "hidden_after": _json_safe(hidden_after),
            "current_time": session.current_time,
            "last_epoch_time": session.current_time,
            "route_snapshot": _json_safe(session.route_snapshot),
            "metadata": _json_safe(session.metadata),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def load(
        self,
        *,
        episode_id: str,
        model_fingerprint: str,
        epoch: Optional[int] = None,
        current_time: Optional[int] = None,
        retry: bool = False,
        route_hash: Optional[str] = None,
    ) -> Optional[Any]:
        try:
            with self.path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return None
        if payload.get("schema_version") != self.schema_version:
            return None
        if payload.get("episode_id") != episode_id or payload.get("model_fingerprint") != model_fingerprint:
            return None
        if epoch is not None:
            saved_epoch = int(payload.get("epoch", -1))
            if saved_epoch > int(epoch):
                return None
            if retry and route_hash is not None:
                saved_route_hash = (payload.get("metadata") or {}).get("input_route_hash")
                if saved_route_hash != route_hash:
                    return None
            if retry and saved_epoch == int(epoch):
                return payload.get("hidden_before")
            if saved_epoch < int(epoch) - 1:
                return None
        if current_time is not None and int(payload.get("current_time", 0)) > int(current_time):
            return None
        return payload.get("hidden_after")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "detach"):
        tensor = value.detach().cpu()
        return tensor.tolist()
    return str(value)
