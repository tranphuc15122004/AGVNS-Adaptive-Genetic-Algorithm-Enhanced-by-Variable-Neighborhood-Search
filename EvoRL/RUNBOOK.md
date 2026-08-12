# EvoRL paper-reproduction runbook

Run commands from this directory.  The primary baseline is trained on the
registered held-out split and follows Algorithm 1 at execution time: RPPO
seeds GA and the better RPPO/GA phenotype is selected at each epoch.
`EvoRL-ICAPS` remains an explicit policy-only ablation.

## Install and checks

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q tests
PYTHONPATH=. python -m compileall -q algorithm training src
```

The real first-epoch transport gate (official simulator versus the actual
`main_algorithm.py` child) is:

```bash
PYTHONPATH=. python - <<'PY'
from training.official_parity import run_one_epoch_parity
result = run_one_epoch_parity(
    checkpoint="checkpoints/smoke.pt", instance_id=1, simulator_seed=0,
    timeout_seconds=60,
)
print(result)
assert result.equal, result.details
PY
```

This compares the locked destination, mutable suffix, carrying stack, item
IDs, and the canonical route hash.  The generic `RuntimeParity` unit test is
not a substitute for this gate.

The compact release smoke gate combines one official training episode,
checkpoint resume, and parity at the 50/1000/4000-order scales:

```bash
PYTHONPATH=. python -m training.smoke_gates \
  --output /tmp/evorl-smoke-gates.pt \
  --parity-instances 1,33,57
```

Exit code 0 means that integration smoke passed.  It is not evidence of
convergence, all-instance completion, or a statistically significant result.

## Official ICAPS training

Before a GPU campaign, verify the host/container exposes the NVIDIA driver:

```bash
nvidia-smi
PYTHONPATH=. python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
```

`--device cuda` now fails closed when CUDA is unavailable; it never silently
converts a requested GPU run into a CPU run.

For a smoke run, use a tiny GA budget only to check the plumbing:

```bash
PYTHONPATH=. python -m training.train --mode official \
  --episodes 1 --instances 1 --ga-population 1 --ga-generations 0 \
  --ga-time-limit 0.05 --validation-every 0 --output checkpoints/smoke.pt
```

For a registered learner seed, use the paper defaults (population 20,
20 generations) and a fixed output path:

```bash
PYTHONPATH=. python -m training.train --mode official \
  --episodes 40 --seed 0 --protocol benchmark_heldout \
  --validation-every 1 --execution-mode EvoRL-paper-repro \
  --output checkpoints/evorl-paper-seed0.pt \
  --latest-output checkpoints/evorl-paper-seed0.latest.pt
```

Training can resume model, optimizer, Python RNG, and Torch RNG state:

```bash
PYTHONPATH=. python -m training.train --mode official \
  --episodes 40 --seed 0 --resume checkpoints/evorl-paper-seed0.latest.pt \
  --validation-every 1 --execution-mode EvoRL-paper-repro \
  --output checkpoints/evorl-paper-seed0.pt \
  --latest-output checkpoints/evorl-paper-seed0.latest.pt
```

## Evaluation

The checkpoint is required for a strict paper-faithful run.  Omit `--instances`
to evaluate the registered test split; pass an explicit range for a smoke
case.

```bash
EVORL_LEGACY_FALLBACK=0 EVORL_REQUIRE_CHECKPOINT=1 PYTHONPATH=. python -m training.evaluate \
  --checkpoint checkpoints/evorl-paper-seed0.pt \
  --execution-mode EvoRL-paper-repro \
  --protocol benchmark_heldout --simulator-seed 0 --instances 1 \
  --data-dir eval_runs/seed0
```

For direct simulator use, the checkpoint is explicit and heuristic fallback is
disabled by default:

```bash
PYTHONPATH=. python main.py --instances 1 --checkpoint checkpoints/evorl-paper-seed0.pt
```

`run_parallel.py` follows the same contract; pass `--checkpoint` to every
worker.  `--allow-heuristic` is reserved for compatibility/debug runs and is
not a valid baseline result.

The simulator subprocess reads the same checkpoint through
`EVORL_CHECKPOINT`; `training.evaluate` sets this automatically.  A strict
table must exclude any run with a Checker error, planner fallback, or a
checkpoint assumptions-hash mismatch.  The synthetic mode is CI only and is
not an ICAPS benchmark result.  For a quick continuation check, train one
episode, resume for one more episode, and verify that checkpoint
`episode/history` advance from 1 to 2.  A full simulator evaluation can take
longer than a unit smoke because the official process starts a child algorithm
at every 10-minute tick; inspect `evorl_trace.jsonl` for per-tick Checker and
fallback status while it runs.

Each `training.evaluate` inference also writes one simulator log per instance
under `src/output/log/`, using the same
`dpdp_<instance>_<pid>_<timestamp>.log` naming convention as the other
algorithm variants. The returned result row includes the `log_file` path
alongside the score and trace path.
