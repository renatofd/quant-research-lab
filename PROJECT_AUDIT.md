# Project Audit

**Audit date:** 2026-07-25

**Scope:** the `freqtrade` checkout, including ignored files under `user_data/`

**Mode:** structural review and conservative cleanup; no experiments executed

## Executive Summary

Before cleanup, the repository contained a complete Freqtrade fork, a custom
Scientific Framework, three generations of research, and approximately 10 GB
of local data and Research Artifacts. The primary publication risk was not dead
code. It was the coexistence of:

- upstream source code;
- scientific instruments;
- final documentation;
- raw data and reproducible Evidence;
- thousands of logs and cache files;
- local operational configuration.

The publication layout uses curated indexes and explicit version-control rules.
Historical Research Artifacts were not relocated, and paths used by scientific
instruments were not rewritten.

## Initial Inventory

| Area | Files | Approximate size | Classification |
|---|---:|---:|---|
| Git-tracked repository | 772 | — | Upstream source and documentation |
| Untracked root files | 46 | ~2.1 MB | Research Protocols, reports, and Scientific Ledgers |
| `user_data/` | 134,917 | 10.02 GB | Source, data, results, and runtime state |
| `user_data/lab/` | 103,500 | 8.91 GB | 3,678 runs, reports, and infrastructure |
| `user_data/discovery_v2/` | 16,128 | 413 MB | Data, QA, instruments, and results |
| `user_data/discovery_v3/` | 15,108 | 627 MB | Data, QA, instruments, and results |
| Logs | 3,595 | 3.27 GB | Disposable |
| Python caches/bytecode | 95 | 1.13 MB | Disposable |
| SQLite databases and sidecars | 5 | 43.18 MB | Preserve |
| `.tmp`, `.bak`, and `.orig` files | 0 | 0 | No findings |

## Findings

### Data and Results

- `user_data/lab/runs/` accounted for most local storage.
- Raw Discovery V2/V3 data is reproducible Evidence but is not suitable for
  Git.
- Manifests, checksums, final reports, Research Protocols, and Scientific
  Ledgers are required for traceability and were preserved.
- SQLite databases and WAL/SHM sidecars were retained because they may contain
  scientific state or unconsolidated transactions.

### Duplication

The review found nine families of identical content in the sampled source and
documents. Material examples included:

- upstream templates copied into `user_data/`;
- historical aliases for final reports;
- audit snapshots and their `latest` states;
- five empty JSON files associated with rejected optimum regions.

No files were removed for duplication alone. Copies are intentional in the
examples, and removing aliases from scientific results could break provenance
or historical references.

### Potentially Obsolete Code

- Historical strategies and operational families remain present even though
  they were scientifically rejected.
- Phase 1–4 modules remain necessary for Reproducibility and audit.
- Discovery V3 acquisition and analysis scripts are standalone CLIs and may not
  appear in an import graph.

There was not enough Evidence to delete any module. In a collection of
scientific CLIs, “not imported” does not mean “dead.”

### Notebooks

The only notebook was the Freqtrade example, plus `.gitkeep` placeholders. It
was not classified as abandoned research.

### Historical Documentation

`PROJECT.md`, `CURRENT_STATE.md`, and `RESEARCH_HANDBOOK.md` describe earlier
project stages rather than the final state. They remain historical records. The
README, Discovery V3 final report, and definitive Scientific Ledger are the
canonical current sources.

### Git and Release State at Audit Time

- the local remote still referenced `freqtrade/freqtrade`;
- the active branch was `develop`;
- `docker-compose.yml` contained a pre-audit local change that was preserved;
- upstream publishing workflows depended on the original project's identity
  and secrets and did not belong in this research release.

These observations describe the audit snapshot. Publication subsequently moved
the project to its own `main` branch and repository.

## Cleanup Performed

The cleanup removed only:

- 3,595 `.log` files;
- 95 Python cache or bytecode files under `__pycache__`, `.pyc`, or `.pyo`;
- empty `__pycache__` directories;
- upstream-specific deployment and package automation that did not affect
  source code.

The cleanup reclaimed approximately **3.27 GB**.

The post-cleanup inventory contained **131,262 files** and **6.75 GB** under
`user_data/`, with no remaining logs or Python caches.

The cleanup did not remove:

- raw data;
- databases or sidecars;
- manifests or checksums;
- Research Protocols;
- final reports;
- Scientific Ledgers;
- scientific results;
- Python modules;
- historical strategies;
- the user's pre-existing local change.

## Publication Layout

```text
.
├── freqtrade/                  # Upstream engine
├── user_data/                 # Instruments and local Evidence
├── research/                  # Public research index
├── reports/                   # Public results index
├── docs/                      # Technical and portfolio documentation
├── scripts/                   # Upstream scripts
├── config_examples/           # Sanitized examples
├── .github/                   # Collaboration and CI
├── ARCHITECTURE.md
├── PROJECT_AUDIT.md
└── SECURITY_AUDIT.md
```

The upstream package was not moved into `src/`. Such a change would break
imports, packaging, tests, and Freqtrade compatibility without providing
scientific value.

## Intentional Follow-up Work

- decide whether raw data should be deposited in an external scientific
  repository;
- avoid Git LFS until retention and cost policies are defined;
- keep Holdouts and local datasets outside Git history;
- complete human review of authorship and citation metadata.

## Decision

The repository was structurally suitable for a public release of source code,
documentation, and summarized Evidence. Local data remained deliberately
outside the Git package. Scientific conclusions and results were preserved.

The final publication set contained 381 previously untracked files (22.82 MB),
with no raw-data blobs, Evidence blobs, databases, logs, or caches.
