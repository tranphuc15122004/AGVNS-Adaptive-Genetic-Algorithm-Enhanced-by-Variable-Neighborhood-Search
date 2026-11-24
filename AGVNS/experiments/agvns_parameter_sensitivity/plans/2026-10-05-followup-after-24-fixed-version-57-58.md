# Kế hoạch tiếp tục sensitivity instance 57–58 sau batch 24 job

## Mục tiêu

Sau khi batch `20261005_014745` kết thúc, kiểm tra đủ 24 job, bổ sung các kết quả còn thiếu để hoàn thành cohort đồng nhất phiên bản code cho instance 57–58, rồi cập nhật bảng sensitivity. Không dùng chung để xếp hạng với kết quả từ các fingerprint code cũ.

## Trạng thái được ghi nhận

- Batch cũ: `AGVNS/experiments/agvns_parameter_sensitivity/runs/20261005_014745`.
- Batch cũ có 24 job, 12 worker, core `0–11`; tại snapshot `2026-10-06`, runner đã dừng, chỉ có 12 workspace của instance 57, không có ledger/summary và 12 key chưa được khởi chạy. Mỗi workspace mới đến simulated time 00:40; các dòng `SUCCESS` trong log là thành công của từng lượt gọi thuật toán, không phải hoàn tất job simulator.
- Batch tiếp tục hiện tại: `AGVNS/experiments/agvns_parameter_sensitivity/runs/20261006_090008`, 24 job, 12 worker, core `0–11`. Runner đã được khởi chạy trong tmux session `agvns_sensitivity_20261006` để tiếp tục sau shell session.
- Fingerprint worktree của batch cũ: `afa5adc6e9179ded92e745598ca8212186c83932472b9c53f3ef09b95c173b4b`; batch mới: `9ffb9b681ae3cbd789021dba5bc46a5761281b8a7560533ea147333a8a69bc6c`; cả hai revision `51e499a23acfaac6ae90a643200f574ae6b20c2f`. Hash worktree mới đổi sau khi lưu các tài liệu kế hoạch; trong lần tiếp tục này không chỉnh sửa file thuật toán. Khi tổng hợp, ghi rõ cả hash và xác nhận danh tính source thuật toán trước khi gộp các kết quả cũ.
- Tại lúc khởi chạy batch mới: 12 job đầu đã được launch, 12 job chờ queue, chưa có result row/score cuối hay lỗi được ghi nhận.
- Trước batch này có 10 success cùng fingerprint: 7 job của instance 57 và 3 job ở instance 49/50. Bảy job instance 57 có runtime stats và log cuối để đối chiếu nhưng chưa có dòng trong `results.jsonl`.
- Nếu 24 job hiện tại đều hợp lệ và 7 job cũ được đối chiếu là cùng source thuật toán, cohort 57–58 có 31/60 kết quả: còn 6 key của instance 57 và 23 key của instance 58, tổng 29 job. Nếu yêu cầu strict cùng full worktree fingerprint, cần chạy lại 7 key cũ bên cạnh 29 key này (36 job).

## Các bước sau khi batch 24 job kết thúc

- [in_progress] 1. Để batch `20261006_090008` hoàn tất; sau đó đối chiếu manifest, result ledger, runtime stats và từng worker log cho đủ 24 key. Chỉ tính job hoàn thành khi có trạng thái cuối thành công, score hữu hạn/hợp lệ và bằng chứng đầu ra tương ứng.
- [pending] 2. Nếu có job fail, thiếu ledger hoặc score không hợp lệ, khoanh đúng key đó và chạy lại bằng cùng fingerprint/seed; giữ concurrency không quá 15 core (mặc định 12 worker như batch hiện tại).
- [in_progress] 3. Sau wave 24, tính lại tập key hợp lệ trong result ledger của fingerprint hiện tại. Kế hoạch chạy lại toàn bộ key target chưa có SUCCESS hợp lệ, kể cả 7 success ở fingerprint cũ.
- [in_progress] 4. Tự sinh danh sách key thiếu từ toàn bộ `configuration 1–10 × instance 57,58 × repetition 1–3`; dự kiến 36 key nếu wave 24 đều success. Nếu wave hiện tại có failure/thiếu ledger, thêm các key đó vào danh sách.
- [in_progress] 5. Đợi wave 24 kết thúc rồi chạy wave follow-up bằng batch riêng, không ghi đè artifact cũ; giữ seed formula `20260824 + instance_id * 1000 + repetition`, 12 worker/core 0–11. Sequencer tmux bảo đảm không chạy chồng wave.
- [pending] 6. Đối chiếu đủ 60/60 key, tính lại CSV/Markdown theo config và instance (n hợp lệ, mean, độ lệch chuẩn, min, max), ghi rõ fingerprint và nguồn từng dòng.
- [pending] 7. Diễn giải kết quả như đánh giá sensitivity sơ bộ trên hai instance lớn; không kết luận cấu hình tốt hơn toàn benchmark chỉ từ 57–58 hoặc từ các kết quả trộn phiên bản.

## Phạm vi rộng hơn và tiêu chí hoàn tất

- Cohort mục tiêu của kế hoạch này là 60 job cho hai instance lớn. Để có ma trận 480 job so sánh đồng nhất trên toàn bộ 16 instance, sau khi chốt cohort 57–58 cần tiếp tục chạy các key còn lại bằng cùng fingerprint; 446 key còn lại là ước tính nếu toàn bộ 34 kết quả cùng fingerprint hiện tại đều hợp lệ.
- Hoàn tất kế hoạch 57–58 khi mọi key của cohort có kết quả hợp lệ, artifact ledger khớp nguồn, báo cáo được cập nhật và mọi ngoại lệ được để trống/ghi rõ thay vì nội suy.

## Lỗi/điều kiện môi trường đã gặp

| Sự cố | Xử lý |
|---|---|
| Lần khởi chạy `20261005_014653` lỗi import `simpy` do dùng Python mặc định | Dùng `/home/tuantb/miniconda3/bin/python` cho các lần chạy tiếp theo; batch mới cũng dùng interpreter này. Không tính lần khởi chạy lỗi môi trường là kết quả thuật toán. |
| Batch `20261005_014745` dừng khi 12 workspace mới chạy tới simulated time 00:40 | Không có result ledger/summary hoặc traceback ghi rõ nguyên nhân. Giữ nguyên artifact dở dang, khởi chạy lại đủ 24 key trong batch mới `20261006_090008`; không coi 12 workspace là success. |
| Không xác định được sự kiện kết thúc chính xác của `20261005_014745` | Batch được khởi chạy gắn với phiên exec foreground; đến ngày 2026-10-06 phiên `74191` trả `Unknown process id`, runner không còn, log không có exit code/signal. Khả năng phù hợp nhất là phiên exec hoặc môi trường đã kết thúc runner; không có bằng chứng để khẳng định OOM hay lỗi thuật toán. Batch mới dùng tmux detached. |
| Patch cập nhật kế hoạch một lần không khớp anchor | Đọc lại đoạn hiện tại và áp dụng patch theo đúng nội dung; lần patch lỗi không sửa file. |

## Snapshot batch đang chạy — 2026-10-06

- Tmux `agvns_sensitivity_20261006` còn hoạt động; 12 worker đã được launch trên core 0–11, 12 key còn lại đang đợi queue.
- Có 12 worker log, chưa có dòng trong `results.jsonl`; 12 key đã tiến tới simulated time 00:50, log cập nhật đến 09:38 UTC, không thấy traceback/ERROR.
- Đã kiểm tra affinity: 12 process simulator lần lượt được pin vào core 0,1,…,11; các tiến trình tìm kiếm thuật toán đang dùng các core này. Đây là wave đầu, runner sẽ cấp key chờ tiếp khi worker hoàn tất.
- Tmux `agvns_sensitivity_followup_20261006` đang chờ wave đầu kết thúc. Sau đó script sẽ đọc ledger, nhận SUCCESS chỉ khi status/return code/score hợp lệ, rồi sinh các key còn thiếu trên 60-key cohort và chạy tối đa 12 worker. Khi 24 job hiện tại đều hợp lệ, wave tiếp theo dự kiến là 36 job: 7 key cũ được chạy lại dưới hash mới và 29 key chưa chạy.

## Điểm tiếp tục

Sau khi wave hiện tại kết thúc, sequencer sẽ đối chiếu ledger và chạy các key còn thiếu trong 60-key cohort bằng wave follow-up; sau cả hai wave, kiểm tra score/lỗi và cập nhật bảng.
