"""Aggregate the four most recent TS batches (instances 1-64) into one Excel sheet.

Batches covered (5 repetitions per instance):
  20260727_110733  -> instances 1-20
  20260730_035109  -> instances 21-40
  20260730_130436  -> instances 41-60
  20260730_205247  -> instances 61-64

Outputs: TS/algorithm/data_interaction_runs/TS_results_64_instances.xlsx
  - "Tong hop"   : one row per instance (64 rows) with score stats over reps
  - "Chi tiet"   : every individual run (320 rows)
  - "Theo nhom don hang" : per order-count group stats
and TS_results_64_instances.csv with the aggregated "Tong hop" data.
"""

import os

import pandas as pd

RUNS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "algorithm",
    "data_interaction_runs",
)

BATCHES = [
    ("20260727_110733", range(1, 21)),
    ("20260730_035109", range(21, 41)),
    ("20260730_130436", range(41, 61)),
    ("20260730_205247", range(61, 65)),
]

# Order-count groups per AGENTS.md benchmark description.
ORDER_GROUPS = [
    (1, 8, 50),
    (9, 16, 100),
    (17, 24, 300),
    (25, 32, 500),
    (33, 40, 1000),
    (41, 48, 2000),
    (49, 56, 3000),
    (57, 64, 4000),
]


def order_group(instance_id: int) -> int:
    for start, end, count in ORDER_GROUPS:
        if start <= instance_id <= end:
            return count
    return 0


def main() -> None:
    frames = []
    for batch_id, _instances in BATCHES:
        path = os.path.join(RUNS_DIR, batch_id, "results.csv")
        frame = pd.read_csv(path, dtype={"instance_id": int})
        frames.append(frame)

    detail = pd.concat(frames, ignore_index=True)
    detail["num_orders"] = detail["instance_id"].map(order_group)

    # ---- Per-instance summary ------------------------------------------------
    rows = []
    for instance in range(1, 65):
        runs = detail[detail["instance_id"] == instance]
        successful = runs[runs["status"] == "SUCCESS"]
        scores = pd.to_numeric(successful["score"], errors="coerce").dropna()
        simulation_runtime = pd.to_numeric(
            successful["simulation_runtime_seconds"], errors="coerce"
        ).dropna()
        wall_time = pd.to_numeric(
            successful["wall_time_seconds"], errors="coerce"
        ).dropna()
        rows.append(
            {
                "instance_id": instance,
                "num_orders": order_group(instance),
                "batch_id": successful["batch_id"].iloc[0]
                if len(successful)
                else runs["batch_id"].iloc[0],
                "successful_reps": len(successful),
                "total_reps": len(runs),
                "score_min": scores.min() if len(scores) else None,
                "score_mean": scores.mean() if len(scores) else None,
                "score_median": scores.median() if len(scores) else None,
                "score_max": scores.max() if len(scores) else None,
                "score_std": scores.std(ddof=0) if len(scores) else None,
                "simulation_runtime_mean_s": (
                    simulation_runtime.mean() if len(simulation_runtime) else None
                ),
                "wall_time_mean_s": wall_time.mean() if len(wall_time) else None,
            }
        )
    summary = pd.DataFrame(rows)

    # ---- Overall stats -------------------------------------------------------
    all_scores = pd.to_numeric(detail["score"], errors="coerce").dropna()
    overall = pd.DataFrame(
        [
            {
                "instance_id": "TONG",
                "num_orders": "",
                "batch_id": "4 batches",
                "successful_reps": int((detail["status"] == "SUCCESS").sum()),
                "total_reps": len(detail),
                "score_min": all_scores.min(),
                "score_mean": all_scores.mean(),
                "score_median": all_scores.median(),
                "score_max": all_scores.max(),
                "score_std": all_scores.std(ddof=0),
                "simulation_runtime_mean_s": pd.to_numeric(
                    detail["simulation_runtime_seconds"], errors="coerce"
                ).mean(),
                "wall_time_mean_s": pd.to_numeric(
                    detail["wall_time_seconds"], errors="coerce"
                ).mean(),
            }
        ]
    )
    summary = pd.concat([summary, overall], ignore_index=True)

    # ---- Per-order-group summary --------------------------------------------
    group_rows = []
    for start, end, count in ORDER_GROUPS:
        mask = detail["instance_id"].between(start, end)
        group_scores = pd.to_numeric(
            detail.loc[mask, "score"], errors="coerce"
        ).dropna()
        group_rows.append(
            {
                "order_group": count,
                "instances": f"{start}-{end}",
                "successful_reps": int((detail.loc[mask, "status"] == "SUCCESS").sum()),
                "total_reps": int(mask.sum()),
                "score_mean": group_scores.mean() if len(group_scores) else None,
                "score_std": (
                    group_scores.std(ddof=0) if len(group_scores) > 1 else None
                ),
            }
        )
    group_summary = pd.DataFrame(group_rows)

    output_path = os.path.join(RUNS_DIR, "TS_results_64_instances.xlsx")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Tong hop", index=False)
        detail.to_excel(writer, sheet_name="Chi tiet", index=False)
        group_summary.to_excel(writer, sheet_name="Theo nhom don hang", index=False)

    # CSV chi chua du lieu tong hop (bảng "Tong hop").
    csv_path = os.path.join(RUNS_DIR, "TS_results_64_instances.csv")
    summary.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print("Wrote:", output_path)
    print("Wrote:", csv_path)
    print("\nSummary preview:")
    print(summary.to_string(index=False))
    print("\nPer order-group:")
    print(group_summary.to_string(index=False))


if __name__ == "__main__":
    main()
