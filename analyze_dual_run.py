# -*- coding: utf-8 -*-
"""Analyze the dual-run comparison log produced by MOEA/D--TS.

MOEA/D--TS now launches the AGVNS pipeline on the exact same restored scene at
every epoch (see ``MOEAD-TS/algorithm/main.py`` ``_launch_agvns_compare``) and
appends one line per epoch to::

    MOEAD-TS/algorithm/data_interaction_compare/<run_id>/comparison.jsonl

Each record is ``{"epoch", "deltaT", "moead_tc", "agvns_tc", "delta",
"moead_route_after", "agvns_route_after"}`` with routes in the canonical JSON
format shared by both algorithms.

This script prints a per-epoch table, finds the FIRST epoch where MOEAD's TC
exceeds AGVNS' by at least ``--threshold`` (default 50), and prints a compact
route summary for both algorithms at every divergent epoch so the bad dispatch
decision can be inspected.

Usage (from the repo root):
    python analyze_dual_run.py [--threshold 50] [--log PATH]
"""

import argparse
import json
import os
import sys

MOEAD_COMPARE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "MOEAD-TS", "algorithm", "data_interaction_compare",
)


def _latest_comparison_log() -> str:
    """Return the most recent comparison.jsonl across all run ids."""
    if not os.path.isdir(MOEAD_COMPARE_DIR):
        return ""
    best, best_mtime = "", -1.0
    for run_id in os.listdir(MOEAD_COMPARE_DIR):
        path = os.path.join(MOEAD_COMPARE_DIR, run_id, "comparison.jsonl")
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            if mtime > best_mtime:
                best, best_mtime = path, mtime
    return best


def _summarize_route(route_after):
    """Compact one-line summary of a canonical or legacy route."""
    if route_after is None:
        return "(none)"
    if isinstance(route_after, str):
        try:
            routes = json.loads(route_after)
        except (ValueError, TypeError):
            return route_after  # legacy "V_1:[...] V_2:[...]" — show raw
    else:
        routes = route_after
    if not isinstance(routes, list):
        return str(route_after)
    parts = []
    for route in routes:
        if (not isinstance(route, list) or len(route) != 2 or
                not isinstance(route[0], str) or not isinstance(route[1], list)):
            return str(route_after)
        vehicle_id, nodes = route
        node_strs = []
        for node in nodes:
            if (not isinstance(node, list) or len(node) != 3):
                return str(route_after)
            factory_id, pickups, deliveries = node
            node_strs.append("{}[p{}|d{}]".format(
                factory_id, len(pickups or []), len(deliveries or [])))
        parts.append("{}: {}".format(vehicle_id, " ".join(node_strs)))
    return " | ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=50.0,
                        help="MOEAD TC must exceed AGVNS TC by at least this to count as divergence")
    parser.add_argument("--log", default=None,
                        help="explicit path to a comparison.jsonl "
                             "(default: latest under MOEAD-TS/algorithm/data_interaction_compare)")
    args = parser.parse_args()

    log_path = args.log or _latest_comparison_log()
    if not log_path or not os.path.isfile(log_path):
        print("No comparison.jsonl found under {}".format(MOEAD_COMPARE_DIR))
        sys.exit(2)

    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue

    if not records:
        print("comparison.jsonl is empty: {}".format(log_path))
        sys.exit(1)

    print("Dual-run comparison log: {}".format(log_path))
    print("Epochs recorded: {}".format(len(records)))
    print()
    header = "{:>6}  {:>12}  {:>12}  {:>12}  {:>8}  {}".format(
        "epoch", "deltaT", "MOEAD TC", "AGVNS TC", "diff", "verdict")
    print(header)
    print("-" * len(header))

    divergent = []
    for rec in records:
        epoch = rec.get("epoch")
        delta_t = rec.get("deltaT", "")
        moead_tc = rec.get("moead_tc")
        agvns_tc = rec.get("agvns_tc")
        delta = rec.get("delta")
        verdict = ""
        if moead_tc is not None and agvns_tc is not None:
            if moead_tc > agvns_tc + args.threshold:
                verdict = "<-- MOEAD worse"
                divergent.append(rec)
            elif agvns_tc > moead_tc + args.threshold:
                verdict = "<-- MOEAD better"
        print("{:>6}  {:>12}  {:>12.2f}  {:>12.2f}  {:>8.2f}  {}".format(
            epoch, delta_t,
            float(moead_tc) if moead_tc is not None else float("nan"),
            float(agvns_tc) if agvns_tc is not None else float("nan"),
            float(delta) if delta is not None else float("nan"),
            verdict))

    print()
    if not divergent:
        print("No divergent epoch found (MOEAD worse by > {:.0f}).".format(args.threshold))
        return

    print("First divergent epoch: epoch {} ({})  (MOEAD TC {} vs AGVNS TC {})".format(
        divergent[0].get("epoch"), divergent[0].get("deltaT"),
        divergent[0].get("moead_tc"), divergent[0].get("agvns_tc")))
    print()
    for rec in divergent:
        print("=" * 90)
        print("Epoch {} ({})  MOEAD TC={}  AGVNS TC={}".format(
            rec.get("epoch"), rec.get("deltaT"),
            rec.get("moead_tc"), rec.get("agvns_tc")))
        print("  MOEAD route_after: {}".format(_summarize_route(rec.get("moead_route_after"))))
        print("  AGVNS route_after: {}".format(_summarize_route(rec.get("agvns_route_after"))))


if __name__ == "__main__":
    main()
