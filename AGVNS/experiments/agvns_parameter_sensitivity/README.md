# AGVNS parameter sensitivity screening

The current screening uses the Taguchi `L9(3^4)` array plus the current AGVNS baseline:

- 9 Taguchi configurations;
- 1 separate baseline control;
- instances `1,2,9,10,17,18,25,26,33,34,41,42,49,50,57,58` (smallest first);
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

The outer worker wall-time guard is disabled by default.  The simulator's own
algorithm timeout remains active.  To opt into a hard outer guard for a diagnostic
run, pass a positive value such as `--job-timeout-seconds 660`.

Parallel workers use an output/log directory inside their isolated workspace to
avoid races in the shared simulator log directory.

To rerun only jobs recorded as `FAILED` because of the runner's outer timeout,
point the runner at the previous run. This creates a new run directory and does
not rerun unrelated failures:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py \
  --execute \
  --retry-timeouts-from AGVNS/experiments/agvns_parameter_sensitivity/runs/<timestamp> \
  --workers 16 --cores 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 \
  --base-seed 20260824
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
