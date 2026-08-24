# Simulator Runtime Statistics Design

## Goal

Give every simulator entrypoint a machine-readable per-instance runtime report
for serial and parallel runs, while preserving the existing score output and
`SUCCESS` completion contract.

## Scope

The change covers AGVNS, MA, TS, MOEAD-TS, EvoRL, and competition baselines
1/2/3. It does not change the simulator's scoring formula, algorithm behavior,
input/output JSON format, or subprocess protocol.

## Design

The repository root gets one self-contained `runtime_stats.py` module. Each
`main.py` adds the repository root to its import path and uses the same
`RuntimeStats` collector. This keeps the eight entrypoints on one schema while
leaving the existing simulator APIs unchanged.

Each run writes a CSV file and a JSON companion. The default location is
`<data-dir>/runtime_stats.csv`; `--stats-file` can override the CSV path. The
JSON companion uses the same path with a `.json` suffix.

Each CSV row contains:

- `instance_id`, `status`, `score`
- `runtime_seconds` measured around the complete `simulate()` call
- `simulator_runtime_seconds` when the simulator API reports its own elapsed
  value, otherwise empty
- UTC start/end timestamps, seed, process ID, and an error message

The JSON companion contains the same per-instance rows plus success/failure
counts and total, mean, minimum, maximum, and population standard deviation of
successful `runtime_seconds` values. The collector persists after every
completed instance using a temporary file and `os.replace`, so a later failed
instance does not erase earlier measurements.

The existing parallel runner already emits one result row per job. Its
`results.csv` remains the authoritative repetition-level report; its
`summary.json` is extended with min/max/standard-deviation runtime fields so
serial and parallel reports expose the same aggregate statistics.

## Error handling

Failed instances are recorded with `status=FAILED`, an empty score, elapsed
time up to failure, and the formatted exception. The simulator keeps its
existing non-zero exit behavior and never prints `SUCCESS` when any instance
fails. A failure while persisting statistics is fatal because an unrecorded
run would violate the reporting contract.

## Verification

- Unit tests cover successful/failed rows, aggregate statistics, custom paths,
  and incremental persistence.
- All eight entrypoints are syntax-checked and expose `--stats-file` through
  `--help`.
- Existing parallel-runner tests remain green, and summary regression tests
  verify the new runtime aggregates.
- A representative simulator smoke run verifies that a real instance creates
  both report files.
