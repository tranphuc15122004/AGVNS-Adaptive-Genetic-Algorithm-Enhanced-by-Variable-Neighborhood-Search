# Findings — EvoRL aggregation

## Nguồn dữ liệu

- Batch hiện tại: `EvoRL/algorithm/data_interaction_runs/20260819_094955/results.csv`.
  - 256 dòng kết quả, instance 1–64, repetition 1–4, tất cả `SUCCESS`.
- Lần chạy trước dùng làm reference: `EvoRL/algorithm/data_interaction_runs/EvoRL_results_64_instances.csv`.
  - 64 dòng dữ liệu, mỗi instance một lần (`repetition=1`), tất cả `SUCCESS`.
  - File này là kết quả nối của batch `20260815_064053` (instance 1–10) và
    `20260817_020323` (instance 11–64), tạo thành một lần chạy 64-instance hoàn chỉnh.
- Không dùng batch `20260818_143854`: batch đó có `status=RUNNING` và `completed_jobs=0`,
  nên không phải nguồn kết quả hợp lệ cho tổng hợp.

## Schema và hướng tổng hợp

- Chỉ tiêu chính: `score` (thấp hơn tốt hơn).
- Chỉ tiêu phụ: `wall_time_seconds`, `simulation_runtime_seconds`,
  `algorithm_time_seconds`, `algorithm_dispatch_count`.
- Mỗi instance sẽ có 5 score: một reference trước đó và 4 repetition hiện tại,
  cùng mean/std/min/max của 5 lần và mean/std của riêng 4 repetition mới.
- Báo cáo cần tách thống kê theo nhóm kích thước instance vì raw score giữa các nhóm
  50–4000 order khác nhau rất lớn; đồng thời báo cáo paired change so với reference.

## Câu hỏi còn mở

- Cần xác nhận bằng dữ liệu xem reference có trùng kết quả với repetition 1 hiện tại
  hay không; nếu có, ghi rõ trong báo cáo thay vì xem là 5 mẫu hoàn toàn độc lập.

## Kiểm tra sơ bộ

- Reference trùng score với repetition 1 hiện tại ở 28/64 instance; 36/64 khác.
- So sánh mean của 4 repetition hiện tại với reference: 20 instance tốt hơn,
  25 bằng, 19 xấu hơn; macro-average thay đổi khoảng -0.082%.
