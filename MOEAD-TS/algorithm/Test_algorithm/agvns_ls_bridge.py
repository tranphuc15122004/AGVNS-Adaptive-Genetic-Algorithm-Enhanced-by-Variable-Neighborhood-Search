"""Load the shared AGVNS local-search implementation for MOEA/D--TS.

The project runs every algorithm variant in a separate Python subprocess, so
the AGVNS source can be executed with MOEA/D--TS's object model and evaluator
imports while remaining a single source of truth for the four local-search
operators.  A subsequent AGVNS LS update is therefore picked up by the next
MOEA/D--TS dispatch subprocess without copying code between variants.
"""

from functools import lru_cache
import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def agvns_ls_source_path() -> Path:
    """Return the repository-level AGVNS local-search source path."""
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "AGVNS" / "algorithm" / "Test_algorithm" / "new_LS.py"


@lru_cache(maxsize=1)
def load_agvns_ls() -> ModuleType:
    """Load AGVNS LS under an isolated module name in this subprocess."""
    source_path = agvns_ls_source_path()
    if not source_path.is_file():
        raise RuntimeError(
            "shared AGVNS local-search source is unavailable: {}".format(source_path)
        )
    module_name = "moead_ts_shared_agvns_local_search"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared AGVNS local-search source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
