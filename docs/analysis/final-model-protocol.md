# Final-model selection and pre-test steps: protocol

| | |
|---|---|
| Status | **Confirmed by the owner 2026-11-11** ("Confirm as proposed"; `owner_confirmation` entry; P4 also logged as a `plan_clarification`). The draft was committed at `084dc3d` before any selection run |
| Written | 2026-11-11 by claude-code, at the owner's instruction ("Pre-test steps first") |
| Governs | `docs/evaluation-plan.md` v2 (`eval-freeze-v2`), §3 ("final model … fixed on train/val … logged before any test label is read"; selection on AUROC_ws, decision D5) and §7 (drift report) |
| Changes to frozen items | **None.** The pipeline, QA rules and evaluation plan are untouched. This protocol fills in details the plan leaves open. Items marked *(claude-code)* need owner confirmation (P1-P7, §6) |
| Scope | Train/val only. No test day is processed or read |

## 1. What the plan requires before test scoring, and what it does not

| Requirement | Plan | Can it be done while the test days are sealed? |
|---|---|---|
| Final model fixed on train/val: architecture, hyperparameters, features, thresholds | §3 | **Yes**, this protocol |
| Selection by inner CV on AUROC_ws | §3, D5 | **Yes**, this protocol |
| Commit hash and artefact SHA-256 logged before any test label is read | §3 | **Yes** |
| Pre-evaluation drift report, per test split, before any test label is read | §7 | **No.** It needs test-day **features**: zero fraction, band levels, zero-shot scores and embeddings. Those exist only after test audio is scored |
| sb01_02-equivalent test deployments identified before any test label is read | sb01_02 plan §3c | **No.** Same reason |

**Correction to the earlier chat summary.** That summary listed the drift report as something to finish
before unsealing. That was wrong. The plan already orders test work in two stages, and this protocol keeps
that order:
- **Stage A, audio:** test audio is scored through the test gate. Then the QA, the sb01_02-equivalence check
  and the drift report are produced and logged. **No labels are read.**
- **Stage B, labels:** test labels are read and the frozen model and thresholds are evaluated.

Each stage needs its own explicit owner release. Stage A does not imply Stage B.

## 2. Candidate set *(claude-code, P1)*

These are the embedding classifiers already in the CV harness, with the hyperparameter that cv_v1 left fixed:

| Family | Features | Day score | Grid |
|---|---|---|---|
| Block LR (weak labels: every 5-min block takes its day's label) | 1280-d block embedding, standardised | aggregation ∈ {max, top-3 mean, top-12 mean, mean} of block probabilities | C ∈ {0.001, 0.01, 0.1, 1, 10} (`C_GRID`) |
| Day-mean LR | mean 1280-d block embedding of the day, standardised | the LR probability | C ∈ `C_GRID` |

That gives 25 configurations: 20 block and 5 day-mean. The aggregation is a day-score choice and needs no
refit, so the block grid costs 5 fits per fold. There are no new features, no new model families and no
architecture search. L2 logistic regression (lbfgs) is deterministic, so the 5-seed rule (evaluation-plan
§6) does not apply. That fact is logged.

## 3. Procedure *(claude-code, P2)*

1. **Selection.** For every configuration, compute out-of-fold day scores with the same leave-deployment-out
   folds as cv_v1 (9 folds; deployment k held out at both sites; Primary variant, all 300 days). Select the
   configuration with the highest **pooled out-of-fold AUROC_ws**.
2. **Tie rule** *(P3)*. Configurations within **0.005** of the best AUROC_ws count as tied. Among tied
   configurations, choose:
   1. the **smallest C** (strongest regularisation);
   2. then **block before day-mean** (the block family carries less site information: site-ID probe 0.61-0.64
      vs 0.69, cv_v1);
   3. then the aggregation in the fixed order **mean, top-12, top-3, max** (from most blocks used to fewest).

   This order is fixed now. It does **not** favour max, which cv_v1.1 shows passing by one comparison out of
   four.
3. **An honest estimate of the selection itself (nested CV).** For each outer fold k:
   - run step 1-2 on the other 8 deployment numbers (inner leave-deployment-out);
   - fit the chosen configuration on those 8;
   - score fold k.

   The pooled outer out-of-fold AUROC_ws, with its deployment-block CI and the pre-specified paired comparisons
   (evaluation-plan v2 §4), is the **train/val performance estimate for the final model**. The configuration
   chosen in each outer fold is logged, to show how stable the selection is.
4. **Sensitivity S1.** Repeat steps 1-3 with sb01_02 excluded (sb01_02 plan §3a) and report whether S1 picks
   the same configuration. The final model comes from Primary in either case.
5. **Final fit.** Fit the selected configuration on all 300 train/val days.

## 4. Thresholds *(claude-code, P4)*

- **The plan's window-detection rule does not apply to the block or day-mean models.** That rule is ≥ 3 window
  detections in a 10-minute span (evaluation-plan §3, eval_plan §4). It is written for 5-second window
  scores. The embedding classifiers score 5-minute blocks or whole days, so they have **no window
  threshold**. Their day score is the aggregation in §2.
  - *Proposed:* log this as an owner **plan clarification**, not a plan change, in the same way as the
    baseline-4 clarification.
- **The day threshold** for the final model maximises balanced accuracy on the **pooled out-of-fold day scores
  of the selected configuration** (step 1, Primary, both sites pooled, decision D4). It is applied to the tests
  unchanged.
- **Baseline thresholds are fixed now too,** because the tests report balanced accuracy for the baselines:
  - the zero-shot primary rule: its window threshold equals its day threshold on the continuous score
    (eval_plan §4);
  - the month prior and the ambient noise baseline: pooled out-of-fold.

  All of them come from the same pooled out-of-fold scores and are logged together.
- **A flag, not a change.** In cv_v1 the block-max pooled out-of-fold threshold is **0.996**, because the
  block probabilities saturate close to 1. A threshold this close to the top of the range may transfer poorly
  to a new site (Test S). The plan already says no cross-site calibration is claimed (eval_plan §6). This is
  noted now so that it is not read later as an explanation made after the fact.

## 5. Artefacts and logging *(claude-code, P5)*

- **The model:** `data/models/final_v1.joblib` (git-ignored, like all of `data/`). Its SHA-256 is logged.
- **A committed spec,** `docs/analysis/final_model/spec.json`, holding:
  - the configuration, C, aggregation and threshold;
  - the baseline thresholds;
  - the code commit, and the sklearn, numpy and Python versions;
  - the SHA-256 of `data/sample_days.csv` and the list of train/val feature files with their hashes;
  - the model artefact's SHA-256.
- **Audit entries:**
  - `run` (selection), then `final_model_selection` (with the per-outer-fold choices), then `final_model`
    (spec SHA-256 and artefact SHA-256);
  - all of them before any Stage A or Stage B release.
- **A results report,** `docs/analysis/final_model/README.md`, reporting:
  - the nested estimate;
  - the pre-specified comparisons;
  - S1;
  - the per-site AUROC, the site-ID probe and the site prior (evaluation-plan §5).

## 6. Decisions for the owner

| # | Proposed | Alternative |
|---|---|---|
| P1 | The candidate set in §2 (block LR × 4 aggregations, plus day-mean LR, × 5 C values) | Block LR only. Or fix C at 0.01 as in cv_v1 and choose the aggregation only |
| P2 | Nested CV for the estimate, with selection on the full 9-fold out-of-fold scores (§3) | No nested estimate: report the selected configuration's 9-fold out-of-fold value. That figure is optimistic, because selection and estimate use the same scores |
| P3 | Tie tolerance 0.005; order: smallest C, then block before day-mean, then mean > top-12 > top-3 > max | Plain argmax, with no tolerance |
| P4 | Log "no window threshold for embedding classifiers" as a plan clarification. The day threshold is pooled out-of-fold, maximising balanced accuracy | Treat it as a v3 plan change, with a tag |
| P5 | Artefacts and logging as in §5 | — |
| P6 | **Leave the ambient-noise C grid unchanged.** cv_v1 found C at the top of the grid (10) in every fold. Widening the grid could only strengthen that baseline, which is the conservative direction, but it would still be a change to a baseline made after its results were seen | Widen it to {…, 100, 1000} before test scoring, labelled as a post-hoc change, and report both |
| P7 | Two-stage release (§1): Stage A (audio, QA, drift report, no labels), then Stage B (labels), each with its own owner approval | A single release |
