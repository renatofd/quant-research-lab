# Contributing

Thank you for helping make this research easier to verify. The current research
program is closed for the available data, and the repository remains derived
from Freqtrade. Contributions must preserve both upstream compatibility and the
Evidence trail.

## Good Contributions

High-value contributions include:

- auditing a Research Protocol or final report;
- improving tests, documentation, accessibility, or Reproducibility;
- reproducing a Research Artifact from its registered manifest;
- reporting inconsistencies between a Scientific Ledger, JSON artifact, and
  Markdown report;
- evaluating a materially new point-in-time dataset;
- fixing software defects without changing the estimand or scientific decision.

The following are not routine improvements:

- retuning a rejected Hypothesis;
- combining technical indicators without an economic mechanism;
- changing gates after outcomes are known;
- converting a statistical relationship directly into a strategy;
- opening a sealed Holdout “to see whether it improves”;
- deleting or rewriting negative Evidence.

## Before Opening a Change

Open an issue before proposing methodological or architectural changes.
Describe:

1. the observable problem;
2. the files and components affected;
3. the effect on Reproducibility and upstream compatibility;
4. whether any result, hash, Research Protocol, or Holdout could change;
5. the validation you will perform.

A new Hypothesis is in scope only when it introduces a credible economic
mechanism and materially new data. Its Research Protocol must be preregistered
before outcomes are observed.

## Development Environment

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-dev.txt
```

## Validation

```bash
pre-commit run --all-files
pytest
```

For changes limited to the research layer, also run `py_compile` for affected
modules and validate every modified JSON file. Tests must not trigger scientific
campaigns as a side effect.

Documentation-only changes should validate:

- UTF-8 encoding;
- relative Markdown links;
- consistent terminology;
- byte-for-byte preservation of protected Research Artifacts.

## Engineering Standards

- Use English for source code, comments, and public documentation.
- Document public functions and non-obvious scientific assumptions.
- Keep changes small, focused, and reviewable.
- Use portable paths through `pathlib`.
- Record seeds, versions, periods, and cost assumptions explicitly.
- Write Research Artifacts atomically.
- Never commit credentials or personal filesystem paths.
- Justify new dependencies.

## Scientific Integrity

- Do not edit final Research Artifacts to fit a preferred narrative.
- Keep Research Protocols and results as separate records.
- Separate mechanical QA from outcome analysis.
- Record every protocol deviation.
- Never treat missing data as zero.
- Do not select the Bootstrap unit after observing results.
- Distinguish experimental failure, documented dataset limitation, blockage,
  and rejection.
- Do not claim an edge without post-cost economic relevance.
- Do not reopen a closed research line without new data and a new mechanism.

## Pull Requests

Every pull request should:

- explain its motivation and scope;
- list files created, modified, and removed;
- state whether scientific results remained byte-for-byte unchanged;
- provide the validation commands and results;
- disclose material use of AI-assisted tooling and confirm human review;
- update documentation and the changelog when appropriate.

Do not include raw data, databases, logs, `.env` files, or
`user_data/config.json`.

## License

By contributing, you agree that your contribution will be distributed under
the GNU General Public License v3 or later, consistent with this repository's
derivation from Freqtrade.
