# New_DPDP: Real-Time Dynamic Pickup and Delivery Problem Solver

## 🎯 Đề Xuất Chính: AGVNS

Repository này chứa **thuật toán chính nghiên cứu (AGVNS)** và các **triển khai baseline so sánh** để giải quyết bài toán **Dynamic Pickup and Delivery Problem (DPDP)** trong cuộc thi **Intelligent Logistics Scheduling Competition** trên Huawei Cloud.

- **🏆 Thuật Toán Chính**: **AGVNS** (Adaptive Genetic Algorithm Enhanced by Variable Neighborhood Search) - Đề xuất mới
- **📊 Baseline So Sánh**: Memetic Algorithm (MA), Gold Algorithm (Top-1 cuộc thi), Silver Algorithm (Top-2 cuộc thi), Bronze Algorithm (Top-3 cuộc thi)
- **📚 Chi Tiết**: Paper đầy đủ, code nguồn mở, data benchmark Huawei Cloud

**Liên kết cuộc thi:** https://competition.huaweicloud.com/information/1000041411/circumstance

## Các Thuật Toán Triển Khai

### 🥇 THUẬT TOÁN CHÍNH: AGVNS

| Thư mục | Tên Đầy Đủ | Đặc Trưng |
|---------|-----------|----------|
| `AGVNS/` | **Adaptive Genetic Algorithm Enhanced by Variable Neighborhood Search** | **ĐỀ XUẤT CHÍNH CỦA NGHIÊN CỨU**<br/><br/>🔑 **Đặc điểm**:<br/>• Genetic Algorithm với cơ chế thích nghi: population size, mutation rate, crossover rate thay đổi theo thời gian<br/>• Variable Neighborhood Search (VNS) làm local search để tăng chất lượng giải<br/>• Tối ưu hóa riêng cho môi trường dynamic/real-time<br/>• Khả năng phản ứng nhanh với các yêu cầu mới<br/><br/>📄 **Paper**: Xem file PDF trong repo<br/>

### 📈 BASELINE SO SÁNH

| Thư mục | Tên | Loại | Mô Tả | 
|---------|-----|------|-------|
| `MA/` | **Memetic Algorithm (MA)** | Hybrid Metaheuristic từ Literature | Memetic algorithm (https://doi.org/10.1007/s12293-024-00407-5). Được triển khai để so sánh với AGVNS trên cùng benchmark. | 
| `1/` | **Gold Algorithm** | Top-1 Cuộc Thi Huawei | Thuật toán đạt huy chương vàng trong cuộc thi Intelligent Logistics Scheduling. Được triển khai lại để so sánh . | 
| `2/` | **Silver Algorithm** | Top-2 Cuộc Thi Huawei | Thuật toán đạt huy chương bạc trong cuộc thi. Được triển khai để benchmark kết quả AGVNS. | 

## Cấu Trúc Repository

```
New_DPDP/
├── AGVNS/                  # Thuật toán chính: Adaptive GA + VNS
│   ├── main.py             # Entry point
│   ├── algorithm/          # Logic thuật toán
│   ├── benchmark/          # 64 benchmark instances
│   └── requirements.txt
│
├── MA/                     # Baseline: Memetic Algorithm
│   ├── main.py
│   ├── algorithm/
│   └── requirements.txt
│
├── 1/                      # Baseline: Gold Algorithm (Top-1 cuộc thi)
├── 2/                      # Baseline: Silver Algorithm (Top-2 cuộc thi)
│
├── README.md               # File này
├── simulation.md           # Hướng dẫn chi tiết chạy simulation
└── Paper PDF               # Chi tiết AGVNS algorithm & kết quả
```


## Cách Sử Dụng

### 1. Clone Repository

```bash
git clone https://github.com/tranphuc15122004/New_DPDP.git
cd New_DPDP
```

### 2. Cài Đặt Môi Trường

Môi trường sử dụng **Python 3.12**

```bash
# Tạo virtual environment (tùy chọn nhưng khuyến cáo)
python -m venv .venv

# Kích hoạt (Windows)
.\.venv\Scripts\Activate.ps1

# Kích hoạt (Linux/macOS)
source .venv/bin/activate
```

### 3. Cài Đặt Dependencies

Chọn thuật toán muốn chạy:

**Chạy AGVNS:**
```bash
pip install -r AGVNS/requirements.txt
```

**Chạy Memetic Algorithm:**
```bash
pip install -r MA/requirements.txt
```

**Chạy Gold/Silver Algorithms:**
- `1/`: Cần Java JDK 8+ (vì có file `.class`)
- `2/`: Tương tự

### 4. Chạy Simulation

**AGVNS:**
```bash
cd AGVNS
python main.py
```

**Memetic Algorithm:**
```bash
cd MA
python main.py
```

Simulator sẽ:
1. Tải dữ liệu instance từ `benchmark/`
2. Khởi động mô phỏng môi trường dynamic (10 phút/vòng)
3. Gọi thuật toán (thời gian tối đa 10 phút/vòng)
4. Đánh giá kết quả và in ra metrics

### 5. Hiểu Chi Tiết Hơn

Xem **`simulation.md`** (tiếng Anh) hoặc **`simulation_vi.md`** (tiếng Việt) để hiểu:
- Input JSON format (`vehicle_info.json`, `unallocated_order_items.json`)
- Output JSON format (`output_destination.json`, `output_route.json`)
- Các constraints và rules quan trọng
- Cách debug/test thuật toán của bạn

## Kết Quả Dự Kiến

Repository đã được kiểm thử trên:
- **64 benchmark instances** từ Huawei Cloud
- **Quy mô**: 50 đến 4000 yêu cầu mỗi instance
- **Chỉ số đánh giá**:
  - Số yêu cầu được phục vụ (Served Requests %)
  - Tổng quãng đường (Total Distance)
  - Thời gian chờ trung bình (Average Waiting Time)
  - Mức độ tuân thủ time windows (Time Window Violation Rate)

**Kết quả từ paper**: AGVNS vượt trội hơn baselines trên hầu hết instances, đặc biệt trong các instance lớn (>1000 yêu cầu).


### Benchmark Datasets

- 64 instances với quy mô tăng dần (50, 100, 300, 500, 1000, 2000, 3000, 4000 yêu cầu)
- File: `benchmark/factory_info.csv`, `benchmark/route_info.csv`
- Ma trận khoảng cách/thời gian giữa các nhà máy được cập nhật dựa trên dữ liệu cuộc thi



## Liên Hệ & Đóng Góp

- **Tác giả**: tranphuc15122004
- **GitHub**: https://github.com/tranphuc15122004/New_DPDP
- **Vấn đề / Đề xuất**: Hãy mở issue trên GitHub
- **Đóng góp**: Pull requests được hoan nghênh!

---

**Cập nhật lần cuối**: December 2025
