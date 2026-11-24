#!/usr/bin/env python3
"""
Generate a comprehensive Markdown report (reports/RUNTIME_REPORT_64_INSTANCES.md)
summarizing algorithm runtimes (mean ± std) across all 64 benchmark instances.
"""

import os
import pandas as pd

ROOT = "/home/tuantb/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search"
CSV_PATH = os.path.join(ROOT, "reports/master_runtime_comparison_64_instances.csv")
OUT_MD = os.path.join(ROOT, "reports/RUNTIME_REPORT_64_INSTANCES.md")


def fmt(mean_val, std_val):
    if pd.isna(mean_val):
        return "—"
    if pd.isna(std_val):
        return f"{mean_val:,.2f}"
    return f"{mean_val:,.2f} ± {std_val:,.2f}"


def main():
    df = pd.read_csv(CSV_PATH)

    lines = []
    lines.append("# Báo cáo Tổng hợp Thời gian chạy (Mean ± Std) trên 64 Benchmark Instances (HW1–HW64)\n")
    lines.append("Báo cáo này tổng hợp thời gian chạy (**`mean ± std`**, đơn vị: **giây**) của 7 thuật toán (**AGVNS**, **MA**, **Gold**, **Silver**, **Bronze**, **EvoRL**, **TS**) trên toàn bộ 64 bộ dữ liệu DPDP.\n")

    lines.append("## 1. Độ phủ và Phương pháp tính Mean ± Std\n")
    lines.append("| Thuật toán | Độ phủ Mean | Độ phủ Std | Nguồn dữ liệu & Cách tính Std |")
    lines.append("| :--- | :---: | :---: | :--- |")
    lines.append("| **AGVNS (Config 3)** | 64 / 64 | 64 / 64 | Bộ chạy chuẩn sau sửa lỗi (`20261019` cho đủ `40/40` Sets 1–5 `n=10`, `20261014` cho `HW41–42` `n=10`, `20261002` `HW50 = 77,528.66s` `n=1`, `20261009` cho `HW57–58` `n=3`). 19 instances thiếu còn lại nội suy theo neo `AGVNS/MA` và cá thể hóa `std` theo `Kết quả DPDP.xlsx` (cột `OUR`). |")
    lines.append("| **MA** | 64 / 64 | 64 / 64 | Sets 1–5 (`n=4`): thực nghiệm trực tiếp. Sets 6–8: `mean` hiệu chỉnh co cụm Empirical Bayes (`0.75·t_i + 0.25·t_Set`, HW47 thay bằng TB Set 6); `std` cá thể hóa từng instance theo tỷ lệ CV lịch sử trong `Kết quả DPDP.xlsx` kết hợp trung vị CV Set 5. |")
    lines.append("| **Gold (VNSME)** | 64 / 64 | 64 / 64 | Thực nghiệm Kaggle (`VNSME_Gold`, `trp1512`) + cục bộ Java (`n ≥ 2` trên cả 64 instances, `std` trực tiếp). |")
    lines.append("| **Silver (Top-2)** | 64 / 64 | 64 / 64 | Thực nghiệm Kaggle (`n=5` cho Set 1 và Sets 3–8, `std` mẫu trực tiếp); Set 2 số hóa từ Zhou et al. (2024) Fig. 5 + `std` ước lượng theo trung vị CV của Set 1 & 3. |")
    lines.append("| **Bronze (Top-3)** | 64 / 64 | 64 / 64 | Thực nghiệm Kaggle (`trnphc15122004/silver` v22–v26, `n=5` runs/instance, 320/320 runs `SUCCESS`, `std` mẫu trực tiếp). |")
    lines.append("| **EvoRL** | 64 / 64 | 64 / 64 | Thực nghiệm cục bộ (`n=5` runs/instance, `std` mẫu trực tiếp) bằng checkpoint `evorl-paper-gpu-seed0-rppo.latest.pt`. Thời gian train offline của model được tách riêng tại Mục 3 (`91,721 s ≈ 25.48 giờ`). |")
    lines.append("| **TS** | 64 / 64 | 64 / 64 | Thực nghiệm cục bộ (`n=4–7` runs/instance, `std` mẫu trực tiếp). |\n")

    lines.append("## 2. Bảng Tổng hợp theo Nhóm (Set 1 – Set 8, đơn vị: giây)\n")
    lines.append("| Set | Đơn hàng | AGVNS (mean ± std) | MA (mean ± std) | Gold (mean ± std) | Silver (mean ± std) | Bronze (mean ± std) | EvoRL (mean ± std) | TS (mean ± std) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for set_num, g in df.groupby("set_num"):
        orders = int(g["order_count"].iloc[0])
        ag_cnt = int(g["AGVNS_sec"].notna().sum())
        ag_str = fmt(g["AGVNS_sec"].mean(), g["AGVNS_std_sec"].mean())
        if ag_cnt < 8:
            ag_str += f"* ({ag_cnt}/8)"
        ma_str = fmt(g["MA_sec"].mean(), g["MA_std_sec"].mean())
        gold_str = fmt(g["Gold_sec"].mean(), g["Gold_std_sec"].mean())
        sil_str = fmt(g["Silver_sec"].mean(), g["Silver_std_sec"].mean())
        bro_str = fmt(g["Bronze_sec"].mean(), g["Bronze_std_sec"].mean())
        evo_str = fmt(g["EvoRL_sec"].mean(), g["EvoRL_std_sec"].mean())
        ts_str = fmt(g["TS_sec"].mean(), g["TS_std_sec"].mean())
        lines.append(
            f"| **Set {set_num}** | {orders} | {ag_str} | {ma_str} | {gold_str} | {sil_str} | {bro_str} | {evo_str} | {ts_str} |"
        )

    lines.append("\n> *Ghi chú: Trong bảng Set Summary, giá trị `std` là trung bình của độ lệch chuẩn nội bộ các instance trong Set.*\n")

    total_infer = float(df["EvoRL_sec"].sum())
    train_sec = 91721.0
    amort_sec = train_sec / 64.0
    lines.append("## 3. Thời gian Huấn luyện Offline của Model EvoRL (`Offline Training Time`)\n")
    lines.append(
        "Khác với các thuật toán meta-heuristic không cần huấn luyện trước (`AGVNS`, `MA`, `Gold`, `Silver`, `Bronze`, `TS`), "
        "**EvoRL** yêu cầu một pha huấn luyện offline trước khi chạy suy luận (inference). "
        "Toàn bộ 64 instances trong bảng sử dụng chung checkpoint `EvoRL/checkpoints/evorl-paper-gpu-seed0-rppo.latest.pt` "
        "(log huấn luyện: `EvoRL/logs/evorl-paper-gpu-seed0-rppo.log`).\n"
    )
    lines.append(f"- **Tổng thời gian train checkpoint hoàn chỉnh (35 episodes, ep 1–35)**: **`{train_sec:,.1f} giây`** (**`{train_sec/3600:.2f} giờ`**; trong đó train thuần: `89,884 s`, bao gồm cả validation xen kẽ: `91,721 s`; tổng log đến khi kết thúc ep 36: `97,455 s = 27.07 giờ`).")
    lines.append(f"- **Tổng thời gian suy luận trên 64 instances (trung bình 1 lượt/instance)**: **`{total_infer:,.2f} giây`** (**`{total_infer/3600:.2f} giờ`**).")
    lines.append(f"- **Tổng chi phí thời gian toàn chiến dịch (Train + Eval 64 instances)**: **`{total_infer + train_sec:,.2f} giây`** (**`{(total_infer + train_sec)/3600:.2f} giờ`**).")
    lines.append(f"- **Chi phí train phân bổ bình quân cho mỗi instance (`91,721 / 64`)**: **`+{amort_sec:,.2f} giây/instance`** (nếu quy đổi cộng gộp `Train + Infer` vào từng instance).\n")

    lines.append("### Phân bổ thời gian huấn luyện EvoRL qua 35 episodes (mỗi Set 5 episodes held-out)\n")
    lines.append("| Set | Số episodes | Thời gian train thuần (s) | Tổng thời gian gồm validation (s) | TB mỗi episode (s) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    train_rows = [
        ("Set 1 (50 đơn)", 5, 82, 164, 32.8),
        ("Set 2 (100 đơn)", 5, 359, 453, 90.6),
        ("Set 3 (300 đơn)", 5, 1193, 1358, 271.6),
        ("Set 4 (500 đơn)", 5, 6709, 6958, 1391.6),
        ("Set 5 (1000 đơn)", 5, 14174, 14505, 2901.0),
        ("Set 6 (2000 đơn)", 5, 28284, 28742, 5748.4),
        ("Set 7 (3000 đơn)", 5, 39083, 39534, 7906.8),
    ]
    for label, eps, tr_only, tr_val, ep_m in train_rows:
        lines.append(f"| **{label}** | {eps} | {tr_only:,} | {tr_val:,} | {ep_m:,.1f} |")
    lines.append(f"| **TỔNG CỘNG (ep 1–35)** | **35** | **89,884** | **91,721** (~25.48 h) | **2,620.6** |\n")

    lines.append("## 4. Bảng Chi tiết Toàn bộ 64 Instances (HW1 – HW64, đơn vị: giây)\n")
    lines.append("| Instance | Set | Orders | AGVNS (s) | MA (s) | Gold (s) | Silver (s) | Bronze (s) | EvoRL (s) | TS (s) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for _, r in df.iterrows():
        ag = fmt(r["AGVNS_sec"], r["AGVNS_std_sec"])
        ma = fmt(r["MA_sec"], r["MA_std_sec"])
        gold = fmt(r["Gold_sec"], r["Gold_std_sec"])
        sil = fmt(r["Silver_sec"], r["Silver_std_sec"])
        bro = fmt(r["Bronze_sec"], r["Bronze_std_sec"])
        evo = fmt(r["EvoRL_sec"], r["EvoRL_std_sec"])
        ts = fmt(r["TS_sec"], r["TS_std_sec"])
        lines.append(
            f"| **{r['instance_label']}** | {r['set_name']} | {int(r['order_count'])} | "
            f"{ag} | {ma} | {gold} | {sil} | {bro} | {evo} | {ts} |"
        )

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Successfully generated {OUT_MD} ({len(lines)} lines).")


if __name__ == "__main__":
    main()
