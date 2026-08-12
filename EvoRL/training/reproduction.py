"""Paper reproduction manifest and experiment presets.

The paper leaves several implementation details unspecified.  This module
loads the versioned manifest instead of scattering guessed constants through
the trainer and evaluation scripts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSUMPTIONS_PATH = _ROOT / "paper_assumptions.yaml"


@dataclass(frozen=True)
class PaperAssumptions:
    name: str
    source_path: str
    source_sha256: str
    values: Mapping[str, Any]

    @property
    def ppo(self) -> Mapping[str, Any]:
        return self.values.get("ppo", {})

    @property
    def ga(self) -> Mapping[str, Any]:
        return self.values.get("ga", {})

    @property
    def reward(self) -> Mapping[str, Any]:
        return self.values.get("reward", {})


def load_assumptions(path: str | Path | None = None) -> PaperAssumptions:
    """Load and fingerprint the reproduction manifest.

    PyYAML is optional for domain-only deployments.  The project dependency
    includes it for training; a JSON manifest remains supported as a useful
    fallback for minimal subprocess environments.
    """

    manifest_path = Path(path or DEFAULT_ASSUMPTIONS_PATH)
    raw = manifest_path.read_bytes()
    try:
        import yaml  # type: ignore

        values = yaml.safe_load(raw.decode("utf-8")) or {}
    except ImportError:
        try:
            values = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("PyYAML is required to read paper_assumptions.yaml") from exc
    if not isinstance(values, Mapping):
        raise ValueError(f"assumptions manifest must contain a mapping: {manifest_path}")
    return PaperAssumptions(
        name=str(values.get("name", "EvoRL-paper")),
        source_path=str(manifest_path),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        values=dict(values),
    )


def split_instances(*, protocol: str = "benchmark_heldout") -> dict[str, tuple[int, ...]]:
    """Return the pre-registered 64-case split used by evaluation scripts.

    Cases are grouped in blocks of eight, matching the paper's eight workload
    scales.  The transductive preset is deliberately labeled and reported
    separately from the held-out comparison.
    """

    if protocol == "paper_transductive":
        return {"train": tuple(range(1, 65)), "validation": (), "test": tuple(range(1, 65))}
    if protocol != "benchmark_heldout":
        raise ValueError(f"unknown data protocol: {protocol}")
    train, validation, test = [], [], []
    for start in range(1, 65, 8):
        train.extend(range(start, start + 5))
        validation.append(start + 5)
        test.extend((start + 6, start + 7))
    return {"train": tuple(train), "validation": tuple(validation), "test": tuple(test)}


def validate_training_instances(protocol: str, instances: Sequence[int]) -> tuple[int, ...]:
    """Validate an explicit training subset before any order file is opened."""

    split = split_instances(protocol=protocol)
    values = tuple(int(instance) for instance in instances)
    if not values or any(instance < 1 or instance > 64 for instance in values):
        raise ValueError("training instance IDs must be within 1..64")
    if protocol == "benchmark_heldout":
        allowed = set(split["train"])
        forbidden = sorted(set(values) - allowed)
        if forbidden:
            raise ValueError(
                "benchmark_heldout training cannot read validation/test instances: "
                + ",".join(str(value) for value in forbidden)
            )
    return tuple(dict.fromkeys(values))


def validate_checkpoint_manifest(checkpoint: Mapping[str, Any], *, protocol: str,
                                 assumptions_sha256: str | None = None,
                                 expected_input_dim: int | None = None,
                                 execution_mode: str = "EvoRL-paper-repro") -> None:
    """Fail closed when a checkpoint is used for strict ICAPS evaluation.

    A model file without provenance can still be opened for exploratory
    inference, but it must not silently enter a held-out benchmark table.  In
    particular, synthetic/smoke checkpoints and a checkpoint trained with a
    test-instance override are incompatible with the official protocol.
    """

    if not isinstance(checkpoint, Mapping) or "model" not in checkpoint:
        raise ValueError("checkpoint is missing model weights")
    current_hash = assumptions_sha256 or load_assumptions().source_sha256
    if checkpoint.get("assumptions_sha256") != current_hash:
        raise ValueError("checkpoint assumptions fingerprint does not match the current manifest")
    resolved = checkpoint.get("resolved_config")
    if not isinstance(resolved, Mapping) or resolved.get("mode") != "official":
        raise ValueError("strict ICAPS evaluation requires an official-training checkpoint")
    if str(resolved.get("protocol", "")) != str(protocol):
        raise ValueError(
            f"checkpoint protocol {resolved.get('protocol')!r} does not match evaluation protocol {protocol!r}"
        )
    if str(resolved.get("execution_mode", "EvoRL-paper-repro")) != str(execution_mode):
        raise ValueError(
            f"checkpoint execution mode {resolved.get('execution_mode')!r} does not match {execution_mode!r}"
        )
    try:
        train_ids = tuple(int(value) for value in resolved.get("train_instances", ()))
        validate_training_instances(protocol, train_ids)
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint contains an invalid training-instance manifest") from exc
    if expected_input_dim is not None and int(checkpoint.get("input_dim", -1)) != int(expected_input_dim):
        raise ValueError(
            f"checkpoint observation dimension {checkpoint.get('input_dim')} != runtime dimension {expected_input_dim}"
        )


def convergence_episode(scores: Sequence[float], *, window: int = 50, delta: float | None = None) -> int | None:
    """Paper-style post-hoc convergence episode.

    The stopping budget is fixed before training; this metric only reports the
    earliest moving average that remains in the final plateau band.
    """

    if len(scores) < max(2, window):
        return None
    tail = list(scores[max(0, int(len(scores) * 0.9)):]) or list(scores)
    if delta is None:
        mean = sum(tail) / len(tail)
        variance = sum((value - mean) ** 2 for value in tail) / max(1, len(tail) - 1)
        delta = variance ** 0.5
    final = sum(tail) / len(tail)
    for index in range(window - 1, len(scores)):
        average = sum(scores[index - window + 1:index + 1]) / window
        if abs(average - final) <= float(delta) and all(
            abs(sum(scores[j - window + 1:j + 1]) / window - final) <= float(delta)
            for j in range(index, len(scores))
        ):
            return index + 1
    return None
