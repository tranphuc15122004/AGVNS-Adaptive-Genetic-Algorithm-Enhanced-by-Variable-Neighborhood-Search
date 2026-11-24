#!/usr/bin/env python3
"""
Watchdog and Transition Runner:
1. Monitors MA batch 20261114_195217 until all 32 jobs of Set 5 (instances 33-40, 4 repetitions each) finish with SUCCESS.
2. Gracefully stops the old runner PID 817000 and kills tmux session 'ma_runtime_resume_20261114'.
3. Cleans up any dummy directories created for instances > 40 in 20261114_195217.
4. Immediately launches Option 2 for Sets 6, 7, 8:
   instances 41-64, repetitions=1, workers=12, cores 0-11.
5. Continues monitoring until Option 2 finishes.
"""

import csv
import datetime
import math
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = "/home/tuantb/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search"
MA_DIR = os.path.join(ROOT, "MA")
OLD_BATCH_DIR = os.path.join(MA_DIR, "algorithm/data_interaction_runs/20261114_195217")
OLD_RESULTS_CSV = os.path.join(OLD_BATCH_DIR, "results.csv")
OLD_TMUX_SESSION = "ma_runtime_resume_20261114"
NEW_TMUX_SESSION = "ma_option2_sets_6_7_8"
LOG_FILE = os.path.join(ROOT, "logs/watch_ma_option2.log")

SET_5_INSTANCES = list(range(33, 41))
REQUIRED_REPETITIONS = [1, 2, 3, 4]
TOTAL_SET_5_JOBS = len(SET_5_INSTANCES) * len(REQUIRED_REPETITIONS)  # 32 jobs


def log(msg: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_completed_set5_jobs():
    if not os.path.exists(OLD_RESULTS_CSV):
        return set()
    completed = set()
    try:
        with open(OLD_RESULTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    inst = int(row["instance_id"])
                    rep = int(row["repetition"])
                    score = float(row["score"])
                    ret = int(row["return_code"])
                    status = row.get("status")
                except (ValueError, KeyError, TypeError):
                    continue
                if inst in SET_5_INSTANCES and rep in REQUIRED_REPETITIONS:
                    if status == "SUCCESS" and ret == 0 and math.isfinite(score):
                        completed.add((inst, rep))
    except Exception as e:
        log(f"Error reading {OLD_RESULTS_CSV}: {e}")
    return completed


def get_active_workers_summary():
    # Find all running python processes under MA
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "pid,pcpu,args"],
            text=True,
            errors="replace"
        )
    except Exception:
        return "N/A"
    active = []
    for line in out.splitlines():
        if "main.py --instances" in line and "20261114_195217" in line:
            m = re.search(r"--instances\s+(\d+)", line)
            m_cpu = re.search(r"--cpu\s+(\d+)", line)
            m_seed = re.search(r"--seed\s+(\d+)", line)
            inst = m.group(1) if m else "?"
            cpu = m_cpu.group(1) if m_cpu else "?"
            seed = m_seed.group(1) if m_seed else "?"
            rep = int(seed) % 1000 if seed.isdigit() else "?"
            active.append(f"inst_{inst}_rep_{rep}_c{cpu}")
    return ", ".join(sorted(active)) if active else "none"


def terminate_old_runner():
    log(f"Terminating old tmux session '{OLD_TMUX_SESSION}' and associated runner...")
    # 1. Kill old tmux session if present
    subprocess.run(["tmux", "kill-session", "-t", OLD_TMUX_SESSION], stderr=subprocess.DEVNULL)
    time.sleep(2)

    # 2. Kill any lingering python processes referencing 20261114_195217 or ma_resume_runner
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,args"], text=True)
        for line in out.splitlines():
            if ("ma_resume_runner_20261114.py" in line or "20261114_195217" in line) and "watch_and_run" not in line:
                pid = int(line.strip().split()[0])
                log(f"Killing lingering process PID {pid}: {line.strip()[:80]}")
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
    except Exception as e:
        log(f"Error terminating lingering processes: {e}")

    # 3. Clean up any dummy folders for instances > 40 in 20261114_195217/jobs
    jobs_dir = os.path.join(OLD_BATCH_DIR, "jobs")
    if os.path.exists(jobs_dir):
        for entry in os.listdir(jobs_dir):
            if entry.startswith("instance_"):
                try:
                    num = int(entry.replace("instance_", ""))
                    if num > 40:
                        full_p = os.path.join(jobs_dir, entry)
                        log(f"Removing dummy job dir: {full_p}")
                        shutil.rmtree(full_p, ignore_errors=True)
                except ValueError:
                    pass


def launch_option_2():
    log("=" * 60)
    log("LAUNCHING OPTION 2 FOR SETS 6, 7, 8 (INSTANCES 41-64, REPETITIONS=1)")
    log("=" * 60)

    cmd = (
        f"cd {MA_DIR} && "
        f"/home/tuantb/miniconda3/bin/python run_parallel.py "
        f"--instances 41-64 --repetitions 1 --workers 12 "
        f"--cores 0,1,2,3,4,5,6,7,8,9,10,11 --base-seed 0 "
        f"2>&1 | tee {ROOT}/logs/ma_option2_execution.log"
    )

    # Launch inside tmux session NEW_TMUX_SESSION
    # Kill session if it already exists
    subprocess.run(["tmux", "kill-session", "-t", NEW_TMUX_SESSION], stderr=subprocess.DEVNULL)
    time.sleep(1)

    log(f"Starting tmux session '{NEW_TMUX_SESSION}' with command:\n{cmd}")
    subprocess.run(["tmux", "new-session", "-d", "-s", NEW_TMUX_SESSION, cmd], check=True)
    time.sleep(3)
    log(f"Option 2 launched successfully in tmux session '{NEW_TMUX_SESSION}'!")


def main():
    log("Watchdog started. Monitoring Set 5 (instances 33-40) in batch 20261114_195217...")
    last_completed_count = -1

    while True:
        completed = get_completed_set5_jobs()
        completed_count = len(completed)

        if completed_count != last_completed_count:
            last_completed_count = completed_count
            by_inst = {}
            for inst in SET_5_INSTANCES:
                reps = sorted([r for (i, r) in completed if i == inst])
                by_inst[inst] = reps
            active_summary = get_active_workers_summary()
            log(f"Set 5 Progress: {completed_count}/{TOTAL_SET_5_JOBS} jobs completed ({(completed_count/TOTAL_SET_5_JOBS)*100:.1f}%)")
            log(f"Instances detail: {by_inst}")
            log(f"Active workers: [{active_summary}]")

        if completed_count >= TOTAL_SET_5_JOBS:
            log("ALL 32 JOBS OF SET 5 ARE COMPLETE!")
            break

        time.sleep(30)

    # Set 5 is complete -> terminate old runner and launch Option 2
    terminate_old_runner()
    time.sleep(5)
    launch_option_2()

    # Now monitor Option 2 progress
    log("Monitoring Option 2 execution...")
    while True:
        # Check if tmux session is still alive
        check = subprocess.run(["tmux", "has-session", "-t", NEW_TMUX_SESSION], stderr=subprocess.DEVNULL)
        if check.returncode != 0:
            log(f"Tmux session '{NEW_TMUX_SESSION}' has finished.")
            break
        time.sleep(60)

    log("Option 2 execution finished!")


if __name__ == "__main__":
    main()
