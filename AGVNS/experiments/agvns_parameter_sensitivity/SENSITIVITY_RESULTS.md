# AGVNS sensitivity results

Snapshot: 2026-10-13 17:28:35 +07 (Asia/Ho_Chi_Minh).

Coverage is **480/480 valid**; 0 run keys are still unresolved: 0 running, 0 queued in the current batch, and 0 that need a rerun.

The 480-row master leaves score and runtime fields blank wherever no valid finalized result exists.

- [Detailed report](reports/sensitivity_report.md)
- [Master table: one row per planned job](reports/sensitivity_results_master.csv)
- [Recorded result attempts and failures](reports/sensitivity_attempts.csv)
- [Coverage and score summaries by instance/configuration](reports/sensitivity_coverage.csv)
- [Current per-instance sensitivity table](reports/sensitivity_table_current.md)
- [Current 480-job status table](reports/sensitivity_jobs_current.csv)
- [480-job dataset grouped by order-count length](reports/sensitivity_jobs_by_length.csv)
- [Summary by order-count length and configuration](reports/sensitivity_summary_by_length.csv)
- [Taguchi factor-level summaries with instance-equal macro improvement](reports/sensitivity_factor_effects.csv)
- [Detailed Taguchi interpretation and per-instance Config 3 analysis](reports/sensitivity_taguchi_interpretation.md)
- [Worker logs without a finalized JSONL result](reports/sensitivity_unrecorded_logs.csv)
- [Report builder](reports/build_sensitivity_report.py)

Latest recorded batch `20261009_015120` selected 36 jobs and used 12 workers on cores `0,1,2,3,4,5,6,7,8,9,10,11`. Rerun `reports/build_sensitivity_report.py` to refresh the snapshot when new result artifacts arrive.
