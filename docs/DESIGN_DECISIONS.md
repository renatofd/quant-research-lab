# Design Decisions

This document records the architectural and methodological choices that shape
the repository. Decision identifiers are stable references for future
maintenance.

## DD-001: Freqtrade Is the Engine; the Laboratory Is a Separate Layer

The upstream core remains intact so the project can reuse market-data access,
persistence, and execution infrastructure without rebuilding a platform.
Scientific interpretation remains outside the engine.

## DD-002: One Hypothesis per Campaign

Each scientific instrument answers one preregistered question. This limits
hidden multiplicity and prevents a focused module from becoming an
unconstrained search tool.

## DD-003: Mechanical QA Precedes Outcomes

Acquisition, coverage, schemas, timestamps, and checksums are evaluated before
returns or PnL. A data failure cannot be converted into an economic result.

## DD-004: Dataset States Are Explicit

The data-quality policy distinguishes:

- `PASS`;
- `PASS WITH DOCUMENTED DATASET LIMITATION`;
- `FAIL`.

The intermediate state requires an official source, a uniform limitation, no
legitimate same-source recovery path, an impact assessment, and complete
traceability. Selective gaps, outcome-dependent missingness, or missing
provenance still block the experiment.

## DD-005: Holdouts Remain Sealed

Holdouts are defined before analysis. If development Evidence fails magnitude
or economic gates, the Holdout remains closed. Statistical independence is not
spent for curiosity.

## DD-006: Bootstrap Units Follow the Data-Generating Process

Adjacent candles are not independent. Each Research Protocol uses days or
blocks appropriate to its estimand instead of independent-candle resampling.

## DD-007: Holm Correction and Negative Controls Are Mandatory

Multiple comparisons receive Holm correction. Pseudo-leaders, circular shifts,
reverse time, placebos, and baselines test whether an apparent effect is
specific to the proposed mechanism.

## DD-008: Economic Value Precedes Operational Work

A coefficient and p-value do not promote a Hypothesis. The effect must survive
costs, replicate across assets and time, and remain operationally measurable.

## DD-009: Historical Research Artifacts Are Not Relocated

The open source release added indexes instead of moving reports and scripts.
Paths are part of manifests, hashes, provenance, and recorded commands.

## DD-010: Raw Data Does Not Belong in Git

Raw data, databases, caches, and logs are stored locally or in a dedicated data
repository. Git contains source, provenance, selected manifests, and aggregate
Research Artifacts.

## DD-011: The GPL License Is Preserved

The repository is derived from Freqtrade under GPLv3. Replacing the root license
with MIT would remove upstream obligations that the maintainer cannot
unilaterally relicense.
