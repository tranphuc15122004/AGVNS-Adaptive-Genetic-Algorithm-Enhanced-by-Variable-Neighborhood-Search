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
