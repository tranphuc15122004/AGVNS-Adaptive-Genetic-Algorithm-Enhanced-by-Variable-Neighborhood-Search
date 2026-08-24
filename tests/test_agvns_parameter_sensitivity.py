import csv
import io
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = ROOT / "AGVNS" / "experiments" / "agvns_parameter_sensitivity"
sys.path.insert(0, str(EXPERIMENT_DIR))
sys.path.insert(0, str(ROOT / "AGVNS"))
sys.path.insert(0, str(ROOT / "AGVNS" / "algorithm"))


def test_screening_design_has_taguchi_rows_baseline_and_expected_jobs():
    from design import (
        BASELINE_CONFIGURATION_ID,
        DESIGN,
        INSTANCE_IDS,
        REPETITIONS,
        TAGUCHI_DESIGN,
        expected_job_count,
        validate_design,
    )

    validate_design()
    assert len(TAGUCHI_DESIGN) == 9
    assert len(DESIGN) == 10
    assert len({row.configuration_id for row in DESIGN}) == 10
    assert BASELINE_CONFIGURATION_ID == 10
    assert INSTANCE_IDS == (57, 58, 49, 50, 41, 42, 33, 34, 25, 26, 17, 18, 9, 10, 1, 2)
    assert REPETITIONS == 3
    assert expected_job_count() == 480


def test_experiment_overrides_parse_and_preserve_factor_values():
    import algorithm_config as config

    values = config.parse_experiment_overrides(
        {
            "AGVNS_EXPERIMENT_ID": "16",
            "AGVNS_EXPERIMENT_T": "80",
            "AGVNS_EXPERIMENT_POPULATION": "40",
            "AGVNS_EXPERIMENT_PERTURBATION": "0.50",
            "AGVNS_EXPERIMENT_MUTATION_SUBSET": "0.25",
            "AGVNS_RANDOM_SEED": "12345",
        }
    )
    assert values == {
        "configuration_id": 16,
        "threshold_orders": 80,
        "population_size": 40,
        "perturbation_rate": 0.5,
        "mutation_rate": 0.25,
        "random_seed": 12345,
    }


def test_worker_log_parser_extracts_final_metrics_and_failure_status():
    from aggregate_results import parse_worker_log_text

    message = """
    Applied AGVNS experiment config: id=16 T=80 population=40 perturbation=0.5 mutation_subset=0.25 seed=12345
    Total distance: 123.500
    Sum over time: 45.000
    Total score: 789.250
    Thoi gian thuc hien thuat toan: 12.5
    Score of instance_1: 789.25, runtime: 15.5 seconds
    SUCCESS
    """
    parsed = parse_worker_log_text(message, instance_id=1, return_code=0)
    assert parsed["status"] == "SUCCESS"
    assert parsed["score"] == 789.25
    assert parsed["total_distance"] == 123.5
    assert parsed["sum_over_time"] == 45.0
    assert parsed["algorithm_time_seconds"] == 12.5
    assert parsed["simulation_runtime_seconds"] == 15.5

    failed = parse_worker_log_text("FAIL\n", instance_id=1, return_code=1)
    assert failed["status"] == "FAILED"
    assert "missing final score" in failed["error"]


def test_job_seed_is_stable_and_configuration_is_joined():
    from design import job_seed, iter_jobs

    first = list(iter_jobs(base_seed=7000))
    second = list(iter_jobs(base_seed=7000))
    assert first == second
    assert first[0]["seed"] == 7000 + first[0]["instance_id"] * 1000 + first[0]["repetition"]
    assert first[0]["configuration_id"] == 1
    assert first[0]["instance_id"] == 57
    assert first[-1]["configuration_id"] == 10
    assert first[-1]["instance_id"] == 2
