# CV v1.1: within-site AUROC (train/val only)

> **Train/val only. Out-of-fold, leave-deployment-out.** No test day was processed or read.
> These are development results. Nothing here is a test result.

| | |
|---|---|
| Code | `src/cv_eval.py` at `045e15b`, after the freeze tag **`eval-freeze-v2`** (`e204ff9`) |
| Rules applied | `docs/evaluation-plan.md` v2 §3-§6 (headline: within-site AUROC, owner decisions D1-D5); `docs/analysis/sb01_02-sensitivity-plan.md` §3 as amended; baseline 4 = **primary-rule zero-shot only** (owner `plan_clarification`, 2026-11-11) |
| Features, folds, variants | As in `docs/analysis/cv_v1/README.md`: 300 days, 9 folds (deployment k held out at both sites), Primary and S1 (sb01_02 excluded, 283 days) |
| Uncertainty | Deployment-block bootstrap, 2,000 resamples, seed 20261109, percentile 95% CI. The within-site CIs use their own stream with the same seed |
| Outputs | `results.json`, `oof_scores.csv` (commit `def6977`; SHA-256 in the `cv_eval` entry). `posthoc_zero_shot_pairs.json` (commit `ef7abf0`; SHA-256 in the `posthoc_analysis` entry) |
| Check against cv_v1 | Every pooled AUROC and pooled CI is **identical** to cv_v1. Only the within-site metrics are new |

**Within-site AUROC (AUROC_ws)** is per-site AUROC over sb01 and sb02, weighted by each site's present × absent
day pairs. It is the probability that a present day outscores an absent day **from the same site**.

## 1. AUROC per method (Primary; S1 in the last column)

| Method | **AUROC_ws [95% CI]** | Pooled AUROC [95% CI] | sb01 / sb02 | AUROC_ws, S1 |
|---|---|---|---|---|
| Block LR, top-12 mean | **0.809** [0.740, 0.863] | 0.813 [0.737, 0.874] | 0.80 / 0.82 | 0.812 |
| Block LR, top-3 mean | **0.807** [0.733, 0.870] | 0.816 [0.748, 0.873] | 0.78 / 0.84 | 0.810 |
| Block LR, max | **0.806** [0.715, 0.877] | 0.816 [0.738, 0.879] | 0.77 / 0.85 | 0.820 |
| Block LR, mean | **0.795** [0.711, 0.855] | 0.799 [0.716, 0.862] | 0.82 / 0.76 | 0.800 |
| Day-mean embedding LR | 0.755 [0.663, 0.832] | 0.774 [0.685, 0.843] | 0.76 / 0.75 | 0.751 |
| Zero-shot, top-10 mean *(not baseline 4)* | 0.698 [0.579, 0.839] | 0.686 [0.577, 0.816] | 0.62 / 0.80 | 0.714 |
| **Zero-shot, primary rule (baseline 4)** | 0.695 [0.575, 0.831] | 0.678 [0.571, 0.803] | 0.60 / 0.81 | 0.711 |
| Zero-shot, max *(not baseline 4)* | 0.686 [0.563, 0.830] | 0.664 [0.547, 0.803] | 0.60 / 0.79 | 0.696 |
| Month prior (baseline 2) | 0.688 [0.579, 0.797] | 0.683 [0.567, 0.786] | 0.69 / 0.68 | 0.665 |
| Ambient noise (baseline 3) | 0.565 [0.470, 0.676] | 0.610 [0.506, 0.716] | 0.59 / 0.53 | 0.566 |
| Always-present | 0.500 | 0.500 | 0.50 / 0.50 | 0.500 |
| Site prior (diagnostic) | 0.174 [0.142, 0.266] | 0.455 [0.319, 0.618] | 0.17 / 0.18 | 0.167 |

Days: Primary 300 (189 present / 111 absent, 18 deployments); S1 283 (17 deployments).

## 2. Improvement claim (evaluation-plan v2 §4)

**Best non-diagnostic baseline by AUROC_ws:** the primary-rule zero-shot model, under both Primary (0.695)
and S1 (0.711). The month prior is second under Primary (0.688).

### 2a. Condition 1: signal beyond site

In CV, the plan's test is the paired CI of AUROC_ws(model) − AUROC_ws(site prior). It excludes 0 for every model:
the lower bounds run from +0.431 (day-mean LR) to +0.499 (block top-12). **This test is weak in CV.** The
out-of-fold site prior scores 0.174 within site because of a leave-out artefact: within a site, the
training-fold rate moves opposite to the held-out deployment's rate. Passing it says little.

AUROC_ws CIs against 0.5, which is how condition 1 works on the test splits:
- **The four block models** have lower bounds **≥ 0.711**.
- **Day-mean LR (0.663), the three zero-shot rules (0.563-0.579) and the month prior (0.579)** have lower
  bounds above 0.5, but well below the block models.
- **Ambient noise's CI [0.470, 0.676] includes 0.5.** Within site, it shows no signal beyond site.

### 2b. Condition 2: paired AUROC_ws vs the best baseline (pre-specified)

| Model − baseline, AUROC_ws | vs zero-shot primary (**best**) | vs month prior | vs ambient noise |
|---|---|---|---|
| Block LR, max | **[+0.008, +0.203] improves** | [−0.026, +0.244] | [+0.066, +0.382] |
| Block LR, top-3 | [−0.003, +0.209] | [−0.018, +0.243] | [+0.078, +0.379] |
| Block LR, top-12 | [−0.028, +0.224] | [−0.010, +0.241] | [+0.097, +0.376] |
| Block LR, mean | [−0.080, +0.231] | [−0.024, +0.223] | [+0.099, +0.347] |
| Day-mean LR | [−0.097, +0.183] | [−0.088, +0.212] | [+0.015, +0.330] |

S1 (sb01_02 excluded), the same pairs:

| Model − baseline, AUROC_ws | vs zero-shot primary (**best**) | vs month prior | vs ambient noise |
|---|---|---|---|
| Block LR, max | **[+0.006, +0.211] improves** | [+0.001, +0.285] | [+0.069, +0.397] |
| Block LR, top-3 | [−0.013, +0.205] | [+0.004, +0.272] | [+0.076, +0.386] |
| Block LR, top-12 | [−0.039, +0.219] | [+0.016, +0.267] | [+0.092, +0.388] |
| Block LR, mean | [−0.090, +0.230] | [+0.005, +0.260] | [+0.093, +0.368] |
| Day-mean LR | [−0.089, +0.243] | [−0.107, +0.168] | [−0.005, +0.335] |

**Reading.** By the plan's rule, **only Block LR max improves**, under Primary and S1, and only just: the lower
bounds are +0.008 and +0.006. This needs three qualifications:
1. **Under Primary, no model beats the month prior within site**, the second-best baseline. The rule compares
   only with the best baseline, so this does not change the verdict. It is reported because the margin is so
   thin.
2. **The four block variants cannot be told apart.** Their AUROC_ws values are 0.795-0.809 and their CIs
   overlap almost completely. No plan designated an aggregation in advance: the four were set as
   candidates in the CV harness (`e8c1d71`) before any result existed, with no winner named. Block max
   passing while top-3, top-12 and mean miss is one of four comparisons, and **is not evidence that max
   aggregation is better.** Choosing the final aggregation is left to the pre-specified inner-CV selection on
   AUROC_ws (decision D5), not to this table.
3. **The pass depends on which zero-shot rule is the baseline** (§3).

## 3. Post-hoc sensitivity checks, not part of the pre-specified analysis

Baseline 4 is the primary-rule zero-shot model (owner `plan_clarification`, 2026-11-11). **The ambiguity was
noticed after results were in.** The top-10 rule has AUROC_ws 0.698 against the primary rule's 0.695. **The
same gap exists in cv_v1:** pooled top-10 0.686 against primary 0.678, where top-10 was also above the month
prior (0.683) that cv_v1 named as the best baseline. The paired CIs below compare against the other two
zero-shot rules. They are **post-hoc sensitivity checks, not part of the pre-specified analysis**, and do not
change the verdict in §2.

`src/posthoc_zs_pairs.py` (commit `069ef7f`) reads the committed `oof_scores.csv` and uses the same bootstrap
functions, seed and resample stream. It first reproduced every pre-specified pair against the primary rule
exactly, for both variants, and would have stopped otherwise.

| Model − zero-shot rule, AUROC_ws | Primary: vs top-10 | Primary: vs max | S1: vs top-10 | S1: vs max |
|---|---|---|---|---|
| Block LR, max | [−0.002, +0.200] | **[+0.010, +0.221]** | [−0.010, +0.207] | **[+0.011, +0.234]** |
| Block LR, top-3 | [−0.011, +0.209] | [−0.001, +0.229] | [−0.026, +0.202] | [−0.006, +0.227] |
| Block LR, top-12 | [−0.035, +0.222] | [−0.025, +0.240] | [−0.050, +0.216] | [−0.031, +0.242] |
| Block LR, mean | [−0.080, +0.225] | [−0.067, +0.239] | [−0.099, +0.224] | [−0.079, +0.249] |
| Day-mean LR | [−0.102, +0.176] | [−0.091, +0.197] | [−0.117, +0.166] | [−0.099, +0.198] |

**Reading. Against the top-10 rule, no model's within-site CI excludes 0.** That includes Block LR max (lower
bound −0.002). The one pre-specified pass in §2b therefore depends on which zero-shot day rule is the
baseline. Against the max rule, Block LR max still passes. The pooled versions of these pairs, a secondary
metric, are in `posthoc_zero_shot_pairs.json`.

## 4. sb01_02 sensitivity (sb01_02 plan §3b, amended: material if pooled **or** within-site meets the rule)

- **Within site:** no method changes materially. The largest |Δ(S1 − Primary)| is 0.023 (month prior). For
  the zero-shot primary rule and Block LR max it is +0.016 and +0.014. No S1 value falls outside the Primary
  CI.
- **Pooled:** as in cv_v1. Only the month prior changes materially (−0.031). Under the amended rule, **the
  month prior is material** and every other method is not.
- **Per fold:** AUROC_ws needs ≥ 5 present and ≥ 5 absent days at a site. Under Primary that holds only in
  folds 02, 04, 05 and 08; in every other fold the value is n/a. Fold values are descriptive and are in
  `results.json` (`per_fold_ws`).

## 5. Shortcut diagnostics (unchanged from cv_v1)

| Method | Pooled − AUROC_ws | Site-ID probe on day scores (labels alone: 0.603) |
|---|---|---|
| Ambient noise | +0.045 | 0.713 |
| Day-mean LR | +0.019 | 0.688 |
| Block LR (4 variants) | +0.004 to +0.010 | 0.607-0.639 |
| Zero-shot primary | −0.017 | 0.54 |

The two methods whose site-ID probe is furthest above the label level are also the two that lose most going
from pooled to within-site. That is consistent with their pooled AUROC partly rewarding site identity. The
block models lose almost nothing.

## 6. Corrections

- An interim chat summary of these results (2026-11-11) said "every model's lower bound is above 0.7". **That
  was wrong.** Only the four block models have AUROC_ws lower bounds ≥ 0.711 (§2a).

## 7. Not decided here

- The final model and aggregation, hyperparameters and window/day thresholds. These come from inner-CV
  selection on train/val with AUROC_ws as the criterion (D5), and are logged before any test label is read.
- Test days remain unprocessed and sealed.
