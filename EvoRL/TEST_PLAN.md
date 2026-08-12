# EvoRL-ICAPS verification and acceptance test plan

## 1. Purpose and claim boundary

This document is the release contract for an EvoRL implementation that can be
trained and deployed on the original ICAPS DPDP simulator.  It turns the
implementation plan into executable tests, trace artifacts, and binary
acceptance gates.

There are two deliberately distinct modes:

| Mode | Claim |
| --- | --- |
| EvoRL-paper-repro | The primary paper-faithful contract.  RPPO seeds GA, the better phenotype under Eq. (33) is executed, and the remaining population supplies pseudo-feedback. |
| EvoRL-ICAPS | Explicit policy-only deployment ablation; GA remains a teacher during training but is not run online. |

The project must not claim an exact byte-for-byte reproduction of the paper:
the paper does not publish a complete network, hyperparameters, queue
estimator, data split, or enough information to resolve every internal
ambiguity.  It can claim paper conformance only for behavior recorded in
PAPER_CONFORMANCE.md and paper_assumptions.yaml.

The scope is intentionally narrow.  DEFER, AGVNS/VNS operators, a stronger
global planner, and hidden-state persistence are not acceptance requirements
for EvoRL-ICAPS v1.  They are separate experiments after this contract passes.

## 2. Non-negotiable test rules

1. The official ICAPS Checker is the final feasibility oracle.
2. The official Evaluator and simulator history are the final score oracle.
   A projected evaluator may be used for planning or shaping, but never as the
   sole final oracle.
3. A strict run has legacy fallback disabled.  A Checker rejection, planner
   fallback, missing checkpoint, non-finite value, or timeout invalidates that
   run; it cannot be hidden by averaging.
4. Every test case has a fixed seed, fixture version, and expected oracle.
   Random/property tests save the failing seed and a minimized fixture.
5. Tests must distinguish:
   - paper-explicit: directly stated in the paper;
   - paper-assumption: frozen in paper_assumptions.yaml because the paper is
     silent or ambiguous;
   - icaps-adapter: the smallest behavior needed to satisfy the original
     simulator and Checker.
6. Test data from held-out benchmark order streams may not be read by
   training, normalization, early stopping, teacher generation, or
   hyperparameter selection in benchmark_heldout mode.

## 3. Test fixtures, oracles, and required traces

### 3.1 Fixture classes

The suite must contain all four fixture classes below.

| Fixture | Purpose | Required contents |
| --- | --- | --- |
| Hand-built canonical state | Fast deterministic unit and property tests. | 1-3 factories, explicit route map, 1-3 vehicles, immutable DTOs, expected route and score by hand. |
| Official mini-instance | Exercise the real simulator, Checker, JSON boundary, and Evaluator in a temporary data directory. | Generated ICAPS-format order/vehicle files, a subset of the real factory/route metadata, deterministic simulator seed. |
| Recorded official snapshot | Regression for hard dynamic states. | Input payload, accepted plan, item/vehicle state, current time, expected normalized dispatch payload and history digest. |
| Benchmark scenario | Performance and scientific evaluation only. | The eight ICAPS workload groups and the registered train/validation/test manifest. |

The mini-instance generator must create real simulator input files, not a
mock-only environment.  Synthetic episodes may appear in unit/gradient smoke
tests, but never as evidence of ICAPS trainability.

### 3.2 Oracle hierarchy

For every scenario, record which oracle decides pass/fail:

1. hand calculation for a small fixture;
2. canonical SolutionValidator as a precondition;
3. official Checker for every dispatch;
4. official Evaluator for terminal score;
5. in-process/subprocess parity trace for transport correctness.

The projected evaluator must be calibrated against the official Evaluator at
the terminal state.  A test must fail if its full-route estimate omits a
committed destination, carrying stack, service time, original-order completion,
or a route suffix.

### 3.3 Required epoch trace

Every official integration, training, and inference run must emit a
machine-readable trace with:

- run ID, code revision, manifest hash, device, learner seed, simulator seed;
- episode ID, monotonic tick ID, input and accepted-route hashes;
- ordered atomic IDs, action masks, sampled/greedy vehicle assignments,
  log-probabilities, values, and policy hidden-state hash if recurrence is
  enabled;
- policy plan H, GA initial population, every GA generation, selected Xi,
  decoder/version hash, and all fallback counters;
- Checker result, current time, vehicle destination/carrying/route state,
  generated/ongoing/completed item sets, history hash, official score
  components, and per-epoch wall time;
- actual reward components, pseudo-reward/confidence components, transition
  type, loss components, finite-gradient check, and checkpoint ID.

The trace schema is versioned.  A missing required field fails strict mode.

## 4. Test layout and execution lanes

Recommended test layout:

~~~text
tests/
  evorl/
    test_domain_contract.py
    test_objective_and_reward.py
    test_decoder_and_policy.py
    test_ga_conformance.py
    test_runtime_parity.py
    test_data_protocol.py
    test_training_health.py
    test_scale_smoke.py
  fixtures/
    mini_icaps/
    recorded_snapshots/
    golden_traces/
~~~

| Lane | Frequency | Scope | Must pass before |
| --- | --- | --- | --- |
| Fast CI | Every change | Unit, property, mini fixture, numerical PPO tests. | Merge. |
| Official integration | Daily and before a training run | Real mini instance, route round-trip, parity, checkpoint/resume. | Any training campaign. |
| Scale preflight | Before each model/config freeze | One representative instance from each of eight scales. | Held-out evaluation. |
| Release campaign | Frozen code/config only | All 64 cases and multi-seed report. | Any result table or comparison claim. |

## 5. Domain and ICAPS-adaptation scenario matrix

All tests in this section are required for both training and inference paths.

| ID | Label | Scenario | Oracle and pass criterion |
| --- | --- | --- | --- |
| D-01 | icaps-adapter | Immutable DTO boundary: deliberately mutate policy input after snapshot. | Simulator-owned item, vehicle, factory, route, and history hashes are unchanged. |
| D-02 | icaps-adapter | Canonical route -> legacy Node/JSON -> restored canonical route round trip. | Destination and suffix are represented exactly once; route hash and item coverage are unchanged. |
| D-03 | icaps-adapter | Same order items arrive in shuffled input order. | Atomic chunks are identical after canonical numeric item sorting. |
| D-04 | icaps-adapter | Demand exactly capacity, just above capacity, multi-item order, and multiple oversized chunks. | A fitting original order is never split; oversized chunks are each <= capacity; exact item coverage holds. |
| D-05 | icaps-adapter | Multi-item original order and chunks delivered by different vehicles/times. | Tardiness is charged once at the latest original-order completion, matching official Evaluator. |
| D-06 | icaps-adapter | Nested pickup/delivery stack and delivery attempted in non-LIFO order. | Valid route passes Validator and Checker; invalid route is rejected by both. |
| D-07 | icaps-adapter | Vehicle already carrying items, with capacity nearly full. | Mask contains only actions which common decoder and Checker accept; load never exceeds capacity. |
| D-08 | icaps-adapter | Vehicle in transit to a locked destination with an accepted suffix. | Decoder never mutates destination/carrying/committed prefix; only mutable suffix changes. |
| D-09 | icaps-adapter | Duplicate destination node in historical solution, including a same-factory suffix. | Canonicalization removes only the duplicate; merge cannot add or remove locked work. |
| D-10 | icaps-adapter | Pickup and delivery at the same factory, empty route, and multiple operations at one factory. | No duplicate item/node occurs after merge/output; every vehicle key is present; Checker accepts. |
| D-11 | icaps-adapter | Deadline equality, overdue allocated order, overdue unallocated order, and no-new-order tick. | Equality has zero tardiness; allocated late order remains valid; expired unallocated order causes strict failure. |
| D-12 | icaps-adapter | An unplanned generated item survives two or more epochs without a new-order diff. | It remains in the candidate set until accepted/picked; it never vanishes or duplicates. |
| D-13 | icaps-adapter | Unknown vehicle, missing vehicle route, duplicate pickup, missing delivery, and nonempty terminal stack. | Canonical validator rejects every case that Checker rejects; any intentional validator superset is logged and cannot enter mask. |
| D-14 | icaps-adapter | Two or more vehicles contend for one dock with load/unload times and tight deadlines. | Official simulator determines execution/history; official score and deadline equality agree with golden values. |
| D-15 | icaps-adapter | 1,000 randomized valid/invalid small states, including destination/carrying states. | Every decoder-produced plan passes Checker; every selected masked action has a valid decoded phenotype; failure stores seed. |
| D-16 | icaps-adapter | No feasible action for a newly due item. | Strict inference fails diagnostically without emitting malformed JSON or silently calling a legacy algorithm. |

The implementation must add a direct differential test between
SolutionValidator and Checker.  Validator may reject a conservative superset
of plans, but it may not mark an action feasible if the common decoder and
Checker reject it.

## 6. Objective, reward, and PPO-correctness scenario matrix

| ID | Label | Scenario | Oracle and pass criterion |
| --- | --- | --- | --- |
| R-01 | icaps-adapter | Full route includes current location, committed destination, service time, carrying delivery, and suffix. | Projected full-route score matches a hand calculation and terminal official Evaluator within tolerance. |
| R-02 | icaps-adapter | Two plans differ only in the committed destination leg. | Their projected cost, insertion delta, GA ranking, and reward differ in the expected direction. |
| R-03 | paper-explicit | Deadline hit, deadline miss, distance change, and terminal transition. | Eq. 13 and any enabled Eq. 19-25 component is logged with the sign/weight in the frozen manifest. |
| R-04 | paper-assumption | Terminal reward replaces versus augments dense reward. | One frozen choice is applied; the test proves no terminal objective is double-counted. |
| R-05 | icaps-adapter | One complete official episode with macro rewards. | Sum of shaped rewards telescopes to the frozen normalized terminal objective, up to a documented constant/tolerance. |
| R-06 | icaps-adapter | Multiple atomic assignments in one simulator epoch. | They are represented as one joint macro-action, or a proven micro-step decomposition with discount 1 inside the epoch; they are not falsely treated as several 10-minute transitions. |
| R-07 | paper-explicit | Policy seed H and GA winner Xi intentionally differ. | There is never an ordinary PPO tuple with action H and environment reward/next-state caused by Xi.  EvoRL-ICAPS executes H for PPO; paper-repro records Xi under a separate tagged contract. |
| R-08 | paper-explicit | GA pseudo candidates differ in quality and feasibility. | Pseudo transitions are stored separately from on-policy PPO data; invalid/masked teacher labels are discarded; all loss/gradient values are finite. |
| R-09 | paper-assumption | Tiny two-action DPDP state where one assignment has lower official cost. | With fixed seed/budget, probability of the better action increases in every learner seed; policy/value losses and gradients remain finite. |
| R-10 | icaps-adapter | Masked logits with all but one action invalid, then an all-invalid state. | The only valid action is selected; all-invalid state produces explicit diagnostic behavior, never NaN, -inf loss, or arbitrary vehicle assignment. |
| R-11 | paper-assumption | CPU checkpoint replay and, when CUDA is available, CUDA replay. | CPU same-seed trace is identical; GPU greedy action/final score match CPU within frozen numeric tolerance. |

R-07 is the primary trainability gate.  A long run is prohibited until it
passes.  More episodes cannot correct an action-to-reward mismatch.

## 7. Policy, decoder, and GA conformance matrix

| ID | Label | Scenario | Oracle and pass criterion |
| --- | --- | --- | --- |
| P-01 | paper-explicit | Observation changes one of order, factory, or vehicle attributes at a time. | The intended O/F/V feature changes, irrelevant features do not, and snapshot objects remain immutable. |
| P-02 | paper-explicit | Permute vehicle dictionary/input order. | Vehicle logits and mask permute equivalently; no vehicle-ID embedding changes the decision. |
| P-03 | paper-assumption | Candidate orders have equal and unequal deadline/creation/order/chunk keys. | Canonical candidate ordering follows the frozen tie-break exactly. |
| P-04 | paper-explicit | Same ordered order-to-vehicle assignment enters policy, GA, in-process dispatcher, and subprocess dispatcher. | All use the common decoder and produce identical canonical route hash. |
| P-05 | paper-explicit | Fixed policy plan H seeds GA population U0. | U0 contains literal H as its first individual; all other members have exact coverage and valid phenotype; fixed RNG produces identical population trace. |
| P-06 | paper-explicit | PMX/fragment crossover and mutation probability 1 on tiny known genomes. | Golden offspring match the frozen operator; repair restores coverage only and does not perform hidden local search. |
| P-07 | paper-assumption | Fitness values below/above average at first and final generation. | FPS positive-shift probabilities and Pc/Pm schedules equal the frozen formula; elitism preserves the current best feasible incumbent. |
| P-08 | paper-explicit | Fitness fixture with current overtime, inefficient completion, carry-over overtime, and dock contention. | Each Eq. 29 component and utility sign is logged; candidate ranking is deterministic. |
| P-09 | icaps-adapter | GA label is replayed through policy's microstate prefix. | Each teacher action is feasible under the matching mask and common decoder; no -inf old log probability or invalid KL term occurs. |
| P-10 | paper-explicit | Inference checkpoint under monkeypatch that makes GA and legacy operators raise. | Policy-only inference completes without GA, AGVNS/VNS, Chromosome, legacy total_cost, or local search. |
| P-11 | paper-assumption | Recurrence enabled: reset episode, retry same tick, change model/episode/tick. | Hidden state resets or restores exactly according to manifest; retry is idempotent.  If v1 is stateless, this test asserts no hidden sidecar is read or written. |

The paper has an ambiguity ledger.  Its prose mentions tournament selection,
Eq. 30 defines fitness-proportional selection, and Algorithm 1 only says
select parents that maximize fitness.  The implementation must choose exactly
one frozen behavior and label P-07 as paper-assumption; it must not claim the
paper uniquely determines that behavior.  The same ledger records the
cost-like Eq. 29/33 values used with argmax, recurrence details, queue
estimation, network architecture, and training split.

## 8. Simulator state-machine, serialization, and parity matrix

| ID | Scenario | Oracle and pass criterion |
| --- | --- | --- |
| S-01 | Call observe repeatedly before and after a step. | State, history, vehicle stack, and current time hashes do not change. |
| S-02 | Step with elapsed training time 0 for several epochs. | Simulator advances exactly one 600-second decision interval per accepted dispatch. |
| S-03 | Reset the same instance twice with the same seed. | Initial snapshot and scripted-action trace are identical. |
| S-04 | Serialize output, invoke the normal subprocess entry point, restore next epoch. | Destination/suffix/item coverage are preserved exactly; no planned work is dispatched twice. |
| S-05 | Retry a subprocess at the same epoch after output failure. | It uses the same pre-step model/session state and emits byte-equivalent canonical output. |
| S-06 | Run two instances/jobs concurrently in separate data directories. | No route, sidecar, checkpoint, or episode identity leaks between jobs. |
| S-07 | Fix learner and simulator seed, then repeat a full run. | Simulator seed is actually passed to simulator initialization; output/score replay according to documented determinism. |
| S-08 | Scripted first-fit, fixed assignment, and frozen-checkpoint policies run in-process and subprocess. | At every epoch compare input payload, action, accepted route, Checker result, time, vehicle position/destination/carrying, item states, history digest, and final official score. |
| S-09 | Strict checkpoint missing, assumptions hash mismatch, decoder failure, and Checker rejection. | Run fails closed with explicit reason and telemetry; no legacy fallback is called. |

S-08 must use real official simulation, not fake lambda callbacks.  A generic
parity utility is not sufficient evidence.

## 9. Data-protocol, checkpoint, and leakage matrix

| ID | Scenario | Oracle and pass criterion |
| --- | --- | --- |
| L-01 | Resolve benchmark_heldout split. | Train, validation, and test IDs are pairwise disjoint and cover the registered 64 cases. |
| L-02 | Attempt to pass test IDs through a training CLI override. | Strict held-out mode rejects it before any test order file is opened. |
| L-03 | Make held-out order files sentinel/read-audited during train, normalizer fit, teacher generation, and selection. | No held-out order stream is opened; static factory/route context remains permitted. |
| L-04 | Generate procedural order streams. | Generator version/seed/distribution are recorded; it uses only allowed train information and is executed by the official simulator. |
| L-05 | Save then resume at an epoch boundary and mid-curriculum. | Model, optimizer, normalizer, Python/NumPy/Torch CPU/CUDA RNG, schedule, teacher configuration, and trace match uninterrupted training. |
| L-06 | Smoke configuration attempts to enter strict evaluation. | Evaluation rejects a checkpoint whose resolved GA budget, train IDs, manifest hash, or mode differs from the registered experiment. |
| L-07 | Train transductively on all published cases. | Artifact path/report mode is explicitly paper_transductive and cannot be merged into held-out statistics. |

Every checkpoint must store its resolved configuration, exact train/validation
IDs, order-stream/generator hashes, code revision, device/library versions,
assumptions hash, seed schedule, normalizer state, and all fallback counters.

## 10. Trainability, stability, and scale scenarios

### 10.1 Preflight learning tests

1. Train five independent learner seeds on the same small official scenario
   with a frozen budget.
2. Compare against a masked-random policy and an untrained checkpoint using
   paired validation scenarios.
3. Require all five runs to complete without NaN/Inf, Checker failure,
   fallback, timeout, or parameter-update failure.
4. Before examining test instances, require at least four of five seeds to
   improve over the paired masked-random baseline and require the paired
   bootstrap 95% confidence interval of the mean validation improvement to
   exclude zero in the favorable direction.
5. Compute the paper-style convergence episode: moving average window 50,
   earliest point that remains within plus/minus delta of its final plateau,
   where delta is derived from the final 10% variance.  Report it for every
   seed; do not use test data to choose it.

These are learning-health gates, not a requirement to beat AGVNS.

### 10.2 Curriculum and scale preflight

Run one validation scenario from each group after the prior group passes:

| Group | Vehicles / orders | Mandatory result |
| --- | --- | --- |
| G1 | 5 / 50 and 5 / 100 | Full episode parity, valid checkpoint, learning-health pass. |
| G2 | 20 / 300 and 20 / 500 | Same plus no queue/destination regression. |
| G3 | 50 / 1000 and 50 / 2000 | Same plus measured planner/decoder cache effectiveness. |
| G4 | 100 / 3000 and 100 / 4000 | Same plus strict runtime preflight. |

For every group:

- all epochs must pass Checker;
- every dispatch must finish under the active runner's 570-second hard limit;
- the report must contain p50, p95, maximum dispatch time, memory peak,
  candidate count, decoder calls, GA teacher time, and fallback count;
- a valid incumbent must exist at every deadline check;
- no scale-specific heuristic may use a held-out order stream.

The paper states a 10-minute runtime constraint per instance while the current
ICAPS integration applies a hard subprocess limit per dispatch.  The release
manifest must record both measured end-to-end instance time and per-dispatch
time, and must not claim identical timing conditions to the paper until that
difference is resolved explicitly.

### 10.3 Final inference and stability campaign

1. Freeze code, manifest, checkpoint-selection rule, hardware profile, and
   test split before the first test invocation.
2. Run strict Algorithm-1 inference on all 64 instances as a technical
   preflight.  Require zero failed epoch, zero Checker rejection, zero
   fallback, zero non-finite score, and zero timeout.
3. Run five learner seeds.  For each, run the registered simulator seeds; if
   simulator behavior is proven deterministic, retain one official seed and
   replay it exactly instead of inventing seed variance.
4. Report score, distance, overtime, runtime per epoch, total runtime,
   Checker/fallback count, trace digest, mean, standard deviation, paired
   bootstrap 95% confidence interval, and results for all eight scale groups.
5. Run RPPO/PPO-only, GA-only teacher, EvoRL-ICAPS, and paper-repro ablations
   with identical split, seeds, time budget, and objective.  Compare AGVNS
   only under the same ICAPS inputs/seeds/runtime reporting.

Stable does not mean guaranteed better than AGVNS.  It means five valid
learner seeds have no collapse, no engineering failure, reproducible
same-seed behavior, and a preregistered validation improvement criterion.
The final report must show dispersion even if the result is worse than AGVNS.

## 11. Paper-conformance release checklist

Before a result is called paper-conformant, produce a traceability table for
Algorithm 1 lines 1-32 and Eqs. 13, 18-34.  Each row must contain:

- paper reference and a short claim;
- implementation module/function;
- test IDs above;
- one of paper-explicit, paper-assumption, or icaps-adapter;
- manifest value/hash for every assumption;
- status: passed, intentionally excluded, or unsupported.

The following paper-visible facts are mandatory to test:

- O/F/V observation and sequential vehicle assignment;
- policy assignment converted into a LIFO route plan;
- policy plan seeding a diverse GA population;
- frozen crossover, mutation, selection, replacement, and adaptive
  probability behavior;
- evaluator fitness component logging;
- best candidate selection and actual simulator transition;
- separately tagged population pseudo-feedback;
- policy-only inference without GA;
- five-seed convergence reporting with the paper's moving-average definition.

Queue wait in Eq. 29 is a special case.  If there is no validated queue
estimator, the manifest must say it is zero/diagnostic and the report must
identify this as an ICAPS adaptation rather than claiming full Eq. 29
reproduction.

## 12. Release gates and definition of done

| Gate | Required evidence | Release decision |
| --- | --- | --- |
| A: domain | D-01 through D-16, including Checker differential/property tests. | No model training before pass. |
| B: math | R-01 through R-11, especially action/reward attribution and telescoping. | No long training before pass. |
| C: fidelity | P-01 through P-11 and full ambiguity ledger. | No paper-conformance claim before pass. |
| D: runtime | S-01 through S-09 on official mini-instance and at least one real case. | No checkpoint deployment before pass. |
| E: protocol | L-01 through L-07 with immutable run manifest. | No held-out model selection before pass. |
| F: scale | G1 through G4 with strict validity and runtime telemetry. | No all-instance evaluation before pass. |
| G: scientific report | Five-seed final campaign, ablations, CI, and AGVNS comparison. | Only then call the result stable and reportable. |

EvoRL-ICAPS is train-ready only after A, B, D, and E pass.  It is
inference-ready on all instances only after A, D, and F pass.  It is
scientifically reportable as a stable EvoRL DPDP baseline only after all
gates, including G, pass.
