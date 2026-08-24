# AGVNS Parameter Sensitivity Screening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use spml:ml-subagent-dev to implement this plan task-by-task.

**Goal:** Implement and execute the approved Taguchi L9 plus baseline AGVNS screening experiment with three seeds on 16 benchmark instances.

**Experiment directory:** `AGVNS/experiments/agvns_parameter_sensitivity/`

**Hypothesis:** The four exposed AGVNS parameters change solution quality, stability, and runtime in ways that can be estimated from a Taguchi orthogonal array.

**Validation scope:** Experiment-specific static checks plus one real simulator smoke job before the batch. The full screening batch is the runtime validation and must use the real simulator to final completion. No training/evaluation checkpoint workflow applies.

**Evaluation design:** Every job evaluates one complete simulator instance. The worker records final score, runtime, status, and raw logs. Aggregation is performed after all jobs complete; failed jobs remain visible and are never silently dropped.

**Architecture:** A versioned design matrix drives an experiment runner. Worker processes receive one configuration and one deterministic seed through environment variables, while AGVNS applies the overrides at algorithm-process startup. The runner stores isolated job workspaces and produces a manifest, raw results, runtime data, and summary tables.

---

## Shared Scaffold

### Existing infra (do not touch unless required)

- Simulator entry point: `AGVNS/main.py`
- Algorithm entry point: `AGVNS/main_algorithm.py`
- AGVNS dispatch: `AGVNS/algorithm/main.py`
- AGVNS configuration: `AGVNS/algorithm/algorithm_config.py`
- AGVNS adaptive crossover: `AGVNS/algorithm/Test_algorithm/GAVND7.py`
- Shared runtime statistics: `runtime_stats.py`
- Existing isolated parallel runner: `parallel_runner.py`

### New experiment files

- `AGVNS/experiments/agvns_parameter_sensitivity/design.py` — validated design matrix and instance/seed constants.
- `AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py` — job scheduler and worker launcher for the 800 jobs.
- `AGVNS/experiments/agvns_parameter_sensitivity/aggregate_results.py` — raw-log/runtime parser and summary generation.
- `AGVNS/experiments/agvns_parameter_sensitivity/README.md` — exact commands, output layout, and restart instructions.
- `tests/test_agvns_parameter_sensitivity.py` — deterministic unit tests for the design and aggregation helpers.

## Subtask 1: Validated screening design matrix

**Role:** Provide the immutable 9-row Taguchi design, baseline control, and fixed instance/seed schedule.

**Implementation:** Add `design.py` with typed configuration records, the approved `L9(3^4)` rows, the baseline control, the descending Set 8-to-Set 1 instance order, three repetitions, and validation functions for uniqueness, orthogonality-level counts, baseline inclusion, and expected job count.

**Unit Tests:** Verify exactly 9 Taguchi rows plus one baseline, the four factor domains, three occurrences per Taguchi level, baseline row 10, descending instance order, and 480 expected jobs.

**Expected Conclusion:** Design validation passes and rejects duplicate/out-of-domain rows.

## Subtask 2: AGVNS experiment parameter injection

**Role:** Make each worker use and report the assigned configuration without changing non-experiment behavior.

**Implementation:**

- Extend `AGVNS/algorithm/algorithm_config.py` with environment-backed `T`, population, perturbation, mutation, configuration ID, and deterministic seed values.
- Seed Python and NumPy random generators in the algorithm subprocess.
- Update `GAVND7.py` to use configurable `threshold_orders` and perturbation rate.
- Keep unrelated adaptive configuration disabled/locked for the screening override path.
- Print a machine-readable applied-configuration line in the algorithm log.
- Disable visualization and executed-route recording for sensitivity workers through an experiment-only environment flag.

**Unit Tests:** Verify valid override parsing, default behavior without overrides, invalid values fail clearly, and the adaptive ratio receives the configured T.

**Expected Conclusion:** A worker started with one design row reports exactly that row and uses the same values in the algorithm process.

## Subtask 3: Metrics and aggregation

**Role:** Convert every completed worker into analysis-ready data without losing failed jobs.

**Implementation:**

- Parse score, total distance, sum over time, total score, algorithm runtime, simulator runtime, and dispatch information from logs/runtime files.
- Join each result with configuration ID, factor values, instance ID, set ID, repetition, and seed.
- Produce `results.csv`, `summary_by_configuration.csv`, `summary_by_set.csv`, `summary_by_instance.csv`, and a JSON manifest.
- Compute mean, standard deviation, median, min/max, and confidence intervals for successful observations, while retaining failure counts.

**Unit Tests:** Parse representative success/failure logs and verify aggregation includes failed jobs and computes deterministic summaries.

**Expected Conclusion:** Aggregation produces stable CSV/JSON outputs and does not treat missing or invalid metrics as successful observations.

## Subtask 4: Screening runner and restart support

**Role:** Schedule all configuration/seed/instance jobs with isolated workspaces and bounded parallelism.

**Implementation:** Add `run_screening.py` that:

- validates the design before launch;
- creates a run manifest and immutable copy of the design;
- launches one `AGVNS/main.py` process per job with configuration and seed environment variables;
- pins workers to selected CPU cores;
- writes progress after every completed job;
- supports `--dry-run`, `--limit`, `--config-id`, `--workers`, `--cores`, `--base-seed`, and `--resume`;
- refuses to start the full batch if the smoke validation has not passed;
- preserves worker logs and runtime statistics in each isolated workspace.

**Unit Tests:** Dry-run job generation, deterministic seed mapping, configuration propagation, and resume filtering.

**Expected Conclusion:** The runner can generate exactly 480 jobs in descending set order and resume without duplicating successful jobs.

## Subtask 5: Full screening execution [INTEGRATION]

**Hypothesis:** The assembled experiment pipeline can run every approved AGVNS configuration through the complete simulator and produce auditable measurements.

**Components consumed:** `design.py`, AGVNS override path, metrics aggregation, and screening runner.

**Implementation:** Run one real smoke job, inspect its log and output files, then execute the complete 480-job screening batch with the approved 16 instances and three repetitions through tmux using 16 workers.

**Integration Tests:** A real `instance_1` smoke run with one design row must finish with `SUCCESS`, a finite score, runtime statistics, and a logged applied configuration.

**Validation:** The batch must report expected job count, per-worker final score/runtime, no silent missing jobs, and explicit failure counts. No configuration conclusion is made in this subtask.

**Expected Conclusion:** The screening dataset is complete or explicitly marked incomplete with recoverable failed jobs and all raw evidence retained.
