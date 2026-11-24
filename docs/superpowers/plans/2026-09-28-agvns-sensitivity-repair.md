# AGVNS Sensitivity Failure Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task by task. Review each test gate before the next task. Do not merge historical and repaired-run result rows.

**Goal:** Make AGVNS dispatch feasible, bound each algorithm invocation, preserve the GA result, and classify sensitivity jobs correctly before rerunning instances 57–58.

**Architecture:** Repair route state at the algorithm boundary using the simulator's current vehicle state as the source of truth. Keep the best GA solution available, validate the chosen plan before output, and propagate infeasible simulator results as failures. Run every confirmation job in a fresh isolated workspace with preserved seed and code provenance.

**Tech stack:** Python 3, pytest, JSONL/CSV, AGVNS simulator.

**Spec:** [57–58 investigation](../../../AGVNS/experiments/agvns_parameter_sensitivity/DEEP_DIVE_57_58_20260903.md); [job-level evidence](../../../AGVNS/experiments/agvns_parameter_sensitivity/ERROR_JOBS_20260903.csv).

## Verified scope and constraints

- Batch `20260903_141120`: 480 unique jobs; 439 feasible scores, 19 process failures, 22 sentinel scores. Process failures are 49:2, 50:1, 57:9, 58:7. Sentinel scores are 57:20, 58:2.
- All 22 sentinel cases have the same restored-route pattern: prior `pickup A, delivery A, pickup B` becomes `delivery A, pickup B`; the affected vehicle is at A's delivery factory with empty cargo. It violates fixed destination in 21 jobs and capacity in one.
- In all 19 process failures, final GA candidate filtering produces an empty list before `unique_population[0]` is used.
- The default AGVNS entry point calls `GAVND_7` then unconditionally replaces its result with the cheapest-insertion plan. Recorded scores cannot measure GA parameter quality.
- Set 8: 35/60 jobs have at least one algorithm call over 600 seconds; 22/60 have a call over 2,000 seconds. The declared AGVNS algorithm limit is 570 seconds. Expensive nested loops in `dispatch_nodePair()` do not check a deadline.
- `AGVNS/src/conf/configs.py` currently has a pre-existing uncommitted 6000-second simulator subprocess timeout. Preserve it while diagnosing; decide the final cap only after the algorithm meets its own budget. Do not overwrite unrelated workspace changes.
- The same legacy route-filter condition appears in MA, TS, and MOEAD-TS copies. Their exposure is **potential**, not proven by this AGVNS batch. The empty-divergence-list pattern also exists in MA's copied `GAVND7.py`; it is not MA's default dispatch.
- Existing test baseline: `pytest -q tests/test_agvns_parameter_sensitivity.py tests/test_agvns_runtime_safety.py --tb=no` gives **31 failed, 9 passed**. Most runtime-safety tests already describe desired behavior but fail against current code. Track their baseline and avoid claiming the entire suite passed after only a narrow repair.

## Files and responsibilities

| File | Responsibility |
|---|---|
| `AGVNS/algorithm/engine.py` | Restore route from prior solution and validate fixed destination/cargo before insertion; bound cheapest-insertion loops. |
| `AGVNS/algorithm/Test_algorithm/new_engine.py` | Apply a deadline and feasible fallback when inserting new pickup/delivery pairs. |
| `AGVNS/algorithm/Test_algorithm/GAVND7.py` | Keep an elite solution when mutation/divergence filters empty the population. |
| `AGVNS/algorithm/main.py` | Output the valid GA result; use CI only as an explicit validated fallback; reject invalid plans before JSON writing. |
| `AGVNS/src/simulator/simulate_environment.py` | At the already existing checker boundary, raise an infeasible-dispatch exception instead of silently returning with `sys.maxsize`. This narrow `src/` change is necessary to propagate failure. |
| `AGVNS/main.py` | Record simulator failures and sentinel scores as failures; never print final `SUCCESS` for them. |
| `AGVNS/experiments/agvns_parameter_sensitivity/aggregate_results.py` | Reclassify historical sentinel scores and exclude them from quality summaries. |
| `AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py` and `README.md` | Select explicit job keys for canaries, preserve provenance, and document only supported retry commands. |
| `tests/test_agvns_runtime_safety.py`, `tests/test_agvns_parameter_sensitivity.py` | Focused regression tests for the observed failures and rerun bookkeeping. |

## Task 1 — Make invalid simulator results unambiguously failed

Core classification condition:

```python
valid_score = score is not None and math.isfinite(score) and 0 <= score < float(sys.maxsize)
if not valid_score or "Dispatch result is infeasible" in message:
    effective_status = "FAILED"
```


- [ ] Add a failing test using `Score of instance_57: 9223372036854775807` plus `Dispatch result is infeasible`; assert parser status `FAILED`, reason `infeasible_dispatch`, and no contribution to score means.
- [ ] Run that test alone and confirm it fails on current `parse_worker_log_text()`.
- [ ] In `SimulateEnvironment.run()`, replace the checker-failure `return` with `raise RuntimeError("infeasible dispatch")`. In `AGVNS/main.py`, catch the propagated error, record `FAILED`, and ensure no final `SUCCESS` marker. Also reject `score >= sys.maxsize` as a defensive guard.
- [ ] Update `aggregate_results.py` so historical rows with `score >= float(sys.maxsize)` or nonfinite scores are classified invalid before `_group_summary()`. Preserve the raw score and original runner status in the raw JSONL; emit a separate effective status/reason in reports.
- [ ] Verify the new parser test, `test_simulator_does_not_report_infeasible_dispatch_as_success`, and a small historical fixture containing one feasible score, one sentinel, and one process failure. Expected summary: one feasible score, two failures.

## Task 2 — Reconcile restored routes with physical vehicle state

Required invariant for every reconstructed plan:

```python
if vehicle.des is not None:
    assert route and route[0].id == vehicle.des.id
    assert route[0].arrive_time == vehicle.des.arrive_time
assert isFeasible(route, vehicle.carrying_items, vehicle.board_capacity)
```

The implementation must check item identity and position as well as factory ID; a same-factory node with different items is not automatically the committed destination.


- [ ] Add three failing route tests based on the saved cases: 57 C1/R1 V_27 (wrong destination), 57 C7/R3 V_28 (empty cargo plus stale delivery), and 58 C1/R2 V_30 (wrong destination). Use small synthetic `solution.json`, `Vehicle`, `Node`, and `OrderItem` fixtures; assert that `vehicle.des` is the first node when present, no delivery action is emitted for an item absent from cargo and already at its delivery factory, and future pickup/delivery pairs remain ordered.
- [ ] Add counterexamples: an item physically carried must retain its future delivery; an item still awaiting pickup at another factory must retain both pickup and delivery; a multi-item `p2/d2` block must not lose individual item IDs.
- [ ] Refactor `restore_scene_with_single_node()` in `AGVNS/algorithm/engine.py` so it uses each vehicle's `carrying_items`, `cur_factory_id`, and `des` when pruning the persisted route. Do not use membership in the global `id_to_ongoing_items` alone as proof that a pickup was physically served. Reconcile the already serviced prefix; seed the committed `des` node as the first planned node when needed, without duplicating its items.
- [ ] Before writing output, validate per vehicle: fixed destination ID and arrival time, no delivery before its pickup or initial cargo, capacity, LIFO, and every newly assigned item represented exactly once. If reconciliation is ambiguous, fail with vehicle/item IDs rather than emitting a superficially successful invalid plan.
- [ ] Run the new route tests and the existing destination-prefix/plan-validator tests in `tests/test_agvns_runtime_safety.py`. Replay the saved input/output snapshots read-only to confirm the repaired route head is the simulator's committed destination in all 22 former sentinel cases.

## Task 3 — Preserve the incumbent and actually output the GA result

The final selection must keep the incumbent in the candidate set:

```python
candidates = remove_similar_individuals(population + [copy.deepcopy(best_solution)], threshold=0.0)
within_delta = [c for c in candidates if c.fitness < best_solution.fitness + config.addDelta]
selected = min(within_delta, key=lambda c: c.fitness) if within_delta else best_solution
```


- [ ] Run existing `test_gavnd7_keeps_incumbent_when_divergence_filter_is_empty`; it currently fails. Add a test in which every member of the final population is worse than the saved best by more than `addDelta`, and assert no `IndexError` and returned fitness no worse than the saved best.
- [ ] Keep a deep-copied elite candidate through the final deduplication/filtering step in `GAVND7.py`. Include the elite in the final candidate set or return it directly when the filtered set is empty; avoid modulo or index access on an empty list. Log the fallback count.
- [ ] Add an entry-point test where `GAVND_7()` returns a route distinct from the CI route. Assert that the route written by `AGVNS/algorithm/main.py` is the GA route when valid. Remove the unconditional second `best_chromosome = Chromosome(copy_vehicleid_to_plan, ...)`. If GA returns no feasible result, use a **validated** CI incumbent and record that fallback in the job log/metadata.
- [ ] Run these tests and one small-instance simulator canary. Verify its output route matches the selected chromosome and the simulator checker accepts it.

## Task 4 — Enforce the 570-second algorithm budget without dropping orders

The innermost search must observe the same absolute monotonic deadline as the caller:

```python
for vehicle_id, vehicle in id_to_vehicle.items():
    if time.monotonic() >= deadline:
        return isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList
    for pickup_position in range(insert_pos, node_list_size + 1):
        if time.monotonic() >= deadline:
            return isExhausive, bestInsertVehicleID, bestInsertPosI, bestInsertPosJ, bestNodeList
        # Check again before each candidate delivery position and cost call.
```


- [ ] Add a failing test with an already-expired deadline for `dispatch_nodePair()` and one for `new_dispatch_new_orders()`; assert fast return, unchanged route on failure, and an explicit failure when no feasible insertion exists.
- [ ] Pass a monotonic absolute deadline from `algorithm/main.py` into pre-GA dispatch and `dispatch_nodePair()`. Check it inside vehicle/position loops and before costly route-cost evaluations. Reserve time for output validation and JSON writing. If CI runs out of time, switch to a bounded feasible insertion; if no complete feasible plan can be constructed, fail the invocation rather than silently omitting an order.
- [ ] Confirm fallback insertion cannot insert ahead of `vehicle.des` and cannot violate capacity/LIFO. Reuse existing deadline and destination tests in `tests/test_agvns_runtime_safety.py` where they match the selected interface.
- [ ] In canaries, record maximum `Thoi gian thuc hien thuat toan` per dispatch. Acceptance: no invocation exceeds the competition's 600-second subprocess window; the 570-second internal target leaves output overhead. If a specific cost operation cannot be interrupted safely, change that operation's bound before rerunning all set-8 jobs.

## Task 5 — Make retries and summaries reproducible

After the selector is implemented, write `canary_jobs.csv` with these seven exact keys; they cover both sentinel manifestations, both `IndexError` instances, and one previously valid control per instance:

```csv
configuration_id,instance_id,repetition
1,57,1
7,57,3
10,57,1
9,57,1
1,58,2
10,58,1
9,58,2
```

Run the canary batch in a new output directory:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py \
  --execute --job-list AGVNS/experiments/agvns_parameter_sensitivity/canary_jobs.csv \
  --base-seed 20260824 --workers 4 --cores 0,1,2,3
```


- [ ] Add a test for an explicit job-key CSV containing `(configuration_id, instance_id, repetition)`. Reject duplicate or out-of-design keys and preserve the original seed formula.
- [ ] Extend `run_screening.py` with a job-list selector for canaries and targeted retries, always creating a new run directory. Put selected keys, base seed, code revision plus dirty-worktree fingerprint, timeout settings, and command in the manifest. Never append repaired results into `20260903_141120/results.jsonl`.
- [ ] Update `README.md`: the current `--retry-timeouts-from` and `--job-timeout-seconds` examples are not accepted by the current parser. Document the implemented job-list command and an all-instance `57,58` command.
- [ ] Add a duplicate-key aggregation test so a rerun cannot silently double-weight a configuration/instance/seed. Keep old and new batches separate in every analysis table.

## Task 6 — Verification and rerun gate

Start with the existing fast tests; report the full-suite baseline separately:

```bash
pytest -q tests/test_agvns_parameter_sensitivity.py
pytest -q tests/test_agvns_runtime_safety.py -k "gavnd7_keeps_incumbent or restore_scene or simulator_does_not_report_infeasible or dispatch_node_pair_returns_without_work"
```


- [ ] Run focused route, GA, status, deadline, and runner tests; compare the full suite with the recorded **31 failed / 9 passed** baseline and document any remaining failures by cause.
- [ ] Run short single-epoch replays from retained JSON first: 57 C1/R1, 57 C7/R3, 58 C1/R2, and an empty-population case from 57 C10/R1 or 58 C10/R1. Check exact destination, item accounting, capacity/LIFO, and bounded runtime.
- [ ] Run one full simulator canary of each failure class plus one formerly valid control, using fresh workspaces and original seeds. Stop the expansion if a canary remains invalid or exceeds the runtime target.
- [ ] After canaries pass, rerun **all 30 jobs for instance 57 and all 30 for instance 58** under the same repaired code. Target 60/60 feasible scores, zero `IndexError`, zero sentinel, and no missing/duplicate job keys. The old batch consumed about **2,120.5 CPU-hours** for these 60 jobs; at 16 cores, **132.5 hours is only a historical lower bound**, and the repaired runtime is unknown.
- [ ] If the goal is a publishable sensitivity ranking, rerun the full **480-job** design under the repaired output path. The 439 old feasible rows cannot be combined with new rows as estimates of GA parameter effects. Recompute configuration and Taguchi summaries only from one coherent code revision.

## Review gates

- The route fix is accepted only when each former sentinel fixture produces a valid route, including 57 C7/R3's capacity case.
- The GA fix is accepted only when the saved best survives an empty divergence filter and a distinct valid GA result reaches output.
- The timeout fix is accepted only when every canary stays below the simulator's subprocess limit with complete order assignment.
- The rerun is accepted only when every job has one unambiguous effective status and the manifest identifies the exact code and seed schedule.
