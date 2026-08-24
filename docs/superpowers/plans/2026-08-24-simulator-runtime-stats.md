# Simulator Runtime Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a consistent per-instance runtime CSV/JSON report to all eight simulator entrypoints and align parallel summary aggregates.

**Architecture:** A root-level `runtime_stats.py` owns the schema, atomic persistence, and aggregate calculations. Each simulator `main.py` supplies only its algorithm name, data directory, seed, score, and elapsed values; existing simulator APIs and subprocess contracts remain unchanged. The shared parallel runner and EvoRL runner expose the same runtime aggregate fields in `summary.json`.

**Tech Stack:** Python standard library (`csv`, `json`, `datetime`, `statistics`, `os.replace`), existing unittest/pytest tests, existing simulator entrypoints.

**Spec:** `docs/superpowers/specs/2026-08-24-simulator-runtime-stats-design.md`

## Global Constraints

- Keep the existing `SUCCESS` stdout contract and non-zero exit behavior for failed instances.
- Measure complete per-instance wall runtime with a monotonic clock.
- Keep Python 3.6-compatible standard-library code in the shared collector.
- Do not modify simulator score calculation or JSON input/output formats.
- Write reports under the worker-owned data directory by default so parallel jobs cannot overwrite one another.

---

### Task 1: Runtime statistics collector

**Files:**
- Create: `runtime_stats.py`
- Test: `tests/test_runtime_stats.py`

**Interfaces:**
- Produces `RuntimeStats(stats_file, algorithm, seed, pid=None)`.
- Produces `RuntimeStats.start_instance(instance_id) -> str`.
- Produces `RuntimeStats.record(instance_id, status, score=None, runtime_seconds=None, simulator_runtime_seconds=None, started_at_utc=None, finished_at_utc=None, error=None)`.
- Produces `RuntimeStats.csv_path`, `RuntimeStats.json_path`, and `RuntimeStats.write()`.

- [x] **Step 1: Write failing tests** for CSV/JSON creation, aggregate values, failed rows, custom paths, and incremental persistence.
- [x] **Step 2: Run `python3 -m unittest tests/test_runtime_stats.py -v` and confirm failure because the collector is missing.
- [x] **Step 3: Implement the collector with normalized numeric values, UTC timestamps, atomic CSV/JSON writes, and population standard deviation.
- [x] **Step 4: Run the focused test and confirm it passes.
- [x] **Step 5: Run the existing root parallel-runner tests to catch import/schema regressions.

### Task 2: Serial simulator integration

**Files:**
- Modify: `AGVNS/main.py`, `MA/main.py`, `TS/main.py`, `MOEAD-TS/main.py`, `EvoRL/main.py`
- Modify: `1/compiled_files/main.py`, `2/Y_final_submission/main.py`, `3/main.py`
- Test: `tests/test_simulator_entrypoints.py`

**Interfaces:**
- Each entrypoint accepts `--stats-file`.
- Each entrypoint defaults to `<Configs.algorithm_data_interaction_folder_path>/runtime_stats.csv`.
- Each completed instance records `runtime_seconds`; TS, MOEAD-TS, and EvoRL also record the simulator API's returned elapsed value.

- [x] **Step 1: Add failing integration tests** that inspect each entrypoint's parser for `--stats-file` and exercise the shared recording helper with success and failure paths.
- [x] **Step 2: Run the focused tests and confirm they fail for the current entrypoints.
- [x] **Step 3: Add root-path imports, CLI arguments, collector initialization, per-instance success/failure records, and final report logging to all eight entrypoints.
- [x] **Step 4: Run the focused tests and confirm all entrypoints pass the contract checks.
- [x] **Step 5: Run `python3 -m py_compile` over all modified simulator files.

### Task 3: Parallel summary aggregates

**Files:**
- Modify: `parallel_runner.py`
- Modify: `EvoRL/run_parallel.py`
- Test: `tests/test_parallel_runner.py`

**Interfaces:**
- `summary.json.per_instance[instance]` includes min/max/mean/standard-deviation simulation runtime and mean wall runtime.
- Top-level summary includes min/max/mean/standard-deviation successful simulation runtime.

- [x] **Step 1: Add failing summary assertions for the new runtime aggregate fields.
- [x] **Step 2: Run the focused test and confirm the missing fields fail.
- [x] **Step 3: Add a small aggregate helper and use it in both runner implementations without changing result-row fields.
- [x] **Step 4: Run all parallel-runner tests and confirm they pass.

### Task 4: Documentation and verification

**Files:**
- Modify: `README.md`, `AGENTS.md`

- [x] **Step 1: Document default report paths, CSV/JSON schema, and `--stats-file` examples.
- [x] **Step 2: Run all targeted tests, syntax checks, CLI help checks, and `git diff --check`.
- [x] **Step 3: Run one representative simulator instance and verify both runtime report files and their per-instance row.
- [x] **Step 4: Review the complete diff and report any unrelated pre-existing changes separately.
