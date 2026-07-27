# Research Index

This directory is the entry point to the scientific record. Research Artifacts
remain in their original locations to preserve paths, hashes, provenance, and
Reproducibility.

## Program Evolution

| Generation | Research question | Canonical source | Status |
|---|---|---|---|
| Phases 1–3 | Do strategies and components generalize? | [`RESEARCH_HANDBOOK.md`](../RESEARCH_HANDBOOK.md) | Closed |
| Phase 4 | Does OHLCV contain an economically useful mechanism? | [`PHASE4_FINAL_SCIENTIFIC_REPORT.md`](../PHASE4_FINAL_SCIENTIFIC_REPORT.md) | Closed without an edge |
| Discovery V2 | Do derivatives data support H01/H02? | [`DISCOVERY_V2_SCIENTIFIC_LEDGER.md`](../DISCOVERY_V2_SCIENTIFIC_LEDGER.md) | Closed |
| Discovery V3 | Is any new mechanism robust and executable? | [Discovery V3 final report](../user_data/discovery_v3/final/DISCOVERY_V3_FINAL_SCIENTIFIC_REPORT.md) | Closed without an edge |

## Current Canonical Records

- [Discovery V3 Charter](../user_data/discovery_v3/governance/DISCOVERY_V3_CHARTER.md)
- [Definitive Scientific Ledger](../user_data/discovery_v3/governance/SCIENTIFIC_LEDGER.md)
- [Final Hypothesis Inventory](../user_data/discovery_v3/final/FINAL_HYPOTHESIS_INVENTORY.md)
- [Final Data Inventory](../user_data/discovery_v3/final/FINAL_DATA_INVENTORY.md)
- [Final Decision Tree](../user_data/discovery_v3/final/FINAL_DECISION_TREE.md)
- [Objective Recommendations](../user_data/discovery_v3/final/OBJECTIVE_RECOMMENDATIONS.md)

## How to Review a Hypothesis

Read each campaign in this order:

1. **Stage 0:** economic rationale and literature.
2. **Stage 1:** data availability, provenance, and scientific cost.
3. **Stage 2:** acquisition and mechanical QA without outcomes.
4. **Stage 3:** frozen development analysis with registered controls.
5. **Decision:** `CONFIRMED`, `REJECTED`, `BLOCKED`, or experimental failure.

Do not begin with the largest coefficient. Begin with the Hypothesis, estimand,
Research Protocol, decision gates, and negative controls.

## Data Availability

Git does not contain the local data lake. Reports and manifests identify
sources, periods, coverage, and hashes. Excluding multi-gigabyte blobs from the
repository does not alter recorded scientific decisions; it keeps source
control separate from data storage.
