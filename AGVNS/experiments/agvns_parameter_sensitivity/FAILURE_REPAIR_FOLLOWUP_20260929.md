# Follow-up audit: sensitivity job failures and repairs

Audit date: 2026-09-29. This supplements the historical batch reports; it does not rewrite their recorded outcomes.

## Scope and conclusion

I re-read every archived `results.jsonl` under this experiment directory: **1,574 rows across repeated runs and retries** (710 raw `SUCCESS`, 864 raw `FAILED`). These are not 1,574 unique design jobs. The most useful baseline is `20260903_141120`: 480 rows, of which 439 have usable scores, 19 failed in the GA, and 22 were raw `SUCCESS` rows with an infeasible-dispatch sentinel.

The source-level defects observed in these archives now have targeted fixes. Verification includes 62 passing regression tests and current-code dispatch replays of **41/41** audited 20260903 failure keys, **107/107** archived FILO/capacity failure snapshots, and **36/36** malformed requested-pair snapshots. These replays invoke the emergency feasibility fallback with an already-expired local deadline, then validate the complete plan. They prove route restoration, pair accounting, destination, and capacity handling for those snapshots; they do not prove GA quality or full-simulator runtime.

No sensitivity workers are running. The latest run, `20260929_155017`, was interrupted after 15 of 41 jobs started: all 15 recorded return code `-15`, 26 remained queued, and no results were finalized. Those rows are cancellations, not algorithm failures.

## Failure signatures and repairs

Counts below are archived log-signature counts. Categories overlap, and retries may repeat the same design key.

| Archived signature | Count | Cause established from code/logs | Current repair and verification |
|---|---:|---|---|
| Committed destination / route-head mismatch | 366 | Route restoration filtered old pickups using global order state but could leave their delivery at the route head. The simulator had already committed a different destination, or the vehicle was empty at that delivery factory. | Reconcile the saved route with cargo and current factory; restore the committed destination as route head; validate the simulator-visible output plan. The 41-key replay includes all 22 sentinel cases from the 20260903 audit. Route restoration and output validation regression tests pass. |
| FILO/capacity plan rejection | 151 signature hits across retries | A stale or partially restored route could violate cargo order/capacity; some rows also had malformed requested pairs. | Dispatch is transactional, checks the resulting plan, and uses a feasible complete-block fallback. All 107 matching 20260827 snapshots and all 41 20260929_100154 retry snapshots replay with no plan-validation errors. |
| Malformed requested pickup/delivery pairs | 36 | Requested IDs could remain in a restored saved route and then be inserted again, doubling pickup and delivery counts. | Remove stale actions for still-unlocated requested IDs before redispatch while preserving committed destination actions. All 36 matching archived snapshots pass; the regression test reproduces duplicate pairs and asserts one pickup plus one delivery. |
| `NoneType.delivery_item_list` | 35 | A restored route could contain a pickup with no matching delivery node; dispatch search dereferenced the missing node. | Guard the missing-delivery case and reject/skip that malformed route safely. The exact 41-key replay includes the 32 occurrences from 20260929_100154; regression coverage exercises the guard. |
| Empty post-filter GA population / `IndexError` | 23 | The diversity/fitness filter could remove every candidate, followed by access to `unique_population[0]`. | Keep the best incumbent and restore it when filtering empties the population. `test_gavnd7_keeps_incumbent_when_divergence_filter_is_empty` passes. The 19 relevant 20260903 keys are in the 41-key snapshot replay; that dispatch replay does not rerun GA. |
| Unexpected `deadline=` keyword | 8 | The deadline argument was not accepted consistently across the dispatch call chain. | Deadline is propagated through the current dispatch functions; expired-deadline and global-clock regression tests pass. |
| Concurrent log-rotation `FileNotFoundError` | 3 | Two workers could rotate the same log; one could remove the source file before the other renamed it. | Treat an already-removed rotation source as a benign race. `test_log_rotation_ignores_file_removed_by_another_worker` passes. |
| Simulator subprocess timeout | 47 signatures | Historical algorithm calls could keep searching after the 570-second algorithm budget, eventually failing the simulator subprocess. Logs include invocations around 570–596 seconds and a later subprocess timeout. | Use a monotonic global deadline and check it in dispatch, cost, and local-search loops; preserve the 570-second algorithm budget and 600-second simulator subprocess limit. Deadline regression tests pass. A full simulator canary after this repair has not been run, so end-to-end timeout behavior remains unconfirmed. |
| Outer sensitivity-job wall timeout | 251 signatures | The 20260827_144605 command explicitly set a 21,600-second (6-hour) per-job cap; 235 jobs hit it. Another 16 older rows were also runner-level timeouts. | This is a launch-time cap, separate from the algorithm budget. The runner’s `--job-timeout-seconds` is optional and defaults to no outer timeout; omit it for long instances. |
| Interrupted jobs | 15 rows in 20260929_155017 | Batch interruption sent SIGTERM after investigation began; 26 jobs had not started. | No algorithm source change applies. These must be rerun in a fresh batch if sensitivity results are needed. |

## Score, fitness, and experiment interpretation

- Infeasible simulator output now raises an error. The entry point records failures for exceptions and sentinel scores, and the aggregator classifies scores at or above `sys.maxsize` as invalid instead of including them in means.
- Nonfinite fitness is represented as unavailable in diagnostic output; previously known finite scores are retained where available. This prevents writing JSON `Infinity`; it does not claim that every internal candidate always has finite fitness.
- The current entry point selects the GA solution only when it passes plan validation and has finite fitness no worse than the validated cheapest-insertion incumbent. The old 20260903 report’s statement that the current code unconditionally overwrites the GA result is stale. Because this selection path changed, the archived 439 scores remain historical observations and should not be used to rank GA parameter quality.

## Limits and rerun status

The current source still declares `ALGO_TIME_LIMIT = 570` seconds and `MAX_RUNTIME_OF_ALGORITHM = 600` seconds. The requested artificial limits `PRE_DISPATCH_TIME_LIMIT`, `LS_MAX_TIME_PER_OP`, and `FINAL_LS_TIME_LIMIT` are absent from the AGVNS algorithm path.

The current worktree has passed:

- `python -m pytest -q tests/test_agvns_runtime_safety.py tests/test_agvns_parameter_sensitivity.py --tb=short`: **62 passed**.
- `git diff --check`: clean.
- 41/41 audited failure-key dispatch replays, 107/107 FILO/capacity replays, and 36/36 malformed-pair replays, all with final plan validation passing.

The archived sensitivity batch itself has not been resumed or rerun end to end. Repaired source and dispatch replays establish the observed code fixes; fresh full-simulator results are still required before reporting new job success rates or a new sensitivity ranking.
