# MOEA/D--TS implementation

`algorithm/Test_algorithm/MOEAD_TS.py` is the production adapter.  The core
is split into `moead_core.py` and `moead_objectives.py` so the dynamic scene
restore/output workflow remains unchanged.

Published paper parameters are kept in `algorithm_config.py`: population 6,
neighborhood size 2, 50 outer iterations, two raw objectives and the four
tabu operators.  The paper does not specify `delta`, `nr`, tabu tenure or
inner tabu iteration limits; those values are marked as reproduction
assumptions in `moead_parameter_manifest()`.

Algorithm 4 follows the pseudocode exactly: each inner iteration randomly
selects one of the four operators (couple-exchange, block-exchange,
couple-relocate, block-relocate) and generates exactly one single-move
neighbour from it. The move constructors are the `sample_*_move` functions in
`algorithm/Test_algorithm/MOEAD_TS.py`; they reuse the same feasibility,
destination-prefix and coverage checks as the `generate_*_neighbors`
enumerators. The tabu list stores canonical signatures of complete solutions.
Consequently, a candidate `x_tmp` is tabu when it duplicates a recently
visited route plan, matching the solution-level tabu condition in Algorithm 4
of the paper. Move descriptors are retained only to construct and test a
single local-search neighbour.

For every TS outer iteration, Algorithm 4 initializes `x_bestNeighbor` with
`x_current`. A feasible non-tabu neighbour replaces it only on a strict `TC`
improvement, so `x_current` is retained when none of the
`NeighborThreshold` samples improves it. `x_best` is likewise updated only by
a strict `TC` improvement. This is the literal paper behavior; diversity comes
from route crossover and random selection among the four operators, not from
accepting a worse TS transition. Initialisation tries the nominal six
independently shuffled CI sequences and drops any incomplete or infeasible
sequence; it never replaces one with a different constructor.

Early stopping (implementation choices, not in the paper): the Algorithm-4
outer loop stops after `MOEAD_TS_STAGNATION_LIMIT` consecutive iterations that
find no strictly improving neighbour, and the MOEA/D generation loop stops
after `MOEAD_STAGNATION_GENERATIONS` consecutive generations with zero
population replacements. Both mechanisms only terminate the search sooner when
no progress is observed, so the accepted moves and the behaviour up to that
point match the paper. Setting either limit to 0 restores the paper's
fixed-iteration behaviour exactly.

Before the TS loops start, the implementation exits immediately when no
movable pickup--delivery unit exists. All four Algorithm-4 operators require
such a unit, so this is an exact empty-neighbourhood termination and avoids
repeating empty samples for `MaxIter × NeighborThreshold` iterations.

`route_crossover` follows Algorithm 3 literally: it starts with an empty
offspring, copies route `r_k` from a random parent for `k = 1, ..., K`, and
repairs the partial offspring immediately after each copy. Vehicle IDs are
ordered numerically (`V_2` before `V_10`) so the first copied route retains a
duplicate order. The remaining orders are then inserted by the current
subproblem's Tchebycheff value. In the dynamic adaptation, a committed
destination and the delivery-only action of an item already carried by a
vehicle are preserved during repair.

The two MOEA/D objectives and scalar `TC` are obtained atomically from one
full-fleet call to `total_cost(..., mode="components")`, which returns
`(f1, f2, TC)`. `cost_of_a_route`, used by inherited AGVNS local search for a
route-replacement candidate, delegates to that same full-fleet evaluator. This
prevents MOEA/D and local search from scoring f1 and f2 using separate partial
evaluations.

The initial population uses the large-route (`model_nodes_num > 8`) cheapest
insertion mechanism from `dispatch_nodePair`: for every dispatch unit it
examines each vehicle and every ordered pair of pickup/delivery positions.
Before score evaluation, the candidate route is canonicalised as it will be
for simulator output and checked for LIFO and capacity feasibility. The winner
is chosen from a dock-aware full-fleet evaluation, not a one-route surrogate.
The small-route permutation tables are intentionally not used here: they
reorder existing work and can alter an immutable dynamic destination prefix.

The paper and simulator impose a 600-second total process limit. The search
reserves 15 seconds for atomic archive and JSON output. Initialization has no
separate time budget: Algorithm 2's CI construction shares the same 600-second
limit, and the only stopping criteria are the 50-iteration cap and the 600 s
deadline. It tries `N = 6` independently shuffled order sequences; each one is
built solely by CI from the restored scene. If CI is incomplete or the
resulting candidate is not fully valid, that individual is discarded
immediately—there is no
append-pair or other fallback constructor. Consequently, the population may
contain fewer than `N` valid members; MOEA/D creates its weights and
neighborhoods from the retained members. When no new order arrives, the six
independent chromosomes are necessarily equivalent copies of the restored
scene. `MOEAD_TS_OPERATOR_TIME_LIMIT` is retained only for backward
compatibility; per-operator time slicing no longer applies. Run a focused test
with:

```bash
cd MOEAD-TS
pytest -q tests
MOEAD_RANDOM_SEED=0 python main_algorithm.py
```

For a simulator smoke run:

```bash
python main.py --instances 1 --seed 0
```

The final candidate is selected by minimum `TC`; MOEA/D replacement uses the
Tchebycheff value for the current subproblem.
