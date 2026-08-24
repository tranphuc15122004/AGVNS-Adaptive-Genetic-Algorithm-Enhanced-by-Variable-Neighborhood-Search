# Cross-Repository Parallel Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add EvoRL-equivalent parallel experiment execution to all seven runnable targets.

**Architecture:** A root `parallel_runner.py` provides the shared scheduler and result contract. Thin target-local `run_parallel.py` adapters select each simulator root and runtime-specific options. Legacy Python, Java, and C++ entry points are made workspace-aware through environment/configuration adapters.

**Tech Stack:** Python 3.6+, `argparse`, `subprocess`, `csv`, `json`, `unittest`; Java 8-compatible source; existing C++ Makefile.

**Spec:** `docs/superpowers/specs/2026-08-24-parallel-runner-design.md`

## Global Constraints

- Preserve existing user changes and existing single-process behavior.
- One job must never write another job's `algorithm/data_interaction` files.
- A worker result is successful only with exit code 0, `SUCCESS`, finite score, and valid runtime.
- Keep Python compatibility with the repository's Python 3.6+ convention.

### Task 1: Shared runner contract tests

**Files:**
- Create: `tests/test_parallel_runner.py`
- Test: `parallel_runner.py`

- [x] Write tests first for instance/range parsing, deterministic job seeds, worker selection, log validation, and CSV/summary persistence.
- [x] Run `python -m unittest tests/test_parallel_runner.py -v` and confirm the import fails because the shared module is not present.

### Task 2: Shared runner implementation

**Files:**
- Create: `parallel_runner.py`

- [x] Implement the tested helpers and scheduler with the common EvoRL artifact schema.
- [x] Add target adapter metadata and worker command construction without embedding target-specific algorithm logic.
- [x] Run the shared unit tests and confirm all pass.

### Task 3: Target adapters

**Files:**
- Create: `AGVNS/run_parallel.py`
- Modify: `MA/run_parallel.py`
- Modify: `TS/run_parallel.py`
- Modify: `MOEAD-TS/run_parallel.py`
- Create: `1/compiled_files/run_parallel.py`
- Create: `2/Y_final_submission/run_parallel.py`
- Create: `3/run_parallel.py`

- [x] Replace duplicated/simple runners with thin wrappers around the shared runner.
- [x] Preserve EvoRL's checkpoint validation and flags in `EvoRL/run_parallel.py`, delegating common behavior where practical.
- [x] Run `python run_parallel.py --help` from every target root.

### Task 4: Workspace-aware simulator and legacy algorithms

**Files:**
- Modify: `AGVNS/main.py`
- Modify: `AGVNS/src/conf/configs.py`
- Modify: `1/compiled_files/main.py`
- Modify: `1/compiled_files/src/conf/configs.py`
- Modify: `1/compiled_files/src/utils/json_tools.py`
- Modify: `1/source-code/src/main_algorithm.java`
- Modify: `2/Y_final_submission/main.py`
- Modify: `2/Y_final_submission/src/conf/configs.py`
- Modify: `3/main.py`
- Modify: `3/src/conf/configs.py`
- Modify: `3/src/utils/json_tools.py`

- [x] Add common runtime CLI handling to AGVNS and submissions 1/2/3.
- [x] Resolve each interaction directory from the worker environment.
- [x] Add explicit path arguments for the C++ adapter and environment-based data root for Java.
- [x] Compile the Java class and C++ target when their toolchains support it; otherwise run syntax/static checks and report the exact limitation.

### Task 5: Documentation and full verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [x] Document commands and target-specific runner locations.
- [x] Run unit tests, Python compile checks, runner help checks, and repository diff/status checks.
- [x] Review all changed files and confirm unrelated EvoRL aggregation artifacts are untouched.

## Execution Notes and Errors

- Initial `unittest discover` commands used `TS/tests` and `EvoRL/tests` while
  already inside those variant directories; rerunning with `-s tests` fixed the
  command path issue.
- The existing TS domain tests require an untracked fixture under
  `TS/algorithm/data_interaction_runs/test_tabu`; five tests remain blocked by
  missing JSON fixtures, while `test_run_parallel.py` passes.
- Top-2 smoke initially failed because NumPy removed the `numpy.Inf` alias.
  A regression test was added and the import was changed to `numpy.inf as Inf`.
- Top-3 smoke initially lacked a parent-process `SUCCESS` marker even though
  the C++ worker completed. Legacy entrypoints now print `SUCCESS` only after
  all selected simulations succeed.
- Top-1 Java smoke confirmed isolated launch and Java execution but was
  interrupted after the legacy algorithm's long late-day runtime; its partial
  batch is intentionally retained under `/tmp/top1_parallel_smoke`.
- Workspace-wide `pytest -q` cannot collect the independent repositories from
  the monorepo root: AGVNS/EvoRL lack their variant roots on `PYTHONPATH`, and
  TS is resolved together with MOEAD-TS. Variant-local runner tests and the
  new root tests pass when executed from their intended roots.
