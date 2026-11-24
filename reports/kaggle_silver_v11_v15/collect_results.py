"""Extract completed Top-2 simulations from saved Kaggle session logs (versions 11-15)."""

import csv
import datetime
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCORE = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+).*Score of instance_(\d+):\s*([\deE.+-]+), runtime:\s*([\d.]+)s')
VEHICLE = re.compile(r'Traveling Distance of Vehicle (V_\d+) is\s+([\d.]+), visited node list: (\d+)')


def save_csv(name, rows):
    with (ROOT / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_version_summary():
    summaries = []
    for v in range(11, 16):
        v_dir = ROOT / ('v%02d' % v)
        log_file = v_dir / 'session.log'
        json_file = v_dir / 'session.json'
        
        events = json.loads(json_file.read_text(encoding='utf-8'))
        text = log_file.read_text(encoding='utf-8')
        
        scores = []
        for line in text.splitlines():
            m = SCORE.search(line)
            if m:
                scores.append([m[2], m[3], m[4]])
        
        errors = [line for line in text.splitlines() if 'ERROR' in line]
        end_time = events[-1]['time'] if events else 0.0
        
        # Commands from notebook
        nb_file = v_dir / 'notebook.ipynb'
        commands = []
        if nb_file.exists():
            nb = json.loads(nb_file.read_text(encoding='utf-8'))
            for cell in nb.get('cells', []):
                if cell.get('cell_type') == 'code':
                    src = "".join(cell.get('source', []))
                    if 'main.py' in src:
                        commands.append(src.strip())
        
        summaries.append({
            'version': v,
            'status': 'KernelWorkerStatus.COMPLETE',
            'commands': commands,
            'scores': scores,
            'error_count': len(errors),
            'errors_tail': errors[-5:],
            'log_bytes': json_file.stat().st_size,
            'end_seconds': end_time,
        })
    
    with (ROOT / 'version_summary.json').open('w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2)


def main():
    results, vehicles = [], []
    for version in range(11, 16):
        pending_vehicles, distance, overtime = [], None, None
        for line in (ROOT / ('v%02d' % version) / 'session.log').read_text(encoding='utf-8').splitlines():
            m = VEHICLE.search(line)
            if m:
                pending_vehicles.append((m[1], float(m[2]), int(m[3])))
            m = re.search(r'Total distance:\s+([\d.]+)', line)
            if m:
                distance = float(m[1])
            m = re.search(r'Sum over time:\s+([\d.]+)', line)
            if m:
                overtime = float(m[1])
            m = SCORE.search(line)
            if not m:
                continue
            instance, score, runtime = int(m[2]), float(m[3]), float(m[4])
            count = len(pending_vehicles)
            assert distance is not None and overtime is not None and count > 0
            assert abs(sum(v[1] for v in pending_vehicles) - distance) < .001
            distance_cost = distance / count
            overtime_cost = overtime * 10000 / 3600
            assert math.isclose(score, distance_cost + overtime_cost, rel_tol=1e-10, abs_tol=1e-5)
            finished = datetime.datetime.strptime(m[1], '%Y-%m-%d %H:%M:%S,%f')
            started = finished - datetime.timedelta(seconds=runtime)
            if 41 <= instance <= 64:
                results.append(dict(version=version, instance=instance, status='SUCCESS', score=score,
                    runtime_seconds=runtime, start_utc_approx=started.isoformat(),
                    finish_utc_log=finished.isoformat(), vehicle_count=count, distance_km=distance,
                    overtime_seconds=overtime, distance_cost=distance_cost, overtime_cost=overtime_cost,
                    source='v%02d/session.log' % version))
                for vid, dist, nodes in pending_vehicles:
                    vehicles.append(dict(version=version, instance=instance, vehicle=vid,
                        distance_km=dist, position_history_entries=nodes))
            pending_vehicles, distance, overtime = [], None, None
            
    assert len(results) == 120
    assert {(x['version'], x['instance']) for x in results} == {(v, i) for v in range(11, 16) for i in range(41, 65)}
    save_csv('completed_runs_41_64.csv', results)
    save_csv('vehicle_distances_41_64.csv', vehicles)
    
    summary = []
    for instance in range(41, 65):
        rows = [r for r in results if r['instance'] == instance]
        assert len({r['score'] for r in rows}) == 1
        times = [r['runtime_seconds'] for r in rows]
        r = rows[0]
        summary.append(dict(instance=instance, runs=len(rows), score=r['score'],
            vehicle_count=r['vehicle_count'], distance_km=r['distance_km'],
            overtime_seconds=r['overtime_seconds'], distance_cost=r['distance_cost'],
            overtime_cost=r['overtime_cost'], runtime_mean_seconds=statistics.mean(times),
            runtime_std_population_seconds=statistics.pstdev(times), runtime_min_seconds=min(times),
            runtime_max_seconds=max(times), **{'runtime_v%d_seconds' % x['version']: x['runtime_seconds'] for x in rows}))
    save_csv('summary_by_instance_41_64.csv', summary)
    
    build_version_summary()
    print(json.dumps({'completed_runs': len(results), 'instances': len(summary), 'vehicle_rows': len(vehicles),
        'versions': [11, 12, 13, 14, 15], 'missing': []}, indent=2))


if __name__ == '__main__':
    main()
