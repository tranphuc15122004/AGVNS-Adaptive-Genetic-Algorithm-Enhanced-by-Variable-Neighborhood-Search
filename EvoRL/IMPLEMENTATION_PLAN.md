# EvoRL-ICAPS implementation plan for ICAPS DPDP

The executable acceptance scenarios, official-oracle hierarchy, and release
gates for this plan are defined in [TEST_PLAN.md](TEST_PLAN.md).  A feature is
not considered complete merely because a smoke test runs; it must pass the
corresponding test-plan gate.

## 1. Scope and success criterion

`EvoRL-paper-repro` is the **primary reproduction baseline** for comparison with
AGVNS.  Its purpose is to implement the algorithmic loop in Yang et al., *A collaborative
evolutionary reinforcement learning approach to dynamic pickup and delivery
challenges* (Algorithm 1, Sections 4.2--4.3), while using the unmodified ICAPS
simulator, Checker, and benchmark objective.

It is not a project to improve EvoRL beyond the paper, nor to deliberately make
it perform poorly.  A score below AGVNS is an expected and useful empirical
outcome, but never an acceptance criterion.  If it wins on an instance, that
result must be reported unchanged.

The repository exposes two labelled training contracts.  `EvoRL-paper-repro`
is the primary trainable baseline: the policy phenotype seeds GA, the better
phenotype is selected for the official environment transition, and the GA
population supplies pseudo-feedback.  `EvoRL-ICAPS` is retained as the
policy-only execution ablation.

The primary comparison uses the selected RPPO/GA phenotype against AGVNS under
the same ICAPS instances, simulator seeds, Checker, and 570-second per-dispatch
limit.  Policy-only inference is reported separately as the `EvoRL-ICAPS`
ablation.

## 2. Fidelity contract

### Paper-defined behavior that must be implemented

At every simulator epoch `t` during training:

1. Build the observation `{O_t, F_t, V_t}`.
2. RPPO assigns every dispatchable order to a vehicle, producing `OA_t`.
3. A deterministic LIFO-aware route transformation turns `OA_t` into RL route
   plan `H_t`.
4. Initialize a GA population with `H_t` plus random route plans, evaluate it,
   then run selection, PMX-style crossover, mutation, and replacement for
   `Phi` iterations.
5. Evaluate `H_t` and GA candidates, execute the best estimated plan in the
   ICAPS environment, observe the next state and actual reward.
6. Store the executed transition and the selected non-best GA candidates in
   the replay data.
7. Update RPPO with the clipped PPO objective and update it again from GA
   pseudo-rewards using the confidence-scaled Eq. (34)-style objective.

At inference, run **RPPO + the same deterministic route transformation only**;
do not invoke GA.

### Neutral ICAPS compatibility layer

These are required to make the paper algorithm executable, not intended as
algorithmic improvements:

- Canonical primitive DTOs at the solver/simulator boundary.  The policy and
  GA never mutate `InputInfo` or simulator-owned objects.
- `AtomicOrder` is one original order when demand is at most 15; an oversized
  order has deterministic chunks of at most 15.  The evaluator still charges
  overtime once at the latest completion of the original order.
- Existing destination, carrying stack, completed work, and committed route
  prefix are immutable.  Only not-yet-picked mutable orders are re-routed.
- A deterministic decoder and `SolutionValidator` enforce exact item coverage,
  capacity, LIFO, factory/item consistency, and every vehicle key before the
  official Checker is called.
- Official score is always `distance / vehicle_count + 10000 * overtime_seconds
  / 3600`; queue waiting is available to the paper evaluator but is not added
  to the ICAPS benchmark score.

### Paper ambiguities: fixed, versioned assumptions

The paper does not give the network architecture, PPO hyperparameters,
population size, number of GA generations, training data split, or a fully
  consistent reward/fitness sign convention.  The primary `EvoRL-paper-repro`
  contract must therefore ship
an immutable `paper_assumptions.yaml` containing all such choices, its SHA256,
and the paper section motivating each choice.

The default convention is a maximization utility:

`utility = -estimated_penalty` and `environment_reward = -official_cost`.

Thus a lower estimated cost or official score is always better, despite the
paper using both cost-like formulas and `argmax` notation.  Raw Eq. (19)--(25)
components, their signed implementation values, and the final objective must
all be logged for audit.

## 3. Frozen algorithmic specification

### 3.1 Dynamic decision state

A macro-step is one 10-minute ICAPS decision epoch.  Its candidate set contains
all generated, not-yet-picked items that are not already in the accepted plan,
vehicle destination, or carrying stack.  It must not be derived only from
`new_order_itemIDs`, because an unassigned order would disappear next epoch.

For a fixed candidate order sequence, RPPO emits sequential vehicle assignments
with a recurrent hidden state.  The sequence is sorted deterministically by
committed completion time, creation time, original order ID, and chunk index.
There is no learned `DEFER` action in the baseline.  If every vehicle is
temporarily infeasible, the ICAPS compatibility boundary may leave the item
unallocated and retry it from the complete pending set next epoch; this is
logged separately and is not a policy decision.

The observation implements the paper's order, factory, and vehicle state:

- order pickup/delivery, load/unload time, demand, creation/deadline and
  expected completion information;
- factory available docks and waiting-vehicle count;
- vehicle current/departure factory, next destination, route load, ETA and
  planned route state;
- derived route-distance, deadline, queue, and action-feasibility features.

Vehicle-ID embeddings are forbidden so that permuting vehicle input order only
permutes logits/actions.  A one-layer GRU is the minimum explicit
operationalization of the paper's claimed RPPO recurrence; its size and PPO
settings live in `paper_assumptions.yaml`.

### 3.2 Route transformation

The policy action is high-level order-to-vehicle assignment, never a raw node
route.  For each vehicle, the decoder takes its assigned order list and creates
a LIFO-valid pickup/delivery sequence after the locked prefix.  It uses a
fixed, documented deterministic sort/insertion rule; it must not run extra
global local search or a stronger AGVNS operator.

If a selected assignment cannot be decoded, record the paper feasibility
penalty, reject that candidate plan, and retain a deterministic valid fallback
only for completing the simulator call.  Such a fallback is counted and makes
the corresponding reproduction run invalid for final reporting until fixed.

### 3.3 Paper-like GA

The GA genotype is a complete fleet plan:

`{vehicle_id: ordered tuple[atomic_order_id, ...]}`.

Every atomic order occurs exactly once.  Its phenotype is produced solely by
the common decoder, so GA and policy are evaluated on comparable ICAPS routes.

- Population `U_0` contains the RPPO plan and randomized valid plans.
- Fitness evaluates the paper components: estimated future overtime, excess
  completion time over fastest completion, carried-over overtime, and dock
  queue time.  It is converted to the frozen maximization utility convention.
- Parent selection uses fitness-proportional selection after a positive shift;
  elitism retains the current best plan.  The apparent `argmax`/FPS ambiguity
  in the paper is documented in the assumptions file.
- Crossover is partial-mapped / fragment exchange over vehicle order strings;
  deterministic repair restores exact coverage but never optimizes a route.
- Mutation swaps or moves orders in fleet strings.  Crossover and mutation
  probabilities follow Eqs. (31)--(32).
- Evaluation is bounded by the configured GA iteration/population budget.  A
  timeout returns the best valid incumbent and is logged.

The GA must not call legacy `Chromosome`, legacy `total_cost`, or AGVNS/VNS
operators.  Those implementations have different objective and feasibility
semantics and would invalidate the baseline.

### 3.4 Collaborative update

`EvoRL-paper-repro` executes the better phenotype under Eq. (33): the policy
phenotype `H_t` is compared with the best GA phenotype `eta_t` using the paper
evaluator, and the selected state is sent to the official simulator.  The GA
population is retained as a separately tagged teacher buffer and contributes
the confidence-scaled update corresponding to Eq. (34).  `EvoRL-ICAPS` remains
an explicit policy-only deployment ablation.

The reward implementation exposes and logs:

- environment overtime/distance reward from Eq. (13);
- intrinsic efficiency, feasibility, and collaborative terms from Eq. (19);
- final terminal objective from Eq. (25);
- GA evaluator utility and confidence coefficient for Eq. (34).

The assumptions file must state whether the terminal term replaces or augments
the last dense reward.  It may not double-count without an explicit
paper-reproduction rationale.

## 4. Work packages and gates

### P0 — Reproduction manifest and characterization

- Extract a conformance matrix from the paper: each equation/Algorithm 1 line,
  its code module, test, and any stated assumption.
- Freeze `paper_assumptions.yaml`, seed scheme, versions, hardware/device, and
  route-decoder rule before training.
- Add small hand-built fixtures for LIFO, multiple items per order, split
  orders, deadline equality, and dock contention.

**Gate:** every paper requirement is marked implemented, intentionally
unimplemented, or underspecified; none is merely implicit.

### P1 — Simulator isolation and parity

- Build a fresh in-process ICAPS environment per episode.
- Implement `begin_episode`, pure cached `observe`, one-advance `step`, and
  single-use `finalize`.
- Persist a canonical accepted plan in `AlgorithmSessionState`; subprocess
  routes use existing JSON persistence and in-process routes use the same
  pure restoration core.
- Rehydrate solver DTO output to official `src.common.Node` objects only at the
  simulator boundary.

**Gate:** a scripted policy has epoch-by-epoch parity between in-process and
subprocess execution: payload, Checker result, time, vehicle/item states,
history, and final score.

### P2 — Paper RPPO policy and route decoder

- Implement the paper observation/action representation and recurrent policy.
- Store hidden-before/hidden-after, masks, log probabilities, values and
  sequence boundaries in the replay buffer.  Rollout snapshots are detached
  from simulator mutation, while optimization uses the manifest's truncated
  BPTT window (16 by default); the paper does not specify sequence length or
  batching.
- Implement exactly one policy route transformation shared by training,
  evaluation, and inference.

**Gate:** vehicle-permutation equivariance, hidden reset/retry behavior,
CPU/CUDA checkpoint parity, and 100% Checker-valid masked-random episodes.

### P3 — Paper GA and evaluator

- Replace the current assignment-only GA with the fleet-string chromosome.
- Implement population initialization, fitness proportional selection,
PMX-style crossover, mutation, adaptive probabilities, replacement, and
elitism.
- Implement evaluator pseudo-rewards and reverse mapping from every selected
candidate to sequential assignment actions.

**Gate:** fixed seed produces deterministic population traces; every candidate
has exact coverage and valid replayed phenotype; GA best never loses to its
initial RL plan under the same evaluator.

### P4 — Coupled EvoRL trainer

- Implement Algorithm 1 training mode and separate actual/pseudo transition
types in the replay buffer.
- Implement Eq. (18) clipped RPPO updates and Eq. (34)-style confidence/KL
updates without relabeling GA samples as ordinary PPO rollout.
- Checkpoint all model, optimizer, normalizer, assumptions hash, factory map,
and RNG states.

**Gate:** one complete small ICAPS episode trains, resumes deterministically,
and emits a trace showing policy plan, GA population, executed plan, actual
reward, pseudo-rewards, and both losses.

### P5 — Training protocol

Two pre-registered presets are required:

1. `benchmark_heldout` is the primary AGVNS comparison.  Train on procedural
   ICAPS-compatible order streams and/or designated training cases; exact
   benchmark test order streams are not used for training, normalization,
   early stopping, or hyperparameter selection.
2. `paper_transductive` permits adaptation on the 64 published order cases.
   It is reported separately and never described as held-out generalization.

Run the paper's eight scale groups (5/50, 5/100, 20/300, 20/500, 50/1000,
50/2000, 100/3000, 100/4000).  Use fixed episode budgets selected before the
run.  The paper's moving-average-50 convergence definition is a reporting
metric, not an unstated test-set early-stopping rule.

**Gate:** manifest proves no held-out order stream was read during the primary
training run; all five learner seeds can resume from a checkpoint.

### P6 — Evaluation and baseline report

- Run primary `EvoRL-paper-repro` against AGVNS and the existing baselines under
  the same ICAPS input, official Checker, simulator seed, and time limit.
- Report five learner seeds, raw score, distance, overtime, Checker failures,
  per-epoch runtime, aggregate mean/std, and bootstrap 95% CI.
- Report RPPO-only and GA-only ablations so the evolutionary contribution is
  visible.
- Publish both the held-out and transductive tables with unambiguous labels.

**Gate:** no checkpoint fallback, planner fallback, or failed Checker result
may enter a strict benchmark table.

## 5. Non-baseline work, intentionally deferred

The following are valuable research variants but must not modify
`EvoRL-ICAPS`:

- PPO-only on-policy plus offline population distillation;
- an improved global planner, AGVNS/VNS teacher, or legacy local-search reuse;
- uncertainty augmentation, additional satisfaction objective, or queue-aware
  benchmark objective;
- A learned `DEFER` action and cross-epoch pending-order optimization; the
  current compatibility fallback is non-learned and already covered by the
  route/pending tests.
- alternate architecture/hyperparameter sweeps selected using test scores.

They belong in separately named experiments after the reproduction baseline has
been frozen and reported.

## 6. Definition of done

`EvoRL-paper-repro` is release-complete when it has a paper conformance manifest,
passes all ICAPS validity/parity gates, trains through the policy/GA loop, selects
the best phenotype at inference on every target instance, and produces reproducible
five-seed comparison reports against AGVNS.  Its relative score is an observed
result, not a forced target.
