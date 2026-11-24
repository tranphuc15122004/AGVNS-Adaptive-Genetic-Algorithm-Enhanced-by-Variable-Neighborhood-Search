# Kết quả notebook Silver, saved version 5–10

Nguồn: Kaggle `trnphc15122004/silver`, các saved version 5–10, tải session log ngày 2026-11-15 UTC. Các file `v05`–`v10` chứa notebook source và session log gốc JSON cùng bản giải mã thành văn bản. Không tái chạy thí nghiệm.

Version 5 chạy `--instances 1..32` nhưng dừng ở instance 9, chỉ hoàn thành 1–8, do đó không có kết quả thuộc khoảng 16–40. Version 6–10 chạy `--instances 16..40`; mỗi version có instance 16 FAILED, sau đó hoàn thành instance 17–40. Tổng cộng **120 lượt thành công** (24 instance × 5 version). Dù Kaggle báo COMPLETE cho từng notebook, log xác nhận instance 16 FAILED trong cả năm batch. Không coi version 5 là lượt chạy instance 16–40.

Instance 16 lỗi vì item `1502480055-1` quá hạn nhưng chưa được phân công tại thời gian mô phỏng 2026-11-15 19:10:00. Simulator gọi `SystemExit(-1)`; runner ghi lỗi và tiếp tục. Các lượt lỗi không nằm trong CSV thành công và không tham gia tính trung bình. Báo cáo không có score hay thời gian chạy thành công cho instance 16.

## Các file

- `completed_runs_16_40.csv`: 120 lượt thành công, kèm version, instance, score, runtime thực (wall time, giây), timestamp, tổng quãng đường, tổng trễ, số xe và hai thành phần cost. Thời điểm kết thúc lấy từ timestamp log; thời điểm bắt đầu được tính gần đúng bằng kết thúc trừ runtime và có thể chênh vài mili giây.
- `summary_by_instance_17_40.csv`: score, thành phần cost, runtime trung bình, độ lệch chuẩn quần thể, min, max và runtime của từng version. Trung bình được tính trên đúng 5 lượt thành công; không bao gồm version 5 hay instance 16.
- `vehicle_distances_16_40.csv`: quãng đường theo từng xe ở từng lượt; `position_history_entries` là số bản ghi vị trí, không phải số nhà máy khác nhau.
- `version_summary.json`: trạng thái Kaggle, lệnh chạy, score và lỗi từng version.
- `collect_results.py`: trích xuất lại và kiểm tra log.

## Kiểm tra và cách diễn giải

Chỉ đưa vào một lượt nếu có dòng `Score of instance` và đầy đủ thông tin evaluator. Script kiểm tra tổng quãng đường từng xe khớp total distance; kiểm tra `score = distance / số xe + overtime × 10000 / 3600` cho tất cả 120 lượt; và xác nhận đủ 5 lượt cho từng instance 17–40. Score của cùng instance giống nhau qua 5 version. Trị số evaluator log làm tròn 3 chữ số sau dấu phẩy; score lấy từ dòng main có độ chính xác cao hơn.

Runtime là thời gian thực trên Kaggle cho từng instance, bao gồm hoạt động mô phỏng và gọi thuật toán; không phải tổng thời gian toàn bộ notebook hay thời gian thuật toán riêng. Timestamp log được hiểu là UTC theo môi trường Kaggle. Trung bình runtime của 24 giá trị trung bình theo instance là khoảng 273,737 giây; tốc độ có thể khác giữa phiên và máy.

Score được báo cáo là simulator đã tính sau khi hoàn thành instance, không phải chứng nhận độc lập rằng tất cả ràng buộc hoặc nghiệm đã được tái kiểm toán từ toàn bộ lịch sử. Seed và phiên bản Git thực tế chưa được xác minh cho từng run; không giả định từ source notebook, vì notebook clone nhánh Git tại thời điểm chạy.
