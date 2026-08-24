import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SubmissionCompatibilityTests(unittest.TestCase):
    def test_top2_algorithm_module_imports_with_installed_numpy(self):
        top2_root = ROOT / "2" / "Y_final_submission"
        result = subprocess.run(
            [sys.executable, "-c", "from algorithm.algorithm_demo import scheduling"],
            cwd=str(top2_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
