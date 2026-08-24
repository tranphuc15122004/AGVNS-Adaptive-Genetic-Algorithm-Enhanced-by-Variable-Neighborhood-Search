# AGVNS Parameter Sensitivity Screening Design

**Experiment directory:** `AGVNS/experiments/agvns_parameter_sensitivity/`

**Objective:** Use the Taguchi orthogonal-array method to screen four AGVNS parameters with three levels each, while measuring quality, variability, validity, and runtime on real simulator runs.

**Scope:** Screening only. There is no confirmation stage and no final parameter selection in this experiment.

## Taguchi design

The four factors have three levels, so `L9(3^4)` is the smallest orthogonal array that estimates all four main effects. Each factor level appears three times and every pair of factor levels appears once. The nine Taguchi rows are configuration IDs 1–9. Configuration ID 10 is the current AGVNS baseline and is run as a separate control; it is not included in the orthogonal main-effect calculation.

| Factor | Level 1 | Level 2 | Level 3 |
|---|---:|---:|---:|
| `T` | 40 | 80 | 120 |
| `population` | 20 | 40 | 60 |
| `perturbation` | 25% | 50% | 75% |
| `mutation_subset` | 10% | 25% | 50% |

The 9 Taguchi rows are:

| ID | T | Population | Perturbation | Mutation subset |
|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 25% | 10% |
| 2 | 40 | 40 | 50% | 25% |
| 3 | 40 | 60 | 75% | 50% |
| 4 | 80 | 20 | 50% | 50% |
| 5 | 80 | 40 | 75% | 10% |
| 6 | 80 | 60 | 25% | 25% |
| 7 | 120 | 20 | 75% | 25% |
| 8 | 120 | 40 | 25% | 50% |
| 9 | 120 | 60 | 50% | 10% |

Control configuration:

`ID 10: (T=80, population=40, perturbation=50%, mutation subset=25%)`

## Fixed conditions

- Real AGVNS simulator, run to the final result for every selected instance.
- Benchmark, simulator, score formula, algorithm operators, generation count, local-search limits, and timeout remain fixed.
- `ALGO_TIME_LIMIT = 570` seconds per algorithm invocation.
- The same deterministic seed schedule is used for every scenario.
- Visualization and executed-route recording are disabled for this batch to avoid cross-worker output collisions and measurement overhead.

## Instances and repetitions

The first two instances in each set are used, processed from the largest set to the smallest:

`57, 58, 49, 50, 41, 42, 33, 34, 25, 26, 17, 18, 9, 10, 1, 2`

Each scenario is run three times. The seed is:

`base_seed + instance_id * 1000 + repetition`

Total jobs:

`(9 Taguchi rows + 1 baseline) × 16 instances × 3 repetitions = 480 jobs`.

## Measurements and analysis

For every scenario, instance, repetition, and seed, collect final score, total distance, overtime, dispatch count, validity/failure status, algorithm runtime, simulator runtime, wall-clock runtime, raw worker log, and per-instance runtime statistics.

The Taguchi analysis reports marginal means, standard deviation, smaller-the-better signal-to-noise ratio, and mean-effect differences for the four factors. The baseline is reported separately as a reference. The L9 design is intended for main effects; it does not estimate all interactions.

## Guardrails

- The applied configuration is printed in every worker log.
- `T` and perturbation are configurable rather than hard-coded.
- Population and mutation values are not silently replaced by unrelated adaptive configuration.
- Failed jobs remain in the raw dataset and summaries.
- Jobs are scheduled set-descending so the largest instances start first.
