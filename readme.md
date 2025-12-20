# New_DPDP

Repository chứa nhiều triển khai và dữ liệu cho các giải pháp tối ưu hóa điều phối phương tiện (DPDP).

**Tổng quan**
- **Mục tiêu:** mã nguồn và dữ liệu thử nghiệm cho các thuật toán tối ưu hóa, dùng để đánh giá trên Huawei benchmark được nêu trong bài báo đính kèm.
- **Thuật toán:** thư mục chứa 4 thuật toán khác nhau đã được triển khai để so sánh/đánh giá trên bộ dữ liệu Huawei benchmark.
- **Ngôn ngữ chính:** Python (có thư mục chứa mã Java/compiled trong `1/`).

**Cấu trúc thư mục chính**
- **`AGVNS/`**: Triển khai Python của các thuật toán (AGVNS). Chứa mã nguồn, benchmark (dữ liệu instance), và file `requirements.txt`.
- **`MA/`**: Thư mục cho một biến thể/thuật toán khác (MA). Có các script `main.py` và `main_algorithm.py` cùng `benchmark/`.
- **`1/`**: Phiên bản gốc + mã đã biên dịch (Java `.class`) và mã nguồn Java trong `source-code/`.

**Tệp quan trọng / điểm vào**
- [AGVNS/main.py](AGVNS/main.py): script khởi chạy cho module AGVNS.
- [AGVNS/main_algorithm.py](AGVNS/main_algorithm.py): script thuật toán chính trong AGVNS.
- [AGVNS/algorithm/main.py](AGVNS/algorithm/main.py): entrypoint cho các thuật toán bên trong.
- [MA/main.py](MA/main.py) và [MA/main_algorithm.py](MA/main_algorithm.py): điểm vào cho module MA.

**Thuật toán triển khai**
- Thư mục chứa 4 thuật toán triển khai để đánh giá cho bài toán Huawei benchmark. Các mã nguồn thuật toán chính nằm trong `AGVNS/algorithm/` và `MA/algorithm/` (kiểm tra các file `main.py` tương ứng để xem điểm vào và cấu hình chạy từng thuật toán).

**Paper & tài liệu**
- Chi tiết phương pháp, thiết kế thí nghiệm và kết quả được mô tả trong file PDF của bài báo đi kèm trong repository; hãy mở file PDF đó để xem mô tả chi tiết (paper và các phụ lục nếu có).

**Cài đặt (Windows)**
1. Tạo môi trường ảo và kích hoạt (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Cài đặt dependencies cho module bạn muốn chạy, ví dụ AGVNS:

```powershell
pip install -r AGVNS\requirements.txt
```

Hoặc cho MA:

```powershell
pip install -r MA\requirements.txt
```

**Chạy nhanh**
- Chạy AGVNS:

```powershell
python AGVNS\main.py
```

- Chạy MA:

```powershell
python MA\main.py
```

Lưu ý: một số script có thể yêu cầu tham số hoặc file cấu hình riêng trong `src/conf` hoặc `benchmark/` — kiểm tra các file `readme.md` riêng của từng thư mục benchmark.

**Dữ liệu thử nghiệm (benchmark)**
- Các folder `AGVNS/benchmark/` và `MA/benchmark/` chứa tập instance (CSV) và file `factory_info.csv`, `route_info.csv` dùng làm input.

**Ghi chú phát triển**
- Nếu bạn cần chạy bằng Java, mã nguồn gốc nằm trong `1/source-code/` và có các lớp `.class` trong `1/compiled_files/`.
- Có nhiều file hỗ trợ (simpy, utils, simulator) đã được đóng gói bên trong các thư mục tương ứng; kiểm tra `src/` trong mỗi module.

**Tác giả / Liên hệ**
- Repository: tranphuc15122004/New_DPDP

Nếu bạn muốn, tôi có thể: cập nhật README chi tiết hơn (hướng dẫn tham số, ví dụ đầu ra), hoặc thêm hướng dẫn chạy từng experiment cụ thể.
