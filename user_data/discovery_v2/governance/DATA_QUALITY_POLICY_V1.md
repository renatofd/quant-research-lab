# Discovery V2 — Permanent Data-Quality Policy v1.0.0

## State model

The permanent global data-admissibility states are:

1. `PASS`
2. `CONDITIONAL_PASS_DOCUMENTED_DATASET_LIMITATION`
3. `FAIL`

The conditional state is neither a mechanical pass nor a scientific result. It does not confirm or reject a hypothesis. The original 99.9% coverage gate remains unchanged and must still be reported as `FAIL` whenever coverage is below 99.9%.

## Conditional admission

Conditional admission requires all 15 criteria C01–C15 in the machine-readable policy. No criterion is waivable. Coverage must be at least 99.5%; a contiguous gap may not exceed 24 hours; there may be at most one affected session in a rolling 12-month interval; the missing set must be official, reproducible, immutable, symmetric, outcome-blind and unrecoverable from the same official source.

No filling, interpolation, reconstruction, favorable substitution or threshold relaxation is permitted. Historical reports remain immutable; any decision is an additive reclassification.

## Mandatory sensitivity

Every conditional dataset must use a pre-registered block-matched sensitivity analysis. Each eligible fully observed block of equal duration is removed globally, one at a time, and the unchanged scientific pipeline is rerun. If any deletion changes the final conclusion, the hypothesis is `INCONCLUSIVE`.

The policy is hypothesis-independent and applies prospectively to all Discovery V2 work. Retroactive use is allowed only when no outcome was inspected and the holdout remains sealed.
