# Cross-Repository Parallel Runner Design

## Goal

Provide the same reproducible, isolated parallel experiment workflow as
`EvoRL/run_parallel.py` for all seven runnable targets in this repository:
`AGVNS`, `MA`, `TS`, `MOEAD-TS`, `1/compiled_files`, `2/Y_final_submission`,
and `3`.

## Contract

Each target exposes a local `run_parallel.py` with the common CLI:

```text
run_parallel.py [INSTANCE ...] [--instances IDS/RANGES] [--all]
                [--repetitions N] [--workers N] [--cores IDS]
                [--base-seed N] [--run-root PATH] [--python PATH]
```

Every job gets a unique workspace and log. A batch writes `manifest.json`,
incremental `results.csv`, and `summary.json`. A job is successful only when
its worker exits successfully and emits `SUCCESS`, a finite score, and a valid
simulation runtime. Interrupted batches retain completed results.

## Architecture

`parallel_runner.py` at the repository root owns parsing, job scheduling,
CPU affinity, result parsing, persistence, and summary aggregation. Each
target's `run_parallel.py` is a thin adapter that supplies the target root,
algorithm name, runtime command, and optional EvoRL checkpoint arguments.

The worker entry points accept `--instances`, `--data-dir`, `--cpu`, and
`--seed`. The Python simulator configurations resolve their interaction
directory from an environment variable so simulator and algorithm subprocesses
share the same job workspace. Submission `1` additionally reads that variable
inside its Java algorithm; submission `3` passes explicit input/output paths to
its C++ executable.

## Compatibility

- Existing single-process commands remain valid.
- No benchmark files or algorithm output directories are shared by concurrent
  jobs.
- `1/compiled_files/run_parallel.py` is the runner for submission 1 because
  that directory contains its executable simulator root.
- Checkpoint enforcement and `--allow-heuristic` remain EvoRL-only options.

## Verification

Unit tests cover common parsing, deterministic job creation, affinity/worker
selection, log validation, result persistence, and command adapters. Each
runner is checked with `--help`; Python modules are compiled; the Java source
patch and C++ source remain syntactically/build compatible where toolchains are
available.
