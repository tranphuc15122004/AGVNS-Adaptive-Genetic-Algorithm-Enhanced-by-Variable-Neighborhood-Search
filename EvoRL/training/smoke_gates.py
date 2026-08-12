"""Small release-gate runner for EvoRL ICAPS integration.

This is deliberately a diagnostic command, not a benchmark campaign.  It
trains one tiny official episode, resumes it once, and runs the real
in-process/subprocess parity check at three benchmark scales.  A successful
report proves that the wiring is usable; it does not claim convergence or
generalisation.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

import torch

from .ga import GAConfig
from .official_parity import run_one_epoch_parity
from .reproduction import load_assumptions, validate_checkpoint_manifest
from .train import train_official
from .observation import ObservationBuilder


def run_smoke_gates(*, output: str | None = None, seed: int = 0,
                    parity_instances=(1, 33, 57), timeout_seconds: float = 90.0) -> dict:
    """Run deterministic train/resume/parity checks and return a JSON report."""

    temporary = tempfile.TemporaryDirectory(prefix="evorl_smoke_gates_") if output is None else None
    root = Path(output).resolve().parent if output else Path(temporary.name)
    root.mkdir(parents=True, exist_ok=True)
    checkpoint = Path(output).resolve() if output else root / "smoke.pt"
    resumed = checkpoint.with_name(checkpoint.stem + "_resume" + checkpoint.suffix)
    # Small but non-degenerate budget: generation one exercises PMX/mutation
    # and the bounded planner deadline without pretending to be the paper's
    # production campaign.
    ga = GAConfig(population_size=4, generations=1, time_limit_seconds=0.2, seed=seed)
    report = {"train": False, "resume": False, "parity": {}, "strict": False}
    try:
        train_result = train_official(
            episodes=1, seed=seed, device="cpu", output=str(checkpoint),
            protocol="benchmark_heldout", instances=(1,), ga_config=ga,
            validation_every=1, execution_mode="EvoRL-paper-repro",
        )
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        assumptions = load_assumptions()
        validate_checkpoint_manifest(
            payload, protocol="benchmark_heldout",
            assumptions_sha256=assumptions.source_sha256,
            expected_input_dim=ObservationBuilder.feature_dim,
            execution_mode="EvoRL-paper-repro",
        )
        history = payload.get("history", [])
        last = history[-1] if history else {}
        report["train"] = bool(
            payload.get("episode") == 1 and len(history) == 1
            and all(math.isfinite(float(last.get(key, 0.0)))
                    for key in ("loss", "policy_loss", "value_loss", "entropy"))
        )

        train_official(
            episodes=1, seed=seed, device="cpu", output=str(resumed),
            protocol="benchmark_heldout", instances=(1,), ga_config=ga,
            resume=str(checkpoint), validation_every=0,
            execution_mode="EvoRL-paper-repro",
        )
        resumed_payload = torch.load(resumed, map_location="cpu", weights_only=False)
        report["resume"] = bool(
            resumed_payload.get("episode") == 2
            and len(resumed_payload.get("history", [])) == 2
        )

        for instance_id in parity_instances:
            result = run_one_epoch_parity(
                checkpoint=str(checkpoint), instance_id=int(instance_id),
                simulator_seed=seed, timeout_seconds=timeout_seconds,
            )
            report["parity"][str(instance_id)] = {
                "equal": bool(result.equal),
                "differing_epochs": list(result.differing_epochs),
                "details": dict(result.details),
            }
        report["strict"] = bool(
            report["train"] and report["resume"]
            and all(value["equal"] for value in report["parity"].values())
        )
        report["checkpoint"] = str(checkpoint)
        report["resumed_checkpoint"] = str(resumed)
        return report
    finally:
        if temporary is not None and report.get("strict"):
            temporary.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run EvoRL ICAPS smoke gates")
    parser.add_argument("--output", default=None, help="checkpoint path; omit for an automatic temporary directory")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--parity-instances", default="1,33,57")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    args = parser.parse_args(argv)
    instances = tuple(int(value) for value in args.parity_instances.split(",") if value.strip())
    result = run_smoke_gates(
        output=args.output, seed=args.seed,
        parity_instances=instances, timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, sort_keys=True, default=str))
    raise SystemExit(0 if result.get("strict") else 1)


if __name__ == "__main__":
    main()
