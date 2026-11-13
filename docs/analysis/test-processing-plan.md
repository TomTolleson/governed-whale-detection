# Test-day processing plan (written before any test day is processed)

| | |
|---|---|
| Status | **Written 2026-11-12, before any test audio is processed and before any test label is read.** Restates the frozen rules (evaluation-plan v2 §2, §5, §7, §8; sb01_02 plan §3c; eval_plan §7) and fixes the operating details they leave open |
| Owner confirmation | **T1, T2 and T3 confirmed 2026-11-13, with amendments A1-A7 (plan text only).** Amended text is marked **[A1]** to **[A7]**. **[A8]** (§2.1, worktree `data/` as a real directory instead of a symlink) was found while making them, tested on a train/val day, and **confirmed by the owner on 2026-11-13** once its inputs and the disk space were stated (§2.1). The concentration cut-offs in [A2] are **confirmed** too. The [A3] headline split stays in this plan; **no `eval-freeze-v3`** (owner decision, 2026-11-13). This version is tagged **`test-plan-v1`** |
| Frozen commit for test scoring | tag **`eval-freeze-v2`**, commit **`e204ff9`** (`e204ff945e215d25de845494fe0b370187024d61`). `src/pilot.py` there is byte-identical to `eval-freeze-v1` (`47a0b6f`) |
| Final model | `emb_block_lr_max_C0.001`, fixed in `docs/analysis/final_model/spec.json` (SHA-256 `a2be3bb4…bb8e931`). Artefact `data/models/final_v1.joblib`, SHA-256 `3f7ed71563dff9f50275ce4ef8613c89d393ac446dfb1b2b0eb2e71921f0bf24`, logged in the `final_model` audit entry (2026-11-12) and backed up (`model_backup` entry) |
| Releases | **Stage A** (audio) and **Stage B** (labels). Each needs its own explicit owner release, quoted verbatim in the log (protocol P7). **Neither has been given** |

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

1. **Checkout of the frozen code** *(amended [A8], 2026-11-13; replaces the symlink wording)*:
   `git worktree add ../noaa-whale-freeze eval-freeze-v2`, with a **real `data/` directory holding copies of the
   inputs**. Not a symlink.
   - **Why the symlink was dropped.** The original wording was "`data/` is a symlink to this repo's `data/`". The
     frozen code cannot run that way.
     - In `src/pilot.py` at e204ff9, `ROOT` is `Path(__file__).resolve().parent.parent`, which is the worktree.
       The CLI resolves `--days` and `--out` with `Path.resolve()`, which follows the symlink out of the worktree.
     - Three calls then raise `ValueError`: `days_csv.relative_to(ROOT)` in `score_start` (line 401),
       `out_dir.relative_to(ROOT)` in `completed_days` (`--skip-existing`), and `path.relative_to(ROOT)` for each
       `.npz` in `save_day`.
     - **Reproduced 2026-11-13** with the frozen code, on a train/val day, with the symlink pointing at a scratch
       copy. The run stopped at line 401 (`ValueError: '…/qa_rerun/trial.csv' is not in the subpath of
       '…/symlink_repro'`). Nothing was logged. No audio was fetched.
     - The output directory had been created first, and it was empty.
     - On a test split, `test_gate_passed` would have been logged before this crash.
   - **The fix needs no code change.** The worktree's `data/` is a real directory:
     - **Inputs are copied in.** These are all the local files the frozen `src/pilot.py` reads. It uses
       `ROOT / …` only for `DAYS_CSV`, `LISTING_PATH`, `MODEL_DIR` and the output directory:
       - `data/sample_days.csv` (24 KB, SHA-256 `3c47e9bc…201947d`);
       - `data/audio_listing.json` (800 KB), the file names and sizes per deployment;
       - `data/models/models/google/multispecies-whale/tensorFlow2/default/2/` (6 files, 27 MB, file-list
         SHA-256 manifest `6f01befd…f0efd1e`);
       - for QA re-runs only: `data/qa_rerun/<day>.csv`, the one-row day lists ([A2]).
     - **Nothing else is copied.** No labels, no train/val features, and no other part of `data/`.
     - **Downloaded at run time, not copied:**
       - the test days' FLAC audio, streamed over HTTPS from the public bucket
         (`https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/…`, anonymous);
       - 2,557 files, about 830 GB in total.
       Each file is read into memory (`io.BytesIO`), decoded and dropped. **No audio is written to disk**
       (`audio_saved_to_disk: false` in `score_start`). So the 830 GB is network transfer, not disk use.
     - **Disk needed.** Outputs are one `.npz` per day: train/val took 461 MB for 300 days, so about 615 MB
       for the 400 test days. They are held twice (worktree and this repo), so about 1.3 GB in total, plus
       28 MB of inputs.
     - **Free on 2026-11-13:** 1,326 GB of 1,967 GB on `/`, about 1,000 times what is needed.
     - Their SHA-256 values are logged in `stage_a_preflight`, and checked again after Stage A.
     - **Outputs** go to the worktree's `data/scores/v2_test/`, the test gate's required directory.
     - **After Stage A,** that directory is copied to this repo's `data/scores/v2_test/`. Every `.npz` is checked
       against the SHA-256 in its `score_day` entry. The logged `npz` paths (`data/scores/v2_test/<day>.npz`)
       are relative, so they hold in both places.
     - The worktree copy is kept until Stage B is complete.
   - **Alternatives considered:**
     - A bind mount needs root and a system change.
     - Hard links would share inodes with this repo's files, so a write in the worktree would change them. Plain
       copies are only 28 MB and cannot.
     - The frozen code has no launch-time root setting. `ROOT` comes from `__file__`. `--out` for a test split
       must equal `ROOT/data/scores/v2_test`.
   - **Why it is safe.**
     - The frozen code reads byte-identical inputs. The copies are hash-checked.
     - Every path it builds stays under `ROOT`, so every `relative_to(ROOT)` call succeeds.
     - Nothing in this repo's `data/` can be written during Stage A.
   - **Why the clean-tree gate still passes.**
     - The gate's dirtiness check is `git status --porcelain -- src`, and it requires an `eval-freeze-*` tag on
       HEAD.
     - `data/` is git-ignored at the tag (checked with `git check-ignore`), so copied inputs and outputs never
       appear in `git status`.
     - The only change git shows is `audit_log.jsonl` (T1), which is outside `src/`.
   - **Tested 2026-11-13 on a harmless day** (train/val `sb01_01_2018-11-14`, which is not a test day; no test
     gate). The test used a scratch worktree at `eval-freeze-v2` with copied inputs and the one-row
     day-list mechanism of [A2].
     - **Before the run:**
       - HEAD was `e204ff945e215d25de845494fe0b370187024d61` with tag `eval-freeze-v2`.
       - `git diff eval-freeze-v2 -- src` was empty, and `src/` had no untracked files.
       - `git status` showed only `audit_log.jsonl`.
       - `src.pilot` imported from the worktree, and `data/` held no symlinks.
       - Called directly with a dummy approval, without running or logging anything, `check_test_gate` passed.
         It refused when the approval was missing.
     - **The run:**
       - It scored and logged the day: `score_start`, `score_day` and `score_end` in the trial's scratch copy of
         the audit log, whose chain verifies.
       - All 12 feature arrays were **byte-identical** to the original train/val `.npz`. These were the
         window scores, embeddings, band levels, zero fraction and the rest.
       - Only the commit stamp (`e204ff9` against the original `d2f4fe5`) and the per-file download and decode
         timings differed.
       - It took 134 s for one day. Most of that is start-up; a single day cannot use the 5 workers.
     - **Records:**
       - The trial's log entries and run report are in `docs/analysis/freeze_trial/`.
       - Its result is logged in this repo as `freeze_worktree_trial`.
       - The scratch worktrees were removed afterwards.
2. **Audit log** *(T1, confirmed; amended [A1])*. The worktree has its own copy of `audit_log.jsonl`, frozen at the
   tag. Logging there would fork the hash chain. So:
   - immediately before scoring, **copy this repo's `audit_log.jsonl` into the worktree** (chain verified);
   - **[A1] from that copy until the copy back, the worktree's log is authoritative.** Nothing is logged in this
     repo.
   - **[A1] After any interruption** (crash, network failure, reboot, thermal or manual stop), work **resumes from
     the worktree's log**. `--skip-existing` reads the worktree's log (`DEFAULT_LOG` there), so a resume sees every
     day logged so far. This repo's log is never copied over the worktree's once scoring has started.
   - **[A1] The log is copied back and the chain verified even if the run fails.** If Stage A is abandoned, the
     worktree's log is copied back, verified and committed, with a `stage_a_stopped` entry giving the reason. A
     failed run never leaves the authoritative log only in the worktree.
   - Afterwards, **copy it back** (chain verified again). Then commit it here.

   The result is one linear chain. In the worktree, `git status` shows only `audit_log.jsonl` as changed.
   `src/` is clean, which is what the test gate checks.
3. **Pre-flight, logged as `stage_a_preflight`:**
   - the worktree HEAD is `e204ff9` and carries `eval-freeze-v2`;
   - `git status` in the worktree shows nothing except `audit_log.jsonl`;
   - `data/` in the worktree is a real directory with no symlinks, and the copied inputs match their logged
     SHA-256 ([A8]);
   - `data/scores/v2_test/` does not exist yet.
4. **Scoring:** two runs through the test gate, with output to `data/scores/v2_test/`. `--owner-approval` quotes
   the owner's Stage A release word for word, and `test_gate_passed` logs it.

   ```
   python -m src.pilot --actor claude-code --split test_T --owner-approval "<Stage A release>"
   python -m src.pilot --actor claude-code --split test_S --owner-approval "<Stage A release>"
   ```

   - If a run is interrupted (network, crash), it is resumed with `--skip-existing`. That keeps only days whose
     `.npz` matches its logged SHA-256. A resume is **not** a QA re-run.
     - **Checkpointing is per day.** A day's `.npz` is written and its `score_day` entry, with SHA-256, logged
       as soon as its last file is processed.
     - An interruption loses only the days in progress, and those are scored again from the start on resume.
     - No `qa_rerun` entry is made and nothing is moved to `v2_test_first_attempt/`. Days whose file is
       missing, or whose hash does not match, are simply scored again.
     - The [A8] trial showed that a re-scored day's features are byte-identical to its first scoring.
   - **[A6] Labels in memory.** The frozen `src/pilot.py` (`select_days`, e204ff9 lines 106-113) reads the
     whole of `sample_days.csv` with pandas, **including its `label` column**. On the next line it keeps only
     `split`, `site`, `deployment` and `date`. So test labels are parsed into memory and dropped at once. They are
     never used, logged, printed or written. Frozen code cannot be changed, so this is stated here rather than
     fixed.
     - **No error path prints dataframe rows.** All of `src/pilot.py` at e204ff9 was checked on 2026-11-13, with
       the `src.audit`, `src.label_survey`, `src.header_check` and `src.flac_header` code it imports or calls. Its only `print` calls write the
       run summary and a per-day line (day key, window count, hours, wall time, QA flags).
     - Its `SystemExit` messages contain the split name, gate problems and `git status` lines. Exceptions that
       can reach a traceback carry a URL, a file name or a `site_deployment` key. A pandas parse error reports a
       line number, not its contents.
     - Python tracebacks do not print local variables. The selected dataframe, which is the only one that
       outlives `select_days`, has no label column.
5. **QA handling.** The rules are evaluation-plan §5, unchanged. Each flag is listed per split in every report:

| Flag | Handling |
|---|---|
| Zero fraction > 0.01 (day) | Kept. Day-level sensitivity: flagged days excluded (eval_plan §7). The deployment-level rule is §3 below |
| Gaps (`>1 min gap`) | Kept. Gaps count as time with no detections. Never bridged |
| Overlaps > 2 s | Kept. Trimming is routine |
| Short day (< 20 h of windows, but eligible by the day table) | Kept and listed |
| Non-finite scores or band levels, decode error, size mismatch, or a day that cannot be completed | **Re-run once.** If the flag remains, **exclude the day and list it with the reason.** It is never replaced by another day |

   Re-run procedure *(T2, confirmed; amended [A2])*:
   - Move the first attempt's `.npz` to `data/scores/v2_test_first_attempt/`. It is never overwritten or deleted.
   - Log `qa_rerun` (day, flag, the first file's SHA-256).
   - Re-score that day alone, through the same gate, from a one-row day list (split, site, deployment and date;
     no label).
     - **[A2] Mechanism, without code changes.** The frozen `src/pilot.py` takes the day list as `--days <csv>`
       (argument parser, e204ff9 line 580). `select_days` keeps the rows whose `split` equals `--split` and reads
       only `split`, `site`, `deployment` and `date`, so a CSV without a `label` column is accepted.
     - The one-row CSV must be a **real file inside the worktree** (for example
       `data/qa_rerun/<day>.csv`), for the same `relative_to(ROOT)` reason as [A8]. The 2026-11-13 trial used
       exactly this mechanism. It is logged with its SHA-256
       in the `qa_rerun` entry.
     - The command is the same as in step 4 with `--days data/qa_rerun/<day>.csv` added, and no
       `--skip-existing`.
     - The re-run's `score_day` entry becomes the latest one for that day. `src/test_eval.py` uses the latest
       `score_day` entry per day and checks its SHA-256. The moved first attempt is kept for the record and never
       read.
   - If the flag remains, log `qa_exclusion` (day, reason). `src/test_eval.py` drops and lists every
     `qa_exclusion` day.
   - **[A2] Concentration rule.** Every report lists QA exclusions per deployment, with each deployment's
     sampled-day count. A deployment is **flagged as concentrated** if either of these holds:
     - it holds at least half of its split's exclusions, and at least 2 of them; or
     - at least 20% of its own sampled days are excluded.
     A flag is reported in the Stage A report and in `results.json` (`qa_exclusion_concentration`). It is
     reported, not acted on: nothing is dropped or re-weighted because of it. *(The 50% / 2-day / 20% cut-offs
     were confirmed by the owner on 2026-11-13, report-only, before any test day was processed.)*
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
   `--self-check` on train/val shows how often each flag fires when there is no shift. It was run and committed
   on 2026-11-12 (`40bf6e7`). It flagged only sb01_02 (zero fraction and embedding spread) and raised no band
   flags.
7. **Stop.** Report the Stage A outputs: QA flags, re-runs, exclusions and their concentration,
   sb01_02-equivalent deployments and drift flags. Then wait for the owner's Stage B release.
8. **[A7] Runtime estimate for Stage A (measured).** It is based on the clean train/val v2 scoring run of
   2026-11-11 (`score_end`: 258 days in 17,514 s, which is **67.9 s per day**, 5 workers, same machine and
   pipeline). The figures are scaled by each split's audio volume. Listed bytes come from
   `data/audio_listing.json` and the frozen `plan_tasks`, with no labels read:

   | Split | Days | Files | Audio | Per day | Estimate |
   |---|---|---|---|---|---|
   | Train/val (reference) | 300 | 1,876 | 675 GB | 2.25 GB | 67.9 s per day measured |
   | Test T | 150 | 972 | 284 GB | 1.89 GB | **about 2.4 h** |
   | Test S | 250 | 1,585 | 546 GB | 2.19 GB | **about 4.6 h** |
   | **Stage A total** | **400** | **2,557** | **830 GB** | | **central estimate about 7 h; conservative budget 11 h** |

   - The run streams about 33 MB/s from the public bucket, so network speed sets the pace.
   - **Conservative budget: 11 h**, which is the central estimate plus about 50%. The reasons:
     - the 2026-11-12 final-model run finished about 50 min after its mid-run estimate, because its last fits
       slowed from 30 to 48 s each;
     - short runs are slower per day (2-3 days took 84-117 s per day; the one-day trial of [A8] took 134 s);
     - network speed on the day is unknown.
     Stage A should start early enough that 11 h ends at a time when it can be checked.
   - The two drift reports take minutes.
   - The train/val scoring was interrupted twice before its clean segment. A resume (step 4) adds start-up
     time but does not repeat completed days.
   - If the measured rate after the first hour is more than 25% slower than 67.9 s per day, the estimate is
     re-stated to the owner. The run is not stopped for that reason.

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

- `src/test_eval.py` is the only code that reads test labels. It is **committed and tagged before Stage A**
  (tag `eval-tool-v1`; its SHA-256 is logged in a `test_eval_frozen` entry). It was dry-run in scratch on
  2026-11-13 with fake labels on non-test data (`tools/dryrun_test_eval.py`; summary in
  `docs/analysis/test_eval_dryrun/`).
- It refuses to run unless all of these hold:
  - the owner's Stage B release is given, and is logged verbatim (`stage_b_release`);
  - the final-model artefact and `spec.json` match their logged SHA-256;
  - both Stage A drift reports are logged;
  - every test `.npz` matches its `score_day` SHA-256 and carries a freeze-tag commit.
- **Labels are read only after every check has passed and `stage_b_release` is logged.** Until then the day list
  is read without its `label` column.
- Nothing is tuned. The model, aggregation, day threshold, baseline thresholds and baseline fits all come from
  the frozen spec and artefact.
- **[A3] Headline split: Test S, with Test T secondary.**
  - The evaluation plan does not name a headline split. `docs/evaluation-plan.md` §4 applies the improvement
    claim "on the split" to every split. §2 lists Test T and Test S side by side, and so does
    `docs/eval_plan.md` §1. So the owner's proposal applies (owner decision, 2026-11-13).
  - It is fixed **in this plan only** (tag `test-plan-v1`). The evaluation plan is not amended, and there is
    no `eval-freeze-v3` (owner decision, 2026-11-13).
  - **Reason.** Embeddings identify the site (AUROC 0.999). evaluation-plan §2 says Test T "inherits this
    shortcut, and Test S cannot". So Test S is the cleaner test of the humpback signal.
  - **Stated with it:** Test S covers the same calendar dates as train/val (evaluation-plan §2, "Known
    coupling"). It is a test of a new location, not of later time.
  - Test T is secondary. The Test S 10-12 slice is reported as before.
  - All three are always reported. The order of reporting does not change any rule.
- **What it computes,** for Test T, Test S and the S 10-12 slice:
  - AUROC_ws (headline) and pooled AUROC, each with a deployment-block bootstrap CI;
  - PR-AUC (absent as positive);
  - balanced accuracy at the fixed thresholds;
  - paired CIs against the month prior, ambient noise, zero-shot primary and the site prior;
  - the two-condition improvement claim against the best baseline by AUROC_ws;
  - breakdowns by site, season and deployment (≥ 5 / ≥ 5 rule; CIs at ≥ 3 deployments);
  - calibration per deployment;
  - site-ID probe (Test T);
  - the zero-flag-day sensitivity, and the sb01_02-equivalent sensitivity where it applies;
  - QA exclusions per deployment and the concentration flag ([A2]).
- **[A4] Failing improvement condition 2 is a reportable result, not grounds to iterate.**
  - Train/val already predicts this: the nested-CV estimate does not meet condition 2. Its paired AUROC_ws
    difference against the month prior is [−0.099, 0.171] (`docs/analysis/final_model/results.json`).
  - If, on any test split, the model does not beat the best non-diagnostic baseline within site, that is
    **reported as the result** (evaluation-plan §4: "that is reported as the result").
  - It is **not** grounds to change the model, features, aggregation, thresholds, baselines, QA rules or day
    lists, nor to re-score or re-evaluate. Any later model is new work. It would need a new plan, and it could
    not be scored on these test days as an unseen test.
- **One clean pass.** Its outputs are committed as produced. Any change after Stage B begins is a **deviation**:
  logged (`deviation`), noted in the results and reported both ways (evaluation-plan §8).

## 5. Known risk, stated before the results

**[A5] Prediction:**
- **Threshold.** The selected model's day threshold is **0.9804**, the maximum balanced accuracy on pooled
  9-fold train/val out-of-fold scores (`spec.json`). Block-max probabilities saturate near 1, so the threshold
  sits close to 1.
- **Test S.** We **predict** that at the new site, **balanced accuracy at 0.9804 will fall further below its
  train/val value than AUROC_ws does.** The score ranking may transfer while the absolute score level shifts.
  - If sb03 scores run higher, most days clear the threshold, so specificity collapses.
  - If they run lower, sensitivity collapses.
- **Test T.** We predict a smaller effect: same sites, later in time.
- **Testing the prediction.** It is checked by comparing each split's balanced accuracy and AUROC_ws with the
  train/val OOF values. The calibration-per-deployment table shows which way any shift goes.
- The threshold is **not** re-fitted on test data in any case. The plan claims no cross-site calibration
  (eval_plan §6).

## 6. Decisions for the owner

| # | Decision | Status |
|---|---|---|
| T1 | Audit log: copy it into the worktree, score, copy it back. One linear chain | **Confirmed 2026-11-13**, amended [A1] |
| T2 | QA re-run: move the first attempt to `v2_test_first_attempt/`, log `qa_rerun`, re-score that day alone; `qa_exclusion` if the flag remains | **Confirmed 2026-11-13**, amended [A2]. Concentration cut-offs confirmed, report-only |
| T3 | Stage A and Stage B as separate releases | **Confirmed 2026-11-13** |
| A8 | Worktree `data/` as a real directory with copied, hash-checked inputs, instead of a symlink (§2.1) | **Confirmed 2026-11-13** (inputs and disk space stated) |
