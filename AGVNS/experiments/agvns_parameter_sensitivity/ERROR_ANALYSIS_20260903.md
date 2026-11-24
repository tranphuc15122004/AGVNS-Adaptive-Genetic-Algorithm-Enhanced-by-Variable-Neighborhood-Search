# Phân tích các instance lỗi của batch sensitivity 20260903_141120

> Historical batch evidence, recorded against the code used at that time. Current repair status and replay verification are in [FAILURE_REPAIR_FOLLOWUP_20260929.md](FAILURE_REPAIR_FOLLOWUP_20260929.md).


Nguồn: `runs/20260903_141120/results.jsonl` (480 khóa job duy nhất) và log riêng của từng job. Bảng chi tiết 41 job có vấn đề nằm trong `ERROR_JOBS_20260903.csv`. Mỗi instance có 10 cấu hình × 3 lần lặp = 30 job. Không có job đang chạy trong batch này.

## Thống kê theo instance

| Instance | Set | Hợp lệ | `FAILED` (`IndexError`) | `SUCCESS` nhưng score sentinel | Tổng có vấn đề | Tỷ lệ có vấn đề |
|---:|---:|---:|---:|---:|---:|---:|
| 49 | 7 | 28 | 2 | 0 | 2/30 | 6,67% |
| 50 | 7 | 29 | 1 | 0 | 1/30 | 3,33% |
| 57 | 8 | 1 | 9 | 20 | 29/30 | 96,67% |
| 58 | 8 | 21 | 7 | 2 | 9/30 | 30,00% |
| **Cộng** | | **79** | **19** | **22** | **41/120** | **34,17%** |

Các instance còn lại (1, 2, 9, 10, 17, 18, 25, 26, 33, 34, 41, 42) đều có đủ 30/30 job hợp lệ. Toàn batch có 439 job hợp lệ, 19 job `FAILED`, 22 job score sentinel.

## Job cụ thể

`C` là configuration ID, `R` là repetition. Chi tiết từng job, gồm đường dẫn log và thông báo checker, nằm trong CSV đi kèm.

| Instance | `FAILED` do `IndexError` | Score sentinel do dispatch không khả thi |
|---:|---|---|
| 49 | C1/R2, C2/R3 | — |
| 50 | C3/R3 | — |
| 57 | C1/R2, C2/R1, C3/R3, C4/R1, C4/R2, C5/R1, C6/R1, C9/R3, C10/R1 | C1/R1, C1/R3, C2/R2, C2/R3, C3/R1, C3/R2, C4/R3, C5/R2, C5/R3, C6/R2, C6/R3, C7/R1, C7/R2, C7/R3, C8/R1, C8/R2, C8/R3, C9/R2, C10/R2, C10/R3 |
| 58 | C6/R2, C7/R3, C8/R1, C8/R3, C10/R1, C10/R2, C10/R3 | C1/R2, C4/R2 |

## Vì sao lỗi

### 1. `IndexError` làm 19 job dừng hẳn

Trong `GAVND7.py`, sau khi loại cá thể trùng, mã lọc tiếp cá thể có `fitness < best_solution.fitness + addDelta` (`addDelta = 400000`). Log của **cả 19 job** đều in ra số cá thể trước lọc là 20, 40 hoặc 60 và sau lọc là **0**. Mã sau đó truy cập `unique_population[0]`, gây `IndexError: list index out of range`. `main_algorithm.py` in `FAIL`, nên simulator không nhận được marker `SUCCESS` và runner ghi trạng thái `FAILED`.

Điều kiện lọc rỗng có thể xảy ra vì quần thể được đột biến trực tiếp, còn `best_solution` được giữ riêng. Trong lần gọi thuật toán cuối của từng job lỗi, fitness tốt nhất của thế hệ cuối cao hơn mức tốt nhất từng ghi trong lần gọi đó **ít nhất 400000**; log phù hợp với việc toàn bộ quần thể vượt ngưỡng lọc. Đây là cơ chế trực tiếp đã kiểm chứng từ mã và log. Nguyên nhân sâu hơn khiến fitness tăng trong từng lần chạy cần truy vết các toán tử để kết luận.

### 2. Dispatch không khả thi tạo 22 score sentinel

Cả 22 job này chạy xong với marker `SUCCESS`, nhưng checker của simulator từ chối kế hoạch xuất ra rồi `run()` trả về sớm. `total_score` giữ giá trị khởi tạo `sys.maxsize = 9223372036854775807`; runner chỉ kiểm tra score hữu hạn nên đánh dấu nhầm là thành công.

| Quy tắc checker bị vi phạm | Số job | Instance |
|---|---:|---|
| Đích trả về của xe đang chạy khác đích gốc | 21 | 57: 19, 58: 2 |
| Vượt sức chứa: xe V_28 còn tải 16 khi sức chứa là 15 | 1 | 57: C7/R3 |

Kiểm tra JSON chi tiết của 57–58 cho thấy **cả 22 job** cùng có một delivery cũ bị giữ lại ở đầu route sau khi pickup tương ứng bị bỏ trong `restore_scene_with_single_node()`. Xe đã ở nhà máy giao đó và có `carrying_items=[]`. Với 21 job, `get_output_solution()` lấy delivery cũ làm destination sai; với job 57 C7/R3, nó xuất lệnh giao một item khi xe rỗng và checker báo vượt capacity. Xem [`DEEP_DIVE_57_58_20260903.md`](DEEP_DIVE_57_58_20260903.md) để biết chuỗi dữ liệu và kế hoạch chạy lại.

## Giới hạn khi diễn giải sensitivity

`algorithm/main.py` hiện gọi `GAVND_7(...)` rồi ngay sau đó **ghi đè** `best_chromosome` bằng `Chromosome` tạo từ kế hoạch cheapest insertion. Kế hoạch được xuất ra không phải nghiệm do GA tối ưu. Vì vậy chênh lệch score trong batch này không thể diễn giải là hiệu quả chất lượng của bốn tham số GA; các tham số vẫn có thể ảnh hưởng thời gian chạy và khả năng lỗi. Kết luận xếp hạng chất lượng cấu hình trong báo cáo tổng hợp trước cần được rút lại cho đến khi luồng xuất nghiệm được sửa và thí nghiệm được chạy lại.
