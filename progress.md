# Progress — EvoRL aggregation

---

# Progress — LaTeX Workshop configuration

## Session log

- Đã đọc lại context sau session trước và xác nhận PDF Springer đã build thành công.
- Đã khảo sát `.vscode/settings.json`: chỉ có Python settings, chưa có LaTeX Workshop.
- Đã xác nhận engine khả dụng ở `/home/tuantb/bin/` và kiểm tra tài liệu chính thức về
  recipe/tool/placeholder của LaTeX Workshop.
- Đã trình bày phạm vi bounded; chưa ghi cấu hình vì còn chờ người dùng duyệt thiết kế.
- Người dùng đã duyệt thiết kế; đã cập nhật `.vscode/settings.json` với recipe
  `pdflatex → bibtex → pdflatex → pdflatex`, output `paper/build/` và `TEXMFVAR` local.
- Đã sửa cách gọi BibTeX thành `cwd=%DIR%`, argument `build/%DOCFILE%` sau khi kiểm tra
  đường dẫn tuyệt đối bị `openout_any` chặn và `cwd=%OUTDIR%` không thấy file `.bib`.
- JSON hợp lệ; recipe đầy đủ chạy với 4/4 bước exit code `0`.
- PDF cuối 31 trang A4, có SyncTeX; log không có fatal error hoặc undefined citation/reference.

---

# Progress — Statistical Validation update

## Session log

- Người dùng xác nhận kiểm định phải bao gồm đủ 7 thuật toán trong các bảng chính,
  bổ sung Evo-RL vào Friedman và sáu so sánh Wilcoxon/Holm.
- Đã tạo `analysis/paper_statistical_validation.py` và test `analysis/test_paper_statistical_validation.py`.
- TDD đã được kiểm tra: test ban đầu fail vì module/parser chưa tồn tại, sau đó 3 test pass.
- Script đọc trực tiếp các dòng HW1--HW64, sinh JSON thống kê và cập nhật phần
  `Statistical Validation` trong `paper/main_Springer_8.2026.tex`.
- Đã xóa các block thống kê cũ bị comment để không còn số liệu 6 thuật toán lỗi thời.
- Recipe LaTeX Workshop `pdflatex → bibtex → pdflatex → pdflatex` chạy 4/4 bước exit code `0`.
- PDF cuối: 31 trang A4; log không có fatal error, undefined citation/reference hoặc
  duplicate label. Nội dung PDF chứa các số liệu mới 234.176, 9.83e-48, 6.781 và Evo-RL.

---

# Progress — Statistical Validation audit

- Đã đọc lại định nghĩa objective: bài toán minimization, objective thấp hơn là tốt hơn.
- Đã đối chiếu độc lập bằng R: 64 blocks × 7 thuật toán; mọi rank, Friedman,
  Wilcoxon asymptotic/no-correction và Holm đều khớp với Python.
- Đã kiểm tra các phương án Wilcoxon exact/approx: các p-value trong LaTeX đúng theo
  asymptotic/no-correction; exact sẽ cho số khác, nên đây là điểm phương pháp cần ghi rõ.
- Đã cập nhật bảng summary và đoạn diễn giải liên quan: Gold là 44/64 và Set 4 là 7/8,
  khớp HW28 trong bảng objective.
- Đã bổ sung vào subsection mô tả đầy đủ quy ước Wilcoxon asymptotic/no-correction,
  zero-difference và average ranks cho tied absolute differences.

---

# Progress — LaTeX paper compilation

## Session log

- Đã đọc các skill bắt buộc cho tác vụ nhiều bước.
- Đã phát hiện và giữ nguyên các thay đổi/workflow EvoRL có sẵn trong workspace.
- Đang ở phase khảo sát cấu trúc `paper/`.
- Đã chạy lần build đầu trong `paper/build/`; `pdflatex` dừng trước khi tạo PDF vì
  `sn-jnl.cls` gọi `\usepackage{cuted}` nhưng `cuted.sty` chưa có trong TinyTeX.
- Đã kiểm tra lại context class và `kpsewhich`; đây là lỗi dependency môi trường, không
  phải lỗi cú pháp ở nội dung source.
- Đã xác định `cuted.sty` thuộc package TeX Live `sttools`; lần cài đầu bị `tlmgr` chặn
  vì yêu cầu `tlmgr update --self` trước.
- Đã cập nhật `tlmgr` và cài thành công `sttools`; build tiếp theo đã qua `cuted.sty`
  nhưng dừng ở dependency kế tiếp `wrapfig.sty` của `sn-jnl.cls`.
- Đã cài `wrapfig`; build đã qua toàn bộ dependency và dừng tại bảng thống kê line 1092.
  Test tối giản cho thấy nguyên nhân là `resizebox` bên trong `threeparttable`; test thay
  bằng `tabular*` đã pass, đủ cơ sở cho fix tối thiểu ở source chính.
- Đã áp dụng thay thế 3 bảng thống kê trong `main_Springer_8.2026.tex`; lỗi source line
  1092 biến mất. Lần build này chỉ còn lỗi môi trường khi TinyTeX cố ghi font PK vào
  `/home/tuantb/.TinyTeX/texmf-var` (read-only), nên cần chuyển `TEXMFVAR` vào build dir.
- Đã chuyển `TEXMFVAR` sang `paper/build/texmf-var`; recipe `pdflatex → bibtex →
  pdflatex → pdflatex` và một pass `pdflatex` verification cuối đều exit code 0.
- PDF cuối là 31 trang A4 tại `paper/build/main_Springer_8.2026.pdf`; kiểm tra log không
  còn fatal error hoặc undefined citation/reference. Chỉ còn các warning layout/glossary
  không chặn build.

## Session log

- Bắt đầu tác vụ tổng hợp 5 lần chạy.
- Đã đọc hướng dẫn planning-with-files và tạo các file kế hoạch.
- Đã xác định nguồn hợp lệ: batch hiện tại `20260819_094955` (256/256 SUCCESS)
  và reference 64-instance `EvoRL_results_64_instances.csv` (64/64 SUCCESS).
- Đã loại batch `20260818_143854` vì chưa có kết quả hoàn tất.
- Đã tạo `EvoRL/analysis/aggregate_evorl_runs.py`, CSV tổng hợp 64 instance và báo cáo Markdown.
- Verification pass: 320 dòng nguồn hợp lệ, 64 dòng aggregate, kiểm tra 128 công thức tổng hợp,
  không có lỗi trạng thái.

---

# Progress — Điều tra lỗi AGVNS parameter sensitivity

## Session log

- Đã đọc lại skill bắt buộc và design/plan hiện có của experiment sensitivity.
- Đã xác định scope: kiểm tra lỗi của batch đang có, không thay đổi implementation.
- Đã bắt đầu phase 1: cần đối chiếu process/runtime với run artifacts.

## Evidence cập nhật

- Xác định run hiện tại là `20260824_162057`; manifest 480 job, results 46 dòng,
  5 SUCCESS/41 FAILED, filesystem 62 worker directories.
- Phân loại 41 lỗi: 37 simulator timeout sau giới hạn 600 giây cho một dispatch;
  4 `IndexError` tại `GAVND7.py:188` khi `unique_population` rỗng sau lọc.
- Xác định 16 job chưa được ghi vào results ledger; không có process sensitivity còn
  sống trong namespace sandbox; kiểm tra ngoài sandbox xác nhận runner vẫn sống với
  16 worker đang chạy. `tmux` chỉ bị hạn chế socket trong sandbox.
- Phát hiện lỗi kiểm tra tạm thời: công thức đối chiếu score ban đầu bỏ qua `/100`
  cho `total_distance`; đã loại kết quả kiểm tra đó và ghi lại công thức đúng.
- Live check: tmux `agvns_taguchi_screening`, runner PID `2176437`, 16 worker đang
  chạy; 418 job còn pending tại thời điểm snapshot.

## Snapshot live cập nhật — 2026-08-27 03:54:28 UTC

- Runner vẫn hoạt động; 16 worker `AGVNS/main.py` cùng các algorithm subprocess đang
  chạy. Worker lâu giờ ở instance 57/58 được xem là thời gian xử lý nhiều tick của
  một instance, chưa kết luận là deadlock.
- Ledger: 47/480 dòng, 5 SUCCESS và 42 FAILED; 38 timeout, 4 `IndexError`; 63
  workspace, 16 đang chạy, 417 job chưa launch/ghi kết quả.
- Timeout dispatch: min 572.418s, max 597.751s, mean 587.484s; giới hạn outer
  simulator là 600s.
- Kiểm tra truyền tham số đã hoàn tất: 62/62 log khớp cấu hình/seed kỳ vọng; không
  thấy OOM, lỗi disk, permission hoặc signal.

## Phân tích cơ chế lỗi

- Bốn `IndexError` cùng nằm ở mutation level 0.50, nhưng nguyên nhân chắc chắn là
  `unique_population` có thể rỗng sau filter và GAVND7 không có fallback/elitism.
- Timeout đại diện ở tick cuối không có `Applied AGVNS experiment config`, nên xảy
  ra trước GAVND7; luồng có khả năng cao là `new_dispatch_new_orders()` gọi
  `dispatch_nodePair()` với các vòng lồng nhau không có `is_timeout()`.
- `ALGO_TIME_LIMIT=570s` không đủ an toàn so với outer 600s khi các thao tác vượt
  deadline ở giữa vòng; timeout check tại biên vòng không tạo hard deadline.

## Khuyến nghị khắc phục

- Guard + fallback `best_solution` và elitism trong GAVND7.
- Propagate deadline xuống CI/insertion/initialization; fallback nhanh khi hết ngân sách.
- Chừa 50--60s cho output/shutdown, sau đó benchmark lại đồng nhất toàn design.
- Kill process group khi timeout và ghi `SystemExit` thành FAILED runtime stats.
- Tạo run mới sau smoke tái hiện; không dùng `--resume` trên batch lỗi để lấy số liệu
  chính thức.

## Phát hiện ảnh hưởng đến validity của sensitivity

- Initial population đang bỏ qua `config.PERTURBATION_RATE` và dùng hằng số `0.5`
  tại `new_engine.py:693`.
- ERFC hard-cut ratio về 0 khi `num_orders >= T`; workload 370--580 và T 40/80/120
  làm mọi config lớn quan sát được có ratio 0. Cần xử lý/ghi rõ điều này trước khi
  dùng rerun làm kết luận sensitivity.

## Root-cause conclusion

- Root cause chính: thời gian một dispatch ở instance lớn chạm/vượt giới hạn 600s.
- Root cause độc lập: `unique_population` bị lọc về rỗng rồi vẫn truy cập phần tử `[0]`
  tại `GAVND7.py:188`.
- Observability/runner risk: `SystemExit` không đi vào `except Exception` của
  `AGVNS/main.py`, nên job FAILED không có runtime_stats cuối; `aggregate_run()` chỉ
  chạy sau khi toàn bộ scheduler kết thúc; `--resume` chỉ bỏ qua SUCCESS và có thể
  ghi đè log lỗi cũ. Đây là rủi ro thiết kế được xác định qua code, chưa phải một
  lỗi mới phát sinh trong snapshot hiện tại.

## Files created/modified

- `task_plan.md` (bổ sung kế hoạch điều tra)
- `findings.md` (bổ sung evidence điều tra)
- `progress.md` (bổ sung log điều tra)

## Error log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-08-27 | Patch anchor không tồn tại | 1 | Đọc tail file và patch append theo anchor ổn định |
| 2026-08-27 | Diagnostic config audit `TypeError` do cộng `int` với `str` khi dựng tuple kỳ vọng | 1 | Bỏ phép dựng tuple thủ công, đối chiếu trực tiếp với `configuration_by_id()` |
| 2026-08-27 | Diagnostic score audit cho sai số vì quên chia distance cho 100 xe | 1 | Chạy lại với công thức score đầy đủ; kết luận metric SUCCESS phù hợp |

## Session log — bỏ outer timeout và rerun timeout jobs

- Người dùng đã xác nhận triển khai: default runner timeout=0, giữ CLI opt-in,
  và rerun các timeout jobs.
- Đã kiểm tra: worktree có thay đổi chưa commit; sẽ chỉ chỉnh runner/docs/test trong
  phạm vi yêu cầu.
- Đã xác định cần filter theo `results.jsonl`, không dùng `--resume` trực tiếp vì
  resume hiện chỉ bỏ qua SUCCESS.

## 2026-08-28 — Runner change implemented

- Đã thêm test RED rồi sửa `run_screening.py`: default `--job-timeout-seconds=0`;
  vẫn cho phép bật guard bằng giá trị dương.
- Đã thêm `--retry-timeouts-from`, lọc chính xác các record FAILED chứa
  `outer job wall-time exceeded` và tạo run directory mới.
- Đã cập nhật README, manifest rerun sẽ lưu nguồn batch cũ.
- GREEN: `pytest -q tests/test_agvns_parameter_sensitivity.py` → 6 passed;
  dry-run nguồn `20260827_144605` → 32 jobs.
- Full `pytest -q` chưa thu thập được do các test ở nhiều variant dùng chung tên
  module nhưng khác `sys.path`; lỗi nằm ở test collection hiện hữu, ngoài phạm vi
  runner sensitivity.
- Đã khởi chạy run mới `20260828_080018` với 32 jobs, 16 workers, cores 0--15,
  `job_timeout_seconds=0.0`; manifest đã ghi nguồn `20260827_144605`. Các worker
  đầu tiên đang xử lý instance 57, chưa có result row tại thời điểm ghi nhận.

## 2026-08-28 — tmux rerun and worker log isolation

- Lần khởi chạy tmux `20260828_090319` bị dừng sau khi phát hiện logger race: các
  worker cùng gọi `delete_files()` trên `AGVNS/src/output/log`; một job lỗi
  `FileNotFoundError` khi xóa log của worker khác.
- Đã dừng đúng các child process thuộc run lỗi, không dừng batch cũ.
- Đã thêm `AGVNS_OUTPUT_DIR` theo workspace vào runner và cho `Configs.output_folder`
  đọc biến môi trường, để mỗi worker có `output/log` riêng.
- Test sensitivity sau thay đổi: `7 passed`; kiểm tra runtime tạo được log riêng
  cho từng workspace và không có traceback ở thời điểm khởi động.
- Đã khởi động lại tmux session `agvns_sensitivity_large_first_20260828`, run
  `20260828_090646`: 480 jobs, 16 workers, bắt đầu từ instance 57, outer timeout 0.

## 2026-10-05 — Lưu kế hoạch tiếp tục sensitivity 57–58

- Đã đọc skill `planning-with-files`, kiểm tra session catch-up (không có nội dung
  chưa đồng bộ), đọc lại trạng thái kế hoạch và báo cáo sensitivity liên quan.
- Đã ghi kế hoạch chi tiết sau batch hiện hành vào
  `AGVNS/experiments/agvns_parameter_sensitivity/plans/2026-10-05-followup-after-24-fixed-version-57-58.md`
  và thêm trạng thái vào `task_plan.md`.
- Batch `20261005_014745` đang chạy theo manifest: 24 job, 12 worker, core 0–11;
  tại 02:11 UTC có 12 workspace/log và chưa có ledger tổng kết. Không coi dòng
  `SUCCESS` bên trong một worker log là kết thúc simulator job.
- Kế hoạch tiếp theo: audit đủ 24 job, xác minh 7 success instance 57 thiếu ledger,
  rồi mới lập danh sách và chạy dự kiến 29 key còn thiếu; không khởi chạy batch kế
  tiếp trong phiên lưu kế hoạch này.
- Sự cố khởi chạy đầu tiên do Python mặc định thiếu `simpy` đã được xử lý bằng
  interpreter Conda cho batch hiện tại.

## 2026-10-06 — Kiểm tra và khởi chạy lại batch sensitivity 24 job

- Kiểm tra batch `20261005_014745`: không còn runner; 12/24 workspace được tạo,
  đều instance 57 và mới đến simulated time 00:40. Không có `results.jsonl`,
  `runtime_stats.csv` hay `summary.json`; 12 key chưa khởi chạy. Log không cho thấy
  traceback hoặc lỗi xác định, nên nguyên nhân dừng chưa biết.
- Job list cũ được kiểm tra bằng `--dry-run`: chọn đúng 24 key.
- Theo yêu cầu trước đó tiếp tục chạy đủ 24 job, đã khởi chạy batch mới
  `20261006_090008` bằng `/home/tuantb/miniconda3/bin/python`, 12 worker trên
  core 0–11. Detached tmux session: `agvns_sensitivity_20261006`.
- Snapshot ngay sau launch: 12 job đã start, 12 queued, 0 result rows. Không có
  score cuối để báo cáo ở thời điểm này.
- Batch mới ghi worktree hash `9ffb9b681ae3cbd789021dba5bc46a5761281b8a7560533ea147333a8a69bc6c`;
  batch cũ là `afa5adc6e9179ded92e745598ca8212186c83932472b9c53f3ef09b95c173b4b`.
  Revision git không đổi; khác biệt do cập nhật tài liệu kế hoạch, không do sửa code
  thuật toán trong lượt này.

## 2026-10-06 — Truy nguyên việc batch cũ dừng và kiểm tra affinity

- Bằng chứng dừng: batch `20261005_014745` không có ledger, summary, exit code hay
  traceback; 12 log cuối cùng dừng sau tick mô phỏng tới 00:40. Session exec cũ
  `74191` trả `Unknown process id`, và process runner không còn trong `ps`.
- Kết luận có giới hạn: nguyên nhân phù hợp nhất là runner đã gắn với phiên exec
  foreground nên bị kết thúc khi phiên/môi trường không còn. Không thể xác định
  chính xác signal hoặc sự kiện kết thúc; không có bằng chứng OOM/lỗi thuật toán.
- Xác nhận batch mới vẫn sống trong tmux `agvns_sensitivity_20261006`. Có 12 job
  worker đang chạy, 12 key chờ, 0/24 result cuối; log gần nhất cập nhật 09:28 UTC,
  đang tìm kiếm ở simulated time 00:40 và không có lỗi.
- Đã xác minh affinity cho worker simulator: core 0 đến core 11, mỗi worker một
  core; 12 worker sẽ tự lấy các key queued tiếp theo khi hoàn tất.
- Log đã tiến tới simulated time 00:50 ở cả 12 workspace; cập nhật cuối đến
  09:38 UTC. Hiện vẫn 0 result row cuối, không có traceback/error; 12 tiến trình
  thuật toán con đang hoạt động, mỗi tiến trình thừa hưởng một core riêng.
- Theo yêu cầu chạy hết các key còn thiếu, đã tạo session detached
  `agvns_sensitivity_followup_20261006`. Session chờ wave 24 kết thúc rồi sinh
  list từ ledger hợp lệ của chính fingerprint hiện tại và chạy phần bù để đủ 60
  key instance 57–58, không overlap và giữ giới hạn 12 core. Nếu 24 job đều tốt,
  dự kiến wave sau có 36 job, trong đó có 7 key success cũ được chạy lại.
- Một lần `apply_patch` dùng anchor không chính xác nên bị từ chối, không làm đổi
  file; đã đọc lại nội dung và patch theo anchor đúng.

---

# Progress — MA runtime batch

- 2026-11-14: Preflight confirmed 64 instances, 20 available CPU cores, requested runner options and Conda `simpy` dependency. No active MA runner was visible in `ps`; `tmux ls` was denied by sandbox permissions, so tmux state is unverified.
- Default Python lacks `simpy`; use `/home/tuantb/miniconda3/bin/python`. No algorithm code changed.
- Full-run import check: `/home/tuantb/miniconda3/bin/python MA/main.py --help` completed successfully.
- Detached launcher attempt exited before creating a manifest; no batch was started by that attempt. The empty tracking files were removed.
- Started the runner in managed exec session `74006`; batch `20261114_192618` is `RUNNING`, 256 jobs planned, 0 finalized at first snapshot. The first 12 per-job workspaces and worker logs were created, and simulator logs advanced through initial ticks.

- Snapshot 2026-11-14 19:32 UTC: batch `20261114_192618` vẫn `RUNNING`; đã ghi 4/256 job `SUCCESS`, 0 `FAILED`. Có 16 workspace đã được khởi tạo; managed exec session `74006` tiếp tục giữ runner hoạt động. Instance 1 chưa đủ repetition tại snapshot này.

- Snapshot 2026-11-14 19:33:47 UTC: 8/256 job `SUCCESS`, 0 `FAILED`; kết quả đã ghi cho instance 1 (2 lượt), instance 2 (4 lượt), instance 3 (2 lượt). Batch còn `RUNNING`.

- Snapshot 2026-11-14 19:36:30 UTC: batch vẫn chạy; `summary.json` ghi 12/256 `SUCCESS`, 0 failure. Các log workspace của instance 4–6 đang tiếp tục tăng kích thước và được cập nhật tới 19:36:30 UTC, xác nhận worker hiện vẫn thực thi. Summary chỉ liệt kê job đã hoàn tất nên không hiện các job active; chưa khởi chạy trùng batch.

- 2026-11-14 19:50 UTC: đã gửi SIGINT có kiểm soát cho runner foreground vì không thể reparent vào tmux (runner dùng pipe, TTY `?`, không có `reptyr`). Batch nguồn `20261114_192618` được ghi trạng thái `INTERRUPTED`, giữ 32 kết quả `SUCCESS` cho instance 1–8; các job dở được loại khỏi kết quả cuối.
- Tạo helper ngoài repo `/tmp/ma_resume_runner_20261114.py`: đọc ledger nguồn, bỏ qua đúng các key `(instance,repetition)` đã `SUCCESS`, giữ nguyên seed formula; dry-run xác nhận 32 lượt reuse + 224 lượt còn thiếu = 256.
- Đã khởi chạy phần còn thiếu trong tmux session `ma_runtime_resume_20261114`; batch tiếp tục `20261114_195217`, manifest xác nhận 224 job, 12 worker, cores 0–11. Snapshot 19:52:41 UTC: trạng thái `RUNNING`, 0/224 job đã finalize; 12 workspace worker logs đã được tạo và đang cập nhật.
