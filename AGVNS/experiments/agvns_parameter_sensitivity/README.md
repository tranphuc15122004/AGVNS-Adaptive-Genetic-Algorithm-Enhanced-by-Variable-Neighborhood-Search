# AGVNS parameter sensitivity screening

The current screening uses the Taguchi `L9(3^4)` array plus the current AGVNS baseline:

- 9 Taguchi configurations;
- 1 separate baseline control;
- instances `57,58,49,50,41,42,33,34,25,26,17,18,9,10,1,2`;
- three deterministic repetitions;
- 480 complete simulator jobs;
- jobs scheduled from Set 8 down to Set 1.

## Validate without running

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py --dry-run
pytest -q tests/test_agvns_parameter_sensitivity.py
```

## Run with tmux

```bash
tmux new-session -d -s agvns_taguchi_screening \
  "python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py --execute --workers 8 --cores 0,1,2,3,4,5,6,7 --base-seed 20260824"
```

Monitor with:

```bash
tmux attach -t agvns_taguchi_screening
```

Raw rows are stored in `runs/<timestamp>/results.jsonl`; summaries are written after the batch completes.

To aggregate an existing run without rerunning jobs:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/aggregate_results.py AGVNS/experiments/agvns_parameter_sensitivity/runs/<timestamp>
```
