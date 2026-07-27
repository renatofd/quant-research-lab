# Publication Guide

This guide documents the release process for maintainers and future archival
snapshots.

## 1. Define the Publication Boundary

Publish source code, documentation, selected manifests, and aggregate Research
Artifacts. Do not publish the local data lake.

## 2. Verify the Repository Destination

The public repository is:

```text
https://github.com/renatofd/quant-research-lab
```

Before any push:

```bash
git remote -v
git branch --show-current
git status --short
```

Do not change a remote until the destination and authorization are verified.

## 3. Inspect the Candidate Files

```bash
git status --short
git check-ignore -v user_data/config.json
git diff
```

After staging:

```bash
git diff --cached --stat
git diff --cached
```

Never use `git add -f` for `user_data/config.json`, `.env` files, `raw/`,
`evidence/`, databases, or logs.

## 4. Review Sensitive Data

Search for tokens, keys, personal paths, private IP addresses, signed URLs, and
session dumps. If a secret has entered Git history, deleting it in the latest
commit is insufficient: revoke the credential and rewrite the affected history
before publication.

## 5. Validate the Release Candidate

Validate:

- Markdown syntax and relative links;
- UTF-8 encoding;
- JSON syntax;
- `CITATION.cff`;
- `py_compile` for scientific modules;
- tests that do not execute research campaigns;
- GitHub Actions without upstream secrets;
- byte-for-byte preservation of protected Research Artifacts.

## 6. Configure GitHub Metadata

Recommended description:

> Falsifiable quantitative-research lab built on Freqtrade, with preregistered
> gates, rigorous negative results, and reproducible scientific Governance.

Recommended topics:

`quantitative-research`, `crypto`, `reproducibility`, `falsification`,
`freqtrade`, `research-engineering`, `open-science`

Recommended repository features:

- Issues;
- Discussions;
- private vulnerability reporting;
- branch protection;
- Dependabot alerts.

## 7. Create a Release

Create the tag only after validation:

```bash
git tag -s v1.0.0 -m "Quantitative Research Lab v1.0.0"
git push origin main v1.0.0
```

A signed tag is recommended but not mandatory. Use
[`RELEASE_NOTES_v1.0.0.md`](../RELEASE_NOTES_v1.0.0.md) as the release body.

## 8. Preserve Licensing and Attribution

Do not replace `LICENSE` with MIT. The combined work is derived from Freqtrade
and remains under GPLv3 or later. Preserve [`NOTICE.md`](../NOTICE.md) and
upstream attribution.
