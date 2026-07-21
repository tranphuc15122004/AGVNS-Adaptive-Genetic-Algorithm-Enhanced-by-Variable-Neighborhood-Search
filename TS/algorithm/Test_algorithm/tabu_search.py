"""
Tabu Search Baseline for the PDP (Pickup and Delivery Problem) with time windows.

Design follows classical Tabu Search (Glover 1989, 1990):
  - Short-term memory (tabu list):  prevents cycling back to recently visited solutions
  - Aspiration criterion:           overrides tabu status when a move yields a new global best
  - Long-term memory (frequency):   guides diversification away from over-used vehicles
  - Intensification:                deeper local search when a new best is discovered

All heavy components (fitness, feasibility, LS operators, perturbation) are reused
from the existing framework to minimise implementation effort.
"""

from typing import Dict, List, Optional, Set, Tuple
from algorithm.Object import *
import algorithm.algorithm_config as config
import random
import time
from algorithm.engine import *
import copy
from algorithm.Test_algorithm.new_engine import *
from algorithm.Test_algorithm.new_LS import *
from algorithm.Test_algorithm.MA_engine import *
from collections import deque


# ═══════════════════════════════════════════════════════════════════════
#  TABU SEARCH HYPER-PARAMETERS
# ═══════════════════════════════════════════════════════════════════════

TABU_TENURE_MIN      = 5        # minimum iterations a move stays tabu
TABU_TENURE_FACTOR   = 0.5      # multiplier for sqrt(|PDG|) dynamic component
TABU_LIST_MAX_SIZE   = 80       # hard cap on tabu list length (FIFO eviction)
STAGNATION_LIMIT     = 15       # consecutive non-improving iterations → diversify
DIVERSIFY_RATE       = 0.3      # fraction of PDGs relocated during perturbation
INTENSIFY_ITERS      = 8        # extra LS sweeps when a new best is found

# Adaptive iteration bounds (scaled by number of PDG pairs)
MAX_ITERATIONS_MIN   = 50       # floor for very small problems
MAX_ITERATIONS_MAX   = 300      # ceiling for large problems
MAX_ITERATIONS_PER_PDG = 20    # additional iterations per PDG pair


# ═══════════════════════════════════════════════════════════════════════
#  TABU LIST (short-term memory)
# ═══════════════════════════════════════════════════════════════════════

def _compute_tenure(num_pdg: int) -> int:
    """Dynamic tabu tenure: scales with problem size."""
    return TABU_TENURE_MIN + max(0, int(TABU_TENURE_FACTOR * math.sqrt(max(1, num_pdg))))


def _make_move_signature(operator_name: str, route_repr: str) -> str:
    """Create a compact hash-based signature that identifies a move.

    We use a hash of the full route representation so that the tabu list
    prevents returning to the *exact same* routing configuration.
    """
    return f"{operator_name}|{abs(hash(route_repr)) & 0x7FFFFFFF}"


def _add_tabu(signature: str, tabu_deque: deque, tabu_set: Set[str]) -> None:
    """Push a signature onto the FIFO tabu list."""
    if len(tabu_deque) >= TABU_LIST_MAX_SIZE:
        oldest = tabu_deque.popleft()
        tabu_set.discard(oldest)
    tabu_deque.append(signature)
    tabu_set.add(signature)


# ═══════════════════════════════════════════════════════════════════════
#  FREQUENCY MAP (long-term memory for diversification)
# ═══════════════════════════════════════════════════════════════════════

def _route_vehicle_usage(solution: Dict[str, List[Node]]) -> Dict[str, int]:
    """Count non-empty nodes per vehicle as a rough activity measure."""
    return {vid: len(route) for vid, route in solution.items()}


# ═══════════════════════════════════════════════════════════════════════
#  CORE: Tabu Search
# ═══════════════════════════════════════════════════════════════════════

def Tabu_Search(
    Base_vehicleid_to_plan: Dict[str, List[Node]],
    route_map: Dict[Tuple, Tuple],
    id_to_vehicle: Dict[str, Vehicle],
    orderID_to_nodelist: Optional[Dict[str, List[List[Node]]]],
    id_to_factory: Dict[str, Factory],
    id_to_unlocated_items: Dict[str, OrderItem],
    new_order_itemIDs: List[str],
) -> Optional[Chromosome]:
    """Run Tabu Search on a single starting solution.

    Parameters
    ----------
    Base_vehicleid_to_plan : existing route plan from previous simulation step.
    route_map             : distance / travel-time lookup.
    id_to_vehicle         : vehicle fleet information.
    orderID_to_nodelist   : PDG pair list produced by Pre_population_initialization_2.
    id_to_factory         : factory information used to build pickup/delivery nodes.
    id_to_unlocated_items : unallocated order items indexed by item ID.
    new_order_itemIDs     : new order item IDs to insert into the initial solution.

    Returns
    -------
    Best Chromosome found, or None when there are no new orders to schedule.
    """
    # ── 0. Guard: nothing to optimise ─────────────────────────────────
    if not new_order_itemIDs:
        return None

    start_time = time.time()

    # ── 1. Build initial feasible solution ───────────────────────────
    try:
        initial_plan = copy.deepcopy(Base_vehicleid_to_plan)
        worse_dispatch_new_orders(
            initial_plan,
            id_to_factory,
            route_map,
            id_to_vehicle,
            id_to_unlocated_items,
            new_order_itemIDs,
        )
        initial = Chromosome(initial_plan, route_map, id_to_vehicle)
    except Exception:
        # Fallback: return a Chromosome from the base plan itself
        return None

    current = copy.deepcopy(initial)
    best    = copy.deepcopy(current)
    best_cost = best.fitness

    # Estimate problem size for dynamic tenure and iteration budget
    num_pdg = sum(
        len(pairs) for pairs in (orderID_to_nodelist or {}).values()
    )
    tenure  = _compute_tenure(num_pdg)
    max_iter = min(MAX_ITERATIONS_MAX, max(MAX_ITERATIONS_MIN, MAX_ITERATIONS_PER_PDG * num_pdg))

    print(f'[TS-Tabu] Init: fitness={best_cost:.2f}, |PDG|={num_pdg}, '
          f'max_iter={max_iter}, tenure={tenure}')

    # ── 2. Tabu structures ──────────────────────────────────────────
    tabu_fifo: deque = deque(maxlen=TABU_LIST_MAX_SIZE)
    tabu_set:  Set[str] = set()

    # ── 3. Neighbourhood operators (ordered by increasing cost) ──────
    operators = [
        ('relocate_pdg',  new_multi_pd_group_relocate),
        ('exchange_pdg',  new_inter_couple_exchange),
        ('exchange_block', new_block_exchange),
        ('relocate_block', new_block_relocate),
    ]

    # ── 4. State variables ──────────────────────────────────────────
    stagnation   = 0
    iteration    = 0
    improve_cnt  = 0

    # ── 5. Main Tabu Search loop ────────────────────────────────────
    while not config.is_timeout() and iteration < max_iter:
        iteration += 1

        best_accept        = None          # best tabu-feasible neighbour
        best_accept_cost   = math.inf
        best_accept_sig    = ""
        best_aspirate      = None          # best aspirated (tabu-override) neighbour
        best_aspirate_cost = math.inf
        best_aspirate_sig  = ""

        # ── 5a. Explore neighbourhood ───────────────────────────────
        for op_name, op_func in operators:
            if config.is_timeout():
                break

            # Work on a **deep copy** so that a rejected move leaves original untouched
            candidate = copy.deepcopy(current)
            before = candidate.fitness

            improved = False
            try:
                improved = op_func(
                    candidate.solution,
                    id_to_vehicle,
                    route_map,
                    limit_time=config.LS_MAX_TIME_PER_OP,
                    is_limited=True,          # ← ONE single move per call
                )
            except Exception:
                continue

            if not improved:
                continue

            after = candidate.fitness

            # Generate tabu signature from the resulting route
            route_repr = get_route_after(candidate.solution, {})
            sig = _make_move_signature(op_name, route_repr)

            is_tabu = sig in tabu_set

            if not is_tabu:
                # Standard acceptance
                if after < best_accept_cost:
                    best_accept      = candidate
                    best_accept_cost = after
                    best_accept_sig  = sig
            else:
                # Aspiration: override tabu if this is a new global best
                if after < best_cost:
                    if after < best_aspirate_cost:
                        best_aspirate      = candidate
                        best_aspirate_cost = after
                        best_aspirate_sig  = sig

        # ── 5b. Choose next current solution ────────────────────────
        # Priority: aspirated move > best non-tabu move
        if best_aspirate is not None:
            current = best_aspirate
            _add_tabu(best_aspirate_sig, tabu_fifo, tabu_set)
        elif best_accept is not None:
            current = best_accept
            _add_tabu(best_accept_sig, tabu_fifo, tabu_set)
        else:
            stagnation += 1
            continue  # no feasible neighbour found

        cur_cost = current.fitness

        # ── 5c. Update global best + Intensification ────────────────
        if cur_cost < best_cost:
            best   = copy.deepcopy(current)
            best_cost = cur_cost
            stagnation = 0
            improve_cnt += 1

            # Intensification: run extra LS sweeps on the new best
            for _ in range(INTENSIFY_ITERS):
                if config.is_timeout():
                    break
                for op_name, op_func in operators:
                    if config.is_timeout():
                        break
                    try:
                        op_func(
                            best.solution,
                            id_to_vehicle,
                            route_map,
                            limit_time=config.LS_MAX_TIME_IN_SINGLE,
                            is_limited=True,
                        )
                    except Exception:
                        continue
                new_c = best.fitness
                if new_c < best_cost:
                    best_cost = new_c
        else:
            stagnation += 1

        # ── 5d. Progress reporting ──────────────────────────────────
        if iteration % 30 == 0 or (improve_cnt > 0 and iteration % 10 == 0):
            elapsed = time.time() - start_time
            print(f'[TS-Tabu] iter={iteration} best={best_cost:.2f} '
                  f'cur={cur_cost:.2f} stuck={stagnation} imp={improve_cnt} '
                  f't={elapsed:.1f}s')

        # ── 5e. Diversification ─────────────────────────────────────
        if stagnation >= STAGNATION_LIMIT:
            elapsed = time.time() - start_time
            print(f'[TS-Tabu] Diversifying at iter={iteration} '
                  f'(stuck={stagnation}, best={best_cost:.2f}, t={elapsed:.1f}s)')
            try:
                perturbed = disturbance_opt(
                    best.solution,
                    id_to_vehicle,
                    route_map,
                    relocate_rate=DIVERSIFY_RATE,
                )
                if perturbed is not None:
                    current = perturbed
                    stagnation = 0
                    # Clear tabu memory to allow exploration of new region
                    tabu_fifo.clear()
                    tabu_set.clear()
                    print(f'[TS-Tabu]   perturbed fitness = {current.fitness:.2f}')
            except Exception as e:
                print(f'[TS-Tabu]   diversification error: {e}', file=sys.stderr)

    # ── 6. Finalise ─────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f'[TS-Tabu] DONE: {iteration} iters, {improve_cnt} improvements, '
          f'best={best_cost:.2f}, time={elapsed:.2f}s')
    return best