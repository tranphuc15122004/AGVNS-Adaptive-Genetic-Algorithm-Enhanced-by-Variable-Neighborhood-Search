# Gold: audit of instances 57, 58, 59, 60, 63, 64

## Confirmed historical scores

`AGVNS/Kết quả thử nghiệm.xlsx`, worksheet `Sheet1`, labels column E as Gold and records the following values. `AGVNS.pdf`, Table 6, repeats them rounded. The workbook already contains the values in Git commit `16b5e93` dated 2025-12-20. Neither source identifies the original job, runtime, seed or execution host.

| Instance | Workbook cell | Gold score |
|---:|---|---:|
| 57 | E58 | 10,686,649.53 |
| 58 | E59 | 10,283,491.05 |
| 59 | E60 | 9,319,943.286 |
| 60 | E61 | 10,700,000 |
| 63 | E64 | 17,760,068.36 |
| 64 | E65 | 16,764,545.721333301 |

The adjacent F–O cells contain numerical values but have no column headers identifying their algorithm, seed, timestamps or source. They cannot independently establish the original Gold jobs or runtimes.

## Scope searched

- The current host reports hostname `teslaT4`. Searched the current project workspace, Gold logs under `1/compiled_files/src/output/log`, targeted locations under `/home/tuantb` and `/mnt/data`, and the DPDP thesis source. The thesis repeats the published Gold scores.
- Inspected source and session logs of all 30 saved versions of `trnphc15122004/gold-medal` and all 65 saved versions of `trp1512/gold-medal-notebook`. No version selects or logs a start or final score for the six instances. Python `range(55, 57)` selects 55 and 56; `range(61, 63)` selects 61 and 62.
- Catalogued the latest saved output files of both Gold notebooks. Their application log filenames do not include these six instances. Downloaded and inspected the latest application logs: the newest logs cover instances 53–54 and 50–51, respectively.
- Examined the notebook source of 441 versions from seven other DPDP-related notebooks across the two accounts. Their `selected_instances` assignments did not select any of the six instances. This is a source-code audit, not a full download of every output file.
- Compared the Gold score in column E and the adjacent unlabeled F–O numeric values for these six rows against scores recorded in the 95 Gold notebook session logs and local Gold application logs; no exact score match was found.

## Interpretation

The historical Gold scores exist, and the previous claim that Gold results were absent was too broad. The saved Gold notebook sessions available in the two named accounts have no recorded job or runtime for the six instances; the original jobs' location remains unknown. The 58/64 figure in `gold_coverage_two_accounts.csv` refers only to completed jobs evidenced by those two notebooks' downloaded session logs, not to historical score availability.
