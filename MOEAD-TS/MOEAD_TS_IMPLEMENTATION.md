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
enumerators. The tabu list stores the applied move keys (operator + moved
unit(s) + target vehicle/positions), not whole-solution signatures, so a
recently used move cannot be reapplied even from a different route layout.

The two MOEA/D objectives and scalar `TC` are obtained atomically from one
full-fleet call to `total_cost(..., mode="components")`, which returns
`(f1, f2, TC)`. `cost_of_a_route`, used by inherited AGVNS local search for a
route-replacement candidate, delegates to that same full-fleet evaluator. This
prevents MOEA/D and local search from scoring f1 and f2 using separate partial
evaluations.

The paper and simulator impose a 600-second total process limit. The search
reserves 15 seconds for atomic archive and JSON output. Initial population
construction is bounded to a configurable fraction of that budget and falls
back to a complete feasible incumbent when exhaustive construction cannot
finish. `MOEAD_TS_OPERATOR_TIME_LIMIT` is retained only for backward
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
