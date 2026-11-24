# AGVNS sensitivity results — current snapshot

Snapshot time (UTC): 2026-10-13 10:28:35 UTC.

Design: 10 configurations × 16 instances × 3 repetitions = 480 jobs. Seed: `20260824 + instance_id × 1000 + repetition`.

## Current coverage

| State | Jobs |
|---|---:|
| Valid completed score | 480 |
| Running in current batch | 0 |
| Queued in current batch | 0 |
| Needs rerun / unresolved | 0 |
| Total planned | 480 |

A VALID row has a finalized SUCCESS record, finite nonnegative score, and the expected seed. Coverage records completed runs; it does not by itself establish that one parameter setting is better.

36/480 canonical valid rows use the current batch fingerprint `1d9f93ccf387c5fc5c3fcafe5d37d364971ac25de57caf0a16dc826d59f10958`; remaining historical results may come from different code fingerprints.

## Interpretation limits

The master combines archived attempts from different code fingerprints. The newest batch is `20261009_015120`; only finalized, seed-matched rows are treated as completed evidence. Partial means are descriptive and should not be used to rank configurations until all three repetitions for the compared configuration-instance pairs finish under comparable code.

- Điểm cần rà soát: trong các kết quả batch mới cho instance 57, config 10 / rep 2: 81201364.193 (5.5× mốc kế tiếp 14883466.681), config 1 / rep 2: 106577225.892 (7.2× mốc kế tiếp 14883466.681). Trạng thái SUCCESS xác nhận lượt chạy kết thúc hợp lệ theo ledger, nhưng riêng trạng thái đó chưa xác nhận tính hợp lý của điểm.

## Sensitivity score means by configuration and instance

Each cell is the mean of VALID repetitions, followed by `n/3`. Empty cells mean no valid completed score is available.

| Config | T | Population | Perturbation | Mutation | I1 | I2 | I9 | I10 | I17 | I18 | I25 | I26 | I33 | I34 | I41 | I42 | I49 | I50 | I57 | I58 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 0.25 | 0.1 | 123.0 (3/3) | 91.8 (3/3) | 4,130.0 (3/3) | 131,561.8 (3/3) | 83.6 (3/3) | 616.8 (3/3) | 10,806.6 (3/3) | 5,607.2 (3/3) | 1,606.5 (3/3) | 7,686.1 (3/3) | 538,335.4 (3/3) | 161,468.8 (3/3) | 2,864,620.2 (3/3) | 3,775,526.9 (3/3) | 45,369,823.5 (3/3) | 12,130,409.2 (3/3) |
| 2 | 40 | 40 | 0.5 | 0.25 | 122.4 (3/3) | 91.8 (3/3) | 4,130.0 (3/3) | 135,215.9 (3/3) | 81.9 (3/3) | 614.9 (3/3) | 9,912.6 (3/3) | 10,132.9 (3/3) | 2,350.3 (3/3) | 8,489.0 (3/3) | 324,254.6 (3/3) | 153,432.5 (3/3) | 2,987,969.5 (3/3) | 3,775,526.9 (3/3) | 13,488,753.4 (3/3) | 32,280,365.5 (3/3) |
| 3 | 40 | 60 | 0.75 | 0.5 | 121.4 (3/3) | 91.8 (3/3) | 4,125.0 (3/3) | 123,145.8 (3/3) | 84.4 (3/3) | 616.1 (3/3) | 11,775.2 (3/3) | 13,243.4 (3/3) | 2,340.0 (3/3) | 10,992.1 (3/3) | 281,233.2 (3/3) | 99,994.9 (3/3) | 3,382,853.3 (3/3) | 3,148,220.9 (3/3) | 13,349,639.6 (3/3) | 12,248,567.5 (3/3) |
| 4 | 80 | 20 | 0.5 | 0.5 | 122.4 (3/3) | 91.8 (3/3) | 4,130.0 (3/3) | 123,145.8 (3/3) | 82.3 (3/3) | 614.5 (3/3) | 10,591.3 (3/3) | 10,715.9 (3/3) | 1,783.5 (3/3) | 9,299.7 (3/3) | 128,566.0 (3/3) | 140,047.7 (3/3) | 3,842,408.7 (3/3) | 3,565,884.6 (3/3) | 106,723,231.8 (3/3) | 12,091,170.5 (3/3) |
| 5 | 80 | 40 | 0.75 | 0.1 | 121.5 (3/3) | 91.8 (3/3) | 4,130.0 (3/3) | 123,145.8 (3/3) | 82.4 (3/3) | 617.6 (3/3) | 9,989.2 (3/3) | 17,089.8 (3/3) | 1,782.2 (3/3) | 9,399.6 (3/3) | 208,725.6 (3/3) | 102,042.6 (3/3) | 3,666,905.2 (3/3) | 3,775,526.9 (3/3) | 13,134,668.4 (3/3) | 98,885,391.1 (3/3) |
| 6 | 80 | 60 | 0.25 | 0.25 | 126.0 (3/3) | 91.8 (3/3) | 4,125.0 (3/3) | 123,145.8 (3/3) | 81.2 (3/3) | 618.3 (3/3) | 12,505.6 (3/3) | 21,611.2 (3/3) | 1,873.2 (3/3) | 12,974.2 (3/3) | 438,120.9 (3/3) | 288,110.6 (3/3) | 4,024,021.9 (3/3) | 3,731,464.5 (3/3) | 12,866,572.3 (3/3) | 12,487,872.6 (3/3) |
| 7 | 120 | 20 | 0.75 | 0.25 | 124.2 (3/3) | 91.8 (3/3) | 4,130.0 (3/3) | 131,561.8 (3/3) | 82.7 (3/3) | 616.6 (3/3) | 11,853.5 (3/3) | 6,633.7 (3/3) | 1,692.0 (3/3) | 10,828.1 (3/3) | 446,104.8 (3/3) | 155,251.7 (3/3) | 4,033,781.1 (3/3) | 3,775,526.9 (3/3) | 44,338,453.3 (3/3) | 12,936,460.2 (3/3) |
| 8 | 120 | 40 | 0.25 | 0.5 | 126.0 (3/3) | 91.8 (3/3) | 4,125.4 (3/3) | 135,215.9 (3/3) | 82.4 (3/3) | 616.8 (3/3) | 15,528.5 (3/3) | 31,819.8 (3/3) | 1,716.7 (3/3) | 10,788.5 (3/3) | 913,733.2 (3/3) | 186,188.5 (3/3) | 3,706,608.3 (3/3) | 3,565,884.6 (3/3) | 54,065,433.0 (3/3) | 13,802,957.0 (3/3) |
| 9 | 120 | 60 | 0.5 | 0.1 | 127.1 (3/3) | 91.8 (3/3) | 4,125.0 (3/3) | 123,145.8 (3/3) | 82.3 (3/3) | 615.7 (3/3) | 11,896.9 (3/3) | 8,326.7 (3/3) | 1,870.4 (3/3) | 11,018.9 (3/3) | 238,903.0 (3/3) | 261,773.5 (3/3) | 3,484,683.2 (3/3) | 3,565,884.6 (3/3) | 14,207,478.8 (3/3) | 13,793,228.1 (3/3) |
| 10 | 80 | 40 | 0.5 | 0.25 | 124.2 (3/3) | 91.8 (3/3) | 3,587.9 (3/3) | 123,145.8 (3/3) | 81.5 (3/3) | 615.9 (3/3) | 11,796.5 (3/3) | 8,566.3 (3/3) | 1,873.8 (3/3) | 9,296.5 (3/3) | 483,427.5 (3/3) | 259,077.6 (3/3) | 3,681,331.4 (3/3) | 3,775,526.9 (3/3) | 36,271,060.9 (3/3) | 13,142,401.7 (3/3) |

## Coverage by configuration

| Config | T | Population | Perturbation | Mutation | Valid / 48 | Running | Queued | Needs rerun |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 20 | 0.25 | 0.1 | 48 / 48 | 0 | 0 | 0 |
| 2 | 40 | 40 | 0.5 | 0.25 | 48 / 48 | 0 | 0 | 0 |
| 3 | 40 | 60 | 0.75 | 0.5 | 48 / 48 | 0 | 0 | 0 |
| 4 | 80 | 20 | 0.5 | 0.5 | 48 / 48 | 0 | 0 | 0 |
| 5 | 80 | 40 | 0.75 | 0.1 | 48 / 48 | 0 | 0 | 0 |
| 6 | 80 | 60 | 0.25 | 0.25 | 48 / 48 | 0 | 0 | 0 |
| 7 | 120 | 20 | 0.75 | 0.25 | 48 / 48 | 0 | 0 | 0 |
| 8 | 120 | 40 | 0.25 | 0.5 | 48 / 48 | 0 | 0 | 0 |
| 9 | 120 | 60 | 0.5 | 0.1 | 48 / 48 | 0 | 0 | 0 |
| 10 | 80 | 40 | 0.5 | 0.25 | 48 / 48 | 0 | 0 | 0 |

## Coverage by instance

| Instance | Valid / 30 | Running | Queued | Needs rerun |
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

## Files

- [One row per planned job (480 rows)](sensitivity_jobs_current.csv)
- [480 planned jobs grouped by order-count length](sensitivity_jobs_by_length.csv)
- [Score summary by length and configuration](sensitivity_summary_by_length.csv)
- [Taguchi factor-level summaries against baseline](sensitivity_factor_effects.csv)
- [Sensitivity summary by configuration and instance (160 rows)](sensitivity_summary_by_config_instance_current.csv)
- [Full attempt and provenance ledger](sensitivity_attempts.csv)
- [Detailed report](sensitivity_report.md)
