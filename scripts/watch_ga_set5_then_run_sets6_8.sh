#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/tuantb/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search"
GA_DIR="$ROOT/GA"
SET5_BATCH="$GA_DIR/algorithm/data_interaction_runs/20261119_115717"
SET5_RESULTS="$SET5_BATCH/results.csv"
WATCH_LOG="$ROOT/logs/ga_sets_6_8_watchdog.log"
RUN_LOG="$ROOT/logs/ga_sets_6_8_rep1.log"
PYTHON_BIN="/home/tuantb/miniconda3/bin/python3"
CORES="8,9,10,11,12,13,14,15,16,17,18,19"

mkdir -p "$ROOT/logs"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" | tee -a "$WATCH_LOG"
}

log "Watchdog started. Monitoring GA Sets 1-5 batch: $SET5_BATCH"

while true; do
    # Count completed rows (excluding header)
    if [[ -f "$SET5_RESULTS" ]]; then
        DONE_COUNT=$(( $(wc -l < "$SET5_RESULTS") - 1 ))
    else
        DONE_COUNT=0
    fi

    # Check if the Set 1-5 run_parallel.py master process is still alive
    if pgrep -f "run_parallel.py --instances 1-40 --repetitions 4" >/dev/null 2>&1; then
        log "GA Sets 1-5 still running ($DONE_COUNT / 160 jobs completed). Sleeping 60s..."
        sleep 60
        continue
    fi

    log "GA Sets 1-5 master process exited ($DONE_COUNT / 160 rows in results.csv)."
    break
done

# Guard against duplicate launch if Sets 6-8 is already running
if pgrep -f "run_parallel.py --instances 41-64 --repetitions 1" >/dev/null 2>&1; then
    log "GA Sets 6-8 batch is already running. Exiting watchdog."
    exit 0
fi

log "Launching GA Sets 6-8 (instances 41-64, repetitions=1, cores=$CORES)..."
cd "$GA_DIR"
"$PYTHON_BIN" -u run_parallel.py --instances 41-64 --repetitions 1 --cores "$CORES" 2>&1 | tee -a "$RUN_LOG"
EXIT_CODE=${PIPESTATUS[0]}
log "GA Sets 6-8 batch finished with exit code $EXIT_CODE."
exit "$EXIT_CODE"
