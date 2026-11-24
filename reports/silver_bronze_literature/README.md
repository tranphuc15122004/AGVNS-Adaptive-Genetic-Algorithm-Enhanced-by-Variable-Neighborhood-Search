# Kết quả đã công bố: Silver và Bronze

## Dữ liệu

`results_64_instances.csv` có 128 dòng: mỗi instance từ 1 đến 64 cho từng thuật toán. Các cột score được chép từ Bảng 3 của Horváth và Kis, “On recent computational results for a dynamic pickup and delivery problem”, *Memetic Computing* 17, 27 (2025), https://doi.org/10.1007/s12293-025-00462-6. Bài báo phát hành theo CC BY 4.0. Bảng nằm ở trang 4–5 bản PDF: https://real.mtak.hu/223164/1/03_horvath2025recent_offprint.pdf.

- `score_original_ports`: score công bố khi dùng dữ liệu gốc, có 6 cổng tại mỗi nhà máy.
- `score_100_ports`: score công bố khi tăng số cổng lên 100; đây là bài toán đã nới lỏng ràng buộc cổng. Giữ riêng để tránh trộn với kết quả dữ liệu gốc.
- `simulator_modified_for_score=yes`: bài báo gắn dấu sao; riêng Silver instance 9, 10, 12, 13, 14, 15, 16 được chạy sau khi bỏ kiểm tra kết thúc simulator khi đơn quá hạn chưa phân công. Các score này không phải kết quả chạy thành công bằng simulator nguyên bản. `not_marked` nghĩa là ô trong bài không có dấu sao, không khẳng định mọi chi tiết môi trường giống repo này.
- Các score được giữ nguyên hai chữ số thập phân như công bố. Không suy diễn cost quãng đường hay cost trễ từ tổng score.
- `runtime_seconds_v5_kaggle` và `runtime_mean_seconds_5_kaggle`: thời gian thực từng instance từ log 5 version notebook `trnphc15122004/silver`, chỉ có với Silver instance 1–8. Đây là những lượt chạy riêng của chúng ta, không phải runtime của bài báo Horváth–Kis. Dữ liệu từng lượt: `../kaggle_silver_audit/results_instances_1_8_all_versions.csv`.
- `zhou_figure5_chart_estimate`, `zhou_figure5_lower_2px`, `zhou_figure5_upper_2px`: giá trị thời gian ước lượng từ Hình 5 của Zhou cho cả Silver và Bronze, cùng độ nhạy theo sai số đọc ±2 pixel. Đơn vị giây là giả định vì trục hình không ghi đơn vị. `zhou_silver_assumed_raw_seconds` là giá trị Silver nhân 29.5, với giả định chưa được xác nhận rằng tác giả đã chia runtime gốc cho 29.5. Xem `ZHOU_FIGURE5.md` để biết phương pháp và giới hạn.
- Ô runtime trống nghĩa là chưa tìm thấy số đo đủ tin cậy, không phải 0. Bảng 3 không công bố runtime. Với 8 instance đầu, score Silver công bố khớp 5 lượt Kaggle khi làm tròn hai chữ số.

Runtime hiện có: Silver 8/64 instance, mỗi instance 5 phép đo Kaggle; Bronze 0/64 instance được xác minh trong nguồn này hoặc inventory nội bộ đã kiểm tra. Thời gian chạy phụ thuộc máy, môi trường và định nghĩa đo, vì vậy không gộp score công bố và runtime Kaggle thành một lượt chạy duy nhất.

## Nguồn runtime khác đã kiểm tra

Zhou và cộng sự, “A memetic algorithm for a real-world dynamic pickup and delivery problem”, https://doi.org/10.1007/s12293-024-00407-5, Hình 5 trình bày thời gian bằng đồ thị, nhưng phần 4.4 cho biết thời gian Python và Java được điều chỉnh bằng hệ số ngôn ngữ. Không có bảng số runtime gốc theo instance có thể xác minh trực tiếp trong nội dung bài được kiểm tra. Không coi giá trị đọc ước lượng từ đồ thị đã điều chỉnh là runtime thực đo.

Horváth–Kis cho rằng kết quả Zhou tương ứng trường hợp số cổng không giới hạn, dựa trên đối chiếu thực nghiệm; vì vậy cần so sánh điều kiện thử trước khi dùng các số đó cho benchmark gốc. Nguồn chính và nhận định này có thể kiểm tra trong mục 4 của bài Horváth–Kis.

## Kiểm tra

CSV đã được đối chiếu 64 số thứ tự liên tiếp, 128 dòng và 7 dấu sao Silver theo Bảng 3. Chưa có dữ liệu nguồn xác minh để điền runtime Bronze hoặc runtime Silver instance 9–64.
