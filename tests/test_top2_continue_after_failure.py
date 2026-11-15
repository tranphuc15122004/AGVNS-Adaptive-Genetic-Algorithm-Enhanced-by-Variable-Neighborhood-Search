import json
import os
import subprocess
import sys
from pathlib import Path


def test_system_exit_does_not_abort_remaining_instances(tmp_path):
    root = Path(__file__).resolve().parents[1]
    variant = root / '2' / 'Y_final_submission'
    stats = tmp_path / 'runtime.csv'
    script = '''
import runpy, sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import src.simulator.simulate_api as api
def simulate(factory, route, instance):
    if instance == 'instance_9':
        raise SystemExit(-1)
    return 100.0
sys.argv = ['main.py', '--instances', '8,9,10', '--stats-file', sys.argv[2]]
with patch.object(api, 'simulate', simulate), patch('src.utils.log_utils.ini_logger'), patch('src.utils.log_utils.remove_file_handler_of_logging'):
    runpy.run_path('main.py', run_name='__main__')
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-c', script, str(variant), str(stats)], cwd=str(variant), env=env, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(stats.with_suffix('.json').read_text())
    assert [(r['instance_id'], r['status']) for r in report['per_instance']] == [('instance_8', 'SUCCESS'), ('instance_9', 'FAILED'), ('instance_10', 'SUCCESS')]
    assert 'SystemExit' in report['per_instance'][1]['error']
