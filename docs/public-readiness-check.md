# Public-readiness check (scan only; nothing published)

| | |
|---|---|
| Run | 2026-11-16 by claude-code, at the owner's instruction. **The repository stays PRIVATE.** Nothing was published, sent or rewritten |
| Scope | Every ref, local and on GitHub: `main`, `plan/eval-freeze-v2-within-site`, `model-backup`, and tags `eval-freeze-v1`, `eval-freeze-v2`, `eval-tool-v1`, `test-plan-v1`, `test-plan-v2`. That is 59 commits, scanned with `git log --all -p` and `git grep` over every revision. The binary blob `final_v1.joblib` was checked with `strings` |
| Tools | Pattern search. No dedicated scanner (gitleaks, trufflehog) is installed. A dedicated scanner is recommended before the repository is made public |

## Findings

| # | Finding | Where | Severity for going public |
|---|---|---|---|
| 1 | **No credentials found.** Patterns searched: AWS, Google API, GitHub, OpenAI, Anthropic and Slack tokens; private keys; password, secret, token and API-key assignments; Authorization and Bearer headers; Kaggle keys. The only two `"key":` hits are dictionary keys in code (`src/`), not secrets | all refs | none |
| 2 | **The owner's personal email address** appears in the content of `audit_log.jsonl` line 127 (the `correction` entry, as `sent_from` of the NCEI email). It is also the author and committer email of all 59 commits | audit log; commit metadata | **high** for privacy |
| 3 | **Records of the owner's personal activity:** an email to NCEI (line 125, recipient `pad.info@noaa.gov`, a public NOAA address), an NCAI newsletter sign-up (126), and its correction (127) | audit log | medium. These are personal records, not project facts |
| 4 | **Local paths** that reveal the username and directory layout: `/home/<user>/noaa-whale/.venv/bin/python`, `/home/<user>/noaa-whale-freeze`, and `/tmp/claude-1000/-home-<user>-noaa-whale/<session-id>/scratchpad/…` | `docs/analysis/stage_a/{test_T,test_S,watchdog_trial}/events.jsonl`; `docs/analysis/test_eval_dryrun/dryrun_summary.json` (lines 139, 146, 153); `audit_log.jsonl` line 637 (`stage_a_preflight`) | low to medium |
| 5 | **Owner's name and GitHub account** (`TomTolleson/whale-detection`, `git@github.com:` remote) | audit log lines 609 and 633; commit author names | low. Expected for an attributed public repository, but the owner's choice |
| 6 | **Machine hostname: not found** in any ref. No IP addresses were found | — | none |
| 7 | **Large or binary content:** only `final_v1.joblib` (44 KB, on the `model-backup` branch), plus text. No audio, no model weights from Google, and no source PDFs are in any ref. `sanctsound_README.pdf` and `data/` are git-ignored and never committed | all refs | none |
| 8 | **Third-party text:** the README and the docs quote short constraint and citation strings from NOAA metadata | docs | none expected (U.S. government metadata, quoted with attribution) |
| 9 | **The Claude session context** appears in places, e.g. "relayed from Claude Desktop" and session IDs in scratch paths | audit log; dry-run summary | low |

## Why nothing was fixed here

- **Findings 2-5 are in `audit_log.jsonl` and in committed evidence files.** The log is append-only and
  hash-chained. Editing or deleting a line breaks `verify_chain` and every later hash.
- **Removing them from history also needs a history rewrite**, such as `git filter-repo`, which changes every
  commit hash after the edit. In particular:
  - all five tags (`eval-freeze-v1`, `eval-freeze-v2`, `eval-tool-v1`, `test-plan-v1`, `test-plan-v2`) point at commits that come
    after line 127, so those tags would no longer resolve to the hashes recorded in the log and on GitHub;
  - the tag timestamps that were meant to be independent evidence would be lost.
- The owner did not ask for either change. Both would destroy the evidence the project is built on.

## Options for the owner (not done)

1. **Keep this repository private** as the authoritative, hash-verified record. Publish a **separate public
   repository** built from a redacted export:
   - code, docs and results at the final commit;
   - an audit-log copy with the personal fields (findings 2-4) replaced by `[redacted]`, and each redaction
     listed;
   - a statement that the private chain, with its tag hashes, can be checked on request.
2. **Publish this repository as it is.** That exposes findings 2-5.
3. **Rewrite history.** Not recommended: it breaks the tag hashes and the audit chain.

**Commit email:** before any public repository is created, consider committing to it with a GitHub
`users.noreply.github.com` address.
