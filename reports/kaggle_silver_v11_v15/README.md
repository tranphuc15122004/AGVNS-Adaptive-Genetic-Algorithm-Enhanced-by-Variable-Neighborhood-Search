# Kết quả notebook Silver, saved version 11–15

Nguồn: Kaggle `trnphc15122004/silver`, các saved version 11–15, tải session log và notebook source ngày 2026-11-15 UTC. Các thư mục `v11`–`v15` chứa notebook source (`notebook.ipynb`), session log gốc JSON (`session.json`) cùng bản giải mã thành văn bản (`session.log`).

Tất cả 5 version đều chạy lệnh `! python main.py --instances $(seq -s, 41 64)` và **đạt 100% thành công**, không có instance nào bị lỗi (0 ERROR). Tổng cộng **120 lượt chạy thành công** (24 instance × 5 version).

## Các file kết quả

- `completed_runs_41_64.csv`: 120 lượt chạy thành công, kèm version (11–15), instance (41–64), status (`SUCCESS`), score, runtime thực (wall time, giây), timestamp bắt đầu/kết thúc, số lượng xe, tổng quãng đường (`distance_km`), tổng trễ (`overtime_seconds`), chi phí quãng đường (`distance_cost`), chi phí trễ hạn (`overtime_cost`), và file nguồn log.
- `summary_by_instance_41_64.csv`: Tổng hợp 24 instance (41–64) qua 5 lượt chạy: score chính xác, số xe, distance, overtime, hai thành phần chi phí, thời gian chạy trung bình (`runtime_mean_seconds`), độ lệch chuẩn (`runtime_std_population_seconds`), min, max và runtime chi tiết của từng version (`v11`–`v15`).
- `vehicle_distances_41_64.csv`: Chi tiết quãng đường di chuyển và số node ghé thăm của từng xe trên từng lượt chạy (tổng cộng 10.000 dòng).
- `version_summary.json`: Trạng thái trên Kaggle, lệnh điều phối, danh sách điểm số, số lỗi (0 lỗi), dung lượng log và thời gian chạy tổng thể của từng version notebook.
- `collect_results.py`: Script trích xuất, xác thực ràng buộc toán học và kiểm tra log.

## Kiểm tra tính nhất quán (Validation)

Toàn bộ 120 lượt chạy đã được kiểm tra tính toàn vẹn:
1. Tổng quãng đường từng xe khớp tuyệt đối với `Total distance` (`|sum(v) - total| < 0.001`).
2. Điểm số khớp chính xác tuyệt đối theo công thức:
   $$\text{Score} = \frac{\text{Distance}}{\text{Số xe}} + \frac{\text{Overtime} \times 10000}{3600}$$
3. Thuật toán mang tính tất định (deterministic) với cấu hình mặc định, do đó điểm số của mỗi instance là **đồng nhất tuyệt đối** qua cả 5 version từ 11 đến 15.
4. Điểm số khớp với các giá trị làm tròn trong y văn / tài liệu tham khảo (ví dụ: instance 41 = 124.253,3 vs 124.000; instance 57 = 22.433.901,4 vs 22.400.000).

## Tóm tắt thời gian chạy

- Nhóm 2.000 orders (Instances 41–48): runtime trung bình ~334,2 giây (~5,57 phút/instance).
- Nhóm 3.000 orders (Instances 49–56): runtime trung bình ~350,0 giây (~5,83 phút/instance).
- Nhóm 4.000 orders (Instances 57–64): runtime trung bình ~371,7 giây (~6,20 phút/instance).
- Tổng thời gian thực thi của mỗi phiên notebook (24 instances) trên Kaggle dao động từ 2,28 đến 2,51 giờ.
