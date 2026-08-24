import os
import subprocess
import sys
import unittest


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMULATORS = [
    "AGVNS",
    "MA",
    "TS",
    "MOEAD-TS",
    "EvoRL",
    os.path.join("1", "compiled_files"),
    os.path.join("2", "Y_final_submission"),
    "3",
]


class SimulatorEntrypointTests(unittest.TestCase):
    def test_every_simulator_exposes_stats_file_option(self):
        for simulator in SIMULATORS:
            with self.subTest(simulator=simulator):
                result = subprocess.run(
                    [sys.executable, "main.py", "--help"],
                    cwd=os.path.join(REPOSITORY_ROOT, simulator),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("--stats-file", result.stdout)


if __name__ == "__main__":
    unittest.main()
