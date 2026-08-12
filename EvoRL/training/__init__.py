"""Training utilities for the EvoRL DPDP policy."""

from .session import AlgorithmSessionState, HiddenStateSidecar
from .official_adapter import OfficialInputAdapter, RouteMapAdapter
from .official_env import OfficialDPDPEnv, OfficialEnvironmentError, OfficialStep
try:
    from .evorl_trainer import EvoRLTrainer
except ImportError:  # domain/session use does not require torch
    EvoRLTrainer = None

__all__ = [
    "AlgorithmSessionState", "HiddenStateSidecar", "OfficialInputAdapter", "RouteMapAdapter",
    "OfficialDPDPEnv", "OfficialEnvironmentError", "OfficialStep", "EvoRLTrainer",
]
