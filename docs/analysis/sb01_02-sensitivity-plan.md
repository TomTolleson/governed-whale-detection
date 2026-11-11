# Deployment sb01_02: evidence and pre-specified sensitivity analysis

Written 2026-11-11 by claude-code at the owner's instruction, and **committed before any humpback model
is trained or evaluated on train/val**. Only QA values and the feature-only checks below had been
computed when it was written. No model results exist yet. Items marked *(claude-code)* are proposals that
**need owner confirmation**. The owner may change them before the first model run, and any later change
is a logged deviation.

## 1. Evidence: sb01_02 is a recorder or deployment property

- **Zero fraction:** in the v2 train/val run (`data/scores/v2`, commit `d2f4fe5`), **17 of 300 days are
  zero-flagged** (`zero_fraction > 0.01`). Every flagged day is in sb01_02, and **every sampled sb01_02 day is
  flagged**, with zero fractions of 1.36-2.25%. Every other train/val deployment has a median zero fraction of 0.
- The v1 pilot showed the same thing per file: 1.3-1.7% exact-zero samples in every sb01_02 file.
- **Interpretation:** the zeros are spread over all of the deployment's days and files, so they are most
  likely a property of the recorder, its firmware or its settings, and not of particular days or events.
  This hasn't been confirmed against SanctSound deployment metadata.
- The sampled sb01_02 days are 10 absent and 7 present (MAM 10, DJF 7).

## 2. Checks (`python -m src.deployment_check`, output `docs/analysis/deployment_check.json`)

The checks use 300 train/val days. Each day's features are the mean 1280-d block embedding plus the daily
median and 90th percentile of the 9 band levels. Zero fraction is **not** a feature. The classifier is a
fixed L2 logistic regression (C=1, standardised) in 5-fold stratified CV over days, seed 20261109, with no
tuning. Labels are used only for class balance and the deployment-prior AUROC.

### 2a. Label rate and class balance per deployment

| Deployment | Sampled days | Present | Rate | Eligible days | Present | Rate |
|---|---|---|---|---|---|---|
| sb01_01 | 20 | 17 | 0.850 | 76 | 66 | 0.868 |
| **sb01_02** | **17** | **7** | **0.412** | **63** | **25** | **0.397** |
| sb01_03 | 14 | 4 | 0.286 | 52 | 16 | 0.308 |
| sb01_04 | 17 | 2 | 0.118 | 61 | 6 | 0.098 |
| sb01_05 | 17 | 3 | 0.176 | 63 | 11 | 0.175 |
| sb01_06 | 16 | 13 | 0.812 | 61 | 51 | 0.836 |
| sb01_07 | 14 | 10 | 0.714 | 55 | 38 | 0.691 |
| sb01_08 | 18 | 7 | 0.389 | 66 | 26 | 0.394 |
| sb01_09 | 17 | 16 | 0.941 | 65 | 62 | 0.954 |
| sb02_01 | 20 | 18 | 0.900 | 76 | 67 | 0.882 |
| sb02_02 | 16 | 8 | 0.500 | 63 | 31 | 0.492 |
| sb02_03 | 15 | 12 | 0.800 | 59 | 46 | 0.780 |
| sb02_04 | 16 | 6 | 0.375 | 61 | 24 | 0.393 |
| sb02_05 | 17 | 12 | 0.706 | 63 | 44 | 0.698 |
| sb02_06 | 16 | 16 | 1.000 | 61 | 59 | 0.967 |
| sb02_07 | 15 | 14 | 0.933 | 55 | 52 | 0.945 |
| sb02_08 | 18 | 8 | 0.444 | 66 | 29 | 0.439 |
| sb02_09 | 17 | 16 | 0.941 | 65 | 62 | 0.954 |

- Overall present rate (sample): 0.630. **By site: sb01 0.527 (79/150), sb02 0.733 (110/150).**
- The sample matches the eligible-day rates closely. Stratified sampling was designed to do that.
- sb01_02's present rate of 0.41 is close to sb01's overall rate. It is not an outlier in class balance.
- Deployment identity alone carries a lot of label information: the deployment present rate,
  leave-one-day-out, gives **AUROC 0.783**. Much of this reflects season, since deployments are consecutive
  periods.

### 2b. Can deployment or recorder be predicted from features alone?

| Task | Chance | Embedding | Band levels |
|---|---|---|---|
| 18-way deployment ID (balanced accuracy) | 0.056 | **0.947** | 0.365 |
| Site ID, sb01 vs sb02 (AUROC; same calendar dates, so season is balanced) | 0.5 | **0.999** | 0.951 |
| sb01_02 vs all other deployments (AUROC) | 0.5 | **0.998** | 0.764 |
| sb01_02 vs sb02_02 (AUROC; same period at the other site) | 0.5 | **1.000** | 0.849 |

**Reading:** yes. The embeddings identify the deployment, and in particular the site, almost perfectly.
They do so even when calendar time is held fixed (site ID; sb01_02 vs sb02_02), so this is not just
season. A classifier on these features **can learn the recorder or site instead of the humpback signal**.

**What this means for the planned design:**
- **Leave-deployment-out CV** (eval plan §1: fold k holds out deployment k at both sites) stops a model
  from memorising the *held-out deployment's* identity. A shortcut through deployment ID cannot help on the
  held-out fold, so out-of-fold results are protected against that one.
- It does **not** remove the **site** shortcut. Both sites are in every training fold, and sb02 has a
  higher present rate (0.73 vs 0.53). A model can score sb02 days higher without hearing any whale.
  The same shortcut applies to **Test T** (same sites) but cannot transfer to **Test S** (the new site sb03).
- sb01_02 is perfectly identifiable, but its label rate is typical, so it gives no direct label shortcut.
  The risk is different: its features shift, so a model trained without it may be miscalibrated on it, and
  the reverse.

## 3. Pre-specified analysis (decided now, before any model results)

### 3a. Variants, all reported, always

1. **Primary: all train/val data.** Includes sb01_02 in training and evaluation, using the leave-deployment-out
   CV and metrics from `docs/eval_plan.md`. Primary results and conclusions come from this variant.
2. **Sensitivity S1: sb01_02 excluded.** The same pipeline, with sb01_02 days removed from **both** training and
   evaluation in every fold. Thresholds are re-chosen on S1's own out-of-fold predictions, with the same rule.
3. **Per-fold table:** the AUROC for each of the 9 folds under Primary and S1, side by side.
   - **Fold 02** is listed separately: under Primary it holds out sb01_02 + sb02_02 (33 days); under S1 only
     sb02_02 (16 days, 8 present and 8 absent).
   - For folds 01 and 03-09, the change shows the effect of having sb01_02 in *training*.
4. *(claude-code)* **Shortcut diagnostics, reported with every result:**
   - per-site AUROC (sb01 only, sb02 only), with the pooled AUROC next to it;
   - a **site-prior baseline**: the score is the training-fold present rate of the day's site, for comparison
     with the model;
   - a **site-ID probe**: a site-ID classifier on the model's own day scores. A model whose day scores
     identify the site well beyond the label-rate difference is using the site.

### 3b. What counts as a material difference *(claude-code; fixed before running)*

S1 differs **materially** from Primary if either of these holds:
- the pooled out-of-fold AUROC changes by **|ΔAUROC| ≥ 0.03**; or
- the S1 pooled AUROC lies **outside the Primary 95% CI**, using the deployment-block bootstrap from eval
  plan §3.

At fold level, a change of **|ΔAUROC| ≥ 0.05** in any single fold counts as material *for that fold*. Fold
results are descriptive, because each fold has only 30-35 days.

Balanced accuracy at the validation threshold: a change of **≥ 0.03** counts as material.

**If a difference is material:** both results are reported side by side, and the conclusion states that the
result depends on deployment sb01_02. The primary variant does **not** change after the results are seen.

### 3c. Rule for equivalent deployments in the test sets (decided now, before any test audio is processed)

- When test days are released, zero fraction is computed in the same v2 scoring pass, from audio QA only.
- A test deployment is **equivalent to sb01_02** if the **median `zero_fraction` over its sampled days is
  above 0.01**, the same 1% cut as eval plan §7.
- These deployments are identified and **logged before any test label or test score is read**.
- **Treatment:** primary test results include them. A sensitivity result excludes them, and both are always
  reported. The §3b materiality rule applies.
- Zero-flagged days in deployments that are *not* equivalent are handled by the day-level sensitivity
  analysis in eval plan §7.
- No other exclusion may be added after test data has been seen, except as a logged deviation reported
  both ways (`docs/evaluation-plan.md` §8).
