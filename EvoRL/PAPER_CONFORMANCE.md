# EvoRL-paper conformance matrix

This file freezes what is claimed as a reproduction, what is an ICAPS
compatibility adapter, and what remains underspecified by the paper.  It is
kept next to `paper_assumptions.yaml` so a checkpoint can be tied to the exact
contract used to produce it.

| Paper requirement | Implementation | Verification/status |
| --- | --- | --- |
| Algorithm 1 observation `{O,F,V}` | `training/observation.py`, `training/official_adapter.py` | Implemented; immutable DTO and feature/mask tests |
| RPPO sequential vehicle assignment | `training/rppo.py`, `training/evorl_trainer.py` | Implemented; recurrent hidden-before/after is stored and optimized through frozen TBPTT chunks |
| LIFO route transformation | `algorithm/evorl/planner.py::decode_assignments`, `algorithm/evorl/dispatch.py` | Implemented; policy, GA, and inference share the transactional decoder and are guarded by `SolutionValidator` and official Checker |
| GA population seeded by RPPO plan | `PaperEvolutionaryTeacher.optimize` | Implemented; seed is retained before random members |
| Fitness-proportional selection | `PaperEvolutionaryTeacher._select` | Implemented with positive FPS shift; sign choice is versioned assumption |
| PMX-style crossover and swap/move mutation | `PaperEvolutionaryTeacher._pmx`, `_mutate` | Implemented with deterministic exact-coverage repair |
| GA pseudo-feedback to RPPO | `EvoRLTrainer`, `RPPOTrainer.collaborative_ga_update` | Implemented in a separate `ga` teacher buffer; never relabels the policy's environment transition |
| Actual environment reward | `training/official_env.py`, `EvoRLTrainer.record_environment_reward` | Implemented; reward replaces projected training placeholder |
| Algorithm 1 execution selection | `training/evorl_trainer.py`, `algorithm/evorl/dispatch.py` | Implemented in primary `EvoRL-paper-repro`: compare RPPO phenotype H and GA phenotype eta with the paper evaluator and execute the better one |
| Policy-only inference ablation | `algorithm/evorl/dispatch.py` | Available only as explicit `EvoRL-ICAPS`; not the primary paper reproduction |
| Official ICAPS objective and Checker | `training/official_env.py`, `src/utils/{checker,evaluator}.py` | Implemented at boundary; benchmark objective remains authoritative |
| In-process/subprocess isolation | `official_adapter.py`, `legacy_adapter.py` | Implemented with immutable item/factory snapshots and route-map adapters |
| Pending/deferred order persistence | `algorithm/evorl/atomic.py` | Implemented for no-`DEFER` baseline by considering all uncovered generated items |
| `DEFER` action | `algorithm/evorl/dispatch.py` | Not a learned policy action; when no valid insertion exists, the compatibility layer keeps the uncovered generated item pending and retries it next epoch |
| Exact paper network and Eq. 19--25 signs | — | Underspecified by paper; choices are explicit in `paper_assumptions.yaml` |
| Published train/test split | — | Underspecified; `training/reproduction.py` supplies preregistered held-out and transductive protocols |

## Strict reporting rule

Only runs with a checkpoint whose assumptions hash matches the current manifest,
`EVORL_LEGACY_FALLBACK=0`, and zero Checker/planner fallback events may enter a
baseline table.  The synthetic trainer is an installation/CI smoke path; it is
not a result on the ICAPS benchmark.
