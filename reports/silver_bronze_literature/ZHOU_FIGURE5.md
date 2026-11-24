# Ước lượng thời gian từ Hình 5 của Zhou et al. (2024)

Nguồn: Zhou et al., *A memetic algorithm for a real-world dynamic pickup and delivery problem*, Hình 5 trang 216 (trang PDF 14), https://doi.org/10.1007/s12293-024-00407-5; bản trong workspace: `MA/memetic-DPDP.pdf`. Bài báo open access CC BY 4.0.

`zhou2024_figure5_digitized_estimates.csv` gồm 128 dòng: Silver (IM, xanh lam) và Bronze (LS, xanh lá), mỗi thuật toán 64 instance. Giá trị được số hóa từ đỉnh cột của hình, không phải dữ liệu số gốc của tác giả. Mỗi set có 8 instance; `instance = (set - 1) × 8 + vị trí trong set`. Trục đứng thang log10: 10^0–10^5 cho set 1–7, 10^0–10^6 cho set 8. PDF được raster hóa ở 180 dpi; đỉnh cột được nhận diện từ màu tô và nội suy log theo mép trục.

- `chart_estimate`: giá trị xấp xỉ hiển thị trong hình; `chart_lower_pixel_2`, `chart_upper_pixel_2` là độ nhạy khi vị trí đỉnh sai ±2 pixel, không phải khoảng tin cậy thống kê hay tổng sai số.
- `raw_time_if_divided_by_29_5`: giá trị Silver nhân 29.5, chỉ đúng theo **giả định** tác giả chia thời gian Python ban đầu cho 29.5 để tạo đồ thị. Phần 4.4 nói đã hiệu chỉnh theo hệ số 29.50, nhưng không ghi rõ phép tính hay công bố thời gian gốc, do đó phép nhân ngược chưa được xác nhận. Hai cột lower/upper là độ nhạy pixel tương ứng, cũng theo giả định này.
- Bronze viết bằng C++, bài báo chỉ nêu hiệu chỉnh VNSME và IM; `chart_estimate` là ước lượng giá trị thể hiện cho Bronze. Không suy diễn điều chỉnh khác.
- Chú thích hình nói tổng thời gian chạy nhưng trục lại ghi `Objective Value` và không ghi đơn vị; phần văn bản lân cận thảo luận thời gian tính bằng giây. Do nhãn hình không nhất quán, đơn vị của từng cột được xem là **giả định giây**, chưa xác nhận độc lập.
- Không coi giá trị số hóa là thời gian đã đo trên máy hiện tại. Không ước tính độ bất định do khác phần cứng, runtime, cách đo và môi trường. Bài báo dùng Intel Xeon Platinum 8269CY 2.5 GHz và RAM 16 GB. Horváth–Kis (2025), https://doi.org/10.1007/s12293-025-00462-6, báo cáo kết quả của Zhou tương ứng điều kiện số cổng được nới lỏng, ảnh hưởng khả năng so sánh.

Kiểm tra hợp lý, không phải xác thực: Silver instance 1 từ hình khoảng 9.77 đơn vị, nhân 29.5 ≈ 288 giây; lượt Kaggle version 5 đo 303.22 giây. Hai con số gần nhau không chứng minh chiều hiệu chỉnh hay tính tương đương thí nghiệm.

## Tái lập

Từ thư mục gốc repository:

```bash
pdftoppm -f 14 -l 14 -png -r 180 -singlefile MA/memetic-DPDP.pdf /tmp/zhou_page14
python reports/silver_bronze_literature/digitize_zhou_figure5.py
```

Script cần Pillow, NumPy và SciPy. Nó kiểm tra đúng 8 cột mỗi màu trong từng set trước khi ghi 128 dòng. Giá trị có thể khác nếu rasterizer render màu khác; tọa độ và màu được hiệu chỉnh theo PDF và lệnh nêu trên.
