"""Canonical EvoRL implementation for the ICAPS DPDP benchmark.

The package deliberately does not import the legacy ``algorithm.engine`` at
module import time.  Legacy objects are accepted through small adapters so
that the training environment and the subprocess solver share the same
validation and planning contracts.
"""

from .dto import AtomicOrder, EpochState, FactoryState, InsertionResult, ItemState, RouteNode, VehicleState
from .atomic import chunk_items, mutable_item_ids
from .cost import CostBreakdown, projected_cost
from .planner import TransactionalPlanner
from .validator import SolutionValidator, ValidationReport

__all__ = [
    "AtomicOrder", "EpochState", "FactoryState", "InsertionResult", "ItemState", "RouteNode", "VehicleState",
    "chunk_items", "mutable_item_ids", "CostBreakdown", "projected_cost",
    "TransactionalPlanner", "SolutionValidator", "ValidationReport",
]
