#!/usr/bin/env python3
"""Aggregate four current EvoRL repetitions with one previous 64-instance run.

Tạo bảng tổng hợp theo instance và báo cáo Markdown bằng thư viện chuẩn Python,
không phụ thuộc pandas/openpyxl để có thể tái lập trong môi trường tối giản.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


METRICS = (
    "score",
    "wall_time_seconds",
    "simulation_runtime_seconds",
    "algorithm_time_seconds",
    "algorithm_dispatch_count",
)

GROUPS = (
    (1, 8, 50),
    (9, 16, 100),
    (17, 24, 300),
    (25, 32, 500),
    (33, 40, 1000),
    (41, 48, 2000),
    (49, 56, 3000),
    (57, 64, 4000),
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--current",
        type=Path,
        default=root / "EvoRL/algorithm/data_interaction_runs/20260819_094955/results.csv",
        help="CSV containing the four current repetitions.",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=root / "EvoRL/algorithm/data_interaction_runs/EvoRL_results_64_instances.csv",
        help="CSV containing the previous one-run reference.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=root / "EvoRL/analysis/evorl_5run_instance_aggregate.csv",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=root / "EvoRL/analysis/evorl_5run_report.md",
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: Mapping[str, str], field: str) -> float:
    return float(row[field])


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.mean(values) if values else 0.0


def population_std(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def fmt_number(value: float) -> str:
    return "{:,.3f}".format(value)


def fmt_compact(value: float) -> str:
    return "{:.12g}".format(value)


def fmt_pct(value: float) -> str:
    return "{:+.3f}%".format(value)


def group_for(instance_id: int) -> Tuple[str, int]:
    for low, high, order_count in GROUPS:
        if low <= instance_id <= high:
            return "{}-{}".format(low, high), order_count
    raise ValueError("Instance {} is outside benchmark groups".format(instance_id))


def validate_inputs(
    current: Sequence[Mapping[str, str]], reference: Sequence[Mapping[str, str]]
) -> None:
    if len(current) != 256:
        raise ValueError("Expected 256 current rows, found {}".format(len(current)))
    if len(reference) != 64:
        raise ValueError("Expected 64 reference rows, found {}".format(len(reference)))

    current_keys = [(int(row["instance_id"]), int(row["repetition"])) for row in current]
    if len(set(current_keys)) != 256:
        raise ValueError("Current CSV does not contain 256 unique instance/repetition pairs")
    expected_keys = {(instance_id, repetition) for instance_id in range(1, 65) for repetition in range(1, 5)}
    if set(current_keys) != expected_keys:
        raise ValueError("Current CSV does not cover every instance 1..64 and repetition 1..4")

    reference_ids = [int(row["instance_id"]) for row in reference]
    if sorted(reference_ids) != list(range(1, 65)):
        raise ValueError("Reference CSV does not contain exactly one row for every instance 1..64")
    if any(row["status"] != "SUCCESS" for row in list(current) + list(reference)):
        raise ValueError("Only SUCCESS rows are allowed in the aggregation")
    for row in list(current) + list(reference):
        for field in METRICS:
            number(row, field)


def paired_change(current_score: float, reference_score: float) -> Tuple[float, float]:
    delta = current_score - reference_score
    pct = (delta / reference_score * 100.0) if reference_score else 0.0
    return delta, pct


def paired_counts(
    current_scores: Sequence[float], reference_scores: Sequence[float]
) -> Tuple[int, int, int]:
    wins = sum(current < reference for current, reference in zip(current_scores, reference_scores))
    ties = sum(current == reference for current, reference in zip(current_scores, reference_scores))
    losses = len(current_scores) - wins - ties
    return wins, ties, losses


def run_summary(rows: Sequence[Mapping[str, str]]) -> Dict[str, float]:
    return {
        "samples": float(len(rows)),
        "mean_score": mean(number(row, "score") for row in rows),
        "median_score": statistics.median(number(row, "score") for row in rows),
        "std_score": population_std(number(row, "score") for row in rows),
        "min_score": min(number(row, "score") for row in rows),
        "max_score": max(number(row, "score") for row in rows),
        "mean_wall": mean(number(row, "wall_time_seconds") for row in rows),
        "mean_simulation": mean(number(row, "simulation_runtime_seconds") for row in rows),
        "mean_algorithm": mean(number(row, "algorithm_time_seconds") for row in rows),
        "mean_dispatch": mean(number(row, "algorithm_dispatch_count") for row in rows),
    }


def summary_row(
    label: str,
    rows: Sequence[Mapping[str, str]],
    reference_by_instance: Mapping[int, Mapping[str, str]],
) -> Dict[str, object]:
    summary = run_summary(rows)
    current_scores = [number(row, "score") for row in rows]
    reference_scores = [number(reference_by_instance[int(row["instance_id"])] , "score") for row in rows]
    deltas = [paired_change(current, reference)[0] for current, reference in zip(current_scores, reference_scores)]
    pcts = [paired_change(current, reference)[1] for current, reference in zip(current_scores, reference_scores)]
    wins, ties, losses = paired_counts(current_scores, reference_scores)
    summary.update(
        {
            "label": label,
            "paired_pct_mean": mean(pcts),
            "paired_pct_median": statistics.median(pcts),
            "paired_delta_mean": mean(deltas),
            "wins": wins,
            "ties": ties,
            "losses": losses,
        }
    )
    return summary


def write_aggregate_csv(
    path: Path,
    current_by_instance: Mapping[int, Mapping[int, Mapping[str, str]]],
    reference_by_instance: Mapping[int, Mapping[str, str]],
) -> None:
    fields = [
        "instance_id",
        "order_count",
        "benchmark_group",
        "reference_batch_id",
        "reference_seed",
        "reference_score",
        "reference_wall_time_seconds",
        "reference_simulation_runtime_seconds",
        "reference_algorithm_time_seconds",
        "reference_algorithm_dispatch_count",
    ]
    for repetition in range(1, 5):
        fields.extend(
            [
                "repetition_{}_batch_id".format(repetition),
                "repetition_{}_seed".format(repetition),
                "repetition_{}_score".format(repetition),
                "repetition_{}_wall_time_seconds".format(repetition),
                "repetition_{}_simulation_runtime_seconds".format(repetition),
                "repetition_{}_algorithm_time_seconds".format(repetition),
                "repetition_{}_algorithm_dispatch_count".format(repetition),
            ]
        )
    fields.extend(
        [
            "current4_mean_score",
            "current4_std_score",
            "current4_min_score",
            "current4_max_score",
            "current4_mean_wall_time_seconds",
            "current4_mean_simulation_runtime_seconds",
            "current4_mean_algorithm_time_seconds",
            "current4_mean_algorithm_dispatch_count",
            "combined5_mean_score",
            "combined5_std_score",
            "combined5_min_score",
            "combined5_max_score",
            "combined5_mean_wall_time_seconds",
            "combined5_mean_simulation_runtime_seconds",
            "combined5_mean_algorithm_time_seconds",
            "combined5_mean_algorithm_dispatch_count",
            "current4_delta_vs_reference_score",
            "current4_pct_vs_reference",
            "best_current_repetition",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for instance_id in range(1, 65):
            reference = reference_by_instance[instance_id]
            repetitions = [current_by_instance[instance_id][r] for r in range(1, 5)]
            current_scores = [number(row, "score") for row in repetitions]
            combined_rows = [reference] + repetitions
            combined_scores = [number(row, "score") for row in combined_rows]
            group, order_count = group_for(instance_id)
            current4_mean = mean(current_scores)
            delta, pct = paired_change(current4_mean, number(reference, "score"))
            best_repetition = min(range(1, 5), key=lambda r: number(current_by_instance[instance_id][r], "score"))
            output: Dict[str, object] = {
                "instance_id": instance_id,
                "order_count": order_count,
                "benchmark_group": group,
                "reference_batch_id": reference["batch_id"],
                "reference_seed": reference["seed"],
                "reference_score": fmt_compact(number(reference, "score")),
                "reference_wall_time_seconds": fmt_compact(number(reference, "wall_time_seconds")),
                "reference_simulation_runtime_seconds": fmt_compact(number(reference, "simulation_runtime_seconds")),
                "reference_algorithm_time_seconds": fmt_compact(number(reference, "algorithm_time_seconds")),
                "reference_algorithm_dispatch_count": fmt_compact(number(reference, "algorithm_dispatch_count")),
                "current4_mean_score": fmt_compact(current4_mean),
                "current4_std_score": fmt_compact(population_std(current_scores)),
                "current4_min_score": fmt_compact(min(current_scores)),
                "current4_max_score": fmt_compact(max(current_scores)),
                "current4_mean_wall_time_seconds": fmt_compact(mean(number(row, "wall_time_seconds") for row in repetitions)),
                "current4_mean_simulation_runtime_seconds": fmt_compact(mean(number(row, "simulation_runtime_seconds") for row in repetitions)),
                "current4_mean_algorithm_time_seconds": fmt_compact(mean(number(row, "algorithm_time_seconds") for row in repetitions)),
                "current4_mean_algorithm_dispatch_count": fmt_compact(mean(number(row, "algorithm_dispatch_count") for row in repetitions)),
                "combined5_mean_score": fmt_compact(mean(combined_scores)),
                "combined5_std_score": fmt_compact(population_std(combined_scores)),
                "combined5_min_score": fmt_compact(min(combined_scores)),
                "combined5_max_score": fmt_compact(max(combined_scores)),
                "combined5_mean_wall_time_seconds": fmt_compact(mean(number(row, "wall_time_seconds") for row in combined_rows)),
                "combined5_mean_simulation_runtime_seconds": fmt_compact(mean(number(row, "simulation_runtime_seconds") for row in combined_rows)),
                "combined5_mean_algorithm_time_seconds": fmt_compact(mean(number(row, "algorithm_time_seconds") for row in combined_rows)),
                "combined5_mean_algorithm_dispatch_count": fmt_compact(mean(number(row, "algorithm_dispatch_count") for row in combined_rows)),
                "current4_delta_vs_reference_score": fmt_compact(delta),
                "current4_pct_vs_reference": fmt_compact(pct),
                "best_current_repetition": best_repetition,
            }
            for repetition, row in enumerate(repetitions, start=1):
                prefix = "repetition_{}".format(repetition)
                output["{}_batch_id".format(prefix)] = row["batch_id"]
                output["{}_seed".format(prefix)] = row["seed"]
                for metric in METRICS:
                    if metric == "score":
                        output["{}_score".format(prefix)] = fmt_compact(number(row, metric))
                    elif metric != "algorithm_dispatch_count" or True:
                        output["{}_{}".format(prefix, metric)] = fmt_compact(number(row, metric))
            writer.writerow(output)


def group_summary(
    current_by_instance: Mapping[int, Mapping[int, Mapping[str, str]]],
    reference_by_instance: Mapping[int, Mapping[str, str]],
) -> List[Dict[str, object]]:
    output = []
    for low, high, order_count in GROUPS:
        ids = list(range(low, high + 1))
        reference_scores = [number(reference_by_instance[i], "score") for i in ids]
        current_means = [mean(number(current_by_instance[i][r], "score") for r in range(1, 5)) for i in ids]
        combined_means = [
            mean([number(reference_by_instance[i], "score")] + [number(current_by_instance[i][r], "score") for r in range(1, 5)])
            for i in ids
        ]
        pcts = [paired_change(current, reference)[1] for current, reference in zip(current_means, reference_scores)]
        wins, ties, losses = paired_counts(current_means, reference_scores)
        output.append(
            {
                "group": "{}-{}".format(low, high),
                "order_count": order_count,
                "reference_mean": mean(reference_scores),
                "current4_mean": mean(current_means),
                "combined5_mean": mean(combined_means),
                "paired_pct_mean": mean(pcts),
                "wins": wins,
                "ties": ties,
                "losses": losses,
            }
        )
    return output


def report_text(
    current: Sequence[Mapping[str, str]],
    reference: Sequence[Mapping[str, str]],
    current_by_instance: Mapping[int, Mapping[int, Mapping[str, str]]],
    reference_by_instance: Mapping[int, Mapping[str, str]],
) -> str:
    generated = datetime.now(timezone.utc).isoformat()
    current_rows_by_rep = {
        repetition: [row for row in current if int(row["repetition"]) == repetition]
        for repetition in range(1, 5)
    }
    ref_scores = [number(reference_by_instance[i], "score") for i in range(1, 65)]
    current4_scores = [mean(number(current_by_instance[i][r], "score") for r in range(1, 5)) for i in range(1, 65)]
    combined5_scores = [
        mean([number(reference_by_instance[i], "score")] + [number(current_by_instance[i][r], "score") for r in range(1, 5)])
        for i in range(1, 65)
    ]
    current4_pcts = [paired_change(current4_scores[i], ref_scores[i])[1] for i in range(64)]
    current4_deltas = [paired_change(current4_scores[i], ref_scores[i])[0] for i in range(64)]
    current4_wins, current4_ties, current4_losses = paired_counts(current4_scores, ref_scores)
    reference_batches = sorted({row["batch_id"] for row in reference})
    same_rep1 = sum(
        number(current_by_instance[i][1], "score") == number(reference_by_instance[i], "score")
        for i in range(1, 65)
    )

    # Thống kê từng run / Per-run statistics.
    run_rows = []
    reference_summary = run_summary(reference)
    run_rows.append(("Reference trước đó", reference_summary, None))
    for repetition in range(1, 5):
        rows = current_rows_by_rep[repetition]
        summary = summary_row("Repetition hiện tại {}".format(repetition), rows, reference_by_instance)
        run_rows.append(("Repetition hiện tại {}".format(repetition), summary, summary))

    groups = group_summary(current_by_instance, reference_by_instance)
    top_improvements = sorted(range(1, 65), key=lambda i: current4_pcts[i - 1])[:5]
    top_regressions = sorted(range(1, 65), key=lambda i: current4_pcts[i - 1], reverse=True)[:5]

    lines = [
        "# Báo cáo tổng hợp 5 lần chạy EvoRL",
        "",
        "- Thời điểm tạo báo cáo (UTC): `{}`".format(generated),
        "- Phạm vi: 64 instance benchmark, gồm 4 repetition hiện tại và 1 lần reference trước đó.",
        "- Chỉ tiêu chính: `score`; **score thấp hơn là tốt hơn**.",
        "- Độ lệch chuẩn trong báo cáo là population standard deviation của các quan sát trong cùng instance/run.",
        "",
        "## 1. Kết luận chính",
        "",
        "- Dữ liệu hợp lệ: **320/320 job thành công** (256 hiện tại + 64 reference), không có dòng lỗi.",
        "- Mean score theo 64 instance: reference **{}**, mean của 4 repetition hiện tại **{}**, và mean gộp 5 lần **{}**.".format(
            fmt_number(mean(ref_scores)), fmt_number(mean(current4_scores)), fmt_number(mean(combined5_scores))
        ),
        "- So với reference, mean của 4 repetition hiện tại thay đổi **{}** theo macro-average phần trăm trên 64 instance; delta raw score trung bình là **{}**.".format(
            fmt_pct(mean(current4_pcts)), fmt_number(mean(current4_deltas))
        ),
        "- Số instance current-4 tốt hơn / bằng / xấu hơn reference: **{} / {} / {}**.".format(
            current4_wins, current4_ties, current4_losses
        ),
        "- Reference trùng score với repetition 1 hiện tại ở **{}/64 instance**. Vì vậy 5 dòng đo không nên được diễn giải là 5 mẫu hoàn toàn độc lập.".format(same_rep1),
        "",
        "Diễn giải: thay đổi tổng thể rất nhỏ; kết quả hiện tại nhìn chung tương đương reference, với lợi thế nhẹ khi tính trung bình theo instance. Các nhóm instance lớn có ảnh hưởng lớn hơn nếu tính raw score, nên cần đọc cùng bảng theo nhóm bên dưới.",
        "",
        "## 2. Thống kê theo lần chạy",
        "",
        "| Nguồn | Số mẫu | Mean score | Median | SD | Min | Max | Wall time mean (s) | Algorithm time mean (s) | So với reference |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, summary, paired in run_rows:
        comparison = "—"
        if paired is not None:
            comparison = "{}; {}/{}/{}".format(
                fmt_pct(float(paired["paired_pct_mean"])),
                int(paired["wins"]),
                int(paired["ties"]),
                int(paired["losses"]),
            )
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                label,
                int(summary["samples"]),
                fmt_number(summary["mean_score"]),
                fmt_number(summary["median_score"]),
                fmt_number(summary["std_score"]),
                fmt_number(summary["min_score"]),
                fmt_number(summary["max_score"]),
                fmt_number(summary["mean_wall"]),
                fmt_number(summary["mean_algorithm"]),
                comparison,
            )
        )
    lines.extend(
        [
            "",
            "Trong cột cuối, format là `mean % change; wins/ties/losses` theo từng instance; phần trăm âm nghĩa là score giảm, tốt hơn.",
            "",
            "## 3. Tổng hợp theo nhóm kích thước instance",
            "",
            "| Instance | Orders | Reference mean | Current-4 mean | Combined-5 mean | Current-4 vs ref | Tốt hơn / bằng / xấu hơn |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for group in groups:
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} / {} / {} |".format(
                group["group"],
                group["order_count"],
                fmt_number(group["reference_mean"]),
                fmt_number(group["current4_mean"]),
                fmt_number(group["combined5_mean"]),
                fmt_pct(group["paired_pct_mean"]),
                group["wins"],
                group["ties"],
                group["losses"],
            )
        )
    lines.extend(
        [
            "",
            "Các nhóm benchmark tương ứng: 1–8 = 50 orders, 9–16 = 100, 17–24 = 300, 25–32 = 500, 33–40 = 1000, 41–48 = 2000, 49–56 = 3000, 57–64 = 4000.",
            "",
            "## 4. Instance thay đổi nhiều nhất",
            "",
            "### Cải thiện nhiều nhất",
            "",
            "| Instance | Orders | Reference | Current-4 mean | Change |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for instance_id in top_improvements:
        group, order_count = group_for(instance_id)
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                instance_id,
                order_count,
                fmt_number(ref_scores[instance_id - 1]),
                fmt_number(current4_scores[instance_id - 1]),
                fmt_pct(current4_pcts[instance_id - 1]),
            )
        )
    lines.extend(
        [
            "",
            "### Xấu đi nhiều nhất",
            "",
            "| Instance | Orders | Reference | Current-4 mean | Change |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for instance_id in top_regressions:
        group, order_count = group_for(instance_id)
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                instance_id,
                order_count,
                fmt_number(ref_scores[instance_id - 1]),
                fmt_number(current4_scores[instance_id - 1]),
                fmt_pct(current4_pcts[instance_id - 1]),
            )
        )
    lines.extend(
        [
            "",
            "## 5. Phương pháp và nguồn",
            "",
            "- Current batch: [`20260819_094955/results.csv`](../algorithm/data_interaction_runs/20260819_094955/results.csv), 256 dòng, repetition 1–4 trên instance 1–64.",
            "- Reference: [`EvoRL_results_64_instances.csv`](../algorithm/data_interaction_runs/EvoRL_results_64_instances.csv), 64 dòng, một dòng/instance.",
            "- Reference có các batch ID: `{}`. Đây là file 64-instance đã được ghép từ các batch hoàn tất trước đó; không dùng batch `20260818_143854` vì batch này chưa hoàn tất.".format(", ".join(reference_batches)),
            "- File CSV chi tiết theo instance: [`evorl_5run_instance_aggregate.csv`](evorl_5run_instance_aggregate.csv). File này giữ score, runtime, seed, mean/std/min/max của 4 repetition và 5 lần.",
            "- So sánh current-4 với reference dùng mean của bốn score hiện tại cho từng instance; khi gộp 5 lần, reference được tính như một quan sát bổ sung.",
            "",
            "## 6. Hạn chế khi diễn giải",
            "",
            "- Reference và repetition 1 hiện tại dùng cùng công thức seed theo instance/repetition; một phần kết quả có thể lặp lại do tính tất định của pipeline.",
            "- Mean raw score bị chi phối bởi các instance lớn (3000–4000 orders). Macro-average phần trăm theo instance được dùng để tránh chỉ nhìn vào các giá trị raw lớn.",
            "- Báo cáo này tổng hợp kết quả đã chạy; chưa phải kiểm định thống kê về ý nghĩa của chênh lệch.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    current = read_csv(args.current)
    reference = read_csv(args.reference)
    validate_inputs(current, reference)
    current_by_instance: Dict[int, Dict[int, Mapping[str, str]]] = defaultdict(dict)
    for row in current:
        current_by_instance[int(row["instance_id"])][int(row["repetition"])] = row
    reference_by_instance = {int(row["instance_id"]): row for row in reference}
    write_aggregate_csv(args.output_csv, current_by_instance, reference_by_instance)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        report_text(current, reference, current_by_instance, reference_by_instance),
        encoding="utf-8",
    )
    print("Wrote {}".format(args.output_csv))
    print("Wrote {}".format(args.output_report))


if __name__ == "__main__":
    main()
