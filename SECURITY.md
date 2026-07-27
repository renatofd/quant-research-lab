# Security Policy

## Supported Versions

| Version | Support |
|---|---|
| 1.x | Security and integrity fixes |
| Earlier snapshots | Historical documentation only |

## Reporting a Vulnerability

Do not open a public issue for:

- exposed credentials;
- arbitrary code execution;
- exploitable dependency vulnerabilities;
- Holdout bypass or silent manipulation of Research Artifacts;
- files containing personal data.

Use GitHub's **Private vulnerability reporting** feature for this repository.
Include:

1. the affected component and version;
2. the expected impact;
3. minimal reproduction steps;
4. sanitized Evidence;
5. a suggested mitigation, if available.

If private reporting is not enabled, do not publish sensitive details. Open a
generic issue asking the maintainers to provide a private security channel.

## Response and Disclosure

When the project has active maintainers, they will acknowledge the report,
assess severity, and coordinate disclosure after a fix is available. This
community project does not provide a commercial service-level agreement.

## Secrets

Never submit exchange keys, tokens, cookies, `.env` files,
`user_data/config.json`, databases, or session dumps. If a secret enters a
commit:

1. revoke it immediately;
2. issue a replacement;
3. remove the exposed value from Git history;
4. document the incident without reproducing the value.

## Scientific Integrity

An inconsistency that could change a scientific decision is an integrity issue.
Do not silently “fix” a final report. Preserve the original Research Artifact,
publish an erratum, and update the Scientific Ledger with a traceable
explanation.
