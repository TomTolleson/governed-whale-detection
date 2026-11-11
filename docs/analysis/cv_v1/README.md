# CV v1: baselines and first classifiers (train/val only)

> **Train/val only. Out-of-fold, leave-deployment-out.** No test day was processed or read.
> These are development results. Nothing here is a test result.

| | |
|---|---|
| Code | `src/cv_eval.py` at `e8c1d71`, after the freeze tag `eval-freeze-v1` (`47a0b6f`) |
| Features | `data/scores/v2` (pipeline v2, `d2f4fe5`), 300 train/val days |
| Folds | 9. Deployment k is held out at both sites |
| Variants | Primary (all 300 days, 18 deployments); S1, with sb01_02 removed from training and evaluation (283 days, 17 deployments) |
| Uncertainty | deployment-block bootstrap, 2,000 resamples, seed 20261109, percentile 95% CI. Paired CIs for differences |
| Outputs | `results.json` and `oof_scores.csv`. SHA-256 values are in the `cv_eval` audit entry |
| Rules applied | `docs/evaluation-plan.md` §3-§6, `docs/analysis/sb01_02-sensitivity-plan.md` §3 (thresholds confirmed by the owner 2026-11-11) |

## Pooled out-of-fold results

| Method | Primary AUROC [95% CI] | S1 AUROC [95% CI] | Δ (S1 − P) | PR-AUC (absent+) P | Bal. acc. P | AUROC sb01 / sb02 (P) | Site-ID probe (P) |
|---|---|---|---|---|---|---|---|
| Always-present | 0.500 | 0.500 | 0 | 0.370 | 0.500 | 0.50 / 0.50 | 0.50 |
| Month prior | 0.683 [0.567, 0.786] | 0.653 [0.540, 0.752] | **−0.031 (material)** | 0.539 | 0.636 | 0.69 / 0.68 | 0.52 |
| Ambient-noise (bands) | 0.610 [0.506, 0.716] | 0.607 [0.479, 0.723] | −0.003 | 0.468 | 0.554 | 0.59 / 0.53 | 0.71 |
| Zero-shot (primary day rule) | 0.678 [0.571, 0.803] | 0.678 [0.567, 0.805] | 0.000 | 0.545 | 0.586 | 0.60 / 0.81 | 0.54 |
| Zero-shot (top-10 mean) | 0.686 [0.577, 0.816] | 0.685 [0.569, 0.817] | −0.001 | 0.566 | 0.592 | 0.62 / 0.80 | 0.52 |
| Site prior (diagnostic) | 0.455 [0.319, 0.618] | 0.445 [0.302, 0.601] | −0.010 | 0.343 | 0.568 | n/a | 1.00 |
| Day-mean embedding LR | 0.774 [0.685, 0.843] | 0.775 [0.681, 0.845] | +0.000 | 0.615 | 0.708 | 0.76 / 0.75 | **0.69** |
| Block LR, max | **0.816 [0.738, 0.879]** | 0.827 [0.753, 0.883] | +0.011 | 0.721 | 0.738 | 0.77 / 0.85 | 0.61 |
| Block LR, top-3 mean | **0.816 [0.748, 0.873]** | 0.816 [0.748, 0.869] | 0.000 | 0.712 | 0.695 | 0.78 / 0.84 | 0.61 |
| Block LR, top-12 mean | 0.813 [0.737, 0.874] | 0.817 [0.746, 0.867] | +0.004 | 0.697 | 0.719 | 0.80 / 0.82 | 0.61 |
| Block LR, mean | 0.799 [0.716, 0.862] | 0.806 [0.721, 0.867] | +0.007 | 0.666 | 0.745 | 0.82 / 0.76 | 0.64 |

Notes on the columns:
- **Absent prevalence:** 0.370 under Primary and 0.357 under S1. This is PR-AUC's chance level.
- **Balanced accuracy:** each fold's day threshold is chosen on the pooled out-of-fold scores of the other 8 folds.
- **Site-ID probe:** the AUROC of separating sb01 from sb02 by the day score. **The labels alone give 0.603.**

## Improvement claims (evaluation-plan §4: the paired CI must exclude 0, against the best baseline)

The best non-diagnostic baseline under Primary is the **month prior** (0.683). The zero-shot model is
close behind (0.678).

| Model − baseline (Primary) | vs month prior | vs zero-shot | vs ambient-noise |
|---|---|---|---|
| Block LR, max | **[+0.002, +0.258]** improves | **[+0.031, +0.238]** improves | **[+0.056, +0.355]** improves |
| Block LR, top-3 | **[+0.003, +0.257]** improves | **[+0.020, +0.242]** improves | **[+0.066, +0.350]** improves |
| Block LR, top-12 | [−0.010, +0.264] not shown | [−0.006, +0.254] not shown | **[+0.068, +0.342]** improves |
| Block LR, mean | [−0.024, +0.247] not shown | [−0.042, +0.260] not shown | **[+0.072, +0.309]** improves |
| Day-mean LR | [−0.063, +0.235] not shown | [−0.063, +0.224] not shown | **[+0.027, +0.289]** improves |

Only the block-level classifier with **max** or **top-3** aggregation beats the best baseline by the plan's
rule, and only just: the lower CI bound is +0.002 to +0.003 against the month prior. With 18
deployments the CIs are wide.

## sb01_02 sensitivity (sb01_02 plan §3b)

- **Pooled:** no model or zero-shot method changes materially. Every |Δ| is ≤ 0.011, and no S1 estimate
  falls outside the Primary CI. **The month prior does change materially (−0.031).** Primary scores on
  S1's days give 0.673, so most of that change comes from removing sb01_02's days from *evaluation*,
  not from training.
- **Fold level (|Δ| ≥ 0.05 is material for the fold):**

| Fold | Zero-shot P → S1 | Block top-12 P → S1 | Block mean P → S1 | Day-mean LR P → S1 |
|---|---|---|---|---|
| **02** (P: sb01_02 + sb02_02, 33 days; S1: sb02_02 only, 16 days) | **0.722 → 0.984** | **0.574 → 0.734** | **0.593 → 0.703** | 0.678 → 0.656 |
| 04 | 0.730 → 0.730 | **0.745 → 0.680** | 0.795 → 0.760 | 0.855 → 0.830 |
| 06 | 0.575 → 0.575 | **0.897 → 0.805** | 0.816 → 0.816 | 0.655 → 0.667 |
| 09 | 0.844 → 0.844 | 0.984 → 0.984 | 0.875 → 0.891 | 0.938 → 0.891 |

  Every fold for every method is in `results.json`.
- **Reading:** **sb01_02's own days are hard for every method.** The zero-shot model, which has no
  training, scores 0.98 on sb02_02 alone but 0.72 with sb01_02 included. So fold 02's drop is a property of
  sb01_02's audio, consistent with the recorder or zero-sample issue, and not something the models learned
  from it. Removing sb01_02 from *training* moves other folds by up to 0.09 for block top-12 (folds 04 and
  06). This variation counts as material at fold level, but with only 30-35 days per fold it is
  descriptive. Pooled results are stable.

## Shortcut diagnostics (sb01_02 plan §3a.4)

- **Site prior: AUROC 0.455**, below chance. Under leave-deployment-out CV, knowing the site alone does not
  help. The held-out deployment's season dominates the site difference.
- **Site-ID probe on day scores:** the labels alone give 0.603.
  - **Block LR:** 0.607-0.639, close to the label level. These models carry little site information beyond
    the labels.
  - **Day-mean LR (0.688) and ambient-noise (0.713):** they carry more site information than the labels
    explain, so they partly score the recorder or site.
- **Per-site AUROC:** the zero-shot model is much better at sb02 (0.81) than at sb01 (0.60). The block-LR
  models are more even: 0.77-0.82 at sb01 and 0.76-0.85 at sb02.

## Other observations

- **Ambient-noise C:** the inner CV chose the grid's top value (C = 10) in every fold, so its C is
  under-explored. A wider grid is a train/val development change. It touches no frozen item, because
  the plan fixes the method and not the grid.
- **Fixed hyperparameters:** the embedding classifiers used fixed C = 0.01 with no tuning, which suits a
  first pass.
- **Weak labels:** the block LR gives every block of a present day a positive label, which is a weak-label
  (multiple-instance) approximation. Max and top-3 aggregation working best fits the fact that a
  humpback day's calls fill only part of the day.

## Not decided here

- The final model, aggregation, hyperparameters and window/day thresholds. These need inner-CV
  selection on train/val and are then logged before any test label is read (evaluation-plan §3).
- Test days remain unprocessed.
