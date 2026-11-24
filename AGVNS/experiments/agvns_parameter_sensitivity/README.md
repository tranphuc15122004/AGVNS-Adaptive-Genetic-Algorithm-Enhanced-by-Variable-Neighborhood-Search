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

The runner writes every execution to a new timestamped directory. A targeted
run never appends to the historical `20260903_141120` batch.

## Run with tmux

```bash
tmux new-session -d -s agvns_taguchi_screening \
  "python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py --execute --workers 8 --cores 0,1,2,3,4,5,6,7 --base-seed 20260824"
```

Parallel workers use an output/log directory inside their isolated workspace to
avoid races in the shared simulator log directory.

`--job-timeout-seconds` optionally terminates a stuck worker process group.
Choose its value from the allowed wall time for the selected instances; the
570-second algorithm budget applies per algorithm call, while a full
simulation instance can make multiple calls.

Run the seven-job repair canary with the original seed schedule:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py \
  --execute --job-list AGVNS/experiments/agvns_parameter_sensitivity/canary_jobs.csv \
  --workers 4 --cores 0,1,2,3 --base-seed 20260824
```

Rerun all 60 designed jobs for instances 57 and 58 (30 per instance) in a
separate run directory:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/run_screening.py \
  --execute --instances 57,58 --workers 4 --cores 0,1,2,3 --base-seed 20260824
```

The manifest records selected job keys, seed schedule, Git revision, a hash of
the dirty worktree, and the simulator timeout settings. The runner accepts
`--job-list`, `--instances`, and optional `--job-timeout-seconds`; it does not
implement `--retry-timeouts-from`.

Monitor with:

```bash
tmux attach -t agvns_taguchi_screening
```

Raw rows are stored in `runs/<timestamp>/results.jsonl`; summaries are written after the batch completes.

To aggregate an existing run without rerunning jobs:

```bash
python AGVNS/experiments/agvns_parameter_sensitivity/aggregate_results.py AGVNS/experiments/agvns_parameter_sensitivity/runs/<timestamp>
```
