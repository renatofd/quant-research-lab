# Release 1.0.0 — Scientific Closure

Release date: 2026-07-25

## What this release is

Version 1.0.0 is the first public, portfolio-ready snapshot of the Quantitative
Research Lab. It packages the framework, scientific instruments, governance and
negative results that led to the formal decision not to build an operational
bot.

## Scientific conclusion

**No robust economic edge was discovered under the tested data, universes,
costs and protocols. No bot is approved.**

The release preserves:

- rejected operational families and their methodological lessons;
- Phase 4 economic hypotheses based on OHLCV;
- Discovery V2 acquisition and QA work;
- Discovery V3 literature, data gates, controls and final ledger;
- sealed holdouts that were not opened after development refutation.

## Highlights

- strict separation between mechanical QA and economic analysis;
- preregistered gates and single-hypothesis campaigns;
- day/block bootstrap rather than independent-candle resampling;
- Holm correction and negative controls;
- temporal and cross-asset replication;
- explicit post-cost economic gates;
- permanent recording of rejection, blockage and experimental failure.

## Repository preparation

- public README and architecture;
- audit and security reports;
- contribution, conduct, support and security policies;
- curated research and report indexes;
- GitHub issue, PR and discussion templates;
- versioning, changelog and citation metadata;
- raw data, databases, logs and local credentials excluded from Git;
- upstream deployment workflows removed from the fork.

## Compatibility

The Freqtrade package layout is preserved. Historical scripts retain their
original paths so imports, provenance and recorded commands are not rewritten.

## Known limitations

- public Git does not include the multi-gigabyte local data lake;
- not every historical report is curated into a top-level index;
- no virgin OHLCV holdout remains for the closed programs;
- H05–H08 require datasets unavailable in the current project;
- this is not trading software approved for real capital.

## Licensing note

The repository remains under GNU GPL v3 or later because it is derived from
Freqtrade. Replacing the root license with MIT would be incompatible with the
upstream copyleft obligations.

## Upgrade notes

No database migration or strategy change is part of this release. Existing local
configuration remains private and untouched. Before publishing, configure a new
Git remote and review staged files with `git diff --cached`.
