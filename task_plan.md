# Kế hoạch tổng hợp kết quả EvoRL

---

# Kế hoạch cấu hình LaTeX Workshop

## Mục tiêu hiện tại

Cấu hình VS Code/LaTeX Workshop để mở và build
`paper/main_Springer_8.2026.tex` bằng các engine đã có trên máy, giữ output trong
`paper/build/` và hỗ trợ bibliography.

## Trạng thái

- [completed] 1. Khảo sát `.vscode/`, engine và recipe hiện có
- [completed] 2. Trình bày thiết kế cấu hình và chờ người dùng duyệt
- [completed] 3. Cập nhật `.vscode/settings.json`
- [completed] 4. Build thử bằng recipe LaTeX Workshop và kiểm tra PDF/log

## Findings chính

- `.vscode/settings.json` hiện chỉ có cấu hình Python, chưa có LaTeX Workshop.
- Engine khả dụng: `/home/tuantb/bin/pdflatex`, `/home/tuantb/bin/bibtex`,
  `/home/tuantb/bin/latexmk`; `makeglossaries` chưa có.
- Recipe an toàn nhất là `pdflatex → bibtex → pdflatex → pdflatex`, vì document
  không gọi `\\printglossaries` và build recipe này đã được xác minh trước đó.
- Cần đặt `TEXMFVAR` vào `%DIR%/build/texmf-var` vì TinyTeX global cache read-only.

## Kết quả cấu hình và kiểm tra

- Đã thêm cấu hình LaTeX Workshop vào `.vscode/settings.json`, giữ nguyên các setting
  Python hiện có.
- `paper-pdflatex` dùng `/home/tuantb/bin/pdflatex`; `paper-bibtex` chạy từ `paper/`
  với `build/%DOCFILE%` để BibTeX tìm được cả `.aux` và `sn-bibliography.bib` mà không
  bị `openout_any` chặn đường dẫn tuyệt đối.
- JSON settings hợp lệ; đủ 4 bước recipe đều exit code `0`.
- PDF cuối: `paper/build/main_Springer_8.2026.pdf`, 31 trang A4; SyncTeX và `.bbl` đã
  được tạo.
- Log cuối: không có fatal error, undefined citation/reference; chỉ còn warning không
  chặn build liên quan tới glossary/layout/float/caption.

## Errors Encountered — task hiện tại

Chưa có.

---

# Kế hoạch biên dịch paper LaTeX

## Mục tiêu hiện tại

Đọc cấu trúc thư mục `paper/` và biên dịch project với entrypoint
`paper/main_Springer_8.2026.tex`, sau đó kiểm tra PDF và các lỗi/cảnh báo chính.

## Các phase hiện tại

- [completed] 1. Khảo sát cấu trúc `paper/` và trạng thái toolchain
- [completed] 2. Xác định thứ tự biên dịch và dependency
- [completed] 3. Biên dịch entrypoint Springer
- [completed] 4. Kiểm tra artifact, log và tổng kết

## Errors Encountered — task hiện tại

| Error | Attempt | Resolution |
|---|---:|---|
| `LaTeX Error: File cuted.sty not found` tại `sn-jnl.cls:774` | 1 | Đã tái hiện; xác nhận `kpsewhich cuted.sty` không tìm thấy. Đang xác định package/provider trước khi cài dependency. |
| `tlmgr install sttools` bị từ chối vì `tlmgr itself needs to be updated` | 2 | Đã xác nhận repository hợp lệ nhưng manager local quá cũ; bước tiếp theo là cập nhật `tlmgr` theo hướng dẫn chính thức rồi cài `sttools`. |
| `LaTeX Error: File wrapfig.sty not found` tại `sn-jnl.cls:1503` | 3 | `sttools/cuted` đã được nạp thành công; dependency kế tiếp của class là package `wrapfig`, sẽ cài riêng và kiểm tra lại. |
| `Missing \\endgroup inserted` tại bảng thống kê line 1092 | 4 | Reproduction tối giản xác nhận `\\resizebox` xung đột với `threeparttable` mà `sn-jnl.cls` tự bọc; thay bằng `tabular*` là thử nghiệm tối thiểu tiếp theo. |
| `pdflatex` không tạo được font `tcrm0700` vì `/home/tuantb/.TinyTeX/texmf-var` read-only | 5 | Source đã qua lỗi bảng; chuyển `TEXMFVAR` sang `paper/build/texmf-var` writable để font cache nằm trong artifact build. |

## Verification hiện tại

- PDF cuối: 31 trang A4, tồn tại và không rỗng.
- Log cuối: 0 fatal error, 0 undefined citation/reference.

## Mục tiêu

Xác định batch 4 repetition hiện tại và một lần chạy trước đó, tổng hợp 5 lần chạy thành dữ liệu có thể kiểm tra, tạo file tổng hợp và báo cáo tiếng Việt.

## Các phase

- [completed] 1. Khảo sát các nguồn kết quả và xác định đúng 5 lần chạy
- [completed] 2. Kiểm tra tính đầy đủ/hợp lệ và thống nhất schema
- [completed] 3. Tính thống kê tổng hợp theo lần chạy, instance và nhóm kích thước
- [completed] 4. Tạo file tổng hợp và báo cáo
- [completed] 5. Kiểm tra đầu ra và bàn giao

## Quyết định cần giữ

- Batch hiện tại đã biết từ lượt trước: `20260819_094955`, gồm 4 repetition × 64 instance = 256 job.
- Không được gộp một run cũ nếu chưa xác định rõ run đó là lần thực hiện trước người dùng muốn so sánh.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| `SyntaxError: unterminated string literal` tại header bảng Markdown | 1 | Tách chuỗi header và separator thành hai phần tử Python hợp lệ |

## Verification

- Generator chạy lại thành công.
- Nguồn: 320 dòng, đều `SUCCESS`.
- Output aggregate: 64 dòng, instance 1–64.
- Đã kiểm tra lại 128 công thức mean (current4 và combined5) so với nguồn.
- Báo cáo chứa đủ các phần kết luận, bảng nhóm và phương pháp.

---

# Kế hoạch cập nhật Statistical Validation

## Mục tiêu

Tính lại kiểm định thống kê từ các bảng objective chính HW1--HW64 trong
`paper/main_Springer_8.2026.tex`, bao gồm đủ 7 thuật toán và cập nhật toàn bộ
subsubsection `Statistical Validation`.

## Trạng thái

- [completed] 1. Xác định bảng nguồn và phạm vi 7 thuật toán
- [completed] 2. Viết/test bộ tính Friedman, Wilcoxon và Holm
- [completed] 3. Tính lại số liệu và cập nhật LaTeX
- [completed] 4. Compile và kiểm tra PDF/log

## Kết quả chính

- Friedman: $\chi^2=234.175879$, $p=9.8348\times10^{-48}$.
- Mean ranks: AGVNS 1.695, Gold 2.320, Bronze 3.844, Silver 3.891,
  MA 4.531, GA 4.938, Evo-RL 6.781.
- AGVNS có ý nghĩa thống kê sau Holm với Evo-RL, GA, MA, Bronze và Silver;
  không có ý nghĩa với Gold ($p_{Holm}=0.0734$).
- Artifact tính toán: `paper/build/statistical_validation_7_algorithms.json`.

## Audit sau cập nhật

- [completed] Đối chiếu độc lập dữ liệu và phép tính bằng R
- [completed] Kiểm tra quy ước Wilcoxon, tie handling và Holm correction
- [completed] Kiểm tra các số thắng/thua theo từng set và đối chiếu summary table

## Findings audit

- Statistical Validation hiện đúng theo objective tables và quy ước asymptotic
  Wilcoxon không continuity correction.
- Summary table và đoạn diễn giải đã được sửa: Gold là 7/8 ở Set 4 và 44/64 overall.
- Compile sau cập nhật: 4/4 recipe steps exit code `0`, PDF 31 trang, không fatal error
  hoặc undefined citation/reference.

---

# Kế hoạch kiểm tra lỗi job AGVNS sensitivity hiện tại

## Mục tiêu hiện tại

Xác định đầy đủ các job lỗi, job thiếu hoặc job treo trong batch sensitivity đang có,
truy nguyên nguyên nhân từ runner đến worker/simulator/output, và báo cáo bằng chứng
theo từng nhóm lỗi. Chỉ điều tra; chưa sửa code hoặc khởi động lại job.

## Các phase

- [completed] 1. Xác định batch hiện tại và trạng thái runtime
- [completed] 2. Kiểm kê kết quả, log và tính đầy đủ của job matrix
- [completed] 3. Truy nguyên các lỗi đại diện và phân loại nguyên nhân
- [completed] 4. Kiểm tra tính nhất quán dữ liệu/metrics và tổng hợp kết luận
- [completed] 5. Bàn giao báo cáo, nêu rõ phần chưa kiểm tra

## Câu hỏi cần trả lời

1. Batch nào thực sự đang chạy và còn process/job nào sống?
2. Có bao nhiêu job SUCCESS, FAILED, RUNNING, missing hoặc có metric không hợp lệ?
3. Các lỗi có cùng một root cause hay là nhiều lỗi độc lập theo worker/instance?
4. Kết quả hiện tại có đủ đáng tin để aggregate hay cần loại/cô lập nhóm nào?

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Patch đầu tiên không áp dụng do anchor `## Findings audit` không tồn tại trong `findings.md` | 1 | Đọc phần cuối từng file và chuyển sang patch append theo anchor chắc chắn |

## Kết luận điều tra

- Snapshot cuối lúc 03:54:28 UTC: 47/480 result rows, 5 SUCCESS, 42 FAILED, 16
  worker đang chạy; batch chưa hoàn tất.
- 38 lỗi timeout do dispatch sát/vượt giới hạn 600 giây; 4 lỗi `IndexError` do
  `unique_population` rỗng tại `GAVND7.py:188`.
- Không phát hiện lỗi sinh job, truyền configuration/seed, OOM, disk hoặc permission.
- Chưa sửa code, chưa dừng runner, chưa resume/rerun và chưa aggregate kết quả một
  phần; đây là điều tra read-only.

---

# Kế hoạch bỏ outer timeout và rerun timeout jobs

## Mục tiêu

Đổi mặc định runner sang không giới hạn outer job timeout, vẫn giữ CLI opt-in để
bật timeout khi cần; sau đó tạo run mới chỉ rerun các job có lỗi `outer job wall-time
exceeded` từ run `20260827_144605`.

## Các phase

- [completed] 1. Kiểm tra thay đổi hiện có và thiết kế filter rerun
- [completed] 2. Viết test RED cho default timeout=0 và lọc timeout jobs
- [completed] 3. Sửa runner/README tối thiểu
- [completed] 4. Chạy test GREEN và kiểm tra CLI/dry-run
- [in_progress] 5. Chạy lại đúng các timeout jobs bằng timeout=0
- [pending] 6. Kiểm tra trạng thái run mới và bàn giao artifact

## Phạm vi bảo vệ

- Không hoàn tác các thay đổi chưa commit hiện có.
- Không ghi đè run cũ; rerun dùng run directory mới.
- Không dừng run cũ đang hoạt động.
