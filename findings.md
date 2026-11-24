# Findings — EvoRL aggregation

---

# Findings — LaTeX Workshop configuration

## Khảo sát hiện tại

- `.vscode/settings.json` đã tồn tại và chứa cấu hình Python; chưa có key `latex-workshop.*`.
- Root file sẽ là `paper/main_Springer_8.2026.tex`; output hiện phù hợp với `paper/build/`.
- LaTeX Workshop hỗ trợ `latex-workshop.latex.tools`, `latex-workshop.latex.recipes`,
  `cwd`, `env`, `%DIR%`, `%DOC%`, `%DOCFILE%`, `%OUTDIR%`; recipe có thể chạy chuỗi
  `pdflatex → bibtex → pdflatex → pdflatex`. Nguồn: tài liệu chính thức LaTeX Workshop.
- Cấu hình đã áp dụng không dùng `latexmk` mặc định vì `makeglossaries` chưa có và tài liệu
  hiện không in glossary; dùng recipe explicit đã được kiểm chứng.
- BibTeX phải chạy từ `%DIR%` với `build/%DOCFILE%`: dùng `%OUTDIR%/%DOCFILE%` tạo đường
  dẫn tuyệt đối khiến BibTeX không ghi được `.blg`, còn `cwd=%OUTDIR%` khiến không tìm thấy
  `sn-bibliography.bib`.

## Verification cấu hình

- `.vscode/settings.json` parse hợp lệ bằng `python3 -m json.tool`.
- Recipe đầy đủ `pdflatex → bibtex → pdflatex → pdflatex` chạy thành công, cả 4 bước
  exit code `0`.
- Artifact cuối là PDF 31 trang A4, có `main_Springer_8.2026.synctex.gz` và `.bbl`.
- Log cuối không có fatal error hoặc undefined citation/reference.

---

# Findings — LaTeX paper compilation

## Task hiện tại

- Entrypoint yêu cầu: `paper/main_Springer_8.2026.tex`.
- Cần kiểm tra cấu trúc, các file phụ thuộc, engine/recipe và artifact trước khi kết luận.

## Khảo sát phase 1

- `paper/` là một project LaTeX phẳng, gồm 3 entrypoint (`main_Springer_8.2026.tex`,
  `main_Elsevier.tex`, `main_taylor.tex`), 2 class (`sn-jnl.cls`, `interact.cls`),
  `gls.tex`, `sn-bibliography.bib` và 8 ảnh PNG trong `paper/figure/` cùng 2 file EPS.
- Entrypoint Springer dùng `\documentclass[pdflatex]{sn-jnl}`.
- Dependency chính nhìn thấy trong preamble: `glossaries` (với `\makeglossaries` và
  `\input{gls}`), `graphicx`, `pgfplotstable`, `algorithm2e`, `natbib`, `hyperref`,
  các gói toán/bảng và `\bibliography{sn-bibliography}`.
- File chính dài 1177 dòng; có title/abstract, các section về Introduction, Problem
  formulation, related work, proposed method, experiments, statistical analysis và
  conclusion; nhiều đoạn/commented draft vẫn nằm trong source.
- Toolchain local có `latexmk`, `pdflatex`, `xelatex`, `lualatex`, `bibtex`; chưa thấy
  `biber` ở bước khảo sát đầu tiên.
- Các package quan trọng (`glossaries`, `pgfplotstable`, `algorithm2e`, `natbib`,
  `subcaption`) đều được `kpsewhich` tìm thấy trong TinyTeX; `sn-jnl.cls` là file local
  nên không nằm trong TeX search path toàn cục nhưng sẽ được tìm từ thư mục source.
- `makeglossaries` chưa có trong PATH. Vì file chính gọi `\makeglossaries` nhưng không
  gọi `\printglossaries`, cần kiểm tra build thực tế để phân biệt warning với lỗi chặn.
- Có 6 lệnh `\includegraphics` đang hoạt động, tất cả trỏ tới ảnh trong `paper/figure/`;
  các lệnh hình còn lại bị comment.
- Bibliography có 30 entry; recipe dự kiến là `pdflatex → bibtex → pdflatex → pdflatex`.

## Chẩn đoán lỗi source sau khi bổ sung dependency

- Sau khi cài `sttools` và `wrapfig`, `pdflatex` đã nạp được toàn bộ preamble và dừng ở
  `main_Springer_8.2026.tex:1092` với `Missing \\endgroup inserted` tại mẫu
  `\\resizebox{...}{!}{\\begin{tabular}...\\end{tabular}}`.
- Reproduction tối giản trong `paper/build/minimal_table_threeparttable.tex` cho cùng lỗi
  khi `\\resizebox` nằm trong `threeparttable`; reproduction tương đương với `tabular*`
  chạy thành công. Vì `sn-jnl.cls` tự bọc mọi `table` trong `threeparttable` (class lines
  1332–1340), đây là tương tác class/package, không phải lỗi dữ liệu trong bảng.
- Fix tối thiểu được chọn: thay 3 wrapper `\\resizebox` đang hoạt động ở các bảng thống kê
  bằng `tabular*` với cùng target width và `\\extracolsep{\\fill}`, giữ nguyên nội dung và
  tránh thay đổi số liệu.

## Verification cuối

- Recipe đã chạy thành công: `pdflatex` lần đầu, `bibtex`, rồi 2 lần `pdflatex` cuối; một
  pass `pdflatex` xác nhận lại sau đó cũng exit code `0`.
- Artifact: `paper/build/main_Springer_8.2026.pdf`, PDF A4, 31 trang, 2,216,336 bytes.
- `pdftotext` tìm thấy title, `Conclusions and future work` và `References`.
- Log cuối không còn fatal error, undefined citation hoặc undefined reference.
- Warning còn lại không chặn build: `glossaries` không có `\\printglossaries`, pgfplots
  compatibility mặc định, một số under/overfull box và float placement, caption package
  không nhận diện hoàn toàn class `sn-jnl`, cùng một `\\textendash` trong math mode.
- `paper/` và PDF bị rule `.gitignore` bỏ qua; source vẫn tồn tại và đã được cập nhật tại
  các bảng thống kê trong `main_Springer_8.2026.tex`.

## Nguồn dữ liệu

- Batch hiện tại: `EvoRL/algorithm/data_interaction_runs/20260819_094955/results.csv`.
  - 256 dòng kết quả, instance 1–64, repetition 1–4, tất cả `SUCCESS`.
- Lần chạy trước dùng làm reference: `EvoRL/algorithm/data_interaction_runs/EvoRL_results_64_instances.csv`.
  - 64 dòng dữ liệu, mỗi instance một lần (`repetition=1`), tất cả `SUCCESS`.
  - File này là kết quả nối của batch `20260815_064053` (instance 1–10) và
    `20260817_020323` (instance 11–64), tạo thành một lần chạy 64-instance hoàn chỉnh.
- Không dùng batch `20260818_143854`: batch đó có `status=RUNNING` và `completed_jobs=0`,
  nên không phải nguồn kết quả hợp lệ cho tổng hợp.

## Schema và hướng tổng hợp

- Chỉ tiêu chính: `score` (thấp hơn tốt hơn).
- Chỉ tiêu phụ: `wall_time_seconds`, `simulation_runtime_seconds`,
  `algorithm_time_seconds`, `algorithm_dispatch_count`.
- Mỗi instance sẽ có 5 score: một reference trước đó và 4 repetition hiện tại,
  cùng mean/std/min/max của 5 lần và mean/std của riêng 4 repetition mới.
- Báo cáo cần tách thống kê theo nhóm kích thước instance vì raw score giữa các nhóm
  50–4000 order khác nhau rất lớn; đồng thời báo cáo paired change so với reference.

## Câu hỏi còn mở

- Cần xác nhận bằng dữ liệu xem reference có trùng kết quả với repetition 1 hiện tại
  hay không; nếu có, ghi rõ trong báo cáo thay vì xem là 5 mẫu hoàn toàn độc lập.

## Kiểm tra sơ bộ

- Reference trùng score với repetition 1 hiện tại ở 28/64 instance; 36/64 khác.
- So sánh mean của 4 repetition hiện tại với reference: 20 instance tốt hơn,
  25 bằng, 19 xấu hơn; macro-average thay đổi khoảng -0.082%.

---

# Findings — Statistical Validation update

- Các bảng kết quả chính trong `main_Springer_8.2026.tex` có 64 dòng HW1--HW64
  và 7 cột thuật toán: Gold, Silver, Bronze, MA, GA, Evo-RL, AGVNS.
- Phần thống kê cũ chỉ dùng 6 thuật toán và bỏ qua Evo-RL; các giá trị cũ đã được
  thay thế bằng kết quả tính trực tiếp từ các dòng bảng hiện hành.
- Quy ước: objective thấp hơn là tốt hơn; Friedman rank 1 là tốt nhất; Wilcoxon
  một phía kiểm định AGVNS có objective thấp hơn đối thủ; Holm hiệu chỉnh 6 p-value.
- Một hòa AGVNS--Bronze được giữ trong win/tie/loss và loại khỏi rank-sum Wilcoxon,
  tạo $W=371.5$ và $p=6.5761\times10^{-6}$.
- Kết quả được sinh bởi `analysis/paper_statistical_validation.py` và lưu JSON tại
  `paper/build/statistical_validation_7_algorithms.json`.

## Audit độc lập

- Parser độc lập bằng R đọc đúng 64 dòng HW1--HW64 và 7 cột; mean ranks,
  Friedman statistic/p-value, Wilcoxon W/p-value và Holm p-value khớp script
  Python ở độ chính xác hiển thị.
- Quy ước hiện tại là Wilcoxon asymptotic/normal approximation, `zero_method=wilcox`,
  không continuity correction. Đây là kết quả hợp lệ và tái lập được, nhưng phải
  ghi rõ nếu muốn loại bỏ mơ hồ với exact Wilcoxon.
- Với Bronze có một zero-difference (HW1); zero này được giữ trong win/tie/loss
  và loại khỏi rank-sum. Các tied absolute differences khác được xếp hạng trung bình,
  không bị loại.
- Đã sửa lỗi nhất quán trong paper: từ các dòng objective, Gold thắng AGVNS
  44/64, riêng Set 4 là 7/8 vì HW28 (AGVNS 7,153 > Gold 7,138). Bảng summary
  và đoạn diễn giải đã được cập nhật từ 45/64, 8/8 thành 44/64, 7/8.
- Các kiểm định hiện dùng một objective value hiển thị cho mỗi thuật toán/instance,
  không phải 10 lần chạy độc lập; do đó kết luận là so sánh theo 64 instance blocks,
  không phải suy luận về run-to-run variability.

---

# Findings — Điều tra lỗi AGVNS parameter sensitivity

## Phạm vi

- Điều tra batch sensitivity hiện tại theo thiết kế tại
  `AGVNS/experiments/agvns_parameter_sensitivity/`.
- Chưa sửa code, chưa xóa artifact, chưa rerun hoặc resume job.
- Các kết luận phải dựa trên manifest, raw results, worker log và process hiện tại.

## Evidence log

- Batch mới nhất `runs/20260824_162057` được tạo lúc `2026-08-24T16:20:57Z`,
  manifest khai báo 480 job, 16 workers, cores 0--15.
- Trong namespace sandbox ban đầu không thấy process và `tmux list-sessions` bị
  chặn socket (`Operation not permitted`); kiểm tra read-only ngoài sandbox sau đó
  xác nhận đây chỉ là giới hạn quan sát. Tại `2026-08-27 03:48Z`, tmux session
  `agvns_taguchi_screening` vẫn sống, runner PID `2176437` và 16 worker
  `AGVNS/main.py` đang chạy.
- `results.jsonl`: 46 dòng, không có JSON hỏng hoặc duplicate key; 5 SUCCESS và
  41 FAILED, tất cả FAILED có return code 255. So với 480 job kỳ vọng còn thiếu
  434 key trong result ledger.
- Filesystem có 62 job directories và 62 worker logs; 16 directory không có
  dòng trong `results.jsonl`. 16 directory này khớp với 16 worker đang hoạt động,
  nên là job đang chạy dở chứ chưa phải job mất. Chúng chưa có `runtime_stats` cuối
  vì `main.py` chỉ ghi stats sau khi toàn bộ instance kết thúc.
- Trong 41 FAILED đã ghi nhận: 37 simulator timeout và 4 algorithm `IndexError`.
  Timeout xảy ra sau `subprocess_function` quá 600 giây, tại các instance 57/58
  (3000/4000-order set), rồi simulator ghi `Timeout` và `Can not catch SUCCESS`.
- 4 IndexError đều tại `AGVNS/algorithm/Test_algorithm/GAVND7.py:188`, với log
  ngay trước traceback cho thấy `unique_population` sau lọc là `0`:
  config 4 / instance 57 / rep 1; config 3 / instance 57 / rep 2--3; config 8 /
  instance 58 / rep 1. Đây là lỗi thuật toán độc lập với nhóm timeout.
- Trong 4 lỗi, `main_algorithm.py` đã in `FAIL`; simulator sau đó gọi `sys.exit(-1)`.
  Trong các timeout, simulator cũng gọi `sys.exit(-1)`. Điều này giải thích mã 255
  và việc không có runtime stats cho FAILED.
- 5 SUCCESS có score, runtime và runtime_stats đầy đủ; kiểm tra lại theo công thức
  `total_distance / 100 + sum_over_time * 10000 / 3600` cho sai số dưới ngưỡng làm
  tròn log.
- 62/62 worker logs có dòng applied configuration; chưa thấy dấu hiệu config/seed
  bị thiếu trong log, nhưng phép đối chiếu đầy đủ theo design matrix đang tiếp tục.
- Không tìm thấy marker về OOM, thiếu disk, permission hoặc signal trong raw logs.
- Hiện còn 418 job chưa launch theo `480 - 46 result - 16 active`; đây là trạng thái
  bình thường của scheduler đang chạy tuần tự theo slot, không phải missing cuối batch.
- Hai run trước đó có scope khác với design hiện hành: `20260824_100956` khai báo
  2400 job nhưng mới ghi 40 SUCCESS (config 1, các instance nhỏ); `20260824_161706`
  khai báo 800 job nhưng mới tạo 8 workspace và chưa ghi result. Chúng không được
  gộp vào batch hiện tại.

## Snapshot live mới nhất (2026-08-27 03:54:28 UTC)

- Runner vẫn sống trong tmux `agvns_taguchi_screening` với PID `2176437`; kiểm tra
  ngoài sandbox thấy 16 worker `AGVNS/main.py` và các tiến trình `main_algorithm.py`
  con đang hoạt động. Không có cơ sở để kết luận runner đã chết.
- `results.jsonl` hiện có 47 dòng: 5 `SUCCESS`, 42 `FAILED`, return code là 5 lần `0`
  và 42 lần `255`. Có 63 workspace đã được tạo; 16 workspace khớp với worker đang
  chạy, nên 417 job vẫn chưa được ghi ledger tại snapshot này.
- Phân loại lại toàn bộ 42 lỗi đã ghi: 38 simulator timeout và 4 `IndexError` rỗng
  `unique_population`. 38 timeout có runtime dispatch cuối trước timeout từ
  572.418 đến 597.751 giây, trung bình 587.484 giây, sát giới hạn 600 giây.
- Các worker `AGVNS/main.py` có thể tồn tại hàng giờ ở instance lớn vì một instance
  gồm nhiều lần dispatch theo tick mô phỏng; đây chưa đủ bằng chứng để gọi là treo.
  Tuy nhiên `subprocess_function()` dùng `shell=True` và chỉ terminate shell, nên
  vẫn có rủi ro process con không bị dừng theo khi timeout; cần kiểm tra/fix riêng,
  không tự ý kill trong lần điều tra này.
- Đối chiếu cấu hình/seed đã hoàn tất: 62/62 log đã ghi applied configuration,
  không có mismatch với design matrix. Dry-run 480 job và test sensitivity hiện có
  đều pass; các lỗi hiện tại không có dấu hiệu bắt nguồn từ sinh job hoặc truyền config.

## Phân tích nguyên nhân sâu hơn

### `IndexError` tại GAVND7

- Luồng lỗi là: quần thể sau GA được rút còn `POPULATION_SIZE`, sau đó
  `remove_similar_individuals()` và bộ lọc `fitness < best_solution.fitness + addDelta`
  loại hết ứng viên. Log xác nhận các cặp kích thước `20 -> 0`, `40 -> 0` và `60 -> 0`.
- `best_solution` được lưu riêng nhưng không được đưa trở lại quần thể sau mỗi lần
  truncate ở các dòng 110--112 của `GAVND7.py`. Vì vậy bộ lọc cuối có thể không còn
  chính `best_solution` để làm fallback.
- Sau bộ lọc, vòng lặp mutation có kiểm tra độ dài, nhưng hai dòng 188--189 vẫn
  truy cập `unique_population[0]` vô điều kiện. Đây là thiếu guard ở điểm sử dụng,
  không phải lỗi dữ liệu đầu vào.
- Cả 4 ca quan sát đều thuộc mức thiết kế `mutation_rate=0.50` (config 3, 4, 8),
  nên mức này có thể làm tăng khả năng population lệch khỏi incumbent; tuy nhiên
  chưa đủ dữ liệu để kết luận mutation là nguyên nhân duy nhất vì nhiều job cùng mức
  đã timeout trước khi đến đoạn này.

### Timeout trước GAVND7

- Ở log đại diện, simulator bắt đầu tick mới và ghi số lượng order, sau đó không có
  dòng `Applied AGVNS experiment config` mà chờ đúng 600 giây rồi ghi `Timeout`.
  Điều này định vị lỗi trước dòng đầu của `GAVND_7()`.
- `algorithm/main.py` gọi `new_dispatch_new_orders()` trước `GAVND_7()`. Hàm này
  lặp qua từng order và gọi `dispatch_nodePair()`; các vòng lặp vehicle/insertion
  sâu trong `engine.py:575--823` không gọi `config.is_timeout()`.
- Vì vậy việc kiểm tra timeout ở `new_dispatch_new_orders()` chỉ có tác dụng giữa
  các order, không thể ngắt một `dispatch_nodePair()` đang đánh giá rất nhiều vị trí
  chèn. Đây là nguyên nhân kỹ thuật phù hợp với dữ liệu: các tick cuối có khoảng
  1,000--1,200 unallocated items và các tick thành công ngay trước đó đã mất
  580--595 giây.
- Sau khi qua GAVND7, `gold_algorithm_LS()` có kiểm tra timeout, nhưng không giải
  thích được nhóm timeout này vì các log lỗi chưa bao giờ in mốc GAVND7.
- Ngoài ra, `new_generate_random_chromosome()` có vòng `while len(population) < quantity`
  không kiểm tra timeout trong thân vòng; đây là rủi ro timeout khác cần chặn khi sửa,
  dù chưa phải vị trí được chứng minh trong các log timeout hiện tại.

## Phương án khắc phục đề xuất

1. Sửa tính an toàn của GAVND7 trước: nếu danh sách sau filter rỗng thì giữ
   `best_solution` (deep copy) làm ứng viên duy nhất; chỉ truy cập `[0]` sau guard.
   Đồng thời đưa incumbent vào pool trước truncate hoặc áp dụng elitism để
   `best_solution` không bị mất khỏi population.
2. Đặt deadline chung và truyền nó xuống `new_dispatch_new_orders()`,
   `dispatch_nodePair()`, `new_generate_random_chromosome()` và các fallback
   exhaustive. Mỗi vòng `vehicle`, `i`, `j` phải thoát khi hết ngân sách; khi đó
   chuyển phần order còn lại sang fallback nhanh/random và vẫn bảo đảm đủ pickup /
   delivery node.
3. Giảm `ALGO_TIME_LIMIT` thực tế xuống dưới giới hạn simulator đủ lớn để dành
   thời gian cho output JSON và shutdown (ví dụ bắt đầu benchmark với 540--550s),
   nhưng chỉ thay đổi đồng nhất cho toàn bộ sensitivity rerun. Chỉ giảm config
   không đủ nếu các vòng lặp bên trong vẫn không có điểm ngắt.
4. Sửa timeout process boundary: tránh `shell=True` nếu có thể; nếu vẫn dùng shell,
   tạo process group/session và terminate cả process group, sau đó kill cưỡng chế
   nếu cần. Nếu không, algorithm child có thể còn sống sau khi shell bị terminate.
5. Đổi simulator failure từ `sys.exit(-1)` sang exception có chủ đích hoặc bắt
   `SystemExit` riêng trong `AGVNS/main.py`, để mọi FAILED job ghi runtime/error
   stats. Chỉ aggregate những job có status và output hợp lệ.
6. Sau khi sửa, không resume batch hiện tại để lấy số liệu chính thức. Chạy smoke
   nhỏ trên các ca tái hiện: config 3/4/8 với instance 57/58, rồi chạy lại toàn bộ
   480 job bằng run directory mới; kiểm tra không còn `[0]` error, không có timeout
   trong các tick cùng workload, và mỗi failure (nếu còn) có runtime stats.

## Kiểm tra tính hợp lệ của sensitivity trước rerun

- `new_generate_random_chromosome()` gọi `disturbance_opt(..., 0.5)` tại
  `new_engine.py:693`, thay vì `config.PERTURBATION_RATE`. Tham số perturbation của
  design chỉ được dùng ở nhánh offspring tại `GAVND7.py:95`; do đó không phải toàn
  bộ pipeline đang thay đổi theo design matrix.
- `GAVND7.py` truyền `current_orders=len(Unongoing_super_nodes)` vào adaptive ERFC.
  Hàm ERFC đặt ratio bằng 0 nếu `num_orders >= T` tại `adaptive_ratio.py:321--323`.
  Các log workload lớn đang có `num_orders` khoảng 370--580, trong khi T chỉ 40/80/120,
  nên crossover ratio bị 0 ở toàn bộ các config hiện quan sát. Đây là vấn đề validity
  của thí nghiệm, không phải nguyên nhân trực tiếp của traceback.
- Trước rerun cần quyết định rõ T điều khiển số order mới, số order đang ongoing hay
  một progress khác; sau đó chọn instance/tick có giá trị hai phía của T hoặc thay
  đổi schedule có chủ đích. Nếu không, kết quả T-sensitivity ở nhóm instance lớn sẽ
  không có thông tin.

## Bổ sung — bỏ outer timeout và rerun

- Runner hiện đặt mặc định `--job-timeout-seconds=660.0`, trong khi run
  `20260827_144605` được khởi chạy với `21600` giây.
- `--resume` chỉ bỏ qua SUCCESS, nên không phù hợp để rerun riêng timeout jobs.
- Thiết kế đã được người dùng duyệt: mặc định `0` (disable outer guard), vẫn giữ
  tham số CLI; thêm bộ lọc đọc các record có lỗi `outer job wall-time exceeded` để
  tạo run mới chỉ chứa các job timeout.

---

# Findings — kế hoạch follow-up sensitivity instance 57–58 (2026-10-05)

- Batch `20261005_014745` có manifest 24 job, 12 worker/core `0–11`, fingerprint
  `afa5adc6e9179ded92e745598ca8212186c83932472b9c53f3ef09b95c173b4b`.
- Snapshot 02:11 UTC: batch chưa có ledger/summary cuối; `SUCCESS` trong worker log
  có thể chỉ là một lần gọi thuật toán trong các tick simulator, không chứng minh
  toàn bộ job đã xong.
- Có 7 job instance 57 cùng fingerprint từ batch `20261002_191917`; log/runtime
  stats là nguồn đối chiếu nhưng thiếu row chuẩn trong `results.jsonl`.
- Sau khi 24 job được xác minh, dự kiến cohort 57–58 có 31/60 key và thiếu 29
  (6 instance 57, 23 instance 58). Nếu 7 key cũ không đối chiếu được hoặc job mới
  lỗi, số phải chạy lại tăng tương ứng.
- Không gộp để xếp hạng các score cũ fingerprint khác: lịch sử có thay đổi đường
  chọn nghiệm và thời gian chạy, nên “score có dữ liệu” chưa đồng nghĩa so sánh
  sensitivity hợp lệ.

## Cập nhật tiến độ — 2026-10-06

- Batch `20261005_014745` không còn runner: 12/24 workspace (đều instance 57), mô
  phỏng mới tới 00:40; không có `results.jsonl`, `runtime_stats.csv` hoặc `summary.json`.
  12 key còn lại chưa được tạo workspace. Không thấy traceback/error trong log hiện có.
- Đã khởi chạy lại đủ 24 key trong `20261006_090008` bằng Conda Python, 12 worker,
  core 0–11. Khi kiểm tra sau launch: 12 key đầu đang chạy, 12 key còn lại trong queue,
  chưa có kết quả cuối.
- Hash worktree đổi từ `afa5...` sang `9ffb...` vì tài liệu kế hoạch được cập nhật;
  git revision vẫn `51e499a...` và không có thay đổi thuật toán trong lượt tiếp tục này.
  Ghi nhận khác biệt này khi chuẩn hóa provenance và tổng hợp 7 kết quả cũ.
- Lần chạy `20261005_014653` có 24 result rows lỗi thiếu `simpy`; đây là lỗi môi
  trường Python và không tính là kết quả thuật toán. Batch hiện tại dùng Conda Python.
- Batch `20261005_014745` được gắn với phiên exec foreground, không có phiên tmux
  hoặc supervisor bền vững. Ngày 2026-10-06 session `74191` trả `Unknown process id`,
  runner không còn, và worker logs không có exit code/signal/traceback. Khả năng phù
  hợp nhất là phiên exec hoặc môi trường kết thúc process; bằng chứng không đủ để
  phân biệt chính xác timeout/cleanup với một sự kiện bên ngoài khác, cũng không có
  bằng chứng OOM hay lỗi thuật toán.
- Batch mới `20261006_090008` đang chạy trong detached tmux. 12/24 worker đã start,
  12 key chờ queue; chưa có result row cuối. Log cập nhật đến 09:28 UTC và vẫn ở
  simulated time 00:40 khi các lượt tìm kiếm tiếp diễn, không có traceback/error.
- Affinity của 12 process simulator được xác nhận lần lượt là core 0–11. Mỗi job
  được gán một core; sau khi job xong runner tái sử dụng core cho key tiếp theo.
- Theo yêu cầu tiếp tục toàn bộ job còn thiếu, đã khởi chạy sequencer detached
  `agvns_sensitivity_followup_20261006`. Sequencer chờ tmux wave đầu kết thúc, đọc
  ledger và loại chỉ các key có `effective_status=SUCCESS`, return code 0 và score
  hữu hạn trong miền hợp lệ; sau đó chạy key còn lại trong cohort 60 bằng 12 worker.
  Dự kiến 36 job tiếp theo nếu 24 hiện tại hợp lệ (gồm 7 key cũ cần chạy lại vì
  fingerprint full worktree khác, cộng 29 key chưa chạy). Nếu có lỗi, key lỗi cũng
  được đưa vào danh sách follow-up.

---

# Findings — MA runtime batch (2026-11-14)

- Scope: 64 benchmark instances, 4 repetitions each (256 jobs), 12 workers on cores 0–11.
- `MA/run_parallel.py` accepts the requested batch settings and creates a fresh timestamped run directory.
- Shared root benchmark contains 64 instances. CPU affinity exposes cores 0–19.
- Default Python lacks `simpy`; Conda base has `simpy 4.1.1`, NumPy 2.3.4 and pandas 2.3.3. The MA simulator imports `simpy`, but does not import FastAPI on the simulation path.
- Use Conda Python for the runner and workers, with base seed 0 for reproducible seeds `instance_id*1000 + repetition`.

## Batch launch snapshot

- Run `20261114_192618` was created by the MA adapter. Manifest confirms 64 instances × 4 repetitions, 12 workers on cores 0–11, base seed 0, and Conda Python for the parent and workers.
- Initial snapshot: summary status `RUNNING`, 0/256 finalized, 12 job workspaces with worker logs; logs show simulated time advancing.
- The runner remains attached to managed exec session `74006` for monitoring.

- Snapshot 2026-11-14 19:32 UTC: batch đang chạy; 4/256 job thành công, chưa có failure nào.
- Snapshot 2026-11-14 19:33:47 UTC: 8/256 job thành công, 0 failure; instance 1 có 2 lượt, instance 2 có 4, instance 3 có 2. Batch còn `RUNNING`.
- Snapshot 2026-11-14 19:36:30 UTC: 12/256 job thành công, 0 failure; log các lượt instance 4–6 đang tăng, cho thấy runner đã chuyển sang các job kế tiếp. `summary.json` chỉ lưu kết quả đã finalize, không liệt kê worker active.
- Chuyển sang tmux: runner foreground không có TTY (`?`), stdout/stderr là pipe và không có `reptyr`, nên không thể attach trực tiếp. SIGINT được xử lý có kiểm soát; batch nguồn ghi `INTERRUPTED` với 32 success (instance 1–8 đủ 4 lượt), không có failure.
- Resume plan `/MA/algorithm/data_interaction_runs/20261114_192618/tmux_resume_plan.json` chọn 224 key còn thiếu theo ledger `SUCCESS`; seed các job còn thiếu vẫn theo `instance_id*1000+repetition`.
- Batch resume `20261114_195217` đang chạy trong tmux `ma_runtime_resume_20261114`; manifest xác nhận 224 job/12 worker/core 0–11. Log worker cập nhật lúc 19:52:41 UTC. Cần ghép thành công 32 kết quả nguồn với kết quả resume để tạo đủ bộ 256 và tổng hợp runtime sau khi xong.
