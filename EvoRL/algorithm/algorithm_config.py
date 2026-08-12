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
LS_METHODS = ['PDPairExchange', 'BlockExchange', 'BlockRelocate', 'mPDG', '2opt']
BEGIN_TIME = 0
ALGO_TIME_LIMIT = 570
DELAY_DISPATCH = False
CROSSOVER_TYPE_RATIO = 0.0  
USE_ADAPTIVE_ORDER_DISCRIMINATE = True
WAITING_WEIGHT = 0

# EvoRL v1 runtime/training contract.  ``DEFER`` is intentionally absent from
# the action mask until pending-item restore is fixed and covered by epochs 2+.
EVORL_ENABLE_CANONICAL_DISPATCH = os.environ.get("EVORL_ENABLE_CANONICAL_DISPATCH", "1") == "1"
# A compatibility DEFER is represented by leaving an uncovered item in the
# simulator's unallocated stream.  It is not a learned action and is only
# taken when no valid DPDP insertion exists at this epoch; the next epoch
# recomputes pending coverage from the full generated item set.
EVORL_ALLOW_DEFER = os.environ.get("EVORL_ALLOW_DEFER", "1") == "1"
EVORL_POLICY_DEVICE = os.environ.get("EVORL_POLICY_DEVICE", "cpu")
EVORL_SHARED_POLICY = True
EVORL_UNCERTAINTY_ABLATION = os.environ.get("EVORL_UNCERTAINTY_ABLATION", "0") == "1"
EVORL_GA_TIME_LIMIT = float(os.environ.get("EVORL_GA_TIME_LIMIT", "30"))

# Random seed chung cho thuật toán. Simulator kế thừa qua env EVORL_RANDOM_SEED.
RANDOM_SEED = 0

def set_begin_time():
    """Set the start time for algorithm execution"""
    global BEGIN_TIME
    BEGIN_TIME = time.time()

def set_random_seed(seed=None):
    """Seed all random sources used by the algorithm child process.

    ``RANDOM_SEED`` is inherited by every simulator-launched subprocess;
    an explicit argument is useful for focused tests.
    """
    global RANDOM_SEED
    if seed is None:
        seed = os.environ.get("EVORL_RANDOM_SEED", RANDOM_SEED)
    RANDOM_SEED = int(seed)
    random.seed(RANDOM_SEED)
    if np is not None:
        np.random.seed(RANDOM_SEED)
    return RANDOM_SEED

def is_timeout() -> bool:
    """Check if algorithm has exceeded time limit"""
    return time.time() - BEGIN_TIME > ALGO_TIME_LIMIT

def get_remaining_time() -> float:
    """Get remaining time in seconds"""
    return max(0, ALGO_TIME_LIMIT - (time.time() - BEGIN_TIME))


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
