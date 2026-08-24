"""Parallel AGVNS experiment adapter."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parallel_runner import run_parallel_main  # noqa: E402


if __name__ == "__main__":
    run_parallel_main(
        os.path.dirname(os.path.abspath(__file__)),
        "AGVNS",
        seed_env="AGVNS_RANDOM_SEED",
    )
