"""Checkpoint and candidate-mask smoke evaluator."""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import random
from pathlib import Path

import torch

from src.utils.log_utils import ini_logger, remove_file_handler_of_logging
from src.utils.logging_engine import logger

from .rppo import RPPOPolicy
from .reproduction import load_assumptions, split_instances, validate_checkpoint_manifest


def _trace_diagnostics(trace_file: Path, *, epoch_budget_seconds: float = 570.0) -> dict:
    """Parse strict-run telemetry without treating a partial trace as valid."""

    trace_epochs = 0
    trace_invalid = []
    wall_seconds = []
    try:
        with trace_file.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                trace_epochs += 1
                record = json.loads(line)
                if not record.get("checker_precondition", False):
                    trace_invalid.append({"epoch": record.get("epoch"), "reason": "checker_precondition"})
                if record.get("validator_errors"):
                    trace_invalid.append({"epoch": record.get("epoch"), "reason": "validator_errors", "errors": record.get("validator_errors")})
                deferred = record.get("deferred_item_ids") or record.get("deferred")
                if deferred:
                    trace_invalid.append({"epoch": record.get("epoch"), "reason": "deferred", "items": deferred})
                if record.get("wall_seconds") is not None:
                    wall = float(record["wall_seconds"])
                    wall_seconds.append(wall)
                    if wall > float(epoch_budget_seconds):
                        trace_invalid.append({"epoch": record.get("epoch"), "reason": "epoch_timeout", "wall_seconds": wall})
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        trace_invalid.append({"reason": "malformed_trace", "error": str(exc)})
    ordered = sorted(wall_seconds)
    percentile = lambda fraction: ordered[min(len(ordered) - 1, int(fraction * (len(ordered) - 1)))] if ordered else None
    return {
        "trace_epochs": trace_epochs,
        "trace_invalid": trace_invalid,
        "trace_p50_wall_seconds": percentile(0.50),
        "trace_p95_wall_seconds": percentile(0.95),
        "trace_max_wall_seconds": max(wall_seconds) if wall_seconds else None,
    }


def evaluate_checkpoint(path: str, *, device: str = "cpu") -> dict:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    policy = RPPOPolicy(
        checkpoint["input_dim"], checkpoint.get("hidden_dim", 128),
        recurrent=bool(checkpoint.get("recurrent", True)),
    ).to(device if device == "cpu" or torch.cuda.is_available() else "cpu")
    policy.load_state_dict(checkpoint["model"])
    features = torch.zeros(1, 8, checkpoint["input_dim"], device=next(policy.parameters()).device)
    mask = torch.ones(1, 8, dtype=torch.bool, device=features.device)
    action, _, _, _, _ = policy.act(features, mask, deterministic=True)
    return {"checkpoint": str(Path(path)), "greedy_action": int(action.item()), "device": str(features.device)}


def evaluate_instances(instances, *, checkpoint: str | None = None, data_dir: str | None = None,
                       protocol: str = "benchmark_heldout", simulator_seed: int = 0,
                       execution_mode: str = "EvoRL-paper-repro"):
    """Run official simulator instances using the same subprocess entrypoint."""
    from src.conf.configs import Configs
    from src.simulator.simulate_api import simulate

    if checkpoint:
        checkpoint_data = torch.load(checkpoint, map_location="cpu", weights_only=False)
        from .observation import ObservationBuilder
        validate_checkpoint_manifest(
            checkpoint_data, protocol=protocol,
            assumptions_sha256=load_assumptions().source_sha256,
            expected_input_dim=ObservationBuilder.feature_dim,
            execution_mode=execution_mode,
        )
        os.environ["EVORL_CHECKPOINT"] = os.path.abspath(checkpoint)
    os.environ["EVORL_PROTOCOL"] = str(protocol)
    os.environ["EVORL_EXECUTION_MODE"] = str(execution_mode)
    os.environ["EVORL_LEGACY_FALLBACK"] = "0"
    os.environ["EVORL_REQUIRE_CHECKPOINT"] = "1" if checkpoint else "0"
    if data_dir:
        os.environ["MA_DATA_INTERACTION_DIR"] = os.path.abspath(data_dir)
        Configs.configure_algorithm_data_dir(data_dir)
    else:
        os.environ.pop("EVORL_TRACE_FILE", None)
    results = []
    for instance_id in instances:
        resolved_data_dir = data_dir
        if data_dir:
            # One simulator episode owns one solution/output stream.  Sharing
            # a directory across instances is a common source of restored-route
            # and hidden-state leakage, even when the algorithm itself is
            # deterministic.
            resolved_data_dir = str(Path(data_dir) / f"instance_{int(instance_id)}")
            Path(resolved_data_dir).mkdir(parents=True, exist_ok=True)
            os.environ["MA_DATA_INTERACTION_DIR"] = os.path.abspath(resolved_data_dir)
            Configs.configure_algorithm_data_dir(resolved_data_dir)
            os.environ["EVORL_TRACE_FILE"] = str(Path(resolved_data_dir) / "evorl_trace.jsonl")
        os.environ["EVORL_EPISODE_ID"] = f"{protocol}-instance-{int(instance_id)}-seed-{int(simulator_seed)}"
        # Keep inference runs auditable in the same format as the baseline
        # simulators.  Mỗi instance có một file log riêng để dễ truy vết.
        instance_name = f"instance_{int(instance_id)}"
        log_file_name = (
            f"dpdp_{instance_name}_{os.getpid()}_"
            f"{datetime.datetime.now().strftime('%y%m%d%H%M%S%f')}.log"
        )
        ini_logger(log_file_name)
        log_file = Path(Configs.output_folder) / "log" / log_file_name
        logger.info(f"Start EvoRL inference for {instance_name}")
        logger.info(f"Checkpoint: {os.environ.get('EVORL_CHECKPOINT', '<none>')}")
        logger.info(f"Protocol: {protocol}, execution mode: {execution_mode}, seed: {simulator_seed}")
        logger.info(f"Data interaction directory: {Configs.algorithm_data_interaction_folder_path}")
        try:
            score, elapsed = simulate(
                Configs.factory_info_file,
                Configs.route_info_file,
                instance_name,
                simulator_seed=int(simulator_seed),
            )
            numeric_score = float(score)
            # The official simulator uses sys.maxsize as its failure score when
            # Checker rejects a dispatch.  Keep the row for diagnostics, but mark
            # it so strict benchmark aggregation can exclude it.
            checker_failed = not math.isfinite(numeric_score) or numeric_score >= float(2**62)
            trace_file = (
                Path(resolved_data_dir) / "evorl_trace.jsonl"
                if resolved_data_dir else None
            )
            if trace_file and trace_file.exists():
                trace_info = _trace_diagnostics(trace_file)
            else:
                trace_info = {
                    "trace_epochs": 0, "trace_invalid": [],
                    "trace_p50_wall_seconds": None,
                    "trace_p95_wall_seconds": None,
                    "trace_max_wall_seconds": None,
                }
            trace_epochs = trace_info["trace_epochs"]
            trace_invalid = trace_info["trace_invalid"]
            strict_valid = not checker_failed and not trace_invalid and trace_epochs > 0
            logger.info(
                f"Score of {instance_name}: {numeric_score}, runtime: {float(elapsed):.6f}s, "
                f"trace_epochs: {trace_epochs}, strict_valid: {strict_valid}"
            )
            if checker_failed:
                logger.error(f"Checker rejected {instance_name} or returned a failure score")
            if trace_invalid:
                logger.error(f"Trace validation errors for {instance_name}: {trace_invalid}")
            results.append({
                "instance": int(instance_id), "score": numeric_score,
                "elapsed_seconds": float(elapsed), "checker_failed": checker_failed,
                "trace_file": str(trace_file) if trace_file else None,
                "log_file": str(log_file),
                "trace_epochs": trace_epochs,
                "trace_invalid": trace_invalid,
                "trace_p50_wall_seconds": trace_info["trace_p50_wall_seconds"],
                "trace_p95_wall_seconds": trace_info["trace_p95_wall_seconds"],
                "trace_max_wall_seconds": trace_info["trace_max_wall_seconds"],
                "strict_valid": strict_valid,
            })
        except Exception:
            logger.exception(f"Failed EvoRL inference for {instance_name}")
            raise
        finally:
            remove_file_handler_of_logging(log_file_name)
    return results


def evaluate_benchmark(
    *,
    checkpoint: str,
    protocol: str = "benchmark_heldout",
    simulator_seed: int = 0,
    data_dir: str | None = None,
    execution_mode: str = "EvoRL-paper-repro",
) -> dict:
    """Evaluate a checkpoint and return a reproducibility-tagged report."""

    split = split_instances(protocol=protocol)
    instances = split["test"]
    results = []
    for instance_id in instances:
        os.environ["EVORL_EPISODE_ID"] = f"{protocol}-instance-{instance_id}-seed-{simulator_seed}"
        os.environ["EVORL_RANDOM_SEED"] = str(int(simulator_seed))
        results.extend(evaluate_instances(
            (instance_id,), checkpoint=checkpoint, data_dir=data_dir,
            protocol=protocol, simulator_seed=simulator_seed,
            execution_mode=execution_mode,
        ))
    valid_scores = [row["score"] for row in results if row.get("strict_valid", False)]
    checker_failures = sum(1 for row in results if row["checker_failed"])
    strict_failures = sum(1 for row in results if not row.get("strict_valid", False))
    return {
        "checkpoint": os.path.abspath(checkpoint), "protocol": protocol,
        "simulator_seed": int(simulator_seed), "instances": list(instances),
        "scores": results,
        "mean_score": sum(valid_scores) / len(valid_scores) if valid_scores and not strict_failures else None,
        "strict_valid": strict_failures == 0,
        "checker_failures": checker_failures,
        "strict_failures": strict_failures,
        "assumptions_sha256": load_assumptions().source_sha256,
    }


def aggregate_seed_reports(reports, *, bootstrap_samples: int = 2000, seed: int = 0) -> dict:
    """Aggregate completed seed reports without hiding invalid runs.

    ``reports`` is a sequence returned by :func:`evaluate_benchmark`.  A
    strict mean/CI is produced only when every report is valid; invalid
    Checker runs remain visible in ``invalid_reports`` for diagnosis.
    """

    invalid = [report for report in reports if not report.get("strict_valid", False)]
    means = [float(report["mean_score"]) for report in reports if report.get("strict_valid") and report.get("mean_score") is not None]
    if invalid or not means:
        return {
            "strict_valid": False, "seed_count": len(reports),
            "invalid_reports": len(invalid), "mean": None, "bootstrap_ci95": None,
        }
    rng = random.Random(seed)
    bootstrap = []
    for _ in range(max(1, int(bootstrap_samples))):
        sample = [means[rng.randrange(len(means))] for _ in means]
        bootstrap.append(sum(sample) / len(sample))
    bootstrap.sort()
    low = bootstrap[int(0.025 * (len(bootstrap) - 1))]
    high = bootstrap[int(0.975 * (len(bootstrap) - 1))]
    return {
        "strict_valid": True, "seed_count": len(reports),
        "invalid_reports": 0, "mean": sum(means) / len(means),
        "std": (sum((value - sum(means) / len(means)) ** 2 for value in means) / max(1, len(means) - 1)) ** 0.5,
        "bootstrap_ci95": (low, high),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--instances", default="", help="IDs/ranges, e.g. 1-8,17; omit for checkpoint smoke")
    parser.add_argument("--data-dir")
    parser.add_argument("--protocol", choices=("benchmark_heldout", "paper_transductive"), default="benchmark_heldout")
    parser.add_argument("--simulator-seed", type=int, default=0)
    parser.add_argument(
        "--execution-mode", choices=("EvoRL-ICAPS", "EvoRL-paper-repro"),
        default="EvoRL-paper-repro",
    )
    args = parser.parse_args(argv)
    if args.instances:
        instances = []
        for part in args.instances.split(","):
            if "-" in part:
                start, end = (int(value) for value in part.split("-", 1))
                instances.extend(range(start, end + 1))
            else:
                instances.append(int(part))
        print(evaluate_instances(
            instances, checkpoint=args.checkpoint, data_dir=args.data_dir,
            protocol=args.protocol, simulator_seed=args.simulator_seed,
            execution_mode=args.execution_mode,
        ))
    else:
        print(evaluate_benchmark(
            checkpoint=args.checkpoint, protocol=args.protocol,
            simulator_seed=args.simulator_seed, data_dir=args.data_dir,
            execution_mode=args.execution_mode,
        ))


if __name__ == "__main__":
    main()
