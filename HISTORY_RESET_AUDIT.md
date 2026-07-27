# Git History Reset Audit

**Date:** 2026-07-27

**Repository:** `renatofd/quant-research-lab`

**Purpose:** replace the inherited Freqtrade Git history with one independent
public-release commit while preserving the complete project tree, GPLv3
licensing, attribution, scientific results, and reproducibility records.

## Scope and Invariants

This operation changes Git metadata and history only. It must not modify:

- source code;
- scientific results;
- reports;
- Research Protocols;
- Scientific Ledgers;
- JSON or CSV Research Artifacts;
- recorded scientific hashes;
- raw or ignored local data.

The required licensing and attribution files remain:

- `LICENSE` — GNU General Public License v3 or later;
- `NOTICE.md` — explicit Freqtrade derivation and attribution;
- `README.md` — project status, upstream attribution, and license summary.

No `AUTHORS`, `AUTHORS.md`, `CONTRIBUTORS`, or `CONTRIBUTORS.md` file existed at
the repository root before the reset.

## Pre-Reset State

| Property | Value |
|---|---|
| Local branch | `main` |
| Local HEAD | `c9cc875ba8239a2a83e930dfd5d51953be0ad94f` |
| Remote | `https://github.com/renatofd/quant-research-lab.git` |
| Remote `main` | `74599fc7a2197bfee2a3a196a227569f110ced5b` |
| Remote tag object `v1.0.0` | `ff974246ec0cbd05becf76730247fe734675b6ad` |
| Remote tag target | `74599fc7a2197bfee2a3a196a227569f110ced5b` |
| Commits reachable from local HEAD | 31,816 |
| Commits reachable from all local refs | 31,847 |
| Distinct author identities | 485 |
| Working tree before backup | Clean; local `main` one commit ahead of `origin/main` |

## Recovery Bundle

Before the old `.git` directory was detached, the complete repository was
archived with:

```bash
git bundle create git_backup_before_history_reset.bundle --all
git bundle verify git_backup_before_history_reset.bundle
```

Bundle properties:

| Property | Value |
|---|---|
| Path | `git_backup_before_history_reset.bundle` |
| Size | 651,610,193 bytes |
| SHA-256 | `f6abecce7bc29cdeeb4551fa291c266174aa339cc15b7eafd346a0439a778c5e` |
| Refs | 122 |
| Verification | Complete history recorded; bundle valid |

The bundle remains in the project root as a local recovery artifact. It is
excluded through the new repository's local `.git/info/exclude` file and is not
committed, because committing it would embed the removed history in the new
repository.

To inspect or restore the previous repository:

```bash
git bundle verify git_backup_before_history_reset.bundle
git clone git_backup_before_history_reset.bundle restored-history
```

## Reset Procedure

1. Confirm a clean working tree and the configured author.
2. Capture exact remote branch and tag object IDs for force-with-lease.
3. Create and verify the complete `--all` recovery bundle.
4. Compute a deterministic SHA-256 inventory of every file outside `.git`.
5. Move the old `.git` directory out of the project without deleting it.
6. Initialize a new repository on `main`.
7. Restore the current user identity and the existing GitHub remote.
8. Exclude only the recovery bundle through `.git/info/exclude`.
9. Stage every non-ignored project file.
10. Create one root commit with message `Initial public release v1.0.0`.
11. Create the annotated tag `v1.0.0`.
12. Compare the complete pre-reset and post-reset file inventories.
13. Run `git fsck` and verify a clean working tree.
14. Show the exact outgoing branch and tag objects.
15. Publish with explicit `--force-with-lease` expectations for both `main` and
    `v1.0.0`; plain `--force` is prohibited.
16. Verify the remote commit count, contributor set, tag target, license,
    attribution, and project-tree integrity.

## GPLv3 and Attribution

Removing inherited Git metadata does not remove source-code copyright or
license obligations. The new repository retains the complete distributed
source tree, root GPLv3 license, Freqtrade attribution in `NOTICE.md`, upstream
references in the README and citation metadata, and the original copyright
notices embedded in source files.

This reset does not claim original authorship of upstream Freqtrade code. It
only prevents the new GitHub repository from presenting the upstream commit
graph as this project's contributor history.

## Commit Hash Note

The new root commit and tag hashes cannot be embedded in this file before that
commit is created: changing this file afterward would necessarily change the
root commit. They are therefore reported in the external completion summary and
can be verified directly with:

```bash
git rev-parse HEAD
git rev-parse v1.0.0
git rev-parse v1.0.0^{}
```
