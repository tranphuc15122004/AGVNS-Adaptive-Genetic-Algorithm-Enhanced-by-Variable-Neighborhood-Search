# AGVNS: Real-Time Dynamic Pickup and Delivery Problem Solver

## 🎯 Đề Xuất Chính: AGVNS

Repository này chứa **thuật toán chính nghiên cứu (AGVNS)** và các **triển khai baseline so sánh** để giải quyết bài toán **Dynamic Pickup and Delivery Problem (DPDP)** trong cuộc thi **Intelligent Logistics Scheduling Competition** trên Huawei Cloud.

- **🏆 Thuật Toán Chính**: **AGVNS** (Adaptive Genetic Algorithm Enhanced by Variable Neighborhood Search) — Đề xuất mới
- **📊 Baseline So Sánh**: Memetic Algorithm (MA), Gold Algorithm (Top-1 cuộc thi), Silver Algorithm (Top-2 cuộc thi), Bronze Algorithm (Quickest Route, Top-3 cuộc thi)
- **📚 Chi Tiết**: Paper đầy đủ, code nguồn mở, data benchmark 64 instances từ Huawei Cloud

**Liên kết cuộc thi:** <https://competition.huaweicloud.com/information/1000041411/circumstance>

---

## Các Thuật Toán Triển Khai

| Thư mục | Tên | Loại | Ngôn ngữ | Đặc trưng |
|---------|-----|------|----------|-----------|
| `AGVNS/` | **Adaptive Genetic Algorithm + VNS** | 🥇 **Chính (Đề xuất)** | Python | GA thích nghi (population, mutation, crossover rate thay đổi động) + VNS local search |
| `MA/` | **Memetic Algorithm** | 📊 Baseline (Literature) | Python | Memetic algorithm từ literature (doi: 10.1007/s12293-024-00407-5) |
| `1/compiled_files/` | **Gold Algorithm** | 🥇 Baseline (Top-1 Huawei) | **Java** | VNS thuần, thuật toán vô địch cuộc thi |
| `2/Y_final_submission/` | **Silver Algorithm** | 🥈 Baseline (Top-2 Huawei) | Python | Dispatch heuristic, thuật toán á quân cuộc thi |
| `3/` | **Bronze Algorithm (Quickest Route)** | 🥉 Baseline (Top-3 Huawei) | **C++** | Greedy + Local Search, thuật toán hạng 3 cuộc thi |

---

## Cấu Trúc Repository

```
New_DPDP/
├── AGVNS/                          # Thuật toán chính: Adaptive GA + VNS
│   ├── main.py                     # Simulator entry point
│   ├── main_algorithm.py           # Algorithm entry point (gọi từ simulator)
│   ├── algorithm/
│   │   ├── main.py                 # Core orchestrator
│   │   ├── In_and_Out.py           # I/O (JSON, CSV)
│   │   ├── engine.py               # GA engine (crossover, mutation, selection)
│   │   ├── local_search.py         # Local search operators
│   │   ├── algorithm_config.py     # Parameters (pop_size, gen, time_limit, ...)
│   │   ├── Test_algorithm/
│   │   │   ├── GAVND7.py           # GAVND_7 — best GA variant (được dùng)
│   │   │   ├── new_engine.py       # New GA engine (adaptive, diversity)
│   │   │   ├── new_LS.py           # New local search operators
│   │   │   └── adaptive_ratio.py   # Adaptive crossover ratio (erfc, KWW)
│   │   └── Object/                 # Data models (Chromosome, Node, Vehicle...)
│   ├── src/                        # Simulator source
│   │   ├── conf/configs.py         # Simulator config
│   │   └── simulator/
│   └── benchmark/                  # 64 benchmark instances + factory/route CSVs
│
├── MA/                             # Baseline: Memetic Algorithm
│   ├── main.py                     # Simulator entry point
│   ├── main_algorithm.py           # Algorithm entry point
│   ├── algorithm/
│   │   ├── main.py                 # Core orchestrator (gọi Memetic_algorithm)
│   │   ├── Test_algorithm/
│   │   │   ├── MA.py               # Memetic_algorithm implementation
│   │   │   └── MA_engine.py        # MA-specific fitness engine
│   │   └── ... (shared structure với AGVNS)
│   └── benchmark/
│
├── 1/
│   ├── compiled_files/             # Gold Algorithm (Java .class)
│   │   ├── main.py                 # Simulator entry point
│   │   ├── main_algorithm.class    # Java algorithm (compiled)
│   │   ├── algorithm/              # Dependencies (Apache POI, JSON libs)
│   │   └── benchmark/
│   └── source-code/                # Java source code
│       └── src/main_algorithm.java
│
├── 2/Y_final_submission/           # Silver Algorithm (Python)
│   ├── main.py                     # Simulator entry point
│   ├── main_algorithm.py           # Algorithm entry point
│   ├── algorithm/
│   │   └── algorithm_demo.py       # Scheduling heuristic
│   └── benchmark/
│
├── 3/                              # Bronze Algorithm — Quickest Route (C++)
│   ├── main.py                     # Simulator entry point
│   ├── main_algorithm.py           # Algorithm entry point (gọi binary)
│   ├── main_algorithm.exe          # Compiled Windows binary (C++)
│   ├── main_algorithm.out          # Compiled Linux binary (C++)
│   ├── algorithm/
│   │   ├── __init__.py
│   │   ├── algorithm_demo.py       # Python wrapper gọi C++ binary
│   │   └── data_interaction/       # JSON I/O
│   ├── SourceCode/                 # C++ source code (g++)
│   │   ├── main.cpp, demo_solver.cpp, lssolver.cpp, ...
│   │   └── Makefile
│   ├── benchmark/
│   └── requirements.txt
│
├── README.md                       # File này
└── simulation.md                   # Hướng dẫn chi tiết (input/output JSON format)
```

---

## ⚙️ Hướng Dẫn Chạy Simulation

### 1. Chuẩn Bị Môi Trường

```bash
# Clone repository
git clone https://github.com/tranphuc15122004/New_DPDP.git
cd New_DPDP

# Tạo virtual environment (khuyến cáo)
python -m venv .venv

# Kích hoạt
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate
```

> **Yêu cầu:** Python 3.12+, pip. Riêng Gold Algorithm cần **Java JDK 8+** (vì là Java `.class`).

---

### 2. Cài Đặt Dependencies

Mỗi thuật toán có dependencies riêng (Python packages cho simulator + algorithm). Chạy lệnh tương ứng:

```bash
# AGVNS
pip install -r AGVNS/requirements.txt

# MA (Memetic Algorithm)
pip install -r MA/requirements.txt

# Silver Algorithm
pip install -r 2/Y_final_submission/requirements.txt

# Gold Algorithm (Java) — cần Java JDK 8+ VÀ Python packages cho simulator
pip install -r 1/compiled_files/requirements.txt
java -version   # Kiểm tra Java đã cài chưa

# Bronze Algorithm (C++) — cần g++ (MinGW) để biên dịch (nếu chưa có binary)
pip install -r 3/requirements.txt
g++ --version   # Kiểm tra C++ compiler
```

---

### 3. Cấu Hình Simulation

Trước khi chạy, có thể tùy chỉnh trong file `src/conf/configs.py` của từng thuật toán. Mỗi thuật toán có file config riêng tại đường dẫn tương ứng:

| Tham số | Mô tả | Giá trị mặc định |
|---------|-------|-----------------|
| `selected_instances` | Danh sách instance muốn chạy. `[]` = chạy tất cả (1-64) | Xem bảng trên |
| `MAX_RUNTIME_OF_ALGORITHM` | Thời gian tối đa cho 1 lần gọi algorithm (giây) | `600` (10 phút) |

**Các instance (64 instances):**

| Instance | Số orders |
|----------|-----------|
| 1-8 | 50 orders |
| 9-16 | 100 orders |
| 17-24 | 300 orders |
| 25-32 | 500 orders |
| 33-40 | 1000 orders |
| 41-48 | 2000 orders |
| 49-56 | 3000 orders |
| 57-64 | 4000 orders |

---

### 4. Chạy Simulation

Tất cả các thuật toán đều dùng chung cơ chế: **`main.py` là simulator entry point**, tự động gọi `main_algorithm.py` (hoặc Java `.class` / C++ binary) theo từng vòng lặp. File `main_algorithm.py` chỉ được gọi trực tiếp nếu muốn **chạy algorithm độc lập** (không qua simulator) để debug.

---

#### 🥇 **AGVNS** (Thuật toán chính — Python)

```bash
cd AGVNS

# Chạy simulator với instance mặc định (instance 1)
python main.py

# Hoặc chạy thẳng algorithm (không qua simulator)
python main_algorithm.py
```

> **Simulator** nằm trong `AGVNS/src/simulator/`.  
> **Algorithm** nằm trong `AGVNS/algorithm/`.

---

#### 📈 **MA** (Memetic Algorithm — Python)

```bash
cd MA

# Chạy simulator
python main.py

# Hoặc chạy thẳng algorithm
python main_algorithm.py
```

> Lưu ý: MA có config mặc định chạy **instance 9** (100 orders).

---

#### 🥇 **Gold Algorithm** (Java)

```bash
cd 1/compiled_files

# Chạy simulator (tự động gọi Java subprocess)
python main.py
```

> Simulator tự động phát hiện file `main_algorithm.class` và gọi `java main_algorithm`.  
> **Yêu cầu:** Java JDK 8+ đã có trong `PATH`.  
> Dependencies Java (Apache POI, JSON libs) nằm trong thư mục `algorithm/`.

---

#### 🥈 **Silver Algorithm** (Python)

```bash
cd 2/Y_final_submission

# Chạy simulator
python main.py

# Hoặc chạy thẳng algorithm
python main_algorithm.py
```

> **Algorithm** là `algorithm/algorithm_demo.py` — dispatch heuristic thuần.

---

#### 🥉 **Bronze Algorithm** (Quickest Route — C++)

**Nếu chưa có binary** (`main_algorithm.exe` / `main_algorithm.out`), biên dịch từ source:

```bash
cd 3/SourceCode
g++ -O3 -std=c++11 -I. -o main_algorithm.out main.cpp probdata.cpp graph.cpp \
    lssolver.cpp scheduler.cpp inputdata.cpp demo_solver.cpp config.cpp \
    binpacking.cpp statistics.cpp pd.cpp pd_ls.cpp -lwinpthread -static
copy main_algorithm.out ..\main_algorithm.exe
cd ..
```

**Chạy simulation:**

```bash
cd 3

python main.py
```

> **Cơ chế:** `main.py` → gọi `main_algorithm.py` → `algorithm/algorithm_demo.py` (wrapper Python) → gọi `main_algorithm.exe` (C++ binary).  
> **Binary có sẵn:** Windows (`main_algorithm.exe`), Linux (`main_algorithm.out`), Windows thay thế (`main_algorithm_windows.out`).

---

### 5. Quy Trình Simulation

Simulator hoạt động theo vòng lặp:

```
1. Đọc instance data từ benchmark/
2. Khởi tạo môi trường (154 factories, 23562 routes, 5 vehicles)
3. Mỗi vòng 10 phút simulated time:
   a. Cập nhật trạng thái vehicles & orders
   b. Ghi JSON input → algorithm/data_interaction/
   c. Gọi algorithm (subprocess) — tối đa 10 phút real time
   d. Algorithm đọc JSON, tính toán, ghi output JSON
   e. Algorithm in "SUCCESS" ra console để báo hiệu hoàn thành
   f. Simulator đọc output, kiểm tra tính khả thi
   g. Update vehicles & orders theo kết quả dispatch
4. Lặp đến khi tất cả orders hoàn thành (state > 1)
5. Tính tổng điểm (score)
```

**Công thức tính score:**
$$Score = \frac{\text{TotalDistance}}{NumTruck} + \frac{\text{SumOverTime} \times \lambda}{3600}$$

Trong đó:

- $\lambda = 10000$ (hệ số mặc định trong `Configs.LAMDA`)
- `TotalDistance`: tổng quãng đường các xe đã đi (km)
- `SumOverTime`: tổng thời gian chờ trễ (giây) — phạt nếu giao trễ
- `NumTruck` : số xe trong mô phỏng

---

### 6. Đọc Kết Quả

Khi simulation kết thúc, output hiển thị:

```
Traveling Distance of Vehicle V_1 is  50.300, visited node list: 131
Traveling Distance of Vehicle V_2 is  241.900, visited node list: 60
...
Total distance:  645.900
Sum over time:  0.000
Total score:  129.180
```
---

### 7. Chạy Nhiều Instances

Để chạy trên nhiều instances, sửa `selected_instances` trong file `src/conf/configs.py` của thuật toán tương ứng:

```python
# Chạy instances 1, 2, 3
selected_instances = [1, 2, 3]

# Chạy tất cả 64 instances
selected_instances = []
```



Kết quả tất cả instances được in dưới dạng list scores và average score:

```
[12.5, 15.3, 18.7, ...]
14.2
Happy Ending
```

---

## 📚 Tài Liệu Tham Khảo

- Xem **`simulation.md`** để hiểu chi tiết về:
  - Input/Output JSON format
  - Các constraints (order non-splitting, destination invariant, ...)
  - Cách debug/test thuật toán

---

## 📝 Ghi Chú Quan Trọng

1. **Gold Algorithm (Java)**: Cần Java JDK 8+ có trong `PATH`. Simulator (Python) tự động gọi `java main_algorithm` từ thư mục `1/compiled_files/`. Nhớ cài Python packages trước: `pip install -r 1/compiled_files/requirements.txt`.
2. **Bronze Algorithm (C++)**: Binary đã được biên dịch sẵn cho Windows (`main_algorithm.exe`) và Linux (`main_algorithm.out`). Nếu cần biên dịch lại từ source, dùng `g++` (MinGW) với lệnh trong phần hướng dẫn. Simulator gọi qua wrapper Python `algorithm/algorithm_demo.py`.
3. **Silver Algorithm**: Nếu gặp lỗi `ImportError: cannot import name 'Inf' from 'numpy.core.numeric'`, sửa thành `from numpy import Inf` trong `algorithm/algorithm_demo.py`.
4. **Thời gian chạy**: Instance càng lớn (50 → 4000 orders), thời gian simulation càng lâu. Instance 1 (50 orders) mất ~1-3 phút. Instance lớn (3000-4000 orders) có thể mất hàng giờ.
5. **Dữ liệu cũ**: Trong thư mục `algorithm/data_interaction/` có thể còn dữ liệu từ lần chạy trước. Simulator sẽ ghi đè khi chạy mới.
6. **Cấu hình riêng**: Mỗi thuật toán có file `src/conf/configs.py` riêng — nhớ sửa đúng file của thuật toán muốn chạy. Giá trị `selected_instances` mặc định khác nhau giữa các thuật toán (xem bảng ở mục 3).

---

## Liên Hệ & Đóng Góp

- **Tác giả**: tranphuc15122004
- **GitHub**: <https://github.com/tranphuc15122004/AGVNS-Adaptive-Genetic-Algorithm-Enhanced-by-Variable-Neighborhood-Search>
- **Vấn đề / Đề xuất**: Hãy mở issue trên GitHub
- **Đóng góp**: Pull requests được hoan nghênh!

---
