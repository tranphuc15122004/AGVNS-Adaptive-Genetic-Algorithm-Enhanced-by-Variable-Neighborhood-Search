# Phân tích độ nhạy tham số AGVNS

> **Bản nháp Markdown để duyệt nội dung trước khi chuyển sang định dạng paper.** Phân tích dùng đủ 480 run theo thiết kế sensitivity hiện tại.

## Thiết kế thí nghiệm và metric

Thí nghiệm gồm chín cấu hình theo thiết kế Taguchi L9 và một cấu hình tham chiếu (Config 10). Bộ dữ liệu có 16 instance, gồm hai instance ở mỗi nhóm kích thước 50, 100, 300, 500, 1.000, 2.000, 3.000 và 4.000 đơn hàng. Mỗi cấu hình được chạy ba lần trên mỗi instance, tổng cộng 480 run, tương ứng 48 run cho mỗi cấu hình. Seed được xác định theo công thức 20260824 + 1000 × instance_id + repetition.

Bốn yếu tố được khảo sát là ngưỡng thích nghi T ∈ {40, 80, 120}, kích thước quần thể P ∈ {20, 40, 60}, mức perturbation ρpert ∈ {0,25; 0,50; 0,75} và tỷ lệ mutation subset ρmut ∈ {0,10; 0,25; 0,50}. Config 10 có cấu hình (T, P, ρpert, ρmut) = (80, 40, 0,50, 0,25) và được dùng làm tham chiếu.

Điểm simulator là metric cần tối thiểu hóa. Báo cáo giữ mean score gộp và S/N theo công thức smaller-is-better, đồng thời dùng hai metric tương đối để giảm ảnh hưởng của chênh lệch scale giữa các instance. Với S/N = −10 log10(mean(score²)), giá trị lớn hơn (ít âm hơn) tốt hơn. Với cấu hình c và instance i, gọi mean(c,i) là mean score của ba repetition. Phần trăm cải thiện trên instance được tính như sau:

> improvement(c, i) = 100 × [mean(Config 10, i) − mean(c, i)] / mean(Config 10, i)

Macro improvement là trung bình cộng của 16 phần trăm cải thiện theo instance; median instance improvement là trung vị của cùng 16 giá trị. Số dương nghĩa là cấu hình có score thấp hơn baseline. Hai metric này cho mỗi instance trọng số ngang nhau; chúng bổ sung chứ không thay thế mean score gộp. Macro percentage vẫn có thể nhạy với instance có baseline nhỏ hoặc biến động bất thường, nên được đọc cùng median và thống kê theo từng nhóm kích thước.

## So sánh các cấu hình đã chạy

Bảng dưới đây là kết quả chính vì nó so sánh trực tiếp các cấu hình đã được chạy. Mean score và S/N được tính trên 48 run của mỗi cấu hình. Hai cột phần trăm được tính bằng cách tổng hợp repetition trong từng instance trước, rồi mới lấy trung bình hoặc trung vị trên 16 instance.

| Config | T | P | ρpert | ρmut | Mean score (×10⁶) | S/N (dB) | Macro improvement (%) | Median instance improvement (%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 0,25 | 0,10 | 4,063 | -144,090 | +5,12 | +0,47 |
| 2 | 40 | 40 | 0,50 | 0,25 | 3,324 | -141,196 | -2,06 | +0,08 |
| **3** | **40** | **60** | **0,75** | **0,50** | **2,042** | **-133,443** | **+5,26** | +0,09 |
| 4 | 80 | 20 | 0,50 | 0,50 | 7,916 | -152,461 | -5,63 | +0,11 |
| 5 | 80 | 40 | 0,75 | 0,10 | 7,496 | -148,000 | -35,34 | 0,00 |
| 6 | 80 | 60 | 0,25 | 0,25 | 2,126 | -133,458 | -9,67 | -0,19 |
| 7 | 120 | 20 | 0,75 | 0,25 | 4,116 | -144,133 | +0,59 | -0,06 |
| 8 | 120 | 40 | 0,25 | 0,50 | 4,778 | -145,910 | -28,02 | -3,23 |
| 9 | 120 | 60 | 0,50 | 0,10 | 2,232 | -134,200 | +5,11 | 0,00 |
| 10 (baseline) | 80 | 40 | 0,50 | 0,25 | 3,611 | -141,985 | 0,00 | 0,00 |

Config 3 có mean score gộp thấp nhất trong chín cấu hình L9 (2,042 × 10⁶), tiếp theo là Config 6 (2,126 × 10⁶) và Config 9 (2,232 × 10⁶). Mean score gộp của Config 3 thấp hơn baseline 43,4%; S/N của nó chỉ cao hơn Config 6 khoảng 0,015 dB. Khi mỗi instance được cân ngang nhau, Config 3 cải thiện trung bình 5,26%, nhưng median cải thiện chỉ là 0,09%. Config 1 và Config 9 đạt macro improvement lần lượt 5,12% và 5,11%, chỉ cách Config 3 tối đa 0,15 điểm phần trăm. Vì vậy, các chênh lệch tương đối này mang tính mô tả và chưa cho thấy Config 3 vượt trội rõ rệt.

Theo mean từng instance, Config 3 có score thấp hơn baseline ở 8/16 instance, cao hơn ở 6/16 và bằng ở 2/16. Kết quả tốt nhất theo mean gộp vì thế không đồng nghĩa với cải thiện đồng đều trên benchmark.

## Hiệu ứng biên theo thiết kế Taguchi

Trong L9, mỗi mức của mỗi yếu tố xuất hiện ở ba cấu hình. Vì vậy, response tại một mức là response biên đã được gộp qua các thiết lập của những yếu tố còn lại trong các cấu hình đó; đây không phải phép so sánh một-yếu-tố-mỗi-lần trong đó mọi yếu tố khác được giữ cố định. Bảng sau trình bày mean score gộp trên 144 run ở mỗi mức và phần trăm cải thiện theo instance so với baseline.

| Yếu tố | Mức | Mean score (×10⁶) | Macro improvement (%) | Median instance improvement (%) |
|---|---:|---:|---:|---:|
| T | 40 | 3,143 | +2,77 | +0,79 |
| T | 80 | 5,846 | -16,88 | -0,08 |
| T | 120 | 3,708 | -7,44 | -2,22 |
| P | 20 | 5,365 | +0,02 | +1,32 |
| P | 40 | 5,199 | -21,81 | -0,10 |
| P | 60 | 2,133 | +0,24 | -0,07 |
| ρpert | 0,25 | 3,655 | -10,85 | -0,85 |
| ρpert | 0,50 | 4,491 | -0,86 | -0,36 |
| ρpert | 0,75 | 4,551 | -9,83 | -0,25 |
| ρmut | 0,10 | 4,597 | -8,37 | +0,14 |
| ρmut | 0,25 | 3,188 | -3,71 | -0,07 |
| ρmut | 0,50 | 4,912 | -9,46 | -0,90 |

Nếu xếp mức theo pooled mean/S/N, các mức có response tốt nhất lần lượt là T=40, P=60, ρpert=0,25 và ρmut=0,25. Theo macro improvement, lựa chọn thay đổi ở perturbation thành 0,50; P=20 (+0,02%) và P=60 (+0,24%) gần như hòa theo macro mean. Median instance lại ưu tiên P=20, ρpert=0,75 và ρmut=0,10. Các metric do đó không chỉ ra một tổ hợp mức thắng theo mọi cách tổng hợp.

Biên độ macro giữa mức cao nhất và thấp nhất là 22,04 điểm phần trăm với population size, 19,65 điểm với threshold, 9,99 điểm với perturbation và 5,75 điểm với mutation subset. Đây là độ lớn chênh lệch mô tả trong thiết kế hiện tại, không phải kiểm định ý nghĩa thống kê hay bằng chứng về tác động nhân quả độc lập.

## Khác biệt theo quy mô instance

Kết quả Config 3 so với baseline thay đổi theo nhóm số đơn hàng. Phần trăm dưới đây là trung bình đều trên hai instance của mỗi nhóm.

| Số đơn hàng | Macro improvement của Config 3 (%) |
|---:|---:|
| 50 | +1,14 |
| 100 | -7,48 |
| 300 | -1,76 |
| 500 | -27,21 |
| 1.000 | -21,56 |
| 2.000 | +51,61 |
| 3.000 | +12,36 |
| 4.000 | +35,00 |

Config 3 có cải thiện tương đối ở các nhóm 2.000–4.000 đơn hàng, trong khi suy giảm ở nhóm 500 và 1.000 đơn hàng. Mỗi nhóm chỉ có hai instance, do đó đây là dấu hiệu mô tả để định hướng nghiên cứu tiếp theo, chưa đủ để kết luận rằng cấu hình này luôn phù hợp hơn cho một quy mô cụ thể.

## Kết luận

Trong các cấu hình đã chạy, Config 3 dẫn đầu theo pooled mean score và đạt macro improvement cao nhất, nhưng lợi thế theo instance-equal metric so với Config 1 và Config 9 rất nhỏ; median của nó cũng chỉ nhỉnh hơn baseline 0,09%. Kết quả ủng hộ việc báo cáo song song mean score gộp và metric phần trăm cân bằng theo instance, thay vì dùng một mean duy nhất cho benchmark có scale điểm khác nhau đáng kể.

Các hiệu ứng Taguchi nên được diễn giải như main effects biên của thiết kế L9. Chín cấu hình không đủ để phân tích riêng mọi tương tác giữa bốn yếu tố; vì vậy không nên xem các mức ghép tốt nhất theo main effect là cấu hình tối ưu đã được xác nhận. Không có kiểm định suy luận hoặc cohort xác nhận độc lập trong phân tích này. Một nghiên cứu tiếp theo nên chạy các cấu hình ứng viên và baseline trên cùng tập instance với nhiều seed hơn, đồng thời báo cáo score tổng hợp và các thành phần distance/overtime.

## Nguồn số liệu

- [Bảng kết quả master 480 run](sensitivity_results_master.csv)
- [Bảng hiệu ứng Taguchi theo mức](sensitivity_factor_effects.csv)
- [Báo cáo sensitivity chi tiết](sensitivity_taguchi_interpretation.md)

