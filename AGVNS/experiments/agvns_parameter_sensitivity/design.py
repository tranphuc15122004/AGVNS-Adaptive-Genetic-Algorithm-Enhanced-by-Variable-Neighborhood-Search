"""Immutable design matrix and job schedule for AGVNS screening."""

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Tuple


@dataclass(frozen=True)
class Configuration:
    configuration_id: int
    threshold_orders: int
    population_size: int
    perturbation_rate: float
    mutation_rate: float


TAGUCHI_DESIGN = (
    Configuration(1, 40, 20, 0.25, 0.10),
    Configuration(2, 40, 40, 0.50, 0.25),
    Configuration(3, 40, 60, 0.75, 0.50),
    Configuration(4, 80, 20, 0.50, 0.50),
    Configuration(5, 80, 40, 0.75, 0.10),
    Configuration(6, 80, 60, 0.25, 0.25),
    Configuration(7, 120, 20, 0.75, 0.25),
    Configuration(8, 120, 40, 0.25, 0.50),
    Configuration(9, 120, 60, 0.50, 0.10),
)

BASELINE_CONFIGURATION_ID = 10
BASELINE_CONFIGURATION = Configuration(10, 80, 40, 0.50, 0.25)
DESIGN = TAGUCHI_DESIGN + (BASELINE_CONFIGURATION,)

# Set 8 -> Set 1. Each set contributes its first two benchmark instances.
INSTANCE_IDS = (57, 58, 49, 50, 41, 42, 33, 34, 25, 26, 17, 18, 9, 10, 1, 2)
REPETITIONS = 3

_T_LEVELS = (40, 80, 120)
_POPULATION_LEVELS = (20, 40, 60)
_PERTURBATION_LEVELS = (0.25, 0.50, 0.75)
_MUTATION_LEVELS = (0.10, 0.25, 0.50)


def validate_design() -> None:
    """Fail fast if the committed screening design is changed incorrectly."""
    if len(TAGUCHI_DESIGN) != 9 or len(DESIGN) != 10:
        raise ValueError("The screening design must contain 9 Taguchi rows plus one baseline")
    ids = [row.configuration_id for row in DESIGN]
    if ids != list(range(1, 11)):
        raise ValueError("Configuration IDs must be the contiguous range 1..10")
    if len({(row.threshold_orders, row.population_size, row.perturbation_rate, row.mutation_rate) for row in DESIGN}) != 10:
        raise ValueError("Screening configurations must be unique")
    if DESIGN[BASELINE_CONFIGURATION_ID - 1] != BASELINE_CONFIGURATION:
        raise ValueError("The current AGVNS baseline must be configuration 10")

    domains = (
        ((row.threshold_orders for row in TAGUCHI_DESIGN), _T_LEVELS, 3),
        ((row.population_size for row in TAGUCHI_DESIGN), _POPULATION_LEVELS, 3),
        ((row.perturbation_rate for row in TAGUCHI_DESIGN), _PERTURBATION_LEVELS, 3),
        ((row.mutation_rate for row in TAGUCHI_DESIGN), _MUTATION_LEVELS, 3),
    )
    for values, levels, expected_count in domains:
        values = tuple(values)
        counts = {level: sum(value == level for value in values) for level in levels}
        if any(count != expected_count for count in counts.values()):
            raise ValueError("Unbalanced screening levels: %s" % counts)
    if len(INSTANCE_IDS) != 16 or len(set(INSTANCE_IDS)) != 16:
        raise ValueError("Exactly 16 unique instances are required")
    if any(instance_id <= 0 or instance_id > 64 for instance_id in INSTANCE_IDS):
        raise ValueError("Screening instance IDs must be in the benchmark range 1..64")


def configuration_by_id(configuration_id: int) -> Configuration:
    validate_design()
    for row in DESIGN:
        if row.configuration_id == configuration_id:
            return row
    raise KeyError("Unknown configuration ID: %s" % configuration_id)


def job_seed(base_seed: int, instance_id: int, repetition: int) -> int:
    if instance_id <= 0 or repetition <= 0:
        raise ValueError("instance_id and repetition must be positive")
    return int(base_seed) + int(instance_id) * 1000 + int(repetition)


def iter_jobs(base_seed: int = 20260824) -> Iterator[Dict[str, object]]:
    validate_design()
    for instance_id in INSTANCE_IDS:
        for configuration in DESIGN:
            for repetition in range(1, REPETITIONS + 1):
                yield {
                    "configuration_id": configuration.configuration_id,
                    "threshold_orders": configuration.threshold_orders,
                    "population_size": configuration.population_size,
                    "perturbation_rate": configuration.perturbation_rate,
                    "mutation_rate": configuration.mutation_rate,
                    "instance_id": instance_id,
                    "repetition": repetition,
                    "seed": job_seed(base_seed, instance_id, repetition),
                }


def expected_job_count() -> int:
    return len(DESIGN) * len(INSTANCE_IDS) * REPETITIONS


validate_design()
