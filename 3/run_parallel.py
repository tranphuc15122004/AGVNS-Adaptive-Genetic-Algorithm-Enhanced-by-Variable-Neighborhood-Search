"""Parallel Top-3 C++ submission experiment adapter."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parallel_runner import run_parallel_main  # noqa: E402


if __name__ == "__main__":
    run_parallel_main(
        os.path.dirname(os.path.abspath(__file__)),
        "TOP-3",
        seed_env="DPDP_RANDOM_SEED",
        explicit_c_paths=True,
    )
