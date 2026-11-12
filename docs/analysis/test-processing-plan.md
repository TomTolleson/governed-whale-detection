# Test-day processing plan (written before any test day is processed)

| | |
|---|---|
| Status | **Written 2026-11-12, before any test audio is processed and before any test label is read.** Restates the frozen rules (evaluation-plan v2 §2, §5, §7, §8; sb01_02 plan §3c; eval_plan §7) and fixes the operating details they leave open. Items marked *(claude-code, T1-T3)* need owner confirmation |
| Frozen commit for test scoring | tag **`eval-freeze-v2`**, commit **`e204ff9`** (`e204ff945e215d25de845494fe0b370187024d61`). `src/pilot.py` there is byte-identical to `eval-freeze-v1` (`47a0b6f`) |
| Final model | Fixed in `docs/analysis/final_model/spec.json`, with its artefact SHA-256 logged in the `final_model` audit entry before Stage A |
| Releases | **Stage A** (audio) and **Stage B** (labels). Each needs its own explicit owner release, quoted verbatim in the log (protocol P7) |

## 1. Which days

The days are exactly those in `data/sample_days.csv` (SHA-256 `3c47e9bc196ba1338d6eab77949e57a41e643b382b7c4c752a39ca6c6201947d`,
seed 20261109). There are **400 test days**. **No day is ever added, swapped or replaced.**

| Split | Site | Deployments and days | Total |
|---|---|---|---|
| Test T | sb01 | 10: 29 · 11: 16 · 12: 30 | 75 |
| Test T | sb02 | 10: 29 · 11: 15 · 12: 31 | 75 |
| Test S | sb03 | 01: 25 · 02: 23 · 03: 21 · 04: 22 · 05: 23 · 06: 22 · 07: 10 · 08: 23 · 09: 23 · 10: 22 · 11: 12 · 12: 24 | 250 |
| Test S 10-12 slice | sb03 | 10, 11, 12 (a subset of S, not scored separately) | 58 |

## 2. Stage A: score the test audio (no labels)

1. **Checkout of the frozen code:** `git worktree add ../noaa-whale-freeze eval-freeze-v2`. Inside it, `data/` is a
   symlink to this repo's `data/`. `data/` is git-ignored, so the link does not count as a change.
2. **Audit log** *(T1)*. The worktree has its own copy of `audit_log.jsonl`, frozen at the tag. Logging there
   would fork the hash chain. So:
   - immediately before scoring, **copy this repo's `audit_log.jsonl` into the worktree** (chain verified);
   - while scoring runs, **log nothing in this repo**;
   - afterwards, **copy it back** (chain verified again);
   - commit it here.

   The result is one linear chain. In the worktree, `git status` shows only `audit_log.jsonl` as changed.
   `src/` is clean, which is what the test gate checks.
3. **Pre-flight, logged as `stage_a_preflight`:**
   - the worktree HEAD is `e204ff9` and carries `eval-freeze-v2`;
   - `git status` in the worktree shows nothing except `audit_log.jsonl`;
   - `data/scores/v2_test/` does not exist yet.
4. **Scoring:** two runs through the test gate, with output to `data/scores/v2_test/`.
   `--owner-approval` quotes the owner's Stage A release word for word, and `test_gate_passed` logs it.

   ```
   python -m src.pilot --actor claude-code --split test_T --owner-approval "<Stage A release>"
   python -m src.pilot --actor claude-code --split test_S --owner-approval "<Stage A release>"
   ```

   - If a run is interrupted (network, crash), it is resumed with `--skip-existing`. That keeps only days whose
     `.npz` matches its logged SHA-256. A resume is **not** a QA re-run.
5. **QA handling.** The rules are evaluation-plan §5, unchanged. Each flag is listed per split in every report:

| Flag | Handling |
|---|---|
| Zero fraction > 0.01 (day) | Kept. Day-level sensitivity: flagged days excluded (eval_plan §7). The deployment-level rule is §3 below |
| Gaps (`>1 min gap`) | Kept. Gaps count as time with no detections. Never bridged |
| Overlaps > 2 s | Kept. Trimming is routine |
| Short day (< 20 h of windows, but eligible by the day table) | Kept and listed |
| Non-finite scores or band levels, decode error, size mismatch, or a day that cannot be completed | **Re-run once.** If the flag remains, **exclude the day and list it with the reason.** It is never replaced by another day |

   Re-run procedure *(T2)*:
   - Move the first attempt's `.npz` to `data/scores/v2_test_first_attempt/`. It is never overwritten or
     deleted.
   - Log `qa_rerun` (day, flag, the first file's SHA-256).
   - Re-score that day alone, through the same gate, from a one-row day list (split, site, deployment and date;
     no label).
   - If the flag remains, log `qa_exclusion` (day, reason). `src/test_eval.py` drops and lists every
     `qa_exclusion` day.
6. **Drift report**, from this repo at the commit that adds `src/drift_report.py`. It reads features only:

   ```
   python -m src.drift_report --actor claude-code --split test_T
   python -m src.drift_report --actor claude-code --split test_S
   ```

   Its outputs:
   - median zero fraction per deployment, with the sb01_02-equivalence check (§3);
   - band levels against the train/val range, with the 6 dB flag;
   - zero-shot Mn score distributions;
   - embedding distance to the nearest train/val deployment, and the deployment-ID probe.

   The report is logged with its hash and committed. **Flags are reported, not acted on.** They exclude nothing.
   `--self-check` on train/val shows how often each flag fires when there is no shift. It is run and committed
   before Stage A.
7. **Stop.** Report the Stage A outputs: QA flags, re-runs, exclusions, sb01_02-equivalent deployments and drift
   flags. Then wait for the owner's Stage B release.

## 3. Deployments like sb01_02 (sb01_02 plan §3c, unchanged)

- A test deployment is **equivalent to sb01_02** if the **median `zero_fraction` over its sampled days is above
  0.01**.
- This is computed in Stage A, from audio QA only, and logged in the `drift_report` entry **before any test label
  or test score is read**.
- **Treatment:**
  - primary test results **include** them;
  - a sensitivity result **excludes** them;
  - both are always reported;
  - the §3b materiality rule applies to pooled AUROC and AUROC_ws (as amended for v2).
- Zero-flagged days in deployments that are not equivalent are handled by the day-level sensitivity
  (eval_plan §7).
- No other exclusion may be added after test data is seen, except as a logged deviation reported both ways.

## 4. Stage B: evaluate (labels read once)

- `src/test_eval.py` is the only code that reads test labels. It is **committed before Stage A**. It refuses to
  run unless all of these hold:
  - the owner's Stage B release is given, and is logged verbatim (`stage_b_release`);
  - the final-model artefact and `spec.json` match their logged SHA-256;
  - both Stage A drift reports are logged;
  - every test `.npz` matches its `score_day` SHA-256 and carries a freeze-tag commit.
- Nothing is tuned. The model, aggregation, day threshold, baseline thresholds and baseline fits all come from
  the frozen spec and artefact.
- **What it computes,** for Test T, Test S and the S 10-12 slice:
  - AUROC_ws (headline) and pooled AUROC, each with a deployment-block bootstrap CI;
  - PR-AUC (absent as positive);
  - balanced accuracy at the fixed thresholds;
  - paired CIs against the month prior, ambient noise, zero-shot primary and the site prior;
  - the two-condition improvement claim against the best baseline by AUROC_ws;
  - breakdowns by site, season and deployment (≥ 5 / ≥ 5 rule; CIs at ≥ 3 deployments);
  - calibration per deployment;
  - site-ID probe (Test T);
  - the zero-flag-day sensitivity, and the sb01_02-equivalent sensitivity where it applies.
- **One clean pass.** Its outputs are committed as produced. Any change after Stage B begins is a **deviation**:
  logged (`deviation`), noted in the results and reported both ways (evaluation-plan §8).

## 5. Known risk, stated before the results

The selected model's day threshold comes from pooled train/val out-of-fold scores. For block-level
aggregations it sits close to 1 (cv_v1: 0.996 for block max), because the block probabilities saturate. At a new
site (Test S) it may transfer poorly, so balanced accuracy could fall while AUROC holds. The plan claims no
cross-site calibration (eval_plan §6).

## 6. Decisions for the owner

| # | Proposed | Alternative |
|---|---|---|
| T1 | Audit log: copy it into the worktree, score, copy it back. One linear chain, and nothing logged here during scoring | Replace the worktree's `audit_log.jsonl` with a symlink to this repo's log |
| T2 | QA re-run: move the first attempt to `v2_test_first_attempt/`, log `qa_rerun`, re-score that day alone; `qa_exclusion` if the flag remains | — |
| T3 | Stage A and Stage B as separate releases | — |
