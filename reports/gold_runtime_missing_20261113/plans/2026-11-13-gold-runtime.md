# Gold runtime measurement

- Target: competition Top-1 Java solver in `1/compiled_files`.
- Instances 57, 58, 59, 60, 63, 64; four repetitions each; 24 independent jobs, at most 12 concurrently on cores 0–11.
- Simulator seed is `20261113 + instance_id * 1000 + repetition`. Java RNG reproducibility is not established.
- Each job has a separate interaction directory and worker log. The runner records wall and simulator runtimes and completion status. The simulator enforces 600 seconds per algorithm call.
- The experiment-local `java` wrapper uses GNU time to append elapsed seconds and exit code for each Java dispatch to that job's `java_dispatch_times.csv`. Time resolution is 0.01 s; wrapper overhead is included in simulator behavior.
- The original queue parser's `algorithm_time_seconds` and `algorithm_dispatch_count` depend on a log string not emitted by Gold. Treat their zeros as unavailable. On completion `summarize_java_timing.py` writes `results_with_java_timing.csv` and `summary_with_java_timing.csv`; per-dispatch data remain available during execution.
- A result must finish successfully, have a finite score below the sentinel, and have recorded successful Java calls to be labelled VALID by the postprocessor. Keep incomplete/failed runs visible.
- Outputs: `runs/<batch_id>/manifest.json`, `results.csv`, `summary.json`, worker directories and `launcher.log`.
