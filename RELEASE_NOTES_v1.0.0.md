# Quantitative Research Lab 1.0.0

**Release date:** 2026-07-25

**Release status:** scientific closure

## Overview

Version 1.0.0 is the first public, portfolio-ready release of the Quantitative
Research Lab. It packages the Scientific Framework, research instruments,
Governance, and negative Evidence that led to the formal decision not to build
an operational trading bot.

## Scientific Conclusion

**No robust economic edge was discovered under the tested data, universes,
costs, and Research Protocols. No bot is approved.**

This release preserves:

- rejected operational families and their methodological lessons;
- Phase 4 economic Hypotheses evaluated with OHLCV data;
- Discovery V2 acquisition and mechanical QA work;
- Discovery V3 literature reviews, data gates, controls, and final Scientific
  Ledger;
- sealed Holdouts that were not opened after development refutation.

## Highlights

- strict separation between mechanical QA and economic analysis;
- preregistered gates and single-Hypothesis campaigns;
- day- or block-level Bootstrap instead of independent-candle resampling;
- Holm correction and negative controls;
- temporal and cross-asset replication;
- explicit post-cost economic gates;
- permanent recording of rejection, blockage, and experimental failure.

## Repository Preparation

- project-focused README and Architecture;
- structural and security audits;
- contribution, conduct, support, and security policies;
- curated research and report indexes;
- GitHub issue, pull request, and discussion templates;
- versioning, changelog, and citation metadata;
- raw data, databases, logs, caches, and local credentials excluded from Git;
- upstream-specific deployment workflows removed from the fork.

## Compatibility

The Freqtrade package layout is preserved. Historical scripts retain their
original paths so imports, provenance records, manifests, and recorded commands
remain valid.

## Known Limitations

- The public repository does not include the multi-gigabyte local data lake.
- Not every historical report is promoted into a top-level index.
- No untouched OHLCV Holdout remains for the closed research programs.
- H05–H08 require datasets unavailable to the current project.
- This release is not trading software approved for real capital.

## Licensing

The repository remains under the GNU General Public License v3 or later because
it is derived from Freqtrade. Replacing the root license with MIT would conflict
with upstream copyleft obligations.

## Upgrade Notes

This release includes no database migration and no scientifically approved
strategy change. Existing local configuration remains private and untouched.

See the [full changelog](CHANGELOG.md) and
[release on GitHub](https://github.com/renatofd/quant-research-lab/releases/tag/v1.0.0).
