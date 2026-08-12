"""Validated assignment-level GA teacher used during RPPO training only."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from algorithm.evorl.cost import projected_cost
from algorithm.evorl.dto import AtomicOrder, EpochState, RouteNode, VehicleState, item_attr
from algorithm.evorl.planner import TransactionalPlanner
from .paper_evaluator import evaluate_paper_fitness


@dataclass(frozen=True)
class GAConfig:
    population_size: int = 20
    generations: int = 20
    elite_size: int = 1
    tournament_size: int = 3
    crossover_probability: float = 0.9
    mutation_probability: float = 0.25
    time_limit_seconds: float = 30.0
    seed: int = 0
    selection: str = "fps"
    crossover_min: float = 0.6
    mutation_min: float = 0.05


@dataclass(frozen=True)
class Genome:
    order: Tuple[int, ...]
    vehicle_assignment: Tuple[int, ...]


@dataclass(frozen=True)
class GAResult:
    state: EpochState
    genome: Genome
    cost: float
    evaluated: int


@dataclass(frozen=True)
class FleetGenome:
    """Paper chromosome: one ordered order string per vehicle.

    A flattened permutation plus a vehicle label is used internally because it
    makes PMX and exact-coverage repair deterministic.  ``routes`` exposes the
    equivalent fleet-string representation described in Section 4.3.2.
    """

    order: Tuple[str, ...]
    vehicle_assignment: Tuple[str, ...]

    def __post_init__(self):
        if len(self.order) != len(self.vehicle_assignment):
            raise ValueError("fleet genome order/assignment length mismatch")
        if len(set(self.order)) != len(self.order):
            raise ValueError("fleet genome contains duplicate atomic IDs")

    @property
    def routes(self) -> Mapping[str, Tuple[str, ...]]:
        result: Dict[str, List[str]] = {}
        for atomic_id, vehicle_id in zip(self.order, self.vehicle_assignment):
            result.setdefault(str(vehicle_id), []).append(str(atomic_id))
        return {vehicle_id: tuple(values) for vehicle_id, values in sorted(result.items())}

    @classmethod
    def from_assignment(
        cls,
        atomics: Sequence[AtomicOrder],
        vehicle_ids: Sequence[str],
        assignments: Sequence[str],
    ) -> "FleetGenome":
        if len(atomics) != len(assignments):
            raise ValueError("assignment length does not match atomics")
        return cls(tuple(atomic.atomic_id for atomic in atomics), tuple(str(x) for x in assignments))


@dataclass(frozen=True)
class PaperGAResult:
    """Population trace and best phenotype for one Algorithm-1 macro-step."""

    state: EpochState
    genome: FleetGenome
    cost: float
    fitness: float
    population: Tuple[FleetGenome, ...]
    population_costs: Tuple[float, ...]
    evaluated: int
    generations_completed: int
    population_fitnesses: Tuple[float, ...] = ()

    @property
    def best_cost(self) -> float:
        return self.cost


class PaperEvolutionaryTeacher:
    """Fleet-string GA matching the paper's route-planning abstraction.

    The implementation is intentionally separate from ``EvolutionaryTeacher``
    so older domain smoke tests and legacy experiments remain reproducible.
    It evaluates candidates through the canonical decoder and validator, never
    through the unsafe legacy ``Chromosome`` implementation.
    """

    def __init__(self, config: GAConfig = GAConfig(), planner: Optional[TransactionalPlanner] = None):
        self.config = config
        self.planner = planner or TransactionalPlanner()

    def optimize(
        self,
        state: EpochState,
        atomics: Sequence[AtomicOrder],
        *,
        seed_genome: Optional[FleetGenome] = None,
        seed_state: Optional[EpochState] = None,
    ) -> PaperGAResult:
        vehicle_ids = tuple(sorted(state.vehicles))
        atomic_by_id = {atomic.atomic_id: atomic for atomic in atomics}
        if not atomics:
            cost = self._cost(state)
            return PaperGAResult(
                state, FleetGenome((), ()), cost, -cost,
                (FleetGenome((), ()),), (cost,), 1, 0, (-cost,),
            )
        if not vehicle_ids:
            raise ValueError("paper GA requires at least one vehicle")
        # Derive a deterministic stream per macro-epoch rather than replaying
        # the exact same random population at every simulator tick.
        rng = random.Random(self.config.seed + int(state.epoch))
        population: List[FleetGenome] = []
        if seed_genome is not None:
            population.append(self._repair(seed_genome, atomics, vehicle_ids))
        while len(population) < max(1, self.config.population_size):
            population.append(self._random_genome(atomics, vehicle_ids, rng))
        # Keep population unique while preserving the RL seed.
        population = self._unique_population(population)
        while len(population) < max(1, self.config.population_size):
            population.append(self._random_genome(atomics, vehicle_ids, rng))

        deadline = time.monotonic() + max(0.001, float(self.config.time_limit_seconds))
        best: Optional[Tuple[float, float, FleetGenome, EpochState]] = None
        evaluated = 0
        completed = 0
        scored_population: List[Tuple[float, float, FleetGenome, EpochState]] = []
        seed_key = population[0] if seed_genome is not None and population else None
        for generation in range(max(0, int(self.config.generations)) + 1):
            scored_population = []
            for genome in population:
                if evaluated and time.monotonic() >= deadline:
                    break
                # The RPPO phenotype H_t is already a transactionally valid
                # plan.  Re-decoding only its assignment chromosome can lose
                # the insertion order used by the policy, so preserve H_t as
                # the literal GA seed in generation zero.
                if generation == 0 and seed_state is not None and genome == seed_key:
                    candidate = seed_state
                else:
                    candidate = self._decode(
                        state, atomics, genome, atomic_by_id, deadline=deadline,
                    )
                evaluated += 1
                if candidate is None:
                    continue
                cost = self._cost(candidate)
                fitness = evaluate_paper_fitness(candidate).utility
                scored_population.append((fitness, cost, genome, candidate))
                if best is None or fitness > best[0]:
                    best = (fitness, cost, genome, candidate)
            if not scored_population:
                break
            scored_population.sort(key=lambda value: (-value[0], value[2].order, value[2].vehicle_assignment))
            if generation >= int(self.config.generations) or time.monotonic() >= deadline:
                break
            completed += 1
            average_fitness = sum(value[0] for value in scored_population) / len(scored_population)
            elite_count = max(1, min(self.config.elite_size, len(scored_population)))
            next_population = [value[2] for value in scored_population[:elite_count]]
            while len(next_population) < max(1, self.config.population_size):
                parent_a = self._select(scored_population, average_fitness, rng)
                parent_b = self._select(scored_population, average_fitness, rng)
                pair_fitness = max(
                    self._fitness_for(parent_a, scored_population),
                    self._fitness_for(parent_b, scored_population),
                )
                crossover_probability = self._adaptive_probability(
                    self.config.crossover_probability, self.config.crossover_min,
                    generation, pair_fitness >= average_fitness,
                )
                mutation_probability = self._adaptive_probability(
                    self.config.mutation_probability, self.config.mutation_min,
                    generation, pair_fitness >= average_fitness,
                )
                child = self._pmx(parent_a, parent_b, rng) if rng.random() < crossover_probability else parent_a
                if rng.random() < mutation_probability:
                    child = self._mutate(child, vehicle_ids, rng)
                next_population.append(self._repair(child, atomics, vehicle_ids))
            population = self._unique_population(next_population)
            while len(population) < max(1, self.config.population_size):
                population.append(self._random_genome(atomics, vehicle_ids, rng))

        if best is None:
            raise ValueError("paper GA could not construct a valid population")
        # ``best`` is tracked across generations, while ``scored_population``
        # only contains the final generation.  Algorithm 1 needs the selected
        # winner to be replayable for the PPO transition, so preserve the
        # global winner in the returned evaluated population even when it was
        # replaced by a later generation.
        final_entries = list(scored_population)
        if not any(entry[2] == best[2] for entry in final_entries):
            final_entries.insert(0, best)
        final_population = tuple(value[2] for value in final_entries)
        final_costs = tuple(float(value[1]) for value in final_entries)
        final_fitnesses = tuple(float(value[0]) for value in final_entries)
        return PaperGAResult(
            state=best[3], genome=best[2], cost=float(best[1]), fitness=float(best[0]),
            population=final_population, population_costs=final_costs,
            evaluated=evaluated, generations_completed=completed,
            population_fitnesses=final_fitnesses,
        )

    def _decode(
        self,
        state: EpochState,
        atomics: Sequence[AtomicOrder],
        genome: FleetGenome,
        atomic_by_id: Mapping[str, AtomicOrder],
        *,
        deadline: Optional[float] = None,
    ) -> Optional[EpochState]:
        if set(genome.order) != set(atomic_by_id) or len(genome.order) != len(atomic_by_id):
            return None
        assignments = dict(zip(genome.order, genome.vehicle_assignment))
        # The policy, GA, and inference paths all use the same transactional
        # insertion decoder.  This prevents a GA route-order improvement from
        # becoming an un-replayable teacher label at policy-only inference.
        return self.planner.decode_assignments(
            state,
            atomics,
            assignments,
            order=genome.order,
            deadline=deadline,
        )

    @staticmethod
    def _decode_sequence_blocks(vehicle: VehicleState, base_route, sequence: Sequence[AtomicOrder], items):
        """Group a fleet chromosome into capacity-feasible LIFO blocks."""

        def route_load() -> float:
            load = sum(float(item_attr(items.get(item_id), "demand", 0.0) or 0.0)
                       for item_id in vehicle.carrying_item_ids)
            for node in base_route:
                for item_id in node.delivery_item_ids:
                    load -= float(item_attr(items.get(item_id), "demand", 0.0) or 0.0)
                for item_id in node.pickup_item_ids:
                    load += float(item_attr(items.get(item_id), "demand", 0.0) or 0.0)
            return load

        capacity = float(vehicle.capacity)
        base_load = route_load()
        if base_load > capacity + 1e-8:
            return ()
        result = []
        block: List[AtomicOrder] = []
        block_load = base_load

        def flush() -> None:
            nonlocal block, block_load
            if not block:
                return
            for atomic in block:
                result.append(RouteNode(atomic.pickup_factory_id, atomic.item_ids, ()))
            for atomic in reversed(block):
                result.append(RouteNode(atomic.delivery_factory_id, (), tuple(reversed(atomic.item_ids))))
            block = []
            block_load = base_load

        for atomic in sequence:
            if block and block_load + atomic.demand > capacity + 1e-8:
                flush()
            if block_load + atomic.demand > capacity + 1e-8:
                # Existing carrying/route suffix leaves no room for this
                # atomic block; the candidate is rejected by validation.
                return ()
            block.append(atomic)
            block_load += float(atomic.demand)
        flush()
        return tuple(result)

    @staticmethod
    def _cost(state: EpochState) -> float:
        return projected_cost(
            {key: value.planned_route for key, value in state.vehicles.items()},
            state.vehicles, state.route_map, state.items, current_time=state.current_time,
        ).benchmark_cost

    @staticmethod
    def _random_genome(atomics: Sequence[AtomicOrder], vehicle_ids: Sequence[str], rng: random.Random) -> FleetGenome:
        order = list(atomics)
        rng.shuffle(order)
        assignment_by_order: Dict[str, str] = {}
        demand_by_order: Dict[str, float] = {}
        for atomic in atomics:
            demand_by_order[atomic.order_id] = demand_by_order.get(atomic.order_id, 0.0) + float(atomic.demand)
        assignments: List[str] = []
        for atomic in order:
            if demand_by_order[atomic.order_id] <= 15.0:
                assignment_by_order.setdefault(atomic.order_id, rng.choice(tuple(vehicle_ids)))
                assignments.append(assignment_by_order[atomic.order_id])
            else:
                assignments.append(rng.choice(tuple(vehicle_ids)))
        return FleetGenome(tuple(atomic.atomic_id for atomic in order), tuple(assignments))

    @staticmethod
    def _repair(genome: FleetGenome, atomics: Sequence[AtomicOrder], vehicle_ids: Sequence[str]) -> FleetGenome:
        valid_ids = {atomic.atomic_id for atomic in atomics}
        order = [atomic_id for atomic_id in genome.order if atomic_id in valid_ids]
        order.extend(atomic.atomic_id for atomic in atomics if atomic.atomic_id not in order)
        assignment = {atomic_id: vehicle_id for atomic_id, vehicle_id in zip(genome.order, genome.vehicle_assignment)}
        fallback = str(vehicle_ids[0])
        result_assignment = [assignment.get(atomic_id, fallback) if assignment.get(atomic_id) in vehicle_ids else fallback for atomic_id in order]
        by_order = {atomic.atomic_id: atomic.order_id for atomic in atomics}
        first_vehicle: Dict[str, str] = {}
        demand_by_order: Dict[str, float] = {}
        for atomic in atomics:
            demand_by_order[atomic.order_id] = demand_by_order.get(atomic.order_id, 0.0) + float(atomic.demand)
        for index, atomic_id in enumerate(order):
            order_id = by_order[atomic_id]
            if demand_by_order[order_id] <= 15.0:
                first_vehicle.setdefault(order_id, result_assignment[index])
                result_assignment[index] = first_vehicle[order_id]
        return FleetGenome(tuple(order), tuple(result_assignment))

    @staticmethod
    def _unique_population(population: Sequence[FleetGenome]) -> List[FleetGenome]:
        seen = set()
        result = []
        for genome in population:
            key = (genome.order, genome.vehicle_assignment)
            if key not in seen:
                seen.add(key)
                result.append(genome)
        return result

    @staticmethod
    def _fitness_for(genome: FleetGenome, scored: Sequence[Tuple[float, float, FleetGenome, EpochState]]) -> float:
        for fitness, _, candidate, _ in scored:
            if candidate == genome:
                return fitness
        return float("-inf")

    def _select(self, scored, average_fitness: float, rng: random.Random) -> FleetGenome:
        if self.config.selection != "fps":
            return min((scored[rng.randrange(len(scored))] for _ in range(max(1, self.config.tournament_size))), key=lambda value: value[1])[2]
        utilities = [max(0.0, value[0] - min(item[0] for item in scored) + 1e-9) for value in scored]
        total = sum(utilities)
        if total <= 0:
            return scored[rng.randrange(len(scored))][2]
        point = rng.random() * total
        running = 0.0
        for value, weight in zip(scored, utilities):
            running += weight
            if running >= point:
                return value[2]
        return scored[-1][2]

    def _pmx(self, left: FleetGenome, right: FleetGenome, rng: random.Random) -> FleetGenome:
        size = len(left.order)
        if size < 2:
            return left
        begin, end = sorted(rng.sample(range(size), 2))
        child = [None] * size
        child[begin:end + 1] = left.order[begin:end + 1]
        # Map the genes already copied from ``left`` to their counterparts
        # in ``right``.  The previous reverse mapping could form a cycle
        # (e.g. a two-gene swap) and hang the GA forever inside the repair
        # loop, defeating the configured time budget.
        segment = set(left.order[begin:end + 1])
        mapping = {left.order[index]: right.order[index] for index in range(begin, end + 1)}
        for index in list(range(0, begin)) + list(range(end + 1, size)):
            gene = right.order[index]
            while gene in segment:
                gene = mapping[gene]
            child[index] = gene
        left_vehicle = dict(zip(left.order, left.vehicle_assignment))
        right_vehicle = dict(zip(right.order, right.vehicle_assignment))
        assignments = tuple(left_vehicle.get(gene, right_vehicle.get(gene, "")) if begin <= index <= end else right_vehicle.get(gene, left_vehicle.get(gene, "")) for index, gene in enumerate(child))
        return FleetGenome(tuple(str(gene) for gene in child), assignments)

    @staticmethod
    def _mutate(genome: FleetGenome, vehicle_ids: Sequence[str], rng: random.Random) -> FleetGenome:
        order = list(genome.order)
        assignments = list(genome.vehicle_assignment)
        if len(order) > 1:
            left, right = rng.sample(range(len(order)), 2)
            order[left], order[right] = order[right], order[left]
            assignments[left], assignments[right] = assignments[right], assignments[left]
        if assignments:
            assignments[rng.randrange(len(assignments))] = rng.choice(tuple(vehicle_ids))
        return FleetGenome(tuple(order), tuple(assignments))

    def _adaptive_probability(self, maximum: float, minimum: float, generation: int, above_average: bool) -> float:
        if not above_average:
            return float(maximum)
        denominator = max(1, int(self.config.generations))
        return max(float(minimum), float(maximum) - (float(maximum) - float(minimum)) * generation / denominator)


class EvolutionaryTeacher:
    def __init__(self, config: GAConfig = GAConfig(), planner: Optional[TransactionalPlanner] = None):
        self.config = config
        self.planner = planner or TransactionalPlanner()

    def optimize(self, state: EpochState, atomics: Sequence[AtomicOrder], *, seed_genome: Optional[Genome] = None) -> GAResult:
        if not atomics:
            cost = projected_cost({key: value.planned_route for key, value in state.vehicles.items()}, state.vehicles, state.route_map, state.items, current_time=state.current_time).benchmark_cost
            return GAResult(state, Genome((), ()), cost, 0)
        rng = random.Random(self.config.seed)
        vehicle_count = max(1, len(state.vehicles))
        population: List[Genome] = []
        if seed_genome is not None:
            population.append(seed_genome)
        base_order = tuple(range(len(atomics)))
        while len(population) < self.config.population_size:
            order = list(base_order)
            rng.shuffle(order)
            assignments = tuple(rng.randrange(vehicle_count) for _ in atomics)
            population.append(Genome(tuple(order), assignments))

        best: Optional[GAResult] = None
        evaluated = 0
        deadline = time.monotonic() + self.config.time_limit_seconds
        vehicle_ids = sorted(state.vehicles)
        for _ in range(self.config.generations):
            scored = []
            for genome in population:
                if time.monotonic() >= deadline:
                    break
                candidate = self._decode(state, atomics, genome, vehicle_ids)
                evaluated += 1
                if candidate is None:
                    continue
                cost = projected_cost(
                    {key: value.planned_route for key, value in candidate.vehicles.items()},
                    candidate.vehicles, candidate.route_map, candidate.items,
                    current_time=candidate.current_time,
                ).benchmark_cost
                scored.append((cost, genome, candidate))
                if best is None or cost < best.cost:
                    best = GAResult(candidate, genome, cost, evaluated)
            if not scored or time.monotonic() >= deadline:
                break
            scored.sort(key=lambda value: value[0])
            elites = [value[1] for value in scored[:self.config.elite_size]]
            population = elites[:]
            while len(population) < self.config.population_size:
                parent_a = self._tournament(scored, rng)
                parent_b = self._tournament(scored, rng)
                child = self._crossover(parent_a, parent_b, rng) if rng.random() < self.config.crossover_probability else parent_a
                population.append(self._mutate(child, rng) if rng.random() < self.config.mutation_probability else child)
        if best is None:
            raise ValueError("GA could not construct a valid population")
        return GAResult(best.state, best.genome, best.cost, evaluated)

    def _decode(self, state, atomics, genome, vehicle_ids):
        current = state
        try:
            for atom_index in genome.order:
                selected = vehicle_ids[genome.vehicle_assignment[atom_index] % len(vehicle_ids)]
                result = self.planner.probe(current, atomics[atom_index], selected_vehicle=selected)
                if not result.ok:
                    return None
                current = self.planner.apply(current, result)
            report = self.planner.validator.validate(
                {key: value.planned_route for key, value in current.vehicles.items()},
                current.vehicles,
                current.items,
                destinations={key: value.destination for key, value in current.vehicles.items()},
            )
            return current if report.valid else None
        except (ValueError, IndexError, KeyError):
            return None

    @staticmethod
    def _tournament(scored, rng):
        choices = [scored[rng.randrange(len(scored))] for _ in range(3)]
        return min(choices, key=lambda value: value[0])[1]

    @staticmethod
    def _crossover(a: Genome, b: Genome, rng: random.Random) -> Genome:
        size = len(a.order)
        if size < 2:
            return a
        left, right = sorted(rng.sample(range(size), 2))
        child = [None] * size
        child[left:right] = a.order[left:right]
        remaining = [item for item in b.order if item not in child]
        for index in range(size):
            if child[index] is None:
                child[index] = remaining.pop(0)
        assignment = tuple(a.vehicle_assignment[index] if rng.random() < 0.5 else b.vehicle_assignment[index] for index in range(size))
        return Genome(tuple(child), assignment)

    @staticmethod
    def _mutate(genome: Genome, rng: random.Random) -> Genome:
        order = list(genome.order)
        assignment = list(genome.vehicle_assignment)
        if len(order) > 1:
            left, right = rng.sample(range(len(order)), 2)
            order[left], order[right] = order[right], order[left]
        if assignment:
            assignment[rng.randrange(len(assignment))] = rng.randrange(max(1, max(assignment) + 1))
        return Genome(tuple(order), tuple(assignment))
