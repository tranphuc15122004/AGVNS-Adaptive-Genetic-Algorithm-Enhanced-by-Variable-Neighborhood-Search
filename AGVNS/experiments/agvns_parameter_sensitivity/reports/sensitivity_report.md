# AGVNS sensitivity: tổng hợp kết quả

- Thời điểm chụp: 2026-10-13 17:28:35 +07 (Asia/Ho_Chi_Minh).
- Thiết kế: 10 cấu hình × 16 instance × 3 repetition = 480 key; seed = `20260824 + instance_id × 1000 + repetition`.
- Tệp chi tiết: [bảng 480 job](sensitivity_results_master.csv), [bảng sensitivity hiện tại](sensitivity_table_current.md), [lịch sử attempt](sensitivity_attempts.csv), [tổng hợp theo instance/cấu hình](sensitivity_coverage.csv), [bộ dữ liệu theo độ dài](sensitivity_jobs_by_length.csv), [tóm tắt theo độ dài](sensitivity_summary_by_length.csv), [hiệu ứng mức yếu tố và macro improvement](sensitivity_factor_effects.csv), [phân tích Taguchi chi tiết](sensitivity_taguchi_interpretation.md), [worker log không có result JSONL](sensitivity_unrecorded_logs.csv).

## Trạng thái hiện tại

| Trạng thái | Số run |
|---|---:|
| Có ít nhất một kết quả hợp lệ | 480 |
| Đang chạy (có worker log) | 0 |
| Đã nằm trong batch nhưng chưa được khởi chạy | 0 |
| Chưa có kết quả hợp lệ, chưa nằm trong batch hiện tại | 0 |
| Tổng thiết kế | 480 |

Một kết quả chỉ được tính hợp lệ nếu score hữu hạn, không âm, nhỏ hơn giá trị sentinel `sys.maxsize`, trạng thái hiệu lực là `SUCCESS`, và seed trùng với thiết kế. Các lần chạy trùng key không làm tăng coverage; lịch sử của chúng vẫn nằm trong attempt ledger.

## Batch hiện tại và quan sát sơ bộ

- Batch `20261009_015120`: 36 key được chọn; 36 result row đã ghi, 36 hợp lệ; 0 workspace đang chạy nhưng chưa có result cuối; 0 key đang chờ khởi chạy.
- 36/480 kết quả hợp lệ trong master có cùng code fingerprint với manifest của batch gần nhất (`1d9f93ccf387c5fc5c3fcafe5d37d364971ac25de57caf0a16dc826d59f10958`). Theo xác nhận của người dùng, toàn bộ 480 kết quả hợp lệ được đưa vào phân tích; fingerprint được giữ làm metadata truy nguyên, không dùng để loại run khỏi thống kê.
- Fingerprint nguồn của 480 dòng canonical: 1d9f93ccf387c5fc5c3fcafe5d37d364971ac25de57caf0a16dc826d59f10958: 36; 9ffb9b681ae3cbd789021dba5bc46a5761281b8a7560533ea147333a8a69bc6c: 24; afa5adc6e9179ded92e745598ca8212186c83932472b9c53f3ef09b95c173b4b: 3; b44262670d6a43bf589ba54a150bf5850700c472f9d7cbf2ed4192a4d245af05: 15; not recorded: 402. Có 402/480 dòng thiếu fingerprint nguồn.
- Điểm instance 57 cao hơn rõ rệt so với phần còn lại: config 10, repetition 2: 81201364.193 (5.5× mức kế tiếp 14883466.681); config 1, repetition 2: 106577225.892 (7.2× mức kế tiếp 14883466.681). Đây là dấu hiệu cần rà soát; SUCCESS và score hữu hạn chưa tự xác nhận tính hợp lý của kết quả.
- Mean score gộp theo job nhạy với scale điểm của instance lớn. Bảng Taguchi vì vậy bổ sung macro % cải thiện so baseline, tính trên mean từng instance rồi lấy trung bình 16 instance với trọng số bằng nhau.

## Coverage theo instance

| Instance | Hợp lệ / 30 | Đang chạy | Đang chờ trong batch | Cần chạy lại |
|---:|---:|---:|---:|---:|
| 1 | 30 / 30 | 0 | 0 | 0 |
| 2 | 30 / 30 | 0 | 0 | 0 |
| 9 | 30 / 30 | 0 | 0 | 0 |
| 10 | 30 / 30 | 0 | 0 | 0 |
| 17 | 30 / 30 | 0 | 0 | 0 |
| 18 | 30 / 30 | 0 | 0 | 0 |
| 25 | 30 / 30 | 0 | 0 | 0 |
| 26 | 30 / 30 | 0 | 0 | 0 |
| 33 | 30 / 30 | 0 | 0 | 0 |
| 34 | 30 / 30 | 0 | 0 | 0 |
| 41 | 30 / 30 | 0 | 0 | 0 |
| 42 | 30 / 30 | 0 | 0 | 0 |
| 49 | 30 / 30 | 0 | 0 | 0 |
| 50 | 30 / 30 | 0 | 0 | 0 |
| 57 | 30 / 30 | 0 | 0 | 0 |
| 58 | 30 / 30 | 0 | 0 | 0 |

## Coverage và điểm theo cấu hình

Điểm trung bình/độ lệch chuẩn bên dưới là thống kê mô tả của các repetition hợp lệ hiện có, gộp qua các instance có kích thước khác nhau. Không nên dùng riêng trung bình gộp này để so sánh nhân quả giữa cấu hình; hãy đối chiếu các dòng instance trong bảng master.

| Config | T | Population | Perturbation | Mutation | Hợp lệ / 48 | Đang chạy | Chờ | Cần chạy lại | Mean score | SD score |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 0.25 | 0.1 | 48 / 48 | 0 | 0 | 0 | 4062656.092 | 15654945.408 |
| 2 | 40 | 40 | 0.5 | 0.25 | 48 / 48 | 0 | 0 | 0 | 3323840.256 | 11101220.823 |
| 3 | 40 | 60 | 0.75 | 0.5 | 48 / 48 | 0 | 0 | 0 | 2042315.280 | 4278383.598 |
| 4 | 80 | 20 | 0.5 | 0.5 | 48 / 48 | 0 | 0 | 0 | 7915742.901 | 41664200.810 |
| 5 | 80 | 40 | 0.75 | 0.1 | 48 / 48 | 0 | 0 | 0 | 7496231.859 | 24228680.137 |
| 6 | 80 | 60 | 0.25 | 0.25 | 48 / 48 | 0 | 0 | 0 | 2125832.188 | 4246219.027 |
| 7 | 120 | 20 | 0.75 | 0.25 | 48 / 48 | 0 | 0 | 0 | 4115824.527 | 15722155.769 |
| 8 | 120 | 40 | 0.25 | 0.5 | 48 / 48 | 0 | 0 | 0 | 4777557.271 | 19364094.141 |
| 9 | 120 | 60 | 0.5 | 0.1 | 48 / 48 | 0 | 0 | 0 | 2232078.236 | 4666444.063 |
| 10 | 80 | 40 | 0.5 | 0.25 | 48 / 48 | 0 | 0 | 0 | 3610750.395 | 12165651.020 |

## Tóm tắt theo độ dài instance

Mỗi nhóm độ dài gồm hai instance và 60 job (10 cấu hình × 2 instance × 3 lần chạy). Biên score cho thấy scale của metric thay đổi theo kích thước; xem CSV để có thống kê từng cấu hình.

| Số đơn hàng | Instance | Hợp lệ / 60 | Score min | Score max |
|---:|---|---:|---:|---:|
| 50 | 1, 2 | 60 / 60 | 90.380 | 128.600 |
| 100 | 9, 10 | 60 / 60 | 159.340 | 170918.653 |
| 300 | 17, 18 | 60 / 60 | 78.060 | 1680.127 |
| 500 | 25, 26 | 60 / 60 | 3104.298 | 37173.156 |
| 1000 | 33, 34 | 60 / 60 | 1407.111 | 14665.027 |
| 2000 | 41, 42 | 60 / 60 | 31170.691 | 1499043.765 |
| 3000 | 49, 50 | 60 / 60 | 1157154.727 | 4930477.360 |
| 4000 | 57, 58 | 60 / 60 | 10040544.226 | 289106541.501 |

## Tóm tắt yếu tố Taguchi so với baseline

Metric phần trăm được tính theo từng instance: lấy mean score của ba repetition cho mỗi cấu hình/mức và baseline, tính `100 × (baseline_mean − score_mean) / baseline_mean`, rồi lấy trung bình trên 16 instance. Mỗi instance có trọng số như nhau; số dương tốt hơn baseline. Cột median là trung vị của 16 mức cải thiện theo instance. Đây là thống kê mô tả, không phải kiểm định ý nghĩa thống kê.

| Yếu tố | Mức | Config IDs | Instance đủ | Mean cải thiện macro (%) | Median cải thiện theo instance (%) | Instance tốt hơn / đủ |
|---|---:|---|---:|---:|---:|---:|
| T | 40 | 1,2,3 | 16 | +2.77 | +0.79 | 8 / 16 |
| T | 80 | 4,5,6 | 16 | -16.88 | -0.08 | 6 / 16 |
| T | 120 | 7,8,9 | 16 | -7.44 | -2.22 | 3 / 16 |
| population | 20 | 1,4,7 | 16 | +0.02 | +1.32 | 10 / 16 |
| population | 40 | 2,5,8 | 16 | -21.81 | -0.10 | 6 / 16 |
| population | 60 | 3,6,9 | 16 | +0.24 | -0.07 | 6 / 16 |
| perturbation | 0.25 | 1,6,8 | 16 | -10.85 | -0.85 | 5 / 16 |
| perturbation | 0.5 | 2,4,9 | 16 | -0.86 | -0.36 | 7 / 16 |
| perturbation | 0.75 | 3,5,7 | 16 | -9.83 | -0.25 | 6 / 16 |
| mutation_subset | 0.1 | 1,5,9 | 16 | -8.37 | +0.14 | 8 / 16 |
| mutation_subset | 0.25 | 2,6,7 | 16 | -3.71 | -0.07 | 6 / 16 |
| mutation_subset | 0.5 | 3,4,8 | 16 | -9.46 | -0.90 | 7 / 16 |

## Các key chưa có kết quả hợp lệ

| Config | Instance | Repetition | Tình trạng hiện tại |
|---:|---:|---:|---|

## Các batch follow-up instance 57–58

| Batch | Kỳ vọng | Đã ghi | Hợp lệ | Lỗi | Worktree fingerprint |
|---|---:|---:|---:|---:|---|
| `20261006_090008` | 24 | 24 | 24 | 0 | `9ffb9b681ae3cbd789021dba5bc46a5761281b8a7560533ea147333a8a69bc6c` |
| `20261009_015120` | 36 | 36 | 36 | 0 | `1d9f93ccf387c5fc5c3fcafe5d37d364971ac25de57caf0a16dc826d59f10958` |

- Hai batch có 60/60 key khác nhau của cohort instance 57–58; canonical results được lấy từ hai batch cho 60/60 key.
- Hai manifest ghi cùng Git revision `51e499a23acfaac6ae90a643200f574ae6b20c2f`, nhưng worktree fingerprints khác nhau. Fingerprint được giữ làm metadata truy nguyên; theo xác nhận của người dùng, toàn bộ 60 run 57–58 đều hợp lệ và được đưa vào phân tích.
- [Dữ liệu 480 job đã sắp theo số lượng đơn hàng](sensitivity_jobs_by_length.csv); [tóm tắt theo độ dài và cấu hình](sensitivity_summary_by_length.csv). Tỷ lệ score so với baseline được ghép theo cùng instance/repetition.

## Review of evidence

### CONFIRMED

- Có 480/480 key thiết kế với kết quả canonical hợp lệ theo ledger: trạng thái SUCCESS, score hữu hạn/không âm và seed đúng.
- Cohort follow-up 57–58 có 60/60 key được chọn từ hai batch đã ghi nhận kết quả hợp lệ.

### EXPLORATORY

- Bảng score và hiệu ứng Taguchi là thống kê mô tả; chưa có kiểm định suy luận hoặc cohort xác nhận độc lập cho cấu hình dự đoán.
- Các điểm 57–58 từ 9 key vượt ngưỡng rà soát 5× median của cùng instance; đây là cờ kiểm tra chất lượng, không tự chứng minh lỗi thuật toán:
  - Config 4, instance 57, repetition 1: 289106541.501 (source `20261006_090008`).
  - Config 8, instance 57, repetition 1: 132743987.723 (source `20261006_090008`).
  - Config 5, instance 58, repetition 3: 113610558.335 (source `20261009_015120`).
  - Config 7, instance 57, repetition 2: 107246473.161 (source `20261006_090008`).
  - Config 1, instance 57, repetition 2: 106577225.892 (source `20261009_015120`).
  - Config 5, instance 58, repetition 2: 94988102.877 (source `20261009_015120`).
  - Config 5, instance 58, repetition 1: 88057512.195 (source `20261009_015120`).
  - Config 10, instance 57, repetition 2: 81201364.193 (source `20261009_015120`).
  - Config 2, instance 58, repetition 3: 73662317.078 (source `20261009_015120`).

### FAILED / INCOMPLETE

- Tại snapshot này: 0 key chưa có kết quả hợp lệ; 0 key RUNNING; 0 key QUEUED; 0 key cần chạy lại.
- Attempt ledger giữ 946 dòng kết quả không hợp lệ/lỗi đã ghi; 216 worker log không có result JSONL cuối được giữ riêng và không được nâng thành success.
- Lý do invalid phổ biến: missing_score=804, worker_failure=84, sentinel_score=58

### HIGHEST VERIFIED RUNG

- Coverage 480/480 key đã hoàn tất; theo xác nhận của người dùng, toàn bộ kết quả được xem là hợp lệ và được đưa vào phân tích. R7 (quyết định cấu hình tối ưu dựa trên cohort xác nhận) chưa đạt.

### EVIDENCE GAPS

- Fingerprint thiếu/khác được giữ để truy nguyên nhưng không dùng loại các run khỏi phân tích theo xác nhận của người dùng.
- Có 3 repetition mỗi key; chưa có kiểm định suy luận. Các score ngoại lệ có thể ảnh hưởng mean/S/N và nên được đọc cùng macro improvement, median instance và thống kê theo độ dài.

### RECOMMENDED NEXT

- Nếu cần chốt cấu hình tối ưu, chạy cohort xác nhận cùng instance/seed cho tổ hợp Taguchi dự đoán, Config 3, Config 6 và baseline; báo cáo mean score cùng macro % cải thiện, median theo instance và score thành phần.

480-job coverage is complete; a definitive R7 configuration decision remains unverified.

## Quy tắc chọn và giới hạn dữ liệu

- Master có đúng một dòng cho mỗi key thiết kế. Nếu có nhiều kết quả hợp lệ cho cùng key, ưu tiên kết quả hợp lệ có fingerprint code hiện tại; nếu không có, chọn kết quả hợp lệ mới nhất theo thời gian archive. Attempt CSV giữ nguyên mọi dòng đã ghi để truy nguyên các lần lặp/lỗi.
- Các lần không có kết quả hợp lệ vẫn có dòng trong master; trường điểm, distance, runtime và source của kết quả hợp lệ để trống. Trạng thái và thông tin attempt lỗi gần nhất được giữ riêng để theo dõi.
- Các run archive cũ không có code fingerprint trong manifest được để trống fingerprint, không suy đoán provenance.
- Số attempt đã ghi: 1674; số attempt hợp lệ: 728; attempt có seed không khớp: 0.
- Có 216 worker log lịch sử không có dòng result JSONL; 0 log có ghi score. Các score chỉ được giữ ở cột `log_observed_score`, không được tính là kết quả hợp lệ vì thiếu record cuối và return code.
