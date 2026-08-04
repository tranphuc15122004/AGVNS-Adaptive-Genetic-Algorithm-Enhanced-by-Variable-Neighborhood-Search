# Timeout checking utilities
import os
import random
import time

try:
    import numpy as np
except ImportError:  # numpy is optional for the standalone algorithm process
    np = None

"""Problem constant"""
APPROACHING_DOCK_TIME = 1800
Delta = 10000.0 / 3600.0
Delta1 = 10000.0 
SLACK_TIME_THRESHOLD = 10000
debugPeriod = "0010-0020"
addDelta = 400000.0
# The four Algorithm-4 operators implemented as single-move samplers in
# MOEAD_TS.py (couple-exchange, block-exchange, couple-relocate, block-relocate).
# ``LS_METHODS`` is kept aligned with AGVNS/algorithm/Test_algorithm/GAVND7.py
# so instrumentation on a Chromosome cannot advertise obsolete TS-only moves.
LS_METHODS = ['PDPairExchange', 'BlockExchange', 'BlockRelocate', 'mPDG']
BEGIN_TIME = 0
# The paper and the simulator both impose a 600-second total process limit.
# Reserve only the final seconds for mandatory archive/JSON output; this time
# remains part of the same 600-second budget.
ALGO_TIME_LIMIT = 600
OUTPUT_RESERVE_SECONDS = 15.0
DELAY_DISPATCH = False
CROSSOVER_TYPE_RATIO = 0.0  
USE_ADAPTIVE_ORDER_DISCRIMINATE = True
WAITING_WEIGHT = 0

# Published MOEA/D--TS parameters.
MOEAD_POPULATION_SIZE = 6       # paper: N=6
MOEAD_NEIGHBOR_SIZE = 2         # paper: T=2
MOEAD_MAX_GENERATIONS = 50      # paper: max 50 outer iterations
MOEAD_DELTA = 0.9                # reproduction assumption; not disclosed
MOEAD_MAX_REPLACEMENTS = 2      # reproduction assumption; not disclosed

# Algorithm 4 parameters not disclosed in the paper.  Keep them configurable
# and log them as implementation choices in the algorithm manifest.
MOEAD_TS_TABU_LIST_SIZE = 20
MOEAD_TS_NEIGHBOR_THRESHOLD = 30
MOEAD_TS_MAX_ITERATIONS = 20
# Retained for backward compatibility with external scripts.  Algorithm 4 now
# generates single random moves per inner iteration, so this per-operator time
# slice is no longer applied by ``tabu_search``.
MOEAD_TS_OPERATOR_TIME_LIMIT = 1.0
MOEAD_INITIALIZATION_TIME_FRACTION = 0.25
MOEAD_INITIALIZATION_MAX_SECONDS = 90.0
MOEAD_RANDOM_SEED = 0
# Backward-compatible aliases for external scripts during migration.
TS_RANDOM_SEED = MOEAD_RANDOM_SEED
TS_TABU_LIST_SIZE = MOEAD_TS_TABU_LIST_SIZE
TS_MAX_ITERATIONS = MOEAD_TS_MAX_ITERATIONS
TS_NEIGHBORS_PER_OPERATOR = 1
TS_SEARCH_TIME_LIMIT = 8.0
TS_STAGNATION_LIMIT = 10
TS_OPERATOR_TIME_LIMIT = 0.25

def set_begin_time():
    """Set the start time for algorithm execution"""
    global BEGIN_TIME
    BEGIN_TIME = time.time()

def set_random_seed(seed=None):
    """Seed all random sources used by the MOEA/D--TS child process.

    ``MOEAD_RANDOM_SEED`` is inherited by every simulator-launched subprocess;
    the old ``TS_RANDOM_SEED`` name remains a compatibility fallback.
    """
    global MOEAD_RANDOM_SEED, TS_RANDOM_SEED
    if seed is None:
        seed = os.environ.get(
            "MOEAD_RANDOM_SEED",
            os.environ.get("TS_RANDOM_SEED", MOEAD_RANDOM_SEED),
        )
    MOEAD_RANDOM_SEED = int(seed)
    TS_RANDOM_SEED = MOEAD_RANDOM_SEED
    random.seed(MOEAD_RANDOM_SEED)
    if np is not None:
        np.random.seed(MOEAD_RANDOM_SEED)
    return MOEAD_RANDOM_SEED

def is_timeout() -> bool:
    """Check if algorithm has exceeded time limit"""
    return time.time() - BEGIN_TIME > ALGO_TIME_LIMIT

def get_remaining_time() -> float:
    """Get remaining time in seconds"""
    return max(0, ALGO_TIME_LIMIT - (time.time() - BEGIN_TIME))


def search_deadline() -> float:
    """Return the global optimization deadline with output safety margin."""
    if BEGIN_TIME == 0:
        set_begin_time()
    return BEGIN_TIME + ALGO_TIME_LIMIT - OUTPUT_RESERVE_SECONDS


def moead_parameter_manifest() -> dict:
    """Return paper parameters separately from reproduction assumptions."""
    return {
        "algorithm": "MOEAD-TS",
        "paper": {
            "population_size": MOEAD_POPULATION_SIZE,
            "neighborhood_size": MOEAD_NEIGHBOR_SIZE,
            "max_outer_iterations": MOEAD_MAX_GENERATIONS,
            "alpha": Delta,
            "normalization": False,
            "tabu_operators": [
                "pdg_exchange", "block_exchange",
                "pdg_relocate", "block_relocate",
            ],
        },
        "implementation_choice": {
            "delta": MOEAD_DELTA,
            "max_replacements": MOEAD_MAX_REPLACEMENTS,
            "tabu_list_size": MOEAD_TS_TABU_LIST_SIZE,
            "ts_max_iterations": MOEAD_TS_MAX_ITERATIONS,
            "neighbor_threshold": MOEAD_TS_NEIGHBOR_THRESHOLD,
            "tabu_item": "move key, not solution signature",
            "neighbor_generation": (
                "one random single move per inner iteration via "
                "sample_*_move in MOEAD_TS.py"
            ),
            "initialization_time_fraction": MOEAD_INITIALIZATION_TIME_FRACTION,
            "initialization_max_seconds": MOEAD_INITIALIZATION_MAX_SECONDS,
            "insertion": "exhaustive feasible positions until global deadline",
            "total_runtime_limit": ALGO_TIME_LIMIT,
            "output_reserve_seconds": OUTPUT_RESERVE_SECONDS,
        },
    }


"""GA configuration"""
POPULATION_SIZE = 20
NUMBER_OF_GENERATION = 20
MUTATION_RATE = 0.25
LS_MAX = 20
IMPROVED_IN_CROSS = 0
IMPROVED_IN_MUTATION = 0
IMPROVED_IN_DIVER = 0
"""Per local search time limit (seconds). Each LS operator should stop when exceeding this budget."""
LS_MAX_TIME_PER_OP = 8  # seconds (adjustable)
LS_MAX_TIME_IN_SINGLE = 1

# GA defensive guards
# Max attempts factor for producing offspring per missing child in a generation (used to avoid infinite loops)
OFFSPRING_ATTEMPTS_FACTOR = 10


def adaptive_config(num_orders: int, num_vehicles: int | None = None, time_budget_sec: float | None = None) -> dict:
    """Adapt GA configuration based on current workload.

    Mapping rule (as requested):
    - Map number of orders in [20, 70] linearly to population size in [40, 10].
      Below 20 orders -> POPULATION_SIZE = 40
      Above 80 orders -> POPULATION_SIZE = 10

    Other parameters remain unchanged.

    Returns a summary dict of the applied parameters for logging.
    """
    global POPULATION_SIZE

    # Define ranges
    min_orders, max_orders = 20, 80
    max_pop, min_pop = 40, 10
    min_mut, max_mut = 0.1, 0.4
    min_ls, max_ls = 20, 100

    # Clamp and interpolate linearly
    if num_orders <= min_orders:
        pop = max_pop
        mut = min_mut
        ls = min_ls
    elif num_orders >= max_orders:
        pop = min_pop
        mut = max_mut
        ls = max_ls
    else:
        ratio = (num_orders - min_orders) / (max_orders - min_orders)
        pop = round(max_pop + ratio * (min_pop - max_pop))
        mut = min_mut + ratio * (max_mut - min_mut)
        ls = round(min_ls + ratio * (max_ls - min_ls))

    global POPULATION_SIZE, MUTATION_RATE, LS_MAX
    POPULATION_SIZE = int(pop)
    MUTATION_RATE = float(mut)
    LS_MAX = int(ls)

    return {
        "num_orders": int(num_orders),
        "num_vehicles": int(num_vehicles) if num_vehicles is not None else None,
        "time_budget_sec": float(time_budget_sec) if time_budget_sec is not None else None,
        "POPULATION_SIZE": POPULATION_SIZE,
        "NUMBER_OF_GENERATION": NUMBER_OF_GENERATION,
        "MUTATION_RATE": MUTATION_RATE,
        "LS_MAX": LS_MAX,
        "LS_MAX_TIME_PER_OP": LS_MAX_TIME_PER_OP,
        "LS_MAX_TIME_IN_SINGLE": LS_MAX_TIME_IN_SINGLE,
    }

""" ACO configuration """
POPULATION_SIZE_ACO = 20
NUMBER_OF_GENERATION_ACO = 100
ALPHA = 1.0          # Mức độ ảnh hưởng của pheromone
BETA = 0.5           # Mức độ ảnh hưởng của heuristic
Q = 100              # Hằng số dùng trong cập nhật pheromone
BASE_PHEROMONE = 0.1         # Giá trị pheromone cơ bản\
EVAPORATION_RATE = 0.85   # Hệ số bay hơi (0.0 - 1.0)


"""modle"""
modle4 = [
    [0,1,2,3],
    [1,2,0,3],
    [0,3,1,2],
    [1,0,3,2]
]

modle6 = [
    [0,1,2,3,4,5],
    [0,2,3,1,4,5],
    [2,3,0,1,4,5],
    [0,2,1,4,3,5],
    [1,4,0,2,3,5],
    [0,1,4,2,3,5],
    [2,3,1,4,0,5],
    [1,2,3,4,0,5],
    [2,1,4,3,0,5],
    [1,4,2,3,0,5],
    [0,2,3,5,1,4],
    [2,3,0,5,1,4],
    [0,5,2,3,1,4],
    [2,0,5,3,1,4],
    [1,2,0,5,3,4],
    [1,0,5,2,3,4],
    [0,5,1,2,3,4],
    [2,3,1,0,5,4],
    [1,2,3,0,5,4],
    [1,0,2,3,5,4],
    [2,0,1,4,5,3],
    [2,1,4,0,5,3],
    [1,4,2,0,5,3],
    [0,5,2,1,4,3],
    [2,0,5,1,4,3],
    [2,1,0,5,4,3],
    [1,0,5,4,2,3],
    [0,5,1,4,2,3],
    [1,4,0,5,2,3],
    [0,1,4,5,2,3]
]
modle8 = [
    [0,1,2,3,4,5,6,7],
    [0,1,3,4,2,5,6,7],
    [3,4,0,1,2,5,6,7],
    [0,3,4,1,2,5,6,7],
    [2,5,0,1,3,4,6,7],
    [0,2,5,1,3,4,6,7],
    [0,1,2,5,3,4,6,7],
    [0,1,3,2,5,4,6,7],
    [3,4,0,2,5,1,6,7],
    [0,3,4,2,5,1,6,7],
    [0,2,3,4,5,1,6,7],
    [0,2,5,3,4,1,6,7],
    [2,5,0,3,4,1,6,7],
    [0,3,2,5,4,1,6,7],
    [2,5,3,4,0,1,6,7],
    [3,2,5,4,0,1,6,7],
    [3,4,2,5,0,1,6,7],
    [2,3,4,5,0,1,6,7],
    [0,1,2,5,6,3,4,7],
    [2,5,0,1,6,3,4,7],
    [0,2,5,1,6,3,4,7],
    [1,6,2,5,0,3,4,7],
    [2,1,6,5,0,3,4,7],
    [1,2,5,6,0,3,4,7],
    [2,5,1,6,0,3,4,7],
    [0,2,1,6,5,3,4,7],
    [0,1,6,2,5,3,4,7],
    [1,6,0,2,5,3,4,7],
    [0,3,1,2,5,6,4,7],
    [0,2,5,3,1,6,4,7],
    [2,5,0,3,1,6,4,7],
    [0,3,2,5,1,6,4,7],
    [0,3,1,6,2,5,4,7],
    [1,6,0,3,2,5,4,7],
    [0,1,6,3,2,5,4,7],
    [0,3,2,1,6,5,4,7],
    [0,3,1,6,4,2,5,7],
    [1,6,0,3,4,2,5,7],
    [0,1,6,3,4,2,5,7],
    [0,1,3,4,6,2,5,7],
    [3,4,0,1,6,2,5,7],
    [0,3,4,1,6,2,5,7],
    [3,1,6,4,0,2,5,7],
    [1,6,3,4,0,2,5,7],
    [3,4,1,6,0,2,5,7],
    [1,3,4,6,0,2,5,7],
    [0,2,1,3,4,6,5,7],
    [3,4,0,2,1,6,5,7],
    [0,3,4,2,1,6,5,7],
    [0,2,3,4,1,6,5,7],
    [0,2,1,6,3,4,5,7],
    [0,1,6,2,3,4,5,7],
    [1,6,0,2,3,4,5,7],
    [0,2,3,1,6,4,5,7],
    [1,6,2,5,3,4,0,7],
    [2,1,6,5,3,4,0,7],
    [2,5,1,6,3,4,0,7],
    [1,2,5,6,3,4,0,7],
    [2,5,3,1,6,4,0,7],
    [3,2,5,1,6,4,0,7],
    [3,1,2,5,6,4,0,7],
    [3,1,6,2,5,4,0,7],
    [1,6,3,2,5,4,0,7],
    [3,2,1,6,5,4,0,7],
    [2,5,1,3,4,6,0,7],
    [1,2,5,3,4,6,0,7],
    [1,3,2,5,4,6,0,7],
    [3,4,2,5,1,6,0,7],
    [2,3,4,5,1,6,0,7],
    [2,5,3,4,1,6,0,7],
    [3,2,5,4,1,6,0,7],
    [3,4,1,2,5,6,0,7],
    [1,3,4,2,5,6,0,7],
    [1,2,3,4,5,6,0,7],
    [3,4,2,1,6,5,0,7],
    [2,3,4,1,6,5,0,7],
    [2,1,3,4,6,5,0,7],
    [1,3,4,6,2,5,0,7],
    [3,4,1,6,2,5,0,7],
    [1,6,3,4,2,5,0,7],
    [3,1,6,4,2,5,0,7],
    [2,3,1,6,4,5,0,7],
    [2,1,6,3,4,5,0,7],
    [1,6,2,3,4,5,0,7],
    [2,5,3,4,0,7,1,6],
    [3,2,5,4,0,7,1,6],
    [3,4,2,5,0,7,1,6],
    [2,3,4,5,0,7,1,6],
    [3,4,0,2,5,7,1,6],
    [0,3,4,2,5,7,1,6],
    [0,2,3,4,5,7,1,6],
    [0,2,5,3,4,7,1,6],
    [2,5,0,3,4,7,1,6],
    [0,3,2,5,4,7,1,6],
    [3,0,7,4,2,5,1,6],
    [0,7,3,4,2,5,1,6],
    [3,4,0,7,2,5,1,6],
    [0,3,4,7,2,5,1,6],
    [2,0,3,4,7,5,1,6],
    [2,3,4,0,7,5,1,6],
    [3,4,2,0,7,5,1,6],
    [0,7,2,3,4,5,1,6],
    [2,0,7,3,4,5,1,6],
    [2,3,0,7,4,5,1,6],
    [2,0,7,5,3,4,1,6],
    [0,7,2,5,3,4,1,6],
    [2,5,0,7,3,4,1,6],
    [0,2,5,7,3,4,1,6],
    [3,0,2,5,7,4,1,6],
    [3,2,5,0,7,4,1,6],
    [2,5,3,0,7,4,1,6],
    [0,7,3,2,5,4,1,6],
    [3,0,7,2,5,4,1,6],
    [3,2,0,7,5,4,1,6],
    [2,0,7,5,1,3,4,6],
    [0,7,2,5,1,3,4,6],
    [2,5,0,7,1,3,4,6],
    [0,2,5,7,1,3,4,6],
    [1,0,2,5,7,3,4,6],
    [1,2,5,0,7,3,4,6],
    [2,5,1,0,7,3,4,6],
    [0,7,1,2,5,3,4,6],
    [1,0,7,2,5,3,4,6],
    [1,2,0,7,5,3,4,6],
    [1,3,2,5,0,7,4,6],
    [1,2,5,3,0,7,4,6],
    [2,5,1,3,0,7,4,6],
    [1,3,0,2,5,7,4,6],
    [1,3,0,7,2,5,4,6],
    [1,0,7,3,2,5,4,6],
    [0,7,1,3,2,5,4,6],
    [1,3,2,0,7,5,4,6],
    [1,3,0,7,4,2,5,6],
    [1,0,7,3,4,2,5,6],
    [0,7,1,3,4,2,5,6],
    [1,0,3,4,7,2,5,6],
    [3,4,1,0,7,2,5,6],
    [1,3,4,0,7,2,5,6],
    [0,7,3,4,1,2,5,6],
    [3,0,7,4,1,2,5,6],
    [0,3,4,7,1,2,5,6],
    [3,4,0,7,1,2,5,6],
    [3,4,1,2,0,7,5,6],
    [1,3,4,2,0,7,5,6],
    [1,2,3,4,0,7,5,6],
    [1,2,0,3,4,7,5,6],
    [1,2,3,0,7,4,5,6],
    [1,2,0,7,3,4,5,6],
    [0,7,1,2,3,4,5,6],
    [1,0,7,2,3,4,5,6],
    [1,0,2,5,3,4,7,6],
    [2,5,1,0,3,4,7,6],
    [1,2,5,0,3,4,7,6],
    [1,0,3,2,5,4,7,6],
    [2,5,1,3,4,0,7,6],
    [1,2,5,3,4,0,7,6],
    [1,3,2,5,4,0,7,6],
    [3,4,2,5,1,0,7,6],
    [2,3,4,5,1,0,7,6],
    [2,5,3,4,1,0,7,6],
    [3,2,5,4,1,0,7,6],
    [3,4,1,2,5,0,7,6],
    [1,3,4,2,5,0,7,6],
    [1,2,3,4,5,0,7,6],
    [1,3,4,0,2,5,7,6],
    [3,4,1,0,2,5,7,6],
    [1,0,3,4,2,5,7,6],
    [1,0,2,3,4,5,7,6],
    [2,5,3,1,0,7,6,4],
    [3,2,5,1,0,7,6,4],
    [3,1,2,5,0,7,6,4],
    [3,1,0,2,5,7,6,4],
    [3,1,2,0,7,5,6,4],
    [3,1,0,7,2,5,6,4],
    [3,0,7,1,2,5,6,4],
    [0,7,3,1,2,5,6,4],
    [2,0,7,5,3,1,6,4],
    [0,7,2,5,3,1,6,4],
    [2,5,0,7,3,1,6,4],
    [0,2,5,7,3,1,6,4],
    [3,0,2,5,7,1,6,4],
    [3,2,5,0,7,1,6,4],
    [2,5,3,0,7,1,6,4],
    [0,7,3,2,5,1,6,4],
    [3,0,7,2,5,1,6,4],
    [3,2,0,7,5,1,6,4],
    [0,1,2,5,6,7,3,4],
    [2,5,0,1,6,7,3,4],
    [0,2,5,1,6,7,3,4],
    [2,5,1,6,0,7,3,4],
    [1,2,5,6,0,7,3,4],
    [2,1,6,5,0,7,3,4],
    [1,6,2,5,0,7,3,4],
    [0,1,6,2,5,7,3,4],
    [1,6,0,2,5,7,3,4],
    [0,2,1,6,5,7,3,4],
    [1,0,7,6,2,5,3,4],
    [0,7,1,6,2,5,3,4],
    [1,6,0,7,2,5,3,4],
    [0,1,6,7,2,5,3,4],
    [2,0,1,6,7,5,3,4],
    [2,1,6,0,7,5,3,4],
    [1,6,2,0,7,5,3,4],
    [0,7,2,1,6,5,3,4],
    [2,0,7,1,6,5,3,4],
    [2,1,0,7,6,5,3,4],
    [1,2,0,7,5,6,3,4],
    [1,0,7,2,5,6,3,4],
    [0,7,1,2,5,6,3,4],
    [1,0,2,5,7,6,3,4],
    [2,5,1,0,7,6,3,4],
    [1,2,5,0,7,6,3,4],
    [0,7,2,5,1,6,3,4],
    [2,0,7,5,1,6,3,4],
    [0,2,5,7,1,6,3,4],
    [2,5,0,7,1,6,3,4],
    [3,2,0,7,1,6,5,4],
    [3,0,7,2,1,6,5,4],
    [0,7,3,2,1,6,5,4],
    [3,2,1,0,7,6,5,4],
    [3,1,0,7,6,2,5,4],
    [3,0,7,1,6,2,5,4],
    [0,7,3,1,6,2,5,4],
    [3,0,1,6,7,2,5,4],
    [1,6,3,0,7,2,5,4],
    [3,1,6,0,7,2,5,4],
    [0,7,1,6,3,2,5,4],
    [1,0,7,6,3,2,5,4],
    [0,1,6,7,3,2,5,4],
    [1,6,0,7,3,2,5,4],
    [3,2,0,1,6,7,5,4],
    [3,2,1,6,0,7,5,4],
    [1,6,3,2,0,7,5,4],
    [3,1,6,2,0,7,5,4],
    [3,0,1,2,5,6,7,4],
    [3,2,5,0,1,6,7,4],
    [2,5,3,0,1,6,7,4],
    [3,0,2,5,1,6,7,4],
    [2,5,1,6,3,0,7,4],
    [1,2,5,6,3,0,7,4],
    [2,1,6,5,3,0,7,4],
    [1,6,2,5,3,0,7,4],
    [3,1,2,5,6,0,7,4],
    [3,2,5,1,6,0,7,4],
    [2,5,3,1,6,0,7,4],
    [3,2,1,6,5,0,7,4],
    [1,6,3,2,5,0,7,4],
    [3,1,6,2,5,0,7,4],
    [3,0,2,1,6,5,7,4],
    [3,0,1,6,2,5,7,4],
    [1,6,3,0,2,5,7,4],
    [3,1,6,0,2,5,7,4],
    [2,0,1,6,3,4,7,5],
    [2,1,6,0,3,4,7,5],
    [1,6,2,0,3,4,7,5],
    [2,0,3,1,6,4,7,5],
    [2,0,1,3,4,6,7,5],
    [2,0,3,4,1,6,7,5],
    [3,4,2,0,1,6,7,5],
    [2,3,4,0,1,6,7,5],
    [1,3,4,6,2,0,7,5],
    [3,4,1,6,2,0,7,5],
    [1,6,3,4,2,0,7,5],
    [3,1,6,4,2,0,7,5],
    [2,1,3,4,6,0,7,5],
    [3,4,2,1,6,0,7,5],
    [2,3,4,1,6,0,7,5],
    [2,3,1,6,4,0,7,5],
    [1,6,2,3,4,0,7,5],
    [2,1,6,3,4,0,7,5],
    [3,0,1,6,7,4,2,5],
    [1,6,3,0,7,4,2,5],
    [3,1,6,0,7,4,2,5],
    [0,7,1,6,3,4,2,5],
    [1,0,7,6,3,4,2,5],
    [0,1,6,7,3,4,2,5],
    [1,6,0,7,3,4,2,5],
    [3,1,0,7,6,4,2,5],
    [3,0,7,1,6,4,2,5],
    [0,7,3,1,6,4,2,5],
    [1,0,3,4,7,6,2,5],
    [1,3,4,0,7,6,2,5],
    [3,4,1,0,7,6,2,5],
    [0,7,1,3,4,6,2,5],
    [1,0,7,3,4,6,2,5],
    [1,3,0,7,4,6,2,5],
    [3,0,7,4,1,6,2,5],
    [0,7,3,4,1,6,2,5],
    [3,4,0,7,1,6,2,5],
    [0,3,4,7,1,6,2,5],
    [0,3,1,6,4,7,2,5],
    [1,6,0,3,4,7,2,5],
    [0,1,6,3,4,7,2,5],
    [0,1,3,4,6,7,2,5],
    [3,4,0,1,6,7,2,5],
    [0,3,4,1,6,7,2,5],
    [3,1,6,4,0,7,2,5],
    [1,6,3,4,0,7,2,5],
    [3,4,1,6,0,7,2,5],
    [1,3,4,6,0,7,2,5],
    [2,1,3,4,0,7,6,5],
    [2,3,4,1,0,7,6,5],
    [3,4,2,1,0,7,6,5],
    [2,1,0,3,4,7,6,5],
    [2,1,3,0,7,4,6,5],
    [2,1,0,7,3,4,6,5],
    [0,7,2,1,3,4,6,5],
    [2,0,7,1,3,4,6,5],
    [2,0,3,4,7,1,6,5],
    [3,4,2,0,7,1,6,5],
    [2,3,4,0,7,1,6,5],
    [2,3,0,7,4,1,6,5],
    [0,7,2,3,4,1,6,5],
    [2,0,7,3,4,1,6,5],
    [0,3,4,7,2,1,6,5],
    [3,4,0,7,2,1,6,5],
    [0,7,3,4,2,1,6,5],
    [3,0,7,4,2,1,6,5],
    [2,3,0,7,1,6,4,5],
    [0,7,2,3,1,6,4,5],
    [2,0,7,3,1,6,4,5],
    [2,3,1,0,7,6,4,5],
    [1,6,2,3,0,7,4,5],
    [2,1,6,3,0,7,4,5],
    [2,3,1,6,0,7,4,5],
    [2,3,0,1,6,7,4,5],
    [0,7,1,6,2,3,4,5],
    [1,0,7,6,2,3,4,5],
    [1,6,0,7,2,3,4,5],
    [0,1,6,7,2,3,4,5],
    [1,6,2,0,7,3,4,5],
    [2,1,6,0,7,3,4,5],
    [2,0,1,6,7,3,4,5],
    [2,0,7,1,6,3,4,5],
    [0,7,2,1,6,3,4,5],
    [2,1,0,7,6,3,4,5]
]
