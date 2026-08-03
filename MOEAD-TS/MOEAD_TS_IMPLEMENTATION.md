# MOEA/D--TS implementation

`algorithm/Test_algorithm/MOEAD_TS.py` is the production adapter.  The core
is split into `moead_core.py` and `moead_objectives.py` so the dynamic scene
restore/output workflow remains unchanged.

Published paper parameters are kept in `algorithm_config.py`: population 6,
neighborhood size 2, 50 outer iterations, two raw objectives and the four
tabu operators.  The paper does not specify `delta`, `nr`, tabu tenure or
inner tabu iteration limits; those values are marked as reproduction
assumptions in `moead_parameter_manifest()`.

Algorithm 4 randomly selects one of the four AGVNS local-search operators at
every neighbor iteration: `PDPairExchange`, `BlockExchange`,
`BlockRelocate`, and `mPDG`. MOEA/D--TS loads them directly from
`AGVNS/algorithm/Test_algorithm/new_LS.py` through `agvns_ls_bridge.py`; AGVNS
is therefore the single source of truth and a future AGVNS LS fix is used by
the next MOEA/D--TS subprocess without copying it into this variant. The
current AGVNS limitations are intentionally retained for a fair comparison,
including no same-vehicle PD-pair exchange and no one-block relocation.

The paper and simulator impose a 600-second total process limit. The search
reserves 15 seconds for atomic archive and JSON output. Initial population
construction is bounded to a configurable fraction of that budget and falls
back to a complete feasible incumbent when exhaustive construction cannot
finish. Each inherited LS call has its own configurable time slice. Run a
focused test with:

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
