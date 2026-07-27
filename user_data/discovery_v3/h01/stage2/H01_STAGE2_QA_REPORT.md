# H01 — Stage 2 Acquisition and Mechanical QA

Status: **STAGE2_QA_PASS**

- Official archives inspected: 5163
- QA failures: 0
- Holdout: SEALED
- Economic outcomes computed: no
- Forward returns computed: no

| Family | Files | Passed | Failed | Rows |
|---|---:|---:|---:|---:|
| liquidation | 2488 | 2488 | 0 | 245912 |
| perp_1m | 102 | 102 | 0 | 4449600 |
| mark_1m | 102 | 102 | 0 | 4449420 |
| index_1m | 102 | 102 | 0 | 4449420 |
| metrics_5m | 2267 | 2267 | 0 | 652572 |
| spot_1m | 102 | 102 | 0 | 4484160 |

Exact provider duplicates in liquidation partitions were removed only in a hashed derived layer; raw archives remain immutable.
Normalized liquidation rows: 122941
Exact duplicates removed: 122971

Stage 2 passed. Stage 3 may inspect development outcomes only.
