# AGVNS Project Guidelines

This repository implements and compares several algorithms for the **Dynamic Pickup and Delivery Problem (DPDP)** from the Huawei Cloud Intelligent Logistics Scheduling Competition. See [`README.md`](README.md) for the full project overview and [`simulation.md`](simulation.md) for input/output JSON format details.

## Architecture

Three main Python algorithm variants share a common simulator infrastructure:

| Directory | Algorithm | Key Characteristics |
|-----------|-----------|-------------------|
| `AGVNS/` | **Adaptive GA + VNS** (Proposed) | Population 40, generations 20, `CROSSOVER_TYPE_RATIO=1.0`, `LS_MAX=1`, `LS_METHODS` includes `'MA'` |
| `MA/` | **Memetic Algorithm** (Baseline) | Population 20, generations 20, `CROSSOVER_TYPE_RATIO=0.0`, `LS_MAX=20` |
| `TS/` | **Tabu Search** (Baseline) | Population 20, generations 15, `CROSSOVER_TYPE_RATIO=0.0`, `LS_MAX=15`, `LS_MAX_TIME_PER_OP=5s` |

**Competition baselines** (not Python): `1/` (Java, Top-1), `2/` (Python, Top-2), `3/` (C++, Top-3).

### Key Files per Variant

Each variant (`TS/`, `MA/`, `AGVNS/`) follows the same layout:
- `main.py` — Simulator entry point (drives simulation loop over instances)
- `main_algorithm.py` — Algorithm entry point (called by simulator as subprocess; must print `"SUCCESS"` on completion)
- `algorithm/main.py` — Core orchestrator (reads input, runs algorithm, writes output)
- `algorithm/algorithm_config.py` — All hyperparameters (population, generations, mutation rate, LS methods, time limit)
- `algorithm/In_and_Out.py` — JSON/CSV I/O layer
- `algorithm/engine.py` — Base engine (scene restoration, cost computation, selection, delay dispatch)
- `algorithm/local_search.py` — LS operators (PDPairExchange, BlockExchange, BlockRelocate, mPDG, 2-opt)
- `algorithm/Object/` — Data models (`Chromosome`, `Node`, `Vehicle`, `Factory`, `OrderItem`, etc.)
- `algorithm/Test_algorithm/` — Algorithm-specific implementations
- `src/conf/configs.py` — Simulator configuration (file paths, instance selection, pallet types)
- `src/simulator/` — Simulator core (simpy-based discrete-event simulation)
- `benchmark/` — 64 instances + `factory_info.csv` (154 factories) + `route_info.csv` (23,562 routes)

### Algorithm Pipeline (common across variants)

1. `Input()` → Read JSON/CSV from `data_interaction/`
2. `deal_old_solution_file()` → Clean previous solution data
3. `restore_scene_with_single_node()` → Rebuild vehicle plans from ongoing orders
4. Algorithm-specific dispatch → Optimize new orders
5. `update_solution_json()` → Save metadata
6. `merge_node()` → Merge consecutive same-factory nodes
7. `get_output_solution()` + `write_*_json_to_file()` → Output results

### AGVNS-specific Architecture

- `algorithm/Test_algorithm/GAVND7.py` — Best GA variant (adaptive GA + VNS)
- `algorithm/Test_algorithm/new_engine.py` — Advanced GA ops (crossover, selection)
- `algorithm/Test_algorithm/new_LS.py` — Advanced LS operators
- `algorithm/Test_algorithm/adaptive_ratio.py` — Adaptive crossover ratio (erfc/KWW decay)
- `main_with_viz.py` — Simulation + auto-visualization
- `posthoc_visualization.py` — Folium maps + Gantt charts from algorithm outputs

## Build, Run & Test

### Dependencies

- **Common**: `simpy`, `numpy`, `pandas`, `fastapi`, `uvicorn`, `flask-socketio`, `Flask`, `flask-cors`
- **AGVNS only**: `matplotlib`, `psutil`

Install for a specific variant:
```bash
cd <variant>
pip install -r requirements.txt
```

### Run Simulation

```bash
# Single instance
cd <variant>
python main.py --instances 1

# Multiple instances
python main.py --instances 1,2,3

# Custom data directory
python main.py --instances 1 --data-dir algorithm/data_interaction_runs/test_run

# CPU pinning (Linux)
python main.py --cpu 0
```

### Run Algorithm Standalone (debugging)

```bash
cd <variant>
python main_algorithm.py
```

### Parallel Runs (MA/TS only)

```bash
python run_parallel.py --all --cores 0,1,2,3
```

### Simulation Flow

1. Simulator ticks every **10 simulated minutes**
2. Writes JSON input → `algorithm/data_interaction/`
3. Calls algorithm subprocess (timeout: **10 minutes real time**)
4. Algorithm reads JSON, computes, writes output JSON
5. Algorithm **must print `"SUCCESS"`** to signal completion
6. Simulator validates and advances

## Coding Conventions

- **Python 3.6+** (3.12+ recommended)
- **Imports**: Standard library → third-party → local. Relative imports within `algorithm/` package (`from algorithm.Object import *`)
- **Type hints**: Required for all function signatures (`Dict`, `List`, `Optional`, `Chromosome`, `Node`)
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for config globals
- **Config pattern**: Global module-level variables in `algorithm_config.py`, modified by `adaptive_config()` at runtime
- **Error handling**: `try/except` with `traceback.format_exc()` logging; outer wrapper in `main_algorithm.py` catches all exceptions
- **Logging**: Use `logger` from `src.utils.logging_engine` (not `print`)
- **Comments**: Bilingual (Vietnamese and English)

## Key Configuration Parameters

See `algorithm/algorithm_config.py` in each variant. Key parameters:

| Parameter | AGVNS | MA/TS |
|-----------|-------|-------|
| `POPULATION_SIZE` | 40 (adaptive: 10–40) | 20 |
| `NUMBER_OF_GENERATION` | 20 | 20 (TS: 15) |
| `MUTATION_RATE` | 0.25 | 0.25 |
| `LS_MAX` | 1 | 20 (TS: 15) |
| `CROSSOVER_TYPE_RATIO` | 1.0 | 0.0 |
| `ALGO_TIME_LIMIT` | 570s | 570s |
| `LS_MAX_TIME_PER_OP` | 8s | 8s (TS: 5s) |

The `adaptive_config(num_orders)` function adjusts `POPULATION_SIZE`, `MUTATION_RATE`, and `LS_MAX` based on order count (linearly mapped: 20 orders → pop=40, 80+ orders → pop=10).

## Benchmark

- **64 instances** grouped by order count: 50 (1–8), 100 (9–16), 300 (17–24), 500 (25–32), 1000 (33–40), 2000 (41–48), 3000 (49–56), 4000 (57–64)
- Each instance: `order.csv` + `vehicle.csv`
- Global: `factory_info.csv` (154 factories with lat/lng/port count), `route_info.csv` (23,562 routes with distance/time)
- **Score**: $Score = \frac{\text{TotalDistance}}{NumTruck} + \frac{\text{SumOverTime} \times 10000}{3600}$

## Common Pitfalls

- **Do not modify `src/` simulator files** unless absolutely necessary — they are shared infrastructure from the competition. The algorithm-specific code lives in `algorithm/`.
- **The `data_interaction/` directory** is dynamically created/cleared each simulation round. Never hardcode paths — use `Configs.algorithm_data_interaction_folder_path`.
- **Time limit is strict** (570s / 9.5 min). The `is_timeout()` function must be checked in all loops. Exceeding it causes the simulator to fail the run.
- **`print("SUCCESS")` is critical** — the simulator waits for this exact string on stdout to detect algorithm completion. `main_algorithm.py` wraps the call and prints it.
- **The `DELAY_DISPATCH` flag** in `algorithm_config.py` changes which output files are written (with/without delay time). Toggle carefully.
- **Merge nodes before output** — `merge_node()` must be called on the solution before writing JSON, or consecutive same-factory nodes cause verification errors.
- **New orders only**: The `restore_scene_with_single_node()` preserves ongoing plans; the algorithm should only optimize placement of truly new (unlocated) orders.
