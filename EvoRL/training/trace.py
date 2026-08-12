"""Small, deterministic JSONL trace writer used by strict EvoRL runs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


def stable_digest(value: Any) -> str:
    """Hash JSON-compatible state without depending on dictionary order."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def append_trace(record: Mapping[str, Any], path: str | os.PathLike[str] | None = None) -> None:
    """Append one flushed JSON record when tracing is enabled.

    Tracing is opt-in so the competition subprocess does not pay a file I/O
    cost by default.  A failed diagnostic write never changes the accepted
    route; strict callers can inspect the missing trace field and fail the
    experiment at the reporting layer.
    """

    target = path or os.environ.get("EVORL_TRACE_FILE")
    if not target:
        return
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(record), sort_keys=True, default=str) + "\n")
        handle.flush()

