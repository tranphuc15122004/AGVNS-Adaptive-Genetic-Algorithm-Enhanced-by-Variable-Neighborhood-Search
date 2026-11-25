#!/usr/bin/env python3
"""
Build the Master Runtime Comparison Table across all 64 benchmark instances (HW1-HW64)
with BOTH mean and std for all algorithms, and export CSV, XLSX, and Markdown reports.
"""

import json
import os
import pandas as pd
import numpy as np

ROOT = "/home/tuantb/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search"
REPORTS_DIR = os.path.join(ROOT, "reports")

OUT_CSV = os.path.join(REPORTS_DIR, "master_runtime_comparison_64_instances.csv")
OUT_MA_CSV = os.path.join(REPORTS_DIR, "ma_runtime_64_instances_estimated.csv")
OUT_XLSX = os.path.join(REPORTS_DIR, "master_runtime_comparison_64_instances.xlsx")


def get_set_info(inst_id: int):
    order_map = {1: 50, 2: 100, 3: 300, 4: 500, 5: 1000, 6: 2000, 7: 3000, 8: 4000}
    set_num = (inst_id - 1) // 8 + 1
    return f"Set {set_num}", set_num, order_map[set_num]


def load_agvns(inv: pd.DataFrame) -> pd.DataFrame:
    # Post-repair consistent October 2026 batches only:
    # - 20261019_042917: Sets 1-5 (40/40 instances, n=10)
    # - 20261014_082749: Set 6 anchors HW41-42 (n=10)
    # - 20261009_015120: Set 8 anchors HW57-58 (n=3)
    # Plus HW50 rep 3 from 20261002_191917 in sensitivity_results_master.csv (n=1, post-repair)
    post_repair_batches = {"20261019_042917", "20261014_082749", "20261009_015120"}
    sub = inv[
        (inv["algorithm"] == "AGVNS")
        & (inv["configuration_id"] == 3.0)
        & (inv["status"] == "SUCCESS")
        & (inv["wall_time_seconds"].notna())
    ].copy()
    sub["batch_id"] = sub["source_file"].apply(
        lambda s: s.split("/")[-2] if isinstance(s, str) else ""
    )
    sub = sub[sub["batch_id"].isin(post_repair_batches)].copy()

    agg = sub.groupby("instance_id").agg(
        AGVNS_sec=("wall_time_seconds", "mean"),
        AGVNS_std_sec=("wall_time_seconds", "std"),
        AGVNS_n=("wall_time_seconds", "count"),
        AGVNS_batch=("batch_id", "first"),
    ).reset_index()
    agg["AGVNS_source"] = agg.apply(
        lambda r: f"empirical_local (Config 3, batch {r['AGVNS_batch']}, n={int(r['AGVNS_n'])})",
        axis=1,
    )
    agg = agg.drop(columns=["AGVNS_batch"])

    # Add HW50 post-repair run from 20261002_191917 in sensitivity_results_master.csv
    sens_path = os.path.join(
        ROOT, "AGVNS/experiments/agvns_parameter_sensitivity/reports/sensitivity_results_master.csv"
    )
    if os.path.exists(sens_path):
        sens = pd.read_csv(sens_path)
        hw50 = sens[
            (sens["configuration_id"] == 3)
            & (sens["instance_id"] == 50)
            & (sens["source_run_id"] == "20261002_191917")
            & (sens["result_state"] == "VALID")
        ]
        if not hw50.empty and 50 not in set(agg["instance_id"]):
            hw50_wall = float(hw50["wall_time_seconds"].mean())
            hw50_row = pd.DataFrame([{
                "instance_id": 50,
                "AGVNS_sec": hw50_wall,
                "AGVNS_std_sec": np.nan,
                "AGVNS_n": int(len(hw50)),
                "AGVNS_source": "empirical_local (Config 3, batch 20261002_191917, n=1)",
            }])
            agg = pd.concat([agg, hw50_row], ignore_index=True)

    return agg


def load_ma() -> tuple[pd.DataFrame, dict]:
    files = [
        (os.path.join(ROOT, "MA/algorithm/data_interaction_runs/20261114_192618/results.csv"), "empirical_local (batch 20261114_192618, n=4)"),
        (os.path.join(ROOT, "MA/algorithm/data_interaction_runs/20261114_195217/results.csv"), "empirical_local (batch 20261114_195217, n=4)"),
        (os.path.join(ROOT, "MA/algorithm/data_interaction_runs/20261117_050324/results.csv"), "empirical_local (batch 20261117_050324, n=1)"),
    ]
    dfs = []
    for path, src in files:
        df = pd.read_csv(path)
        df = df[(df["status"] == "SUCCESS") & (df["wall_time_seconds"].notna())].copy()
        df["source_label"] = src
        dfs.append(df)
    all_ma = pd.concat(dfs, ignore_index=True)

    agg = all_ma.groupby("instance_id").agg(
        MA_raw_sec=("wall_time_seconds", "mean"),
        MA_std_raw_sec=("wall_time_seconds", "std"),
        MA_n=("wall_time_seconds", "count"),
        MA_source=("source_label", "first"),
    ).reset_index()

    agg["set_num"] = (agg["instance_id"] - 1) // 8 + 1

    set5 = agg[agg["set_num"] == 5].copy()
    set5_cv = set5["MA_std_raw_sec"] / set5["MA_raw_sec"]
    cv_median_set5 = float(set5_cv.median())

    # Load historical MA mean & std from Kết quả DPDP.xlsx for instance-specific CV modulation
    dp_m = pd.read_excel(os.path.join(ROOT, "Kết quả DPDP.xlsx"), sheet_name="main").iloc[:64][["HW", "MA"]].rename(columns={"MA": "dp_mean"})
    dp_s = pd.read_excel(os.path.join(ROOT, "Kết quả DPDP.xlsx"), sheet_name="STD").iloc[:64][["HW", "MA"]].rename(columns={"MA": "dp_std"})
    dp = dp_m.merge(dp_s, on="HW")
    dp["instance_id"] = dp["HW"].str.replace("HW", "").astype(int)
    dp["dp_cv"] = pd.to_numeric(dp["dp_std"], errors="coerce") / pd.to_numeric(dp["dp_mean"], errors="coerce")
    dp["set_num"] = (dp["instance_id"] - 1) // 8 + 1
    dp_cv_map = dp.set_index("instance_id")["dp_cv"].to_dict()
    dp_set_cv_map = dp.groupby("set_num")["dp_cv"].mean().to_dict()

    # Compute Empirical Bayes shrinkage set means for Sets 6, 7, 8 (excluding HW47 early infeasible stop)
    set_means = {}
    for s_num in [6, 7, 8]:
        valid = agg[(agg["set_num"] == s_num) & (agg["instance_id"] != 47)]
        set_means[s_num] = float(valid["MA_raw_sec"].mean())

    ma_secs, ma_stds, ma_sources = [], [], []
    for _, row in agg.iterrows():
        inst = int(row["instance_id"])
        s_num = int(row["set_num"])
        if inst <= 40:
            val = float(row["MA_raw_sec"])
            std = float(row["MA_std_raw_sec"])
            src = str(row["MA_source"])
        else:
            set_mean = set_means[s_num]
            val = set_mean if inst == 47 else (0.75 * float(row["MA_raw_sec"]) + 0.25 * set_mean)
            dp_cv_i = dp_cv_map.get(inst, dp_set_cv_map[s_num])
            dp_cv_s = dp_set_cv_map[s_num]
            est_cv = cv_median_set5 * float(np.sqrt(dp_cv_i / dp_cv_s))
            std = val * est_cv
            if inst == 47:
                src = f"imputed (Set 6 valid mean); std (Set5 CV * DPDP_CV ratio={est_cv:.4f})"
            else:
                src = f"EB_shrinkage (0.75*obs+0.25*Set{s_num}); std (DPDP_CV_mod={est_cv:.4f})"
        ma_secs.append(val)
        ma_stds.append(std)
        ma_sources.append(src)

    agg["MA_sec"] = ma_secs
    agg["MA_std_sec"] = ma_stds
    agg["MA_source"] = ma_sources
    agg = agg.drop(columns=["set_num"])

    stats_meta = {
        "cv_median_set5": cv_median_set5,
        "set6_valid_mean": set_means[6],
        "hw47_raw": float(agg.loc[agg["instance_id"] == 47, "MA_raw_sec"].iloc[0]),
    }
    return agg, stats_meta


def load_ga() -> pd.DataFrame:
    """Load completed GA runs from the current systematic batches."""
    files = [
        (
            os.path.join(ROOT, "GA/algorithm/data_interaction_runs/20261119_115717/results.csv"),
            "20261119_115717",
        ),
        (
            os.path.join(ROOT, "GA/algorithm/data_interaction_runs/20261121_050952/results.csv"),
            "20261121_050952",
        ),
    ]
    dfs = []
    planned_instances: dict[int, str] = {}
    for path, batch_id in files:
        manifest_path = os.path.join(os.path.dirname(path), "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)
            for instance_id in manifest.get("instances", []):
                planned_instances[int(instance_id)] = batch_id
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df = df[(df["status"] == "SUCCESS") & (df["wall_time_seconds"].notna())].copy()
        if df.empty:
            continue
        df["GA_batch"] = batch_id
        dfs.append(df)

    if dfs:
        all_ga = pd.concat(dfs, ignore_index=True)
        agg = all_ga.groupby("instance_id").agg(
            GA_sec=("wall_time_seconds", "mean"),
            GA_std_sec=("wall_time_seconds", "std"),
            GA_n=("wall_time_seconds", "count"),
            GA_batch=("GA_batch", "first"),
        ).reset_index()
        agg["GA_source"] = agg.apply(
            lambda r: f"empirical_local (batch {r['GA_batch']}, n={int(r['GA_n'])})",
            axis=1,
        )
        agg = agg.drop(columns=["GA_batch"])
    else:
        agg = pd.DataFrame(columns=["instance_id", "GA_sec", "GA_std_sec", "GA_n", "GA_source"])

    completed_instances = set(agg["instance_id"].astype(int))
    pending_rows = [
        {
            "instance_id": instance_id,
            "GA_sec": np.nan,
            "GA_std_sec": np.nan,
            "GA_n": 0,
            "GA_source": f"pending (batch {batch_id}; no completed result)",
        }
        for instance_id, batch_id in planned_instances.items()
        if instance_id not in completed_instances
    ]
    if pending_rows:
        agg = pd.concat([agg, pd.DataFrame(pending_rows)], ignore_index=True)
    return agg


def load_inventory_alg(inv: pd.DataFrame, alg_name: str, col_prefix: str) -> pd.DataFrame:
    sub = inv[
        (inv["algorithm"] == alg_name)
        & (inv["status"] == "SUCCESS")
        & (inv["wall_time_seconds"].notna())
    ]
    agg = sub.groupby("instance_id").agg(**{
        f"{col_prefix}_sec": ("wall_time_seconds", "mean"),
        f"{col_prefix}_std_sec": ("wall_time_seconds", "std"),
        f"{col_prefix}_n": ("wall_time_seconds", "count"),
    }).reset_index()
    agg[f"{col_prefix}_source"] = f"empirical_local ({alg_name})"
    return agg


def load_gold(cov: pd.DataFrame) -> pd.DataFrame:
    g1 = cov[cov["algorithm"] == "VNSME_Gold"].set_index("instance_id")
    g2 = cov[cov["algorithm"] == "VNSME_Gold_trp1512"].set_index("instance_id")
    g3 = cov[cov["algorithm"] == "VNSME_Gold_local"].set_index("instance_id")

    rows = []
    for inst in range(1, 65):
        val, std_val, n_obs, src = np.nan, np.nan, 0, "missing"
        if inst in g1.index and pd.notna(g1.loc[inst, "wall_mean_seconds"]):
            val = float(g1.loc[inst, "wall_mean_seconds"])
            std_val = float(g1.loc[inst, "wall_std_seconds"]) if pd.notna(g1.loc[inst, "wall_std_seconds"]) else np.nan
            n_obs = int(g1.loc[inst, "wall_observations"])
            src = "empirical_kaggle (VNSME_Gold v1-v30)"
        elif inst in g2.index and pd.notna(g2.loc[inst, "wall_mean_seconds"]):
            val = float(g2.loc[inst, "wall_mean_seconds"])
            std_val = float(g2.loc[inst, "wall_std_seconds"]) if pd.notna(g2.loc[inst, "wall_std_seconds"]) else np.nan
            n_obs = int(g2.loc[inst, "wall_observations"])
            src = "empirical_kaggle (VNSME_Gold trp1512)"
        elif inst in g3.index and pd.notna(g3.loc[inst, "wall_mean_seconds"]):
            val = float(g3.loc[inst, "wall_mean_seconds"])
            std_val = float(g3.loc[inst, "wall_std_seconds"]) if pd.notna(g3.loc[inst, "wall_std_seconds"]) else np.nan
            n_obs = int(g3.loc[inst, "wall_observations"])
            src = "empirical_local (VNSME_Gold Java)"
        rows.append({
            "instance_id": inst,
            "Gold_sec": val,
            "Gold_std_sec": std_val,
            "Gold_n": n_obs,
            "Gold_source": src,
        })
    return pd.DataFrame(rows)


def load_silver_and_bronze() -> tuple[pd.DataFrame, pd.DataFrame]:
    sbl = pd.read_csv(os.path.join(REPORTS_DIR, "silver_bronze_literature/results_64_instances.csv"))
    s1_8 = pd.read_csv(os.path.join(REPORTS_DIR, "kaggle_silver_audit/results_instances_1_8_all_versions.csv"))
    sv1 = pd.read_csv(os.path.join(REPORTS_DIR, "kaggle_silver_v05_v10/summary_by_instance_17_40.csv")).set_index("instance")
    sv2 = pd.read_csv(os.path.join(REPORTS_DIR, "kaggle_silver_v11_v15/summary_by_instance_41_64.csv")).set_index("instance")
    bronze_kg = pd.read_csv(os.path.join(REPORTS_DIR, "kaggle_bronze_v22_v26/summary_by_instance_1_64.csv")).set_index("inst_num")

    s1_8_agg = s1_8.groupby("instance")["runtime_seconds"].agg(["count", "mean", "std"])
    sbl_silver = sbl[sbl["algorithm"] == "Silver"].set_index("instance")

    # Compute empirical median CV of Silver from Set 1 (1-8) and Set 3 (17-24) for Set 2 std estimation
    silver_cvs = list(s1_8_agg["std"] / s1_8_agg["mean"])
    for inst in range(17, 25):
        if inst in sv1.index:
            m = float(sv1.loc[inst, "runtime_mean_seconds"])
            # summary_by_instance uses population std -> convert to sample std (ddof=1)
            n = int(sv1.loc[inst, "runs"])
            s_pop = float(sv1.loc[inst, "runtime_std_population_seconds"])
            s_samp = s_pop * np.sqrt(n / (n - 1)) if n > 1 else np.nan
            silver_cvs.append(s_samp / m)
    silver_cv_med = float(np.median(silver_cvs))

    silver_rows, bronze_rows = [], []
    for inst in range(1, 65):
        if inst in s1_8_agg.index:
            s_val = float(s1_8_agg.loc[inst, "mean"])
            s_std = float(s1_8_agg.loc[inst, "std"])
            s_n = int(s1_8_agg.loc[inst, "count"])
            s_src = "empirical_kaggle (Silver v1-v5)"
        elif inst in sv1.index and pd.notna(sv1.loc[inst, "runtime_mean_seconds"]):
            s_val = float(sv1.loc[inst, "runtime_mean_seconds"])
            s_n = int(sv1.loc[inst, "runs"])
            s_pop = float(sv1.loc[inst, "runtime_std_population_seconds"])
            s_std = s_pop * np.sqrt(s_n / (s_n - 1)) if s_n > 1 else np.nan
            s_src = "empirical_kaggle (Silver v05-v10)"
        elif inst in sv2.index and pd.notna(sv2.loc[inst, "runtime_mean_seconds"]):
            s_val = float(sv2.loc[inst, "runtime_mean_seconds"])
            s_n = int(sv2.loc[inst, "runs"])
            s_pop = float(sv2.loc[inst, "runtime_std_population_seconds"])
            s_std = s_pop * np.sqrt(s_n / (s_n - 1)) if s_n > 1 else np.nan
            s_src = "empirical_kaggle (Silver v11-v15)"
        elif inst in sbl_silver.index and pd.notna(sbl_silver.loc[inst, "zhou_silver_assumed_raw_seconds"]):
            s_val = float(sbl_silver.loc[inst, "zhou_silver_assumed_raw_seconds"])
            s_std = s_val * silver_cv_med
            s_n = 1
            s_src = f"literature_digitized (Zhou 2024 Fig. 5); std_est (Set1&3 CV={silver_cv_med:.4f})"
        else:
            s_val, s_std, s_n, s_src = np.nan, np.nan, 0, "missing"

        silver_rows.append({
            "instance_id": inst,
            "Silver_sec": s_val,
            "Silver_std_sec": s_std,
            "Silver_n": s_n,
            "Silver_source": s_src,
        })

        if inst in bronze_kg.index and pd.notna(bronze_kg.loc[inst, "runtime_mean_seconds"]):
            b_val = float(bronze_kg.loc[inst, "runtime_mean_seconds"])
            b_std = float(bronze_kg.loc[inst, "runtime_std_seconds"])
            b_n = int(bronze_kg.loc[inst, "runs"])
            b_src = "empirical_kaggle (Bronze Top-3 v22-v26, n=5)"
        else:
            b_val, b_std, b_n, b_src = np.nan, np.nan, 0, "missing"

        bronze_rows.append({
            "instance_id": inst,
            "Bronze_sec": b_val,
            "Bronze_std_sec": b_std,
            "Bronze_n": b_n,
            "Bronze_source": b_src,
        })

    return pd.DataFrame(silver_rows), pd.DataFrame(bronze_rows)


def fmt_mean_std(mean_val, std_val):
    if pd.isna(mean_val):
        return "—"
    if pd.isna(std_val):
        return f"{mean_val:.2f}"
    return f"{mean_val:.2f} ± {std_val:.2f}"


def fmt_ga_mean_std(mean_val, std_val):
    """Keep GA's mean ± std presentation explicit when only one run exists."""
    if pd.isna(mean_val):
        return "—"
    if pd.isna(std_val):
        return f"{mean_val:.2f} ± —"
    return f"{mean_val:.2f} ± {std_val:.2f}"


def main():
    inv = pd.read_csv(os.path.join(REPORTS_DIR, "runtime_inventory.csv"))
    cov = pd.read_csv(os.path.join(REPORTS_DIR, "runtime_coverage_by_instance.csv"))

    base = pd.DataFrame({"instance_id": range(1, 65)})
    base["instance_label"] = base["instance_id"].apply(lambda x: f"HW{x}")
    set_info = base["instance_id"].apply(get_set_info)
    base["set_name"] = [s[0] for s in set_info]
    base["set_num"] = [s[1] for s in set_info]
    base["order_count"] = [s[2] for s in set_info]

    agvns = load_agvns(inv)
    ma, _ = load_ma()
    ga = load_ga()
    gold = load_gold(cov)
    silver, bronze = load_silver_and_bronze()
    evorl = load_inventory_alg(inv, "EvoRL", "EvoRL")
    ts = load_inventory_alg(inv, "TS", "TS")

    master = (
        base.merge(agvns, on="instance_id", how="left")
        .merge(ma, on="instance_id", how="left")
        .merge(gold, on="instance_id", how="left")
        .merge(silver, on="instance_id", how="left")
        .merge(bronze, on="instance_id", how="left")
        .merge(evorl, on="instance_id", how="left")
        .merge(ts, on="instance_id", how="left")
        .merge(ga, on="instance_id", how="left")
    )

    master["AGVNS_n"] = master["AGVNS_n"].fillna(0).astype(int)
    master["GA_n"] = master["GA_n"].fillna(0).astype(int)
    master["GA_source"] = master["GA_source"].fillna("no completed result in selected GA batches")

    # Load historical OUR (AGVNS) mean & std from Kết quả DPDP.xlsx for instance-specific CV modulation
    dp_our_m = pd.read_excel(os.path.join(ROOT, "Kết quả DPDP.xlsx"), sheet_name="main").iloc[:64][["HW", "OUR"]].rename(columns={"OUR": "dp_mean"})
    dp_our_s = pd.read_excel(os.path.join(ROOT, "Kết quả DPDP.xlsx"), sheet_name="STD").iloc[:64][["HW", "OUR"]].rename(columns={"OUR": "dp_std"})
    dp_our = dp_our_m.merge(dp_our_s, on="HW")
    dp_our["instance_id"] = dp_our["HW"].str.replace("HW", "").astype(int)
    dp_our["dp_cv"] = pd.to_numeric(dp_our["dp_std"], errors="coerce") / pd.to_numeric(dp_our["dp_mean"], errors="coerce")
    dp_our["set_num"] = (dp_our["instance_id"] - 1) // 8 + 1
    dp_our_cv_map = dp_our.set_index("instance_id")["dp_cv"].to_dict()
    dp_our_set_cv_map = dp_our.groupby("set_num")["dp_cv"].mean().to_dict()

    # Anchor-calibrated interpolation for missing AGVNS instances in Sets 6, 7, 8
    # using post-repair anchors: Set 6 [41, 42], Set 7 [50], Set 8 [57, 58]
    a6 = master[master["instance_id"].isin([41, 42])]
    a8 = master[master["instance_id"].isin([57, 58])]
    cv6_base = float((a6["AGVNS_std_sec"] / a6["AGVNS_sec"]).mean())
    cv8_base = float((a8["AGVNS_std_sec"] / a8["AGVNS_sec"]).mean())
    cv7_base = 0.5 * (cv6_base + cv8_base)

    anchor_configs = [
        (6, [41, 42], cv6_base),
        (7, [50], cv7_base),
        (8, [57, 58], cv8_base),
    ]
    for s_num, anchors, cv_base in anchor_configs:
        sub_a = master[master["instance_id"].isin(anchors)]
        k_s = float(sub_a["AGVNS_sec"].sum() / sub_a["MA_sec"].sum())
        dp_cv_s = dp_our_set_cv_map[s_num]

        set_mask = master["set_num"] == s_num
        for idx in master[set_mask].index:
            inst = int(master.loc[idx, "instance_id"])
            dp_cv_i = dp_our_cv_map.get(inst, dp_cv_s)
            ratio = float(np.clip(dp_cv_i / dp_cv_s, 0.3, 2.5))
            est_cv = cv_base * float(np.sqrt(ratio))

            if pd.isna(master.loc[idx, "AGVNS_sec"]):
                est_mean = k_s * float(master.loc[idx, "MA_sec"])
                master.loc[idx, "AGVNS_sec"] = est_mean
                master.loc[idx, "AGVNS_std_sec"] = est_mean * est_cv
                master.loc[idx, "AGVNS_source"] = (
                    f"interpolated (Set {s_num} anchors {anchors}: k={k_s:.4f}*MA, DPDP_OUR_CV={est_cv:.4f})"
                )
            elif pd.isna(master.loc[idx, "AGVNS_std_sec"]):
                # HW50 has empirical n=1 mean; estimate its std using CV7 modulated by DPDP_OUR
                val = float(master.loc[idx, "AGVNS_sec"])
                master.loc[idx, "AGVNS_std_sec"] = val * est_cv
                master.loc[idx, "AGVNS_source"] = (
                    f"{master.loc[idx, 'AGVNS_source']}; std_est (CV7*DPDP_OUR={est_cv:.4f})"
                )

    sec_cols = [c for c in master.columns if c.endswith("_sec")]
    for c in sec_cols:
        master[c] = master[c].round(2)

    master.to_csv(OUT_CSV, index=False, encoding="utf-8")

    # Keep dedicated MA CSV in sync
    ma_out = master[[
        "instance_id", "instance_label", "set_name", "order_count",
        "MA_n", "MA_sec", "MA_std_sec", "MA_raw_sec", "MA_source"
    ]].copy()
    ma_out["MA_mean_pm_std"] = ma_out.apply(
        lambda r: f"{r['MA_sec']:.2f} ± {r['MA_std_sec']:.2f}", axis=1
    )
    ma_out.to_csv(OUT_MA_CSV, index=False, encoding="utf-8")

    # Formatted mean ± std table for Excel Sheet 1
    formatted_df = pd.DataFrame({
        "ID": master["instance_id"],
        "Instance": master["instance_label"],
        "Set": master["set_name"],
        "Orders": master["order_count"],
        "AGVNS (s)": [fmt_mean_std(r["AGVNS_sec"], r["AGVNS_std_sec"]) for _, r in master.iterrows()],
        "MA (s)": [fmt_mean_std(r["MA_sec"], r["MA_std_sec"]) for _, r in master.iterrows()],
        "Gold (s)": [fmt_mean_std(r["Gold_sec"], r["Gold_std_sec"]) for _, r in master.iterrows()],
        "Silver (s)": [fmt_mean_std(r["Silver_sec"], r["Silver_std_sec"]) for _, r in master.iterrows()],
        "Bronze (s)": [fmt_mean_std(r["Bronze_sec"], r["Bronze_std_sec"]) for _, r in master.iterrows()],
        "EvoRL (s)": [fmt_mean_std(r["EvoRL_sec"], r["EvoRL_std_sec"]) for _, r in master.iterrows()],
        "TS (s)": [fmt_mean_std(r["TS_sec"], r["TS_std_sec"]) for _, r in master.iterrows()],
        "GA (s)": [fmt_ga_mean_std(r["GA_sec"], r["GA_std_sec"]) for _, r in master.iterrows()],
    })

    # Numeric side-by-side table for Excel
    numeric_cols = [
        "instance_id", "instance_label", "set_name", "order_count",
        "AGVNS_sec", "AGVNS_std_sec",
        "MA_sec", "MA_std_sec",
        "Gold_sec", "Gold_std_sec",
        "Silver_sec", "Silver_std_sec",
        "Bronze_sec", "Bronze_std_sec",
        "EvoRL_sec", "EvoRL_std_sec",
        "TS_sec", "TS_std_sec",
        "GA_sec", "GA_std_sec", "GA_n",
    ]
    numeric_df = master[numeric_cols].copy()

    # Set summary
    algs = ["AGVNS", "MA", "Gold", "Silver", "Bronze", "EvoRL", "TS", "GA"]
    set_summary_rows = []
    for set_num, g in master.groupby("set_num"):
        row = {
            "Set": f"Set {set_num}",
            "Orders": int(g["order_count"].iloc[0]),
            "Instances": f"HW{g['instance_id'].min()}-HW{g['instance_id'].max()}",
        }
        for alg in algs:
            m_col = f"{alg}_sec"
            s_col = f"{alg}_std_sec"
            valid_m = g[m_col].dropna()
            valid_s = g[s_col].dropna()
            mean_m = valid_m.mean() if len(valid_m) > 0 else np.nan
            mean_s = valid_s.mean() if len(valid_s) > 0 else np.nan
            formatter = fmt_ga_mean_std if alg == "GA" else fmt_mean_std
            row[f"{alg} (mean ± avg_std, s)"] = formatter(mean_m, mean_s)
            row[f"{alg}_coverage"] = f"{len(valid_m)}/8"
        set_summary_rows.append(row)
    set_summary_df = pd.DataFrame(set_summary_rows)

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        formatted_df.to_excel(writer, sheet_name="Master_64_Mean_Std", index=False)
        set_summary_df.to_excel(writer, sheet_name="Set_Summary", index=False)
        numeric_df.to_excel(writer, sheet_name="Numeric_Mean_Std", index=False)
        master.to_excel(writer, sheet_name="Full_Data_and_Sources", index=False)

        evorl_train_rows = [
            {"Set": "Set 1 (50 orders)", "Episodes": 5, "Train_Only_sec": 82.0, "Train_Plus_Val_sec": 164.0, "Mean_Per_Episode_sec": 32.8},
            {"Set": "Set 2 (100 orders)", "Episodes": 5, "Train_Only_sec": 359.0, "Train_Plus_Val_sec": 453.0, "Mean_Per_Episode_sec": 90.6},
            {"Set": "Set 3 (300 orders)", "Episodes": 5, "Train_Only_sec": 1193.0, "Train_Plus_Val_sec": 1358.0, "Mean_Per_Episode_sec": 271.6},
            {"Set": "Set 4 (500 orders)", "Episodes": 5, "Train_Only_sec": 6709.0, "Train_Plus_Val_sec": 6958.0, "Mean_Per_Episode_sec": 1391.6},
            {"Set": "Set 5 (1000 orders)", "Episodes": 5, "Train_Only_sec": 14174.0, "Train_Plus_Val_sec": 14505.0, "Mean_Per_Episode_sec": 2901.0},
            {"Set": "Set 6 (2000 orders)", "Episodes": 5, "Train_Only_sec": 28284.0, "Train_Plus_Val_sec": 28742.0, "Mean_Per_Episode_sec": 5748.4},
            {"Set": "Set 7 (3000 orders)", "Episodes": 5, "Train_Only_sec": 39083.0, "Train_Plus_Val_sec": 39534.0, "Mean_Per_Episode_sec": 7906.8},
            {"Set": "TOTAL (ep 1-35 checkpoint)", "Episodes": 35, "Train_Only_sec": 89884.0, "Train_Plus_Val_sec": 91721.0, "Mean_Per_Episode_sec": 2620.6},
        ]
        pd.DataFrame(evorl_train_rows).to_excel(writer, sheet_name="EvoRL_Training_Time", index=False)

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val_str = str(cell.value) if cell.value is not None else ""
                    max_len = max(max_len, len(val_str))
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 42)

    print("=== std Coverage Across All 64 Instances ===")
    for alg in algs:
        std_cnt = master[f"{alg}_std_sec"].notna().sum()
        mean_cnt = master[f"{alg}_sec"].notna().sum()
        print(f"  {alg:8s}: mean={mean_cnt}/64, std={std_cnt}/64")

    print("\n=== Set Summary (mean ± avg within-instance std, seconds) ===")
    cols_show = ["Set", "Orders"] + [f"{alg} (mean ± avg_std, s)" for alg in algs]
    print(set_summary_df[cols_show].to_string(index=False))


if __name__ == "__main__":
    main()
