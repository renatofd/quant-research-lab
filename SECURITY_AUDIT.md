# Security Audit

**Audit date:** 2026-07-25

**Scope:** tracked files, root-level publication candidates, and scientific
source/documentation under `user_data/`

## Result

No real secrets were found in the publication set. The high-confidence scan
identified one intentionally truncated PEM block in `docs/exchanges.md`. The
generic scan identified documentation tokens and static test credentials.
Contextual review confirmed that these were placeholders, expired examples, or
fixtures—not local credentials.

The review found no:

- private keys;
- live GitHub tokens;
- AWS access keys;
- maintainer personal email addresses;
- paths containing a personal username;
- private IP addresses embedded in scientific source;
- literal credentials in modules, reports, or Research Protocols.

## Important Local Finding

`user_data/config.json` contains local Freqtrade API authentication values. The
file was already ignored by Git and remained outside the publication set. Its
contents were not displayed, copied, or modified.

Controls:

- `user_data/config.json` remains ignored;
- `.env` files, databases, WAL/SHM sidecars, and logs remain ignored;
- public examples use placeholders;
- documentation prohibits publishing real configurations;
- any secret shared outside this directory should be rotated, even if it never
  entered Git.

## Workflows and Supply Chain

The fork inherited Freqtrade workflows for Docker Hub, GHCR, documentation
deployment, tier updates, and package cleanup. Those workflows were tied to the
upstream identity and could request permissions or secrets irrelevant to this
repository.

For the scientific release:

- upstream-specific publishing and maintenance workflows were removed;
- test and security-analysis CI remained;
- existing actions use pinned commits, reducing mutable-tag risk;
- documentation, JSON, and bytecode checks require no secrets.

## Residual Risk

| Risk | Impact | Mitigation |
|---|---|---|
| Manually publishing `user_data/config.json` | Critical | `.gitignore`, staged-diff review, and credential rotation |
| Adding large raw datasets to Git | High | explicit exclusions for `raw/`, `evidence/`, databases, and logs |
| Running an upstream workflow against the wrong namespace | High | removal of deployment and package workflows |
| Trusting a scientific result without provenance | High | manifests, checksums, Scientific Ledger, and final report |
| Vulnerable third-party dependencies | Variable | Dependabot, existing pins, and periodic review |
| Mistaking historical operational code for a recommendation | High | README status and responsible-use disclaimer |

## Policy for New Files

Before every commit:

```bash
git status --short
git diff --cached
```

Review especially:

- `.env*`;
- `user_data/config*.json`;
- `*.sqlite*`;
- `*.pem`, `*.key`, `*.p12`, and `*.pfx`;
- logs and terminal dumps;
- signed URLs;
- cookies and authentication headers;
- personal filesystem paths.

Never partially redact a secret and assume it is safe. Remove it from history,
revoke it at the source, and issue a replacement.

## Decision

**Approved for publication under the current exclusion rules.** This approval
applied to the Git publication set, not to all local content under
`user_data/`. Ignored data and configuration must never be forced into Git with
`git add -f`.
