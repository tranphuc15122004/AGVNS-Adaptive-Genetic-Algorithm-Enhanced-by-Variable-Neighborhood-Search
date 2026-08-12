"""Runtime adapters and per-epoch parity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from .trace import stable_digest


@dataclass(frozen=True)
class ParityResult:
    equal: bool
    differing_epochs: tuple[int, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)


class RuntimeParity:
    """Compare in-process and serialized execution at every epoch."""

    def __init__(self, in_process: Callable[[Any, Any], Mapping[str, Any]], subprocess: Callable[[Any, Any], Mapping[str, Any]]):
        self.in_process = in_process
        self.subprocess = subprocess

    def compare(self, initial_state: Any, actions: Sequence[Any]) -> ParityResult:
        left = initial_state
        right = initial_state
        differing = []
        details = {}
        for epoch, action in enumerate(actions):
            left_result = self.in_process(left, action)
            right_result = self.subprocess(right, action)
            left = left_result.get("state", left)
            right = right_result.get("state", right)
            left_route = left_result.get("route_snapshot", left_result)
            right_route = right_result.get("route_snapshot", right_result)
            if left_route != right_route:
                differing.append(epoch)
                details[str(epoch)] = {"in_process": left_route, "subprocess": right_route}
        return ParityResult(not differing, tuple(differing), details)

    @staticmethod
    def compare_traces(in_process: Sequence[Mapping[str, Any]],
                       subprocess: Sequence[Mapping[str, Any]], *,
                       fields: Sequence[str] = (
                           "epoch", "current_time", "route_hash", "checker_precondition",
                       )) -> ParityResult:
        """Compare real official epoch traces, not only toy callback states.

        Records may contain large route snapshots; the result keeps a compact
        field-level diff and a digest of each record for reproducible failure
        reports.  Missing epochs and missing fields are failures in strict
        mode, which prevents a truncated subprocess log from looking like a
        successful parity run.
        """

        differing = []
        details = {}
        size = max(len(in_process), len(subprocess))
        for index in range(size):
            left = in_process[index] if index < len(in_process) else None
            right = subprocess[index] if index < len(subprocess) else None
            mismatch = left is None or right is None
            field_diff = {}
            if left is not None and right is not None:
                for field in fields:
                    if field not in left or field not in right or left.get(field) != right.get(field):
                        mismatch = True
                        field_diff[field] = {"in_process": left.get(field), "subprocess": right.get(field)}
            if mismatch:
                differing.append(index)
                details[str(index)] = {
                    "fields": field_diff,
                    "in_process_digest": stable_digest(left),
                    "subprocess_digest": stable_digest(right),
                }
        return ParityResult(not differing, tuple(differing), details)
