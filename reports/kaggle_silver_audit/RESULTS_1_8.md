# Kết quả Top-2 trên Kaggle: instance 1–8

Nguồn: log thực thi 5 saved version của notebook `trnphc15122004/silver`, thu thập ngày 2026-11-15. Mỗi version hoàn thành instance 1–8. Cả 5 version có cùng score, tổng quãng đường và tổng thời gian trễ cho từng instance; runtime khác nhau. Version 5 có seed 0 trong runtime report. Seed của version 1–4 chưa được xác minh từ runtime report tương ứng.

| Instance | Score | Tổng quãng đường (km) | Tổng trễ (giây) | Cost quãng đường | Cost trễ | Runtime v5 (giây) | Runtime trung bình 5 version (giây) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2,303.593 | 851.3 | 768 | 170.260 | 2,133.333 | 303.221 | 317.015 |
| 2 | 30,478.904 | 547.3 | 10,933 | 109.460 | 30,369.444 | 313.169 | 333.551 |
| 3 | 35,800.722 | 767.5 | 12,833 | 153.500 | 35,647.222 | 305.102 | 319.603 |
| 4 | 5,491.578 | 694.0 | 1,927 | 138.800 | 5,352.778 | 311.996 | 329.017 |
| 5 | 16,928.787 | 685.6 | 6,045 | 137.120 | 16,791.667 | 304.551 | 318.771 |
| 6 | 4,761.871 | 753.8 | 1,660 | 150.760 | 4,611.111 | 297.784 | 317.174 |
| 7 | 12,847.393 | 820.3 | 4,566 | 164.060 | 12,683.333 | 314.381 | 331.723 |
| 8 | 797.113 | 443.9 | 255 | 88.780 | 708.333 | 319.154 | 344.844 |

Score trung bình của 8 instance là 13,676.245. Tổng runtime của 8 instance trong version 5 là 2,469.357 giây, khoảng 41 phút 9 giây; thời gian này không bao gồm toàn bộ công đoạn khởi tạo notebook.

Simulator tính `score = tổng quãng đường / số xe + tổng thời gian trễ × 10000 / 3600`; cả 8 instance dùng 5 xe. Tổng thời gian trễ là tổng phần trễ dương theo đơn, với thời điểm hoàn tất đơn là thời điểm hoàn tất item cuối cùng của đơn; đây không phải tổng thời gian chạy của chương trình. Hai cost thành phần trong bảng được tính lại từ quãng đường và thời gian trễ được ghi trong log. Score trong CSV được lấy từ dòng `Score of instance` có độ chính xác cao hơn dòng `Total score` đã làm tròn ba chữ số.

## Dữ liệu đầy đủ

- `results_instances_1_8_all_versions.csv`: 40 dòng, một dòng cho mỗi instance và version; gồm score, runtime, thời điểm đầu/cuối xấp xỉ, tổng distance, tổng trễ và hai cost thành phần. Thời điểm kết thúc lấy từ dòng log `Score of instance`, thời điểm bắt đầu suy ra bằng cách trừ runtime; cả hai được ghi ở độ chính xác xấp xỉ mili giây. Version 5 có thời điểm bắt đầu/kết thúc chính xác hơn trong `latest_output/.../2/Y_final_submission/algorithm/data_interaction/runtime_stats.json`.
- `vehicle_distances_instances_1_8_all_versions.csv`: 200 dòng, ghi quãng đường và số bản ghi vị trí/nhà máy trong lịch sử theo từng xe, instance và version. Số bản ghi không nhất thiết là số nhà máy khác nhau.
- `versions/v01`–`v05/session.log`: log gốc đã giải mã, có timestamp và các dòng evaluator.

Log hiện có không cung cấp trực tiếp số đơn trễ, độ trễ từng đơn, thời gian chạy riêng của thuật toán tại mỗi epoch, hoặc dữ liệu tuyến đầy đủ theo từng instance. Không suy diễn các giá trị đó từ score.
