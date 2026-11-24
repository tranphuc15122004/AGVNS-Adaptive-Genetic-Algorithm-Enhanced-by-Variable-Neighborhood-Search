# Kiểm tra Kaggle notebook `trnphc15122004/silver`

Ngày kiểm tra: 2026-11-15 UTC. Đã đọc trạng thái, source và session log của toàn bộ **5 saved version**, đồng thời tải output liên quan của version 5. Chỉ thực hiện chẩn đoán; không sửa hay chạy lại notebook trên Kaggle.

## Kết luận

Cả 5 version đều kết thúc do lỗi điều phối tại **instance 9**, sau khi hoàn thành instance 1–8. Instance 10–32 chưa được chạy trong các phiên này. Đây là tiến trình simulator đã thoát, không còn là phiên đang tạm dừng chờ tiếp tục.

Kaggle báo `COMPLETE` cho cả 5 version, nhưng log của cả 5 đều có cùng lỗi:

```text
Item 2323390097-1's committed_completion_time is 2026-11-15 03:23:39
which has timed out, however it is still ignored in the dispatch result.
Simulator terminated
```

Tại thời gian mô phỏng **2026-11-15 03:30:00**, đơn này vẫn không có trong kế hoạch xe, đã quá hạn **6 phút 21 giây**. Log chỉ ra simulator tự kết thúc theo kiểm tra đơn quá hạn chưa được phân công; không có bằng chứng phiên kết thúc do giới hạn runtime, thiếu RAM hay mất kết nối Kaggle.

## Đối chiếu saved version

| Version | Kaggle | Instance hoàn thành | Instance lỗi | Thời điểm lỗi thực tế (UTC, 2026-11-14) | Thời lượng session đến hết log |
|---|---|---|---|---|---|
| 1 | COMPLETE | 1–8 | 9 | 20:45:33.836 | 52 phút 07.6 giây |
| 2 | COMPLETE | 1–8 | 9 | 20:44:06.763 | 50 phút 38.7 giây |
| 3 | COMPLETE | 1–8 | 9 | 20:41:58.564 | 48 phút 25.0 giây |
| 4 | COMPLETE | 1–8 | 9 | 20:44:12.117 | 50 phút 34.2 giây |
| 5 | COMPLETE | 1–8 | 9 | 20:40:55.046 | 47 phút 12.6 giây |

Thời lượng session bao gồm khởi tạo, clone, cài đặt và xuất notebook; không phải runtime riêng của instance 9. Cả 5 source notebook giống nhau khi so sánh nội dung các cell, cùng gọi:

```python
! python main.py --instances $(seq -s, 1 32)
```

Notebook chạy baseline **Top-2**, tại `2/Y_final_submission`, không chạy thuật toán AGVNS. Score của instance 1–8 giống nhau giữa cả 5 version. Lưu hoặc chạy lại cùng cấu hình đã lặp lại cùng lỗi.

## Nguyên nhân trực tiếp trong thuật toán

Source tải từ output Kaggle trùng byte với source hiện có trong repository đối với `main.py`, `algorithm/algorithm_demo.py` và `src/simulator/simulate_environment.py`.

Trong `algorithm/algorithm_demo.py:698`, `new_dispatch()` loại xe khỏi danh sách nhận đơn nếu xe có destination, hoặc `leave_time_at_current_factory != gps_update_time`. Ở snapshot cuối, thời gian hiện tại là 03:30:00:

| Xe | Có destination | Thời gian còn lại trước khi rời xưởng | Hàng đang chở | Kết quả bộ lọc |
|---|---|---|---|---|
| V_1 | Không | 504 giây | Không | Loại |
| V_2 | Không | 312 giây | Không | Loại |
| V_3 | Không | 60 giây | Không | Loại |
| V_4 | Không | 996 giây | Không | Loại |
| V_5 | Có | 96 giây | 1 item | Loại |

Vì không còn xe khả dụng và không có xe được ghép trước cho hai đơn cuối, nhánh phân công không chạy. Output vẫn để V_1–V_4 có destination `null`, tất cả planned route rỗng; V_5 chỉ giữ chuyến giao item đang chở `2321040096-1`.

Hai item còn lại `2323390097-1` và `2326550098-1` vẫn nằm trong `unallocated_order_items.json`, không xuất hiện trong output. Bộ kiểm tra simulator phát hiện item thứ nhất đã quá hạn và gọi `sys.exit(-1)` tại `simulate_environment.py:130`.

Đã phát lại trực tiếp `new_dispatch()` trên snapshot tải từ Kaggle: tái hiện `No available vehicle`, tái hiện hai item chưa được phân công, và xác nhận destination cùng planned route khớp output đã lưu. Kết quả tại `replay_result.json`; script tại `replay_terminal_snapshot.py`.

Snapshot này chứng minh cơ chế bỏ phân công tại vòng cuối. Chưa tải lịch sử input/output của từng vòng trước, nên chưa xác định vòng sớm nhất mà một chính sách khác có thể nhận hai đơn này.

## Vì sao Kaggle và runtime report vẫn báo thành công

1. Cell dùng cú pháp shell `! python ...`. IPython không tự chuyển mã thoát khác 0 của lệnh shell thành exception của cell; notebook tiếp tục xuất kết quả, nên Kaggle ghi `COMPLETE`.
2. `sys.exit(-1)` tạo `SystemExit`, không thuộc `Exception`. Vì vậy `except Exception` trong `main.py:91` không ghi nhận instance 9 thất bại, cũng không tiếp tục instance 10.
3. `runtime_stats.json` mới nhất chỉ có **8 instance**, `failed_instances: 0`, `status: SUCCESS`, được ghi lần cuối lúc **20:35:23 UTC**, trước lỗi instance 9 lúc **20:40:55 UTC**. Báo cáo đó mô tả 8 instance đã ghi, không xác nhận hoàn thành batch 32 instance.

## Hướng xử lý

- Với notebook: gọi bằng `subprocess.run([...], check=True)` để mã thoát lỗi làm saved run báo thất bại đúng trạng thái.
- Với batch runner: xử lý `SystemExit` từ simulator tại ranh giới từng instance, ghi trạng thái FAILED và bảo đảm báo cáo cuối thể hiện instance chưa chạy. Có thể cho các instance còn lại tiếp tục nếu đó là chính sách mong muốn.
- Với Top-2: đánh giá lại chính sách chờ ghép đơn và khả năng lập kế hoạch cho xe đang hoàn tất phục vụ. Cần có cơ chế ưu tiên đơn sắp quá hạn; sửa bộ báo lỗi đơn thuần không giải quyết việc hai đơn bị bỏ phân công. Việc sửa thuật toán baseline cần ghi nhận rõ khi so sánh kết quả benchmark.

Không bỏ kiểm tra đơn quá hạn của simulator để làm batch trông như thành công. Chưa triển khai các thay đổi này trong lần chẩn đoán.

## Bằng chứng đã lưu

- `discovery.json`: thời điểm kiểm tra, số version và trạng thái mới nhất.
- `version_summary.csv`, `version_summary.json`: kết quả đối chiếu từng version.
- `versions/v01` đến `versions/v05`: source notebook, session log gốc JSON và log đã giải mã.
- `latest_output/`: source, runtime report, application log instance 9 và input/output cuối của version 5.
- `output_catalog_prefix.json`: danh mục 4.400 output đầu tiên, đã duyệt hết thư mục Top-2; không phải danh mục toàn bộ output của repository.
- `replay_terminal_snapshot.py`, `replay_result.json`: phát lại vòng cuối chỉ đọc dữ liệu, không ghi đè output thuật toán.
