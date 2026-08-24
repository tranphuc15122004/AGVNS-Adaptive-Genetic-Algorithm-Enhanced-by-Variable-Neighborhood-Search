# Kế hoạch tổng hợp kết quả EvoRL

## Mục tiêu

Xác định batch 4 repetition hiện tại và một lần chạy trước đó, tổng hợp 5 lần chạy thành dữ liệu có thể kiểm tra, tạo file tổng hợp và báo cáo tiếng Việt.

## Các phase

- [completed] 1. Khảo sát các nguồn kết quả và xác định đúng 5 lần chạy
- [completed] 2. Kiểm tra tính đầy đủ/hợp lệ và thống nhất schema
- [completed] 3. Tính thống kê tổng hợp theo lần chạy, instance và nhóm kích thước
- [completed] 4. Tạo file tổng hợp và báo cáo
- [completed] 5. Kiểm tra đầu ra và bàn giao

## Quyết định cần giữ

- Batch hiện tại đã biết từ lượt trước: `20260819_094955`, gồm 4 repetition × 64 instance = 256 job.
- Không được gộp một run cũ nếu chưa xác định rõ run đó là lần thực hiện trước người dùng muốn so sánh.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| `SyntaxError: unterminated string literal` tại header bảng Markdown | 1 | Tách chuỗi header và separator thành hai phần tử Python hợp lệ |

## Verification

- Generator chạy lại thành công.
- Nguồn: 320 dòng, đều `SUCCESS`.
- Output aggregate: 64 dòng, instance 1–64.
- Đã kiểm tra lại 128 công thức mean (current4 và combined5) so với nguồn.
- Báo cáo chứa đủ các phần kết luận, bảng nhóm và phương pháp.
