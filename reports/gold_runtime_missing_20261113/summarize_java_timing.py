#!/home/tuantb/miniconda3/bin/python
"""Aggregate queue results and per-dispatch GNU time records after a Gold batch."""
import csv
import math
import pathlib
import statistics
import sys

run_root = pathlib.Path(sys.argv[1])
batches = sorted(p for p in run_root.iterdir() if p.is_dir() and (p / 'manifest.json').exists())
if len(batches) != 1:
    raise SystemExit('Expected exactly one batch, found %d' % len(batches))
batch = batches[0]
with (batch / 'results.csv').open(newline='', encoding='utf-8-sig') as handle:
    reader = csv.DictReader(handle)
    fields = list(reader.fieldnames or [])
    rows = list(reader)
extra = ['java_dispatch_total_seconds', 'java_dispatch_count', 'java_dispatch_failed_count', 'analysis_status']
for row in rows:
    path = batch / row['workspace'] / 'java_dispatch_times.csv'
    times = []
    failed = 0
    if path.exists():
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            pieces = line.split(',')
            if len(pieces) != 2:
                continue
            try:
                elapsed, code = float(pieces[0]), int(pieces[1])
            except ValueError:
                continue
            if math.isfinite(elapsed) and elapsed >= 0:
                times.append(elapsed)
                failed += code != 0
    row['java_dispatch_total_seconds'] = round(sum(times), 3) if times else ''
    row['java_dispatch_count'] = len(times)
    row['java_dispatch_failed_count'] = failed
    try:
        score = float(row['score'])
        valid_score = math.isfinite(score) and 0 <= score < sys.maxsize
    except (ValueError, TypeError):
        valid_score = False
    row['analysis_status'] = ('VALID' if row['status'] == 'SUCCESS' and valid_score and times and not failed
                              else 'CHECK_OR_FAILED')
with (batch / 'results_with_java_timing.csv').open('w', newline='', encoding='utf-8-sig') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields + extra)
    writer.writeheader()
    writer.writerows(rows)
summary = []
for instance in (57, 58, 59, 60, 63, 64):
    current = [r for r in rows if int(r['instance_id']) == instance]
    valid = [r for r in current if r['analysis_status'] == 'VALID']
    simulation = [float(r['simulation_runtime_seconds']) for r in valid if r['simulation_runtime_seconds']]
    java = [float(r['java_dispatch_total_seconds']) for r in valid]
    summary.append({'instance_id': instance, 'expected_runs': 4, 'finished_runs': len(current),
                    'valid_runs': len(valid), 'simulation_mean_seconds': round(statistics.mean(simulation), 3) if simulation else '',
                    'simulation_std_seconds': round(statistics.stdev(simulation), 3) if len(simulation) > 1 else '',
                    'java_mean_seconds': round(statistics.mean(java), 3) if java else '',
                    'java_std_seconds': round(statistics.stdev(java), 3) if len(java) > 1 else ''})
with (batch / 'summary_with_java_timing.csv').open('w', newline='', encoding='utf-8-sig') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)
print('Timing reports written to', batch, flush=True)
