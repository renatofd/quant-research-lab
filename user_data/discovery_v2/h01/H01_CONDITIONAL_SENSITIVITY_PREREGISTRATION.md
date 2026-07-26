# V2-H01 — Conditional Dataset Sensitivity Preregistration

This document was frozen while the holdout was `SEALED` and before any economic outcome was inspected.

The official missing block is 29 June 2026, 00:00–23:55 UTC: 288 five-minute timestamps, common to all ten assets and to mark, index and premium feeds. H01 is a general 24-month, multi-asset funding/basis carry hypothesis; this calendar day is not a defining event, regime or causal window in the pre-outcome catalog or D0 decision.

## Common intersection

The missing day must be excluded globally from every asset and every required H01 feed, including spot, perpetual and funding data that are locally present. Nothing may be filled, reconstructed or substituted.

## Block-matched sensitivity

After the complete D2–D4 pipeline is frozen, it must first run on the common-intersection dataset. Then every eligible, fully observed UTC day of equal duration is removed globally, one day at a time, and the exact pipeline is rerun without tuning, selection or early stopping.

If any matched-day deletion changes the final H01 conclusion, H01 is `INCONCLUSIVE`. Sensitivity can never rescue a failed primary gate. All candidate days, stage decisions and conclusion flips must be reported.

Prospective operational replication remains mandatory even if every historical gate passes.
