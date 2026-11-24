#!/bin/bash
set -u
ROOT='/home/tuantb/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search'
REPORT="$ROOT/reports/gold_runtime_missing_20261113"
export PATH="$REPORT/bin:$PATH"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$ROOT/1/compiled_files" || exit 1
/home/tuantb/miniconda3/bin/python run_parallel.py --instances 57,58,59,60,63,64 --repetitions 4 --workers 12 --cores 0,1,2,3,4,5,6,7,8,9,10,11 --base-seed 20261113 --run-root "$REPORT/runs" --python /home/tuantb/miniconda3/bin/python >> "$REPORT/launcher.log" 2>&1
runner_status=$?
/home/tuantb/miniconda3/bin/python "$REPORT/summarize_java_timing.py" "$REPORT/runs" >> "$REPORT/launcher.log" 2>&1 || true
exit "$runner_status"
