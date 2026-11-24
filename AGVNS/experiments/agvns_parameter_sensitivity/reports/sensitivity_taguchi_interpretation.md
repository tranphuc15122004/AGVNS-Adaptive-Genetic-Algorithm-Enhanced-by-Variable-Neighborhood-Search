# Phân tích Taguchi và lựa chọn cấu hình AGVNS

**Phạm vi:** diễn giải hiệu ứng các tham số và xác định cấu hình ứng viên từ bộ sensitivity hiện có.  
**Snapshot dữ liệu:** 2026-10-13.  
**Nguồn:** [bảng kết quả master 480 job](sensitivity_results_master.csv), [bảng hiệu ứng so với baseline](sensitivity_factor_effects.csv), [báo cáo sensitivity tổng](sensitivity_report.md).

## 1. Kết luận chính

- Thiết kế gồm 9 cấu hình Taguchi L9 và một cấu hình baseline, chạy trên 16 instance với 3 repetition: **480/480 key có kết quả hợp lệ** theo ledger.
- Phân tích main effect theo score/S/N raw gợi ý **threshold = 40, population = 60, perturbation = 0.25, mutation = 0.25**; theo macro % so baseline, perturbation tốt nhất chuyển thành **0.50**. Cả hai tổ hợp đều chưa xuất hiện trong 9 cấu hình L9.
- Trong các cấu hình đã chạy, **Config 3 có mean score thấp nhất** (2,042,315), kế đến Config 6 (2,125,832) và Config 9 (2,232,078). Config 3 cũng có S/N cao nhất trong 10 cấu hình, nhưng chỉ nhỉnh hơn Config 6 khoảng 0.015 dB.
- Theo từng instance, Config 3 thấp điểm hơn baseline ở 8/16, cao hơn ở 6/16 và bằng ở 2/16. Nó nổi bật hơn ở nhóm 2,000–4,000 đơn hàng, nhưng yếu ở 500–1,000 đơn hàng; không thắng đồng đều theo benchmark.
- Hiệu ứng tham số thay đổi theo độ dài: population 20 có mean tốt nhất ở phần lớn nhóm 500–2,000, còn population 60 đứng đầu ở 3,000–4,000. Vì vậy mức tốt nhất gộp không nên áp dụng mặc định cho mọi cỡ instance.
- Theo xác nhận của người dùng, cả 480 kết quả được xem là hợp lệ và được đưa vào phân tích; fingerprint chỉ lưu làm metadata truy nguyên. Chưa có kiểm định suy luận hoặc cohort xác nhận riêng cho cấu hình dự đoán, nên kết luận cấu hình tối ưu vẫn ở mức mô tả.

## 2. Thiết kế và response được phân tích

Chín dòng L9 thay đổi bốn yếu tố, mỗi yếu tố có ba mức. Mỗi cấu hình được chạy trên 16 instance, mỗi instance có 3 repetition, tương ứng 48 kết quả/cấu hình. Mỗi mức của từng yếu tố xuất hiện ở ba cấu hình L9, nên có 144 kết quả/mức. Config 10 là baseline và không được đưa vào tính hiệu ứng Taguchi của 9 cấu hình.

Response chính là score mà simulator tối thiểu hóa:

$$
Score = \frac{TotalDistance}{NumTruck} + \frac{SumOverTime \times 10000}{3600}.
$$

Score thấp hơn biểu thị tổng hợp tốt hơn giữa quãng đường trên số xe và thời gian quá hạn bị phạt. Từ score tổng hợp này, không thể kết luận riêng một tham số làm giảm distance hay overtime nếu chưa phân tích từng thành phần đó.

## 3. Ý nghĩa các thống kê

| Thống kê | Cách tính/đọc | Ý nghĩa trong báo cáo |
|---|---|---|
| Mean score | Trung bình score; **thấp hơn tốt hơn** | Chất lượng trung bình. Nhạy với các score rất lớn và với scale khác nhau giữa instance nhỏ/lớn. |
| Median score | Trung vị; **thấp hơn tốt hơn** | Kết quả điển hình, ít bị một vài score cực lớn kéo lệch hơn mean. |
| SD | Độ lệch chuẩn giữa các kết quả; **thấp hơn thường ổn định hơn** | Mức biến thiên. SD gộp ở đây cũng chịu ảnh hưởng của việc trộn instance có scale score khác nhau. |
| Taguchi S/N, smaller-is-better | $S/N=-10\log_{10}(\frac{1}{n}\sum_i y_i^2)$, với $y_i=Score_i$ | **S/N lớn hơn/ít âm hơn tốt hơn**. Bình phương score khiến các lần chạy rất xấu bị phạt mạnh, nên S/N phản ánh cả mức score lẫn rủi ro biến thiên lớn. |
| Delta của yếu tố | Mức response lớn nhất trừ mức nhỏ nhất | Delta lớn cho thấy yếu tố có main effect biểu kiến lớn hơn trong thiết kế này. Đây không phải p-value và không chứng minh ý nghĩa thống kê. |
| Tỷ lệ so với baseline | Score cấu hình / score baseline theo cùng instance và repetition; < 1 tốt hơn trong cặp | Ghép theo cùng instance/repetition để so cùng bài toán và seed; code fingerprint được giữ làm metadata, không dùng loại run theo xác nhận của người dùng. |
| Macro mean % cải thiện so baseline | Với mỗi instance, lấy mean score qua repetition; tính `100 × (baseline_mean − score_mean) / baseline_mean`; sau đó lấy mean của 16 instance | Mỗi instance có trọng số bằng nhau, bất kể score tuyệt đối lớn hay nhỏ. Số dương tốt hơn baseline. Đây là metric bổ sung cho mean score, không thay thế score/S/N. |

Với một factor level, trước hết gộp các cấu hình thuộc mức đó và 3 repetition thành mean score theo từng instance; so sánh mean này với mean 3 repetition của Config 10 trên cùng instance; cuối cùng lấy trung bình 16 phần trăm cải thiện. Vì thiết kế đầy đủ, mỗi instance có cùng số kết quả ở từng mức. Median instance trong bảng là trung vị của 16 phần trăm cải thiện đó, giúp thấy mức điển hình khi macro mean bị một vài instance tác động mạnh.

Trong dữ liệu này, mean score/S/N raw ưu tiên cùng một mức ở cả bốn yếu tố; macro % cải thiện so baseline thay đổi lựa chọn perturbation và cho thấy population 20/60 gần như hòa. Median instance còn cho lựa chọn khác nữa. Vì vậy cần đọc các metric cùng nhau thay vì chọn một mức chỉ dựa trên score gộp.

### Mỗi tham số tác động vào bước nào của AGVNS?

| Tham số | Cơ chế trong `GAVND7` | Tác động khi tăng mức |
|---|---|---|
| `threshold_orders` (T) | Đưa vào lịch ERFC để đặt `CROSSOVER_TYPE_RATIO`. Bộ đếm được truyền vào lịch là `len(Unongoing_super_nodes)`. Trong mỗi vòng sinh con, xác suất nhỏ hơn ratio dùng crossover; nhánh còn lại dùng disturbance. Khi bộ đếm đạt T, ratio bị cắt về 0. | Dịch ngưỡng mà lịch crossover giảm về 0; T lớn hơn giữ cơ hội crossover đến mức bộ đếm cao hơn. T không trực tiếp là số thế hệ hoặc giới hạn thời gian. |
| `population_size` | Quy mô quần thể khởi tạo; mỗi thế hệ sinh mục tiêu khoảng `2 × population`, sau đó giữ lại population cá thể tốt nhất. | Tăng số ứng viên được khám phá và số phép đánh giá; có thể tăng đa dạng nhưng cũng tiêu tốn ngân sách thời gian nhiều hơn. |
| `perturbation_rate` | Truyền làm `relocate_rate` cho `disturbance_opt`; số cặp pickup-delivery bị chọn để di chuyển là xấp xỉ `max(1, int(số cặp × rate))`. | Tăng mức xáo trộn tuyến trong nhánh disturbance; có thể tăng đa dạng tìm kiếm nhưng cũng làm thay đổi nhiều cặp hơn. |
| `mutation_rate` | Đặt phần quần thể được duyệt để chạy một lượt `randon_1_LS` giới hạn trong mỗi thế hệ. | Tăng số cá thể nhận local search, tức tăng cường khai thác lân cận và chi phí tính toán mỗi thế hệ. |

Diễn giải này mô tả nơi các biến được dùng trong `GAVND7.py` và các operator ở checkout hiện tại. Theo xác nhận của người dùng, toàn bộ kết quả hợp lệ được đưa vào so sánh; fingerprint không dùng để loại run. Hiệu ứng score bên dưới là kết quả của toàn pipeline; thiết kế này không tách riêng tác dụng của một operator trong điều kiện giữ mọi yếu tố khác cố định.

## 4. Hiệu ứng Taguchi theo từng yếu tố

Các số dưới đây được tính trực tiếp từ score của 9 cấu hình L9 trong master CSV. Mỗi mức có **144 job**. Hai cột phần trăm so baseline dùng mean repetition theo instance rồi macro-average trên 16 instance; median là median của 16 phần trăm theo instance. Số dương ở hai cột phần trăm nghĩa là cải thiện.

| Yếu tố | Mức | Mean score | Median score | S/N (dB) | Macro mean cải thiện vs baseline (%) | Median cải thiện theo instance (%) |
|---|---:|---:|---:|---:|---:|---:|
| `threshold_orders` | 40 | 3,142,937.210 | 10,776.294 | −141.360 | **+2.77** | **+0.79** |
|  | 80 | 5,845,935.649 | 13,189.767 | −149.059 | −16.88 | −0.08 |
|  | 120 | 3,708,486.678 | 12,106.679 | −143.524 | −7.44 | −2.22 |
| `population_size` | 20 | 5,364,741.173 | 10,628.315 | −148.804 | +0.02 | **+1.32** |
|  | 40 | 5,199,209.795 | 12,246.342 | −145.846 | −21.81 | −0.10 |
|  | 60 | 2,133,408.568 | 13,294.307 | −133.715 | **+0.24** | −0.07 |
| `perturbation_rate` | 0.25 | 3,655,348.517 | 12,951.174 | −143.481 | −10.85 | −0.85 |
|  | 0.50 | 4,490,553.798 | 10,645.005 | −148.063 | **−0.86** | −0.36 |
|  | 0.75 | 4,551,457.222 | 12,231.033 | −144.829 | −9.83 | **−0.25** |
| `mutation_rate` | 0.10 | 4,596,988.729 | 10,880.211 | −144.837 | −8.37 | **+0.14** |
|  | 0.25 | 3,188,498.990 | 11,758.379 | −141.387 | **−3.71** | −0.07 |
|  | 0.50 | 4,911,871.817 | 13,189.767 | −148.602 | −9.46 | −0.90 |

| Xếp hạng theo Delta macro | Yếu tố | Delta mean score | Delta S/N (dB) | Delta macro improvement (điểm %) | Mức raw mean/SN tốt nhất | Mức macro % tốt nhất |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `population_size` | 3,231,332.605 | 15.089 | 22.04 | 60 | 60* |
| 2 | `threshold_orders` | 2,702,998.440 | 7.699 | 19.65 | 40 | 40 |
| 3 | `perturbation_rate` | 896,108.705 | 4.582 | 9.99 | 0.25 | 0.50 |
| 4 | `mutation_rate` | 1,723,372.827 | 7.215 | 5.75 | 0.25 | 0.25 |

`*` Macro mean chọn population 60 (+0.24%) nhưng gần population 20 (+0.02%); median instance lại ưu tiên population 20 (+1.32%). Hai mức population 20 và 60 vì thế chưa phân biệt rõ theo metric tương đối.

### Diễn giải

1. **Population size có biên độ main effect lớn nhất theo cả raw score và macro %.** Macro response cho thấy mức 40 tệ hơn rõ, nhưng 20 (+0.02%) và 60 (+0.24%) gần như hòa theo mean; median instance ủng hộ mức 20. Vì vậy dữ liệu không cho thấy quan hệ đơn điệu “population càng lớn càng tốt”.
2. **Threshold 40 được ưu tiên.** Mức 80 có mean score cao nhất trong ba mức, còn mức 120 nằm giữa. Dữ liệu hiện tại không ủng hộ chọn 80 nếu mục tiêu chỉ là giảm score tổng hợp.
3. **Perturbation thay đổi rõ theo cách cân trọng số.** Raw mean/S/N ưu tiên 0.25; macro mean % ưu tiên 0.50, còn median instance ưu tiên 0.75. Mutation 0.25 tốt nhất theo raw mean/S/N và macro mean %; mutation 0.10 có median instance cao nhất. Đây là dấu hiệu hiệu ứng phụ thuộc instance và phân phối score.
4. **Delta chỉ dùng để xếp hạng độ lớn hiệu ứng quan sát được.** L9 ở đây không cung cấp kiểm định p-value, khoảng tin cậy hay phân tích đầy đủ tương tác giữa các yếu tố.

## 5. Hiệu ứng tham số theo kích thước instance

Phân tích gộp ở mục 4 che khuất khác biệt theo quy mô. Bảng dưới tính **mean score riêng trong từng nhóm độ dài**, mỗi mức có `n = 18` (2 instance × 3 repetition × 3 cấu hình L9). `T40/T80/T120`, `P20/P40/P60`, `Pert.25/.50/.75`, và `Mut.10/.25/.50` lần lượt là mức của tham số. In đậm là mức có mean thấp nhất trong hàng.

### Threshold T: mean score theo mức

| Số đơn hàng | T=40 | T=80 | T=120 | Mức mean thấp nhất |
|---:|---:|---:|---:|---:|
| 50 | **107.038** | 107.559 | 108.791 | 40 |
| 100 | 67,051.412 | **63,637.056** | 67,050.642 | 80 |
| 300 | 349.608 | **349.379** | 349.420 | 80 |
| 500 | **10,246.330** | 13,750.499 | 14,343.195 | 40 |
| 1,000 | **5,577.329** | 6,185.418 | 6,319.097 | 40 |
| 2,000 | 259,786.576 | **217,602.213** | 366,992.447 | 80 |
| 3,000 | **3,322,452.931** | 3,767,701.964 | 3,688,728.106 | 40 |
| 4,000 | **21,477,926.453** | 42,698,151.106 | 25,524,001.726 | 40 |

### Population size: mean score theo mức

| Số đơn hàng | P=20 | P=40 | P=60 | Mức mean thấp nhất |
|---:|---:|---:|---:|---:|
| 50 | **107.521** | 107.548 | 108.319 | 20 |
| 100 | 66,443.238 | 67,660.494 | **63,635.379** | 60 |
| 300 | 349.425 | **349.329** | 349.654 | 40 |
| 500 | **9,368.026** | 15,745.487 | 13,226.512 | 20 |
| 1,000 | **5,482.647** | 5,754.395 | 6,844.801 | 20 |
| 2,000 | **261,629.077** | 314,729.475 | 268,022.684 | 20 |
| 3,000 | 3,642,958.052 | 3,579,736.888 | **3,556,188.060** | 60 |
| 4,000 | 38,931,591.400 | 37,609,594.748 | **13,158,893.137** | 60 |

### Perturbation rate: mean score theo mức

| Số đơn hàng | Pert.=0.25 | Pert.=0.50 | Pert.=0.75 | Mức mean thấp nhất |
|---:|---:|---:|---:|---:|
| 50 | 108.414 | 107.887 | **107.087** | 0.75 |
| 100 | 67,050.642 | 65,648.741 | **65,039.728** | 0.75 |
| 300 | 349.851 | **348.583** | 349.974 | 0.50 |
| 500 | 16,313.160 | **10,262.726** | 11,764.139 | 0.50 |
| 1,000 | 6,107.531 | **5,801.975** | 6,172.337 | 0.50 |
| 2,000 | 420,992.892 | **207,829.542** | 215,558.802 | 0.50 |
| 3,000 | 3,611,354.378 | **3,537,059.583** | 3,630,469.039 | 0.50 |
| 4,000 | **25,120,511.267** | 32,097,371.347 | 32,482,196.672 | 0.25 |

### Mutation rate: mean score theo mức

| Số đơn hàng | Mut.=0.10 | Mut.=0.25 | Mut.=0.50 | Mức mean thấp nhất |
|---:|---:|---:|---:|---:|
| 50 | 107.844 | 108.002 | **107.541** | 0.50 |
| 100 | **65,039.728** | 67,051.412 | 65,647.971 | 0.10 |
| 300 | 349.739 | **349.259** | 349.410 | 0.25 |
| 500 | **10,619.418** | 12,108.250 | 15,612.357 | 0.10 |
| 1,000 | **5,560.605** | 6,367.808 | 6,153.430 | 0.10 |
| 2,000 | **251,874.817** | 300,879.182 | 291,627.236 | 0.10 |
| 3,000 | **3,522,191.166** | 3,721,381.779 | 3,535,310.055 | 0.10 |
| 4,000 | 32,920,166.518 | **21,399,746.228** | 35,380,166.540 | 0.25 |

### Tác động phụ thuộc kích thước

- **Không có một mức thắng trên mọi kích thước.** Population 20 có mean thấp nhất ở 500–2,000 đơn hàng, còn population 60 thắng ở 3,000–4,000. Đây là dấu hiệu nên kiểm tra giả thuyết quần thể lớn hữu ích hơn ở bài toán lớn, nhưng các run hiện tại chưa đủ đồng nhất để xác nhận quan hệ nhân quả.
- Perturbation 0.50 có mean thấp nhất ở 300–3,000; 0.75 ở 50–100; 0.25 ở 4,000. Mức xáo trộn phù hợp có thể thay đổi theo quy mô bài toán.
- Mutation 0.10 có mean thấp nhất ở 100 và 500–3,000; mutation 0.25 ở 300 và 4,000; mutation 0.50 chỉ ở nhóm 50. Tăng số lượt local search không tạo ra cải thiện đơn điệu.
- T=40 có mean thấp nhất ở 50, 500, 1,000, 3,000, 4,000; T=80 ở 100, 300, 2,000. Ở nhóm 300, mức thắng theo mean là T=80 nhưng theo S/N là T=40; chênh lệch score rất nhỏ nên thứ tự nhạy với cách đo.
- Tổ hợp mức tốt nhất gộp `(40, 60, 0.25, 0.25)` trùng với các mức thắng ở nhóm 4,000 đơn hàng. Vì score của nhóm lớn có scale cao hơn nhiều, kết quả gộp bị nhóm lớn chi phối; không nên mặc định đây là cấu hình tốt nhất cho instance nhỏ.

## 6. So sánh các cấu hình đã chạy

S/N ở bảng này được tính lại theo công thức smaller-is-better trên 48 score của mỗi cấu hình; baseline Config 10 được giữ để tham chiếu, không đưa vào fit main effect L9.

| Config | Threshold | Population | Perturbation | Mutation | Mean score | Median score | SD mẫu | S/N (dB) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 0.25 | 0.10 | 4,062,656.092 | 10,392.347 | 15,654,945.408 | −144.090 |
| 2 | 40 | 40 | 0.50 | 0.25 | 3,323,840.256 | 10,526.858 | 11,101,220.823 | −141.196 |
| 3 | 40 | 60 | 0.75 | 0.50 | **2,042,315.280** | 13,220.434 | 4,278,383.598 | **−133.443** |
| 4 | 80 | 20 | 0.50 | 0.50 | 7,915,742.901 | 11,898.544 | 41,664,200.810 | −152.461 |
| 5 | 80 | 40 | 0.75 | 0.10 | 7,496,231.859 | 11,926.352 | 24,228,680.137 | −148.000 |
| 6 | 80 | 60 | 0.25 | 0.25 | 2,125,832.188 | 17,763.920 | 4,246,219.027 | −133.458 |
| 7 | 120 | 20 | 0.75 | 0.25 | 4,115,824.527 | 10,984.347 | 15,722,155.769 | −144.133 |
| 8 | 120 | 40 | 0.25 | 0.50 | 4,777,557.271 | 25,277.025 | 19,364,094.141 | −145.910 |
| 9 | 120 | 60 | 0.50 | 0.10 | 2,232,078.236 | 11,327.351 | 4,666,444.063 | −134.200 |
| 10 (baseline) | 80 | 40 | 0.50 | 0.25 | 3,610,750.395 | 11,422.569 | 12,165,651.020 | −141.985 |

### Metric so baseline theo từng cấu hình

| Config | Mean % cải thiện macro trên 16 instance | Median % cải thiện theo instance |
|---:|---:|---:|
| 1 | +5.12 | +0.47 |
| 2 | −2.06 | +0.08 |
| 3 | **+5.26** | +0.09 |
| 4 | −5.63 | +0.11 |
| 5 | −35.34 | 0.00 |
| 6 | −9.67 | −0.19 |
| 7 | +0.59 | −0.06 |
| 8 | −28.02 | −3.23 |
| 9 | +5.11 | 0.00 |
| 10 (baseline) | 0.00 | 0.00 |

Theo macro mean, Config 3 cải thiện **5.26%** so với baseline khi mọi instance có trọng số như nhau; median instance chỉ **+0.09%**. Trong khi đó, so mean score gộp theo job cho mức giảm 43.4%. Hai con số trả lời hai câu hỏi khác nhau: pooled score phản ánh tổng scale score của benchmark; macro % phản ánh mức cải thiện trung bình trên một instance điển hình với mỗi instance được cân ngang nhau.

Chênh lệch macro giữa Config 3 và Config 1 (+5.12%) chỉ **0.14 điểm phần trăm**; Config 9 (+5.11%) cũng chỉ cách **0.15 điểm**. Median instance của Config 1 (+0.47%) cao hơn Config 3 (+0.09%), nên không nên xem Config 3 là thắng tuyệt đối theo metric tương đối.

### Cách đọc bảng cấu hình

- **Config 3 thắng theo mean score và S/N**, nhưng S/N gần như hòa với Config 6: chênh 0.015 dB. Mean của Config 3 thấp hơn Config 6 khoảng 3.9% trong bộ gộp hiện tại.
- **Config 1 có median thấp nhất** (10,392), trong khi mean của nó cao hơn Config 3 khoảng gấp đôi. Điều này cho thấy số ít điểm score lớn làm thay đổi mạnh thứ hạng theo mean.
- Config 3 có mean score gộp thấp hơn baseline khoảng 43.4%, nhưng macro improvement chỉ +5.26% và median instance +0.09%. Khi mô tả kết quả, nên nêu cả pooled score và macro % để tránh để các instance điểm lớn đại diện cho toàn bộ benchmark.
- Không có cấu hình nào tốt nhất theo mọi thước đo. Nếu ưu tiên mean/S/N thì Config 3 đứng đầu; nếu ưu tiên median thì Config 1 đứng đầu. Việc chọn metric phải theo mục tiêu đánh giá và cần giữ cùng benchmark/code version.

## 7. Config 3 thắng và thua ở những instance nào?

Mỗi dòng dưới đây là mean của 3 repetition cho instance đó. `% cải thiện` là `100 × (mean baseline − mean Config 3) / mean baseline`; số dương có lợi cho Config 3. Rank xếp mean của Config 3 trong 10 cấu hình (rank 1 là thấp nhất); cột ties đếm số cấu hình khác có mean bằng Config 3. `C3 < C10` đếm số repetition có score Config 3 thấp hơn baseline.

| Instance | Đơn hàng | C3 mean | Baseline mean | C3 cải thiện vs baseline (%) | C3 rank / ties | Repetition C3 < baseline |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50 | 121.380 | 124.213 | +2.28% | 1 / 0 | 3/3 |
| 2 | 50 | 91.813 | 91.813 | 0.00% | 1 / 9 | 0/3 |
| 9 | 100 | 4,124.968 | 3,587.883 | −14.97% | 2 / 2 | 1/3 |
| 10 | 100 | 123,145.789 | 123,145.789 | 0.00% | 1 / 5 | 0/3 |
| 17 | 300 | 84.383 | 81.545 | −3.48% | 10 / 0 | 0/3 |
| 18 | 300 | 616.092 | 615.879 | −0.03% | 5 / 0 | 1/3 |
| 25 | 500 | 11,775.226 | 11,796.518 | +0.18% | 5 / 0 | 1/3 |
| 26 | 500 | 13,243.401 | 8,566.268 | −54.60% | 7 / 0 | 0/3 |
| 33 | 1,000 | 2,340.010 | 1,873.847 | −24.88% | 9 / 0 | 2/3 |
| 34 | 1,000 | 10,992.095 | 9,296.547 | −18.24% | 8 / 0 | 1/3 |
| 41 | 2,000 | 281,233.241 | 483,427.531 | +41.83% | 4 / 0 | 2/3 |
| 42 | 2,000 | 99,994.885 | 259,077.596 | +61.40% | 1 / 0 | 2/3 |
| 49 | 3,000 | 3,382,853.303 | 3,681,331.384 | +8.11% | 3 / 0 | 1/3 |
| 50 | 3,000 | 3,148,220.867 | 3,775,526.896 | +16.62% | 1 / 0 | 1/3 |
| 57 | 4,000 | 13,349,639.563 | 36,271,060.877 | +63.19% | 3 / 0 | 2/3 |
| 58 | 4,000 | 12,248,567.470 | 13,142,401.742 | +6.80% | 3 / 0 | 2/3 |

Theo mean từng instance, Config 3 tốt hơn baseline ở **8/16**, kém hơn ở **6/16**, và bằng ở **2/16**. Nó đứng hạng 1 ở 5 instance, nhưng chỉ **3 instance là thắng duy nhất** (1, 42, 50); instance 2 và 10 có nhiều cấu hình đồng điểm. Vì vậy “Config 3 thắng” không có nghĩa là nó thắng đồng đều trên benchmark.

### Kết quả gộp theo độ dài

| Đơn hàng | C3 mean | Baseline mean | Pooled mean cải thiện (%) | Macro cải thiện đều 2 instance (%) | Hạng C3 trong nhóm | Cấu hình mean tốt nhất | C3 tốt hơn baseline ở repetition |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | 106.597 | 108.013 | +1.31% | +1.14% | 1 | C3 | 3/6 |
| 100 | 63,635.379 | 63,366.836 | −0.42% | −7.48% | 2 | C10 | 1/6 |
| 300 | 350.238 | 348.712 | −0.44% | −1.76% | 10 | C2 | 1/6 |
| 500 | 12,509.313 | 10,181.393 | −22.86% | −27.21% | 7 | C1 | 1/6 |
| 1,000 | 6,666.053 | 5,585.197 | −19.35% | −21.56% | 9 | C1 | 3/6 |
| 2,000 | 190,614.063 | 371,252.564 | +48.66% | +51.61% | 3 | C4 | 4/6 |
| 3,000 | 3,265,537.085 | 3,728,429.140 | +12.42% | +12.36% | 1 | C3 | 2/6 |
| 4,000 | 12,799,103.516 | 24,706,731.310 | +48.20% | +35.00% | 2 | C6 | 4/6 |

**Điểm mạnh của Config 3:** các nhóm 2,000–4,000 đơn hàng có mean gộp thấp hơn baseline; tại 3,000 đơn hàng Config 3 đứng đầu, còn 4,000 đơn hàng đứng thứ hai và chỉ kém Config 6 khoảng 1.0% theo mean. Các mức cải thiện lớn nhất so với baseline là instance 57 (+63.19%) và 42 (+61.40%).

**Điểm yếu của Config 3:** ở nhóm 500 và 1,000 đơn hàng, pooled mean score cao hơn baseline lần lượt 22.86% và 19.35%; instance 26 là trường hợp xấu nhất tương đối (−54.60% cải thiện, hạng 7), kế đến instance 33 (−24.88%, hạng 9) và 34 (−18.24%, hạng 8). Ở nhóm 300 đơn hàng, C3 đứng cuối theo mean dù chênh lệch tuyệt đối nhỏ.

Trong metadata hiện có, chỉ 3/48 cặp C3-baseline có cùng fingerprint không rỗng (hai cặp ở instance 57, một ở 58). Theo xác nhận của người dùng, toàn bộ run được coi hợp lệ và đều được tính; fingerprint ở đây chỉ là thông tin truy nguyên, không phải bộ lọc dữ liệu.

## 8. Cấu hình dự đoán và cấu hình quan sát

### Cấu hình dự đoán theo từng response

Ghép các mức tốt nhất theo **mean score/S/N raw** tạo thành:

> **Threshold = 40, Population = 60, Perturbation = 0.25, Mutation = 0.25.**

Ghép các mức tốt nhất theo **macro % cải thiện so baseline** tạo thành:

> **Threshold = 40, Population = 60, Perturbation = 0.50, Mutation = 0.25.**

Median instance lại ưu tiên `(40, 20, 0.75, 0.10)`. Các tổ hợp này đều là **dự đoán từ main effect**, không phải cấu hình đã được chạy. L9 không có dòng chứa đúng tổ hợp nào trong ba tổ hợp trên. Không gán cho chúng score/S/N bằng cách ghép trung bình yếu tố; tương tác giữa tham số có thể làm kết quả thực tế khác dự đoán.

### Cấu hình quan sát tốt nhất

Config 3 `(40, 60, 0.75, 0.50)` có mean score thấp nhất trong 9 dòng L9. Theo macro improvement, Config 3 cũng cao nhất (+5.26%), nhưng median instance chỉ +0.09%; Config 6 `(80, 60, 0.25, 0.25)` gần như ngang Config 3 theo S/N. Config 3 là ứng viên mạnh theo bộ dữ liệu hiện có, nhưng cần chọn response ưu tiên và không nên gọi là tối ưu duy nhất khi raw score, macro mean và median instance đưa ra các mức tham số khác nhau.

## 9. Giới hạn bằng chứng

1. **Tất cả 480 run được dùng theo xác nhận của người dùng.** Fingerprint thiếu hoặc khác được giữ như metadata truy nguyên, không loại run khỏi phép tính.
2. **Có một số score ngoại lệ ở instance 57–58.** Báo cáo tổng gắn cờ 9 score vượt 5 lần median của instance tương ứng. Chúng được giữ trong metric vì người dùng xác nhận kết quả hợp lệ; median và bảng theo instance giúp nhìn rõ ảnh hưởng của chúng.
3. **Các instance có scale rất khác nhau.** Mean/S/N raw gộp qua 50 đến 4,000 đơn hàng chịu ảnh hưởng lớn từ instance điểm cao. Macro % cải thiện khắc phục việc một instance điểm lớn có trọng số tuyệt đối lớn hơn, bằng cách chuẩn hóa theo baseline trong từng instance rồi lấy trung bình đều.
4. **Macro improvement vẫn có thể nhạy với một instance có mức suy giảm phần trăm lớn.** Vì vậy báo cáo kèm median của 16 phần trăm instance và kết quả riêng từng instance; macro mean không nên được đọc một mình.
5. `sensitivity_factor_effects.csv` giữ các cột ratio cũ ở cấp từng repetition. `mean_relative_score_vs_baseline_percent` dương nghĩa score cao hơn/tệ hơn; cột mới `macro_mean_improvement_vs_baseline_percent` dương nghĩa cải thiện. Ví dụ T=40: mean các ratio từng repetition cho thấy score cao hơn baseline 27.47%, trong khi macro theo mean mỗi instance cho thấy cải thiện 2.77%. Hai phép gộp khác nhau; ratio theo repetition có thể bị một repetition với baseline thấp chi phối. Bảng Taguchi trong báo cáo này dùng macro metric mới.
5. **Không có kiểm định ý nghĩa thống kê hoặc phân tích tương tác trong các con số trên.** Delta là chỉ báo độ lớn main effect mô tả, không phải phép kiểm định.

## 10. Kết luận và bước xác nhận đề xuất

Theo raw mean/S/N, các mức gợi ý là `(40, 60, 0.25, 0.25)`; theo macro % cải thiện so baseline là `(40, 60, 0.50, 0.25)`; median instance lại ưu tiên `(40, 20, 0.75, 0.10)`. Config 3 có pooled mean score thấp nhất trong các cấu hình đã chạy và macro improvement +5.26%, nhưng median instance chỉ +0.09%. Đây là các góc nhìn bổ sung; không có một tổ hợp dự đoán thắng theo mọi metric.

Nếu cần chốt một cấu hình duy nhất, nên chạy cùng instance/seed cho các phương án `(40,60,0.25,0.25)`, `(40,60,0.50,0.25)`, Config 3, Config 6 và baseline Config 10. So sánh đồng thời pooled mean score, macro % cải thiện, median theo instance, S/N và hai thành phần distance/overtime.

**Câu kết luận phù hợp để dùng hiện tại:** “Config 3 có pooled mean score thấp nhất và macro improvement +5.26% khi mỗi instance có trọng số như nhau; median instance improvement là +0.09%. Taguchi gợi ý threshold 40, population 60, mutation 0.25; mức perturbation được chọn là 0.25 theo score/S/N raw nhưng 0.50 theo macro % cải thiện. Cần chọn metric theo mục tiêu đánh giá trước khi chốt cấu hình.”
