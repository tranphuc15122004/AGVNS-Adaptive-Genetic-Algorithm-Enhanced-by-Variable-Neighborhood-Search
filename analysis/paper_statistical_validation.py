"""Statistical tests used to update the paper's validation section."""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class FriedmanSummary:
    statistic: float
    p_value: float
    mean_ranks: np.ndarray


@dataclass(frozen=True)
class WilcoxonSummary:
    wins: int
    ties: int
    losses: int
    statistic: float
    p_value: float


SOURCE_ALGORITHMS = ["Gold", "Silver", "Bronze", "MA", "GA", "Evo-RL", "AGVNS"]
ALGORITHM_ORDER = ["AGVNS", "Gold", "Silver", "Bronze", "MA", "GA", "Evo-RL"]
_ROW_PATTERN = re.compile(
    r"^[ \t]*&[ \t]*HW(?P<instance>\d+)[ \t]*&(?P<cells>.*?)[ \t]*\\\\[ \t]*$",
    re.MULTILINE,
)


def _strip_latex_markup(cell: str) -> str:
    value = re.sub(r"\\(?:textbf|textit|mathbf)\s*\{([^{}]*)\}", r"\1", cell)
    return value.replace(",", "").strip()


def parse_result_table(latex: str) -> Tuple[List[int], np.ndarray]:
    """Parse active HW rows from the two main result tables in the paper."""
    rows: Dict[int, List[float]] = {}
    for match in _ROW_PATTERN.finditer(latex):
        instance = int(match.group("instance"))
        cells = [_strip_latex_markup(cell) for cell in match.group("cells").split("&")]
        if len(cells) != len(SOURCE_ALGORITHMS):
            raise ValueError(
                f"HW{instance} has {len(cells)} result columns; "
                f"expected {len(SOURCE_ALGORITHMS)}"
            )
        try:
            rows[instance] = [float(cell) for cell in cells]
        except ValueError as exc:
            raise ValueError(f"Could not parse objective values for HW{instance}") from exc

    if not rows:
        raise ValueError("No active HW result rows were found")
    if len(rows) != len(_ROW_PATTERN.findall(latex)):
        raise ValueError("Duplicate HW instance rows were found")

    instances = sorted(rows)
    values = np.asarray([rows[instance] for instance in instances], dtype=float)
    return instances, values


def load_paper_results(path: Path) -> Tuple[List[int], List[str], np.ndarray]:
    """Load and reorder the 64-instance result tables into paper order."""
    instances, source_values = parse_result_table(path.read_text(encoding="utf-8"))
    expected_instances = list(range(1, 65))
    if instances != expected_instances:
        raise ValueError(f"Expected HW1--HW64, found {instances[0]}--{instances[-1]}")

    reorder = [SOURCE_ALGORITHMS.index(name) for name in ALGORITHM_ORDER]
    return instances, ALGORITHM_ORDER, source_values[:, reorder]


def friedman_summary(values: np.ndarray) -> FriedmanSummary:
    """Return Friedman statistic, p-value, and per-algorithm mean ranks.

    ``values`` has one row per instance and one column per algorithm. Lower
    objective values are ranked first, which matches the paper's objective.
    """
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 3:
        raise ValueError("values must be a 2-D matrix with at least 2 rows and 3 columns")

    ranks = stats.rankdata(matrix, axis=1, method="average")
    statistic, p_value = stats.friedmanchisquare(*matrix.T)
    return FriedmanSummary(
        statistic=float(statistic),
        p_value=float(p_value),
        mean_ranks=np.mean(ranks, axis=0),
    )


def holm_adjust(p_values: Sequence[float]) -> List[float]:
    """Apply the Holm step-down correction while preserving input order."""
    p_values_array = np.asarray(list(p_values), dtype=float)
    if p_values_array.ndim != 1 or p_values_array.size == 0:
        raise ValueError("p_values must be a non-empty one-dimensional sequence")
    if np.any((p_values_array < 0) | (p_values_array > 1)):
        raise ValueError("p-values must be between 0 and 1")

    order = np.argsort(p_values_array, kind="stable")
    sorted_values = p_values_array[order]
    adjusted_sorted = np.maximum.accumulate(
        (sorted_values * (len(sorted_values) - np.arange(len(sorted_values))))
    )
    adjusted_sorted = np.minimum(adjusted_sorted, 1.0)

    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted.tolist()


def wilcoxon_summary(control: np.ndarray, competitor: np.ndarray) -> WilcoxonSummary:
    """Run a one-sided Wilcoxon test for lower control objectives."""
    control_values = np.asarray(control, dtype=float)
    competitor_values = np.asarray(competitor, dtype=float)
    if control_values.shape != competitor_values.shape or control_values.ndim != 1:
        raise ValueError("control and competitor must be one-dimensional arrays of equal length")

    result = stats.wilcoxon(
        control_values,
        competitor_values,
        zero_method="wilcox",
        alternative="less",
        method="approx",
    )
    differences = control_values - competitor_values
    return WilcoxonSummary(
        wins=int(np.sum(differences < 0)),
        ties=int(np.sum(differences == 0)),
        losses=int(np.sum(differences > 0)),
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
    )


def build_report(instances: Sequence[int], names: Sequence[str], values: np.ndarray) -> dict:
    """Build JSON-serialisable Friedman and AGVNS-vs-baseline results."""
    if list(names) != ALGORITHM_ORDER:
        raise ValueError(f"Expected algorithm order {ALGORITHM_ORDER}")
    summary = friedman_summary(values)
    pairwise = []
    raw_p_values = []
    for column, name in enumerate(names[1:], start=1):
        result = wilcoxon_summary(values[:, 0], values[:, column])
        pairwise.append({"competitor": name, **result.__dict__})
        raw_p_values.append(result.p_value)

    adjusted = holm_adjust(raw_p_values)
    for item, adjusted_p in zip(pairwise, adjusted):
        item["holm_adjusted_p_value"] = adjusted_p
        item["reject_at_0_05"] = adjusted_p <= 0.05

    return {
        "instances": len(instances),
        "algorithms": list(names),
        "friedman": {
            "statistic": summary.statistic,
            "p_value": summary.p_value,
            "mean_ranks": dict(zip(names, summary.mean_ranks.tolist())),
        },
        "pairwise_wilcoxon": pairwise,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex_path", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    instances, names, values = load_paper_results(args.tex_path)
    report = build_report(instances, names, values)
    print(json.dumps(report, indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
