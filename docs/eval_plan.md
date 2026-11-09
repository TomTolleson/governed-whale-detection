# Evaluation plan (frozen)

Frozen 2026-11-09, before any model code ran. Changes after this point must be logged as new
audit entries and marked as amendments here, with the reason. Items marked *(claude-code)* fill in
details the owner's instructions did not state, and **need owner confirmation**.

## 1. Splits

Only eligible days from `data/day_table.csv` (rule: `docs/labeling_rules.md`).

| Split | Contents | Eligible days | Use |
|---|---|---|---|
| Train/val | sb01 + sb02, deployments 01-09 | 1,131 | Training, model selection and every threshold choice |
| Test T | sb01 + sb02, deployments 10-12 | 320 | Final evaluation, later in time at the same sites |
| Test S | sb03, all deployments 01-12 | 695 | Final evaluation, held-out site |
| Test S, 10-12 slice | sb03, deployments 10-12 (a subset of S) | from S | Reported separately: new site *and* later in time |

- Test T and Test S are not used for any choice: not for model selection, thresholds, feature design
  or debugging. No test-day audio is processed until the owner says so.
- Model selection uses **leave-deployment-out cross-validation** within train/val only.
  - *(claude-code)* A fold holds out one deployment number at **both** sites (e.g. sb01_04 and sb02_04
    together), which gives 9 folds. sb01 and sb02 record the same calendar dates, so holding out one site's
    deployment while training on the other site's would let same-day conditions leak across the fold.
- Thresholds (window threshold, day threshold) are chosen on the pooled out-of-fold validation predictions.

## 2. Sampling

- Script: `src/sample_days.py`. Seed: **20261109** (numpy `default_rng`).
- Within each split, the same fraction of days is drawn from every deployment × label cell, which keeps
  the class balance and each deployment's share.
  - *(claude-code)* Cell counts are `fraction × cell size`, rounded by largest remainder so each split
    hits its target exactly. Days within a cell are drawn without replacement.
- Targets: **300** train/val days, **150** Test T days, **250** Test S days.
- The exact day lists go to `data/sample_days.csv` (columns: split, site, deployment, date, label,
  season). Its SHA-256 is logged in `audit_log.jsonl`. `data/` is git-ignored, so the hash in the log
  is the record.
- The Test S 10-12 slice is the sampled S days from sb03 deployments 10-12. It is not sampled separately.
- The pilot (60 days) is drawn from the sampled train/val days only (seed 20261109, stratified the same way).

## 3. Metrics

All metrics are day-level: one score and one label per site-day.

- **Primary: AUROC**, with "present" (label 1) as the positive class.
  - 95% confidence interval from a **block bootstrap by deployment**: resample deployments with
    replacement and keep all of each chosen deployment's days.
  - *(claude-code)* 2,000 resamples, percentile interval. A resample that ends up with only one class is
    redrawn.
- **Secondary:**
  - PR-AUC (average precision), with **"absent" (label 0) as the positive class**. Report the absent
    prevalence next to it, since that is PR-AUC's chance level.
  - Balanced accuracy at a day threshold fixed on validation.
    - *(claude-code)* The threshold is the one that maximises balanced accuracy on the out-of-fold
      validation predictions.
- **Breakdowns:** per site, per season (DJF, MAM, JJA, SON, by UTC month) and per deployment.
  - A breakdown is reported **only where both classes have at least 5 days**. Any other cell is
    shown as "n/a (n present / n absent)".
  - *(claude-code)* Breakdowns get bootstrap CIs only where they contain at least 3 deployments. Otherwise
    only a point estimate is shown.

## 4. Day-score rules

The model scores 5-second windows. These rules turn window scores into a day score:

1. **Primary:** a day counts as present if there are **at least 3 window detections within any
   10-minute span** (a detection is a humpback window score ≥ the window threshold).
   - The window threshold is chosen on validation only.
   - *(claude-code)* For AUROC the day needs a continuous score, so the day score is the largest *k* such
     that some 10-minute span has 3 windows scoring ≥ *k*. That is the 3rd-highest window score in the
     best 10-minute span. The binary rule at the validation threshold equals "day score ≥ threshold".
   - *(claude-code)* The window threshold is the one that maximises balanced accuracy of this binary
     rule on out-of-fold validation days.
2. **Secondary:** max window score; mean of the top 10 window scores.

*(claude-code)* Windows are non-overlapping, 5 s each. Spans are measured on the windows' real start
times, so gaps between files count as time with no detections.

## 5. Baselines

Every baseline is evaluated on the same days and with the same metrics as the model.

- **Always-present:** constant score. AUROC = 0.5 by construction; it is reported to anchor balanced accuracy.
- **Month prior:** score = fraction of present days in that UTC calendar month, computed from
  **train/val days only**.
  - *(claude-code)* Months with no train/val days use the overall train/val present rate.
- **Ambient-noise baseline:** logistic regression on band-level spectral features of the day's audio.
  - *(claude-code)* Features: daily median and 90th-percentile power in octave bands from 50 Hz to
    12 kHz, plus 50-500 Hz. This stays below the 24 kHz Nyquist limit of a 48 kHz recording. Features are
    standardised, and the L2 regularisation is chosen by the same leave-deployment-out CV.

## 6. Known limits (to be stated with every result)

- Labels are detection-based daily presence. **0 means no confirmed detection, not proof of absence.**
  "Absent" is therefore partly "not detected by the original analysts".
- Day boundaries are UTC as **inferred** from file names. The FLAC metadata has no timestamps, so UTC
  cannot be confirmed from the files (`docs/header_check.md`).
- Test T autumn (SON) has only **5 absent days** in the full eligible set, and fewer after sampling.
  Season breakdowns for it will mostly be n/a.
- Test T has no DJF or MAM days.
- Test S covers the same calendar dates as train/val. It tests a new site, not a later period.
- **No claim of cross-site calibration.** Thresholds are fixed on sb01/sb02 validation. Test S results
  show how they transfer, not that scores are calibrated at sb03.
- 12 deployments have fewer than 5 absent eligible days (`docs/eligible_summary.md`), so
  per-deployment metrics will be n/a for most of them.
