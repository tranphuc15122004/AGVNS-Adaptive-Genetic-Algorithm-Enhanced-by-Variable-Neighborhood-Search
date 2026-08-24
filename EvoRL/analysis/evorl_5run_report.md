# Báo cáo tổng hợp 5 lần chạy EvoRL

- Thời điểm tạo báo cáo (UTC): `2026-08-20T13:13:29.408840+00:00`
- Phạm vi: 64 instance benchmark, gồm 4 repetition hiện tại và 1 lần reference trước đó.
- Chỉ tiêu chính: `score`; **score thấp hơn là tốt hơn**.
- Độ lệch chuẩn trong báo cáo là population standard deviation của các quan sát trong cùng instance/run.

## 1. Kết luận chính

- Dữ liệu hợp lệ: **320/320 job thành công** (256 hiện tại + 64 reference), không có dòng lỗi.
- Mean score theo 64 instance: reference **407,248,319.047**, mean của 4 repetition hiện tại **406,230,765.487**, và mean gộp 5 lần **406,434,276.199**.
- So với reference, mean của 4 repetition hiện tại thay đổi **-0.082%** theo macro-average phần trăm trên 64 instance; delta raw score trung bình là **-1,017,553.559**.
- Số instance current-4 tốt hơn / bằng / xấu hơn reference: **20 / 25 / 19**.
- Reference trùng score với repetition 1 hiện tại ở **28/64 instance**. Vì vậy 5 dòng đo không nên được diễn giải là 5 mẫu hoàn toàn độc lập.

Diễn giải: thay đổi tổng thể rất nhỏ; kết quả hiện tại nhìn chung tương đương reference, với lợi thế nhẹ khi tính trung bình theo instance. Các nhóm instance lớn có ảnh hưởng lớn hơn nếu tính raw score, nên cần đọc cùng bảng theo nhóm bên dưới.

## 2. Thống kê theo lần chạy

| Nguồn | Số mẫu | Mean score | Median | SD | Min | Max | Wall time mean (s) | Algorithm time mean (s) | So với reference |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Reference trước đó | 64 | 407,248,319.047 | 31,300,258.856 | 625,313,819.925 | 120.780 | 1,914,127,162.531 | 4,714.201 | 4,171.382 | — |
| Repetition hiện tại 1 | 64 | 406,324,578.239 | 31,075,771.195 | 624,660,393.024 | 120.780 | 1,925,911,389.308 | 4,846.562 | 4,285.176 | -0.105%; 18/28/18 |
| Repetition hiện tại 2 | 64 | 406,692,116.882 | 30,230,828.955 | 625,031,985.780 | 120.780 | 1,945,675,753.816 | 4,845.149 | 4,281.003 | -0.080%; 18/28/18 |
| Repetition hiện tại 3 | 64 | 406,111,744.154 | 30,637,977.021 | 623,207,744.918 | 120.780 | 1,945,675,753.816 | 4,757.942 | 4,212.130 | -0.019%; 22/26/16 |
| Repetition hiện tại 4 | 64 | 405,794,622.673 | 30,447,139.361 | 622,348,948.163 | 120.780 | 1,945,675,753.816 | 4,710.439 | 4,167.674 | -0.125%; 19/28/17 |

Trong cột cuối, format là `mean % change; wins/ties/losses` theo từng instance; phần trăm âm nghĩa là score giảm, tốt hơn.

## 3. Tổng hợp theo nhóm kích thước instance

| Instance | Orders | Reference mean | Current-4 mean | Combined-5 mean | Current-4 vs ref | Tốt hơn / bằng / xấu hơn |
|---|---:|---:|---:|---:|---:|---:|
| 1-8 | 50 | 9,446.699 | 9,446.699 | 9,446.699 | +0.000% | 0 / 8 / 0 |
| 9-16 | 100 | 2,682,188.661 | 2,682,188.661 | 2,682,188.661 | +0.000% | 0 / 8 / 0 |
| 17-24 | 300 | 275,019.508 | 275,019.508 | 275,019.508 | +0.000% | 0 / 8 / 0 |
| 25-32 | 500 | 26,974,486.994 | 27,072,864.058 | 27,053,188.645 | +0.415% | 1 / 1 / 6 |
| 33-40 | 1000 | 35,343,358.171 | 35,224,480.654 | 35,248,256.157 | -0.408% | 4 / 0 / 4 |
| 41-48 | 2000 | 422,010,266.710 | 421,944,955.351 | 421,958,017.623 | -0.005% | 3 / 0 / 5 |
| 49-56 | 3000 | 919,392,602.838 | 915,302,076.281 | 916,120,181.592 | -0.443% | 6 / 0 / 2 |
| 57-64 | 4000 | 1,851,299,182.792 | 1,847,335,092.685 | 1,848,127,910.707 | -0.217% | 6 / 0 / 2 |

Các nhóm benchmark tương ứng: 1–8 = 50 orders, 9–16 = 100, 17–24 = 300, 25–32 = 500, 33–40 = 1000, 41–48 = 2000, 49–56 = 3000, 57–64 = 4000.

## 4. Instance thay đổi nhiều nhất

### Cải thiện nhiều nhất

| Instance | Orders | Reference | Current-4 mean | Change |
|---:|---:|---:|---:|---:|
| 33 | 1000 | 32,296,893.032 | 30,526,381.294 | -5.482% |
| 50 | 3000 | 912,831,991.427 | 887,146,655.687 | -2.814% |
| 45 | 2000 | 426,822,351.401 | 417,559,630.513 | -2.170% |
| 32 | 500 | 30,490,917.609 | 29,873,537.381 | -2.025% |
| 57 | 4000 | 1,837,950,743.966 | 1,812,696,287.293 | -1.374% |

### Xấu đi nhiều nhất

| Instance | Orders | Reference | Current-4 mean | Change |
|---:|---:|---:|---:|---:|
| 35 | 1000 | 36,615,418.335 | 37,572,790.535 | +2.615% |
| 31 | 500 | 30,126,671.110 | 30,669,476.973 | +1.802% |
| 47 | 2000 | 417,221,501.942 | 423,821,837.989 | +1.582% |
| 30 | 500 | 24,306,416.991 | 24,671,060.434 | +1.500% |
| 64 | 4000 | 1,914,127,162.531 | 1,940,734,662.689 | +1.390% |

## 5. Phương pháp và nguồn

- Current batch: [`20260819_094955/results.csv`](../algorithm/data_interaction_runs/20260819_094955/results.csv), 256 dòng, repetition 1–4 trên instance 1–64.
- Reference: [`EvoRL_results_64_instances.csv`](../algorithm/data_interaction_runs/EvoRL_results_64_instances.csv), 64 dòng, một dòng/instance.
- Reference có các batch ID: `20260815_064053, 20260817_020323`. Đây là file 64-instance đã được ghép từ các batch hoàn tất trước đó; không dùng batch `20260818_143854` vì batch này chưa hoàn tất.
- File CSV chi tiết theo instance: [`evorl_5run_instance_aggregate.csv`](evorl_5run_instance_aggregate.csv). File này giữ score, runtime, seed, mean/std/min/max của 4 repetition và 5 lần.
- So sánh current-4 với reference dùng mean của bốn score hiện tại cho từng instance; khi gộp 5 lần, reference được tính như một quan sát bổ sung.

## 6. Hạn chế khi diễn giải

- Reference và repetition 1 hiện tại dùng cùng công thức seed theo instance/repetition; một phần kết quả có thể lặp lại do tính tất định của pipeline.
- Mean raw score bị chi phối bởi các instance lớn (3000–4000 orders). Macro-average phần trăm theo instance được dùng để tránh chỉ nhìn vào các giá trị raw lớn.
- Báo cáo này tổng hợp kết quả đã chạy; chưa phải kiểm định thống kê về ý nghĩa của chênh lệch.
