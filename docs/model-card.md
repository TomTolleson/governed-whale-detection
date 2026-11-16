# Model card: `final_v1`, day-level humpback presence (Stellwagen Bank)

| | |
|---|---|
| Written | **2026-11-16** by claude-code, at the owner's instruction. This is a **late artifact**: a model card should exist when a model is fixed. It was written **after** train/val modeling (model fixed 2026-11-12) and **after** Stage A (test audio scored 2026-11-13/14), **before** Stage B |
| Sources used | Train/val results (`docs/analysis/final_model/results.json`, `spec.json`) and Stage A QA and drift outputs only. **No test label was read** to write it. There are **no test results**. This card is to be extended after Stage B, with test results added as a dated section, and nothing above it changed |
| Changes to frozen work | **None.** It describes the model fixed under `docs/analysis/final-model-protocol.md` (P1-P7) and `eval-freeze-v2` (D1-D5) |

## Model details

| Item | Value |
|---|---|
| Name | `final_v1`, configuration `emb_block_lr_max_C0.001` |
| Type | L2-regularised logistic regression (lbfgs, C = 0.001) on standardised 1280-d block embeddings. Day score = **max** over the day's 5-min block probabilities |
| Features | Mean embedding per 5-min block from Google `multispecies-whale` (Kaggle, TF2 v2, Apache 2.0, used under its research and conservation terms). File hashes are in the `model_download` audit entry, and facts read from the SavedModel are in `docs/model_notes.md` |
| Training labels | Weak: every block takes its day's label (SanctSound `humpbackwhale_1d` daily presence) |
| Day threshold | **0.9804** (maximum balanced accuracy on pooled 9-fold out-of-fold train/val scores). No window threshold (P4) |
| Artefact | `data/models/final_v1.joblib`, SHA-256 `3f7ed71563dff9f50275ce4ef8613c89d393ac446dfb1b2b0eb2e71921f0bf24`. Spec `docs/analysis/final_model/spec.json`, `a2be3bb4…b8e931` |
| Backups | Local `~/noaa-whale-backups/final_v1_2026-11-13/`. **Off-machine:** branch `model-backup` (`8bde462`) of the private GitHub repository. Both verified by SHA-256 on 2026-11-14 |
| Fitted at | commit `f516b506`. Python 3.10.12, scikit-learn 1.5.2, numpy 1.26.4. Deterministic (no random seed is involved) |
| Developer | Independent, non-commercial research by the project owner, with claude-code (an AI coding assistant) doing the implementation under the owner's logged decisions |

## Intended use

- **Research use only.** It estimates, for one UTC day of SanctSound audio from Stellwagen Bank, whether
  humpback whale presence was likely to have been confirmed by analysts.
- **Out of scope:** operational, management, permitting or regulatory decisions; any site other than sb01,
  sb02 and sb03; any recorder or pipeline other than pipeline v2; and window-level or call-level detection.
- **Not a replacement** for analyst review. A score is not a measure of whale abundance.

## Training data

300 train/val days (189 present, 111 absent), sampled with seed 20261109 from eligible days (≥ 20 h of
audio) at sb01 and sb02, deployments 01-09 (Nov 2018 to Jun 2020). `data/sample_days.csv`
`3c47e9bc…201947d`. Data sheet: `docs/datasheet-esip-ai-ready.md`.

## Evaluation so far: train/val only, no test results

Leave-deployment-out cross-validation: fold k holds out deployment k at both sites. The headline metric is
**within-site AUROC (AUROC_ws)**, the chance that a present day outscores an absent day from the same site.
Bootstrap 95% CIs use 2,000 resamples.

| Method | AUROC_ws [95% CI] | Pooled AUROC [95% CI] | sb01 | sb02 |
|---|---|---|---|---|
| **Nested selection (honest estimate for this procedure)** | **0.726 [0.639, 0.819]** | 0.735 [0.649, 0.818] | 0.694 | 0.767 |
| Selected config, out-of-fold (optimistic: selected on these folds) | 0.804 [0.720, 0.869] | 0.817 [0.738, 0.877] | 0.779 | 0.836 |
| Month-prior baseline | 0.688 [0.579, 0.797] | 0.683 [0.567, 0.786] | 0.692 | 0.683 |
| Zero-shot `Mn` score | 0.695 [0.575, 0.831] | 0.678 [0.571, 0.803] | 0.604 | 0.811 |
| Ambient-noise baseline | 0.565 [0.470, 0.676] | 0.610 [0.506, 0.716] | 0.594 | 0.527 |
| Site-prior baseline | 0.174 [0.142, 0.266] | 0.455 [0.319, 0.618] | 0.166 | 0.184 |

Paired AUROC_ws differences for nested selection:
- vs the month prior: **[−0.099, 0.171]**. This includes 0, so the model **fails improvement condition 2**
  against the month prior.
- vs zero-shot `Mn`: [−0.075, 0.135], also including 0.
- vs the site prior: [0.414, 0.636].

Under plan A4 this result is reportable, not grounds to iterate. Under S1 (repeat selection) the selection
picked `C = 0.01` (AUROC_ws 0.779).

**Plainly:** on train/val the model has not been shown to beat a calendar-month guess. The test evaluation
(Stage B, not yet run) will show whether that holds on later deployments (Test T) and at a new site (Test S).

## Known limits and risks

- **Site and recorder shortcut.** The embeddings identify the recorder deployment (18-way balanced accuracy
  0.947) and the site (AUROC 0.999), and the site present rates differ (sb01 0.53, sb02 0.73).
  - Pooled metrics can reward site recognition, so AUROC_ws, per-site AUROC, the site-prior baseline and a
    site-ID probe are reported with every result.
  - The site-ID probe on the nested scores gives AUROC 0.598, against 0.603 from the labels alone.
- **Pretraining overlap.** The Google model's training data includes SanctSound, with sites and dates not
  stated. Test results will be an audit of a pretrained model, not evidence of generalisation to unseen audio.
- **Labels.** 0 means no confirmed detection, not proof of absence. Day boundaries are UTC as inferred from
  file names.
- **Threshold transfer.** The 0.9804 threshold was fixed on sb01/sb02. No claim of calibration at sb03.
- **Weak labels.** Every block of a present day is treated as present, although most blocks of a present day
  contain no call.

## Stage A: test audio QA and drift (audio only, no labels)

- 400 of 400 test days were scored with the frozen pipeline: Test T 150 (sb01/sb02 deployments 10-12) and
  Test S 250 (sb03 deployments 01-12).
- 4 Test S days have soft QA flags: 2 file overlaps trimmed and 2 days with gaps. There were **0 re-runs and
  0 exclusions**.
- No deployment is sb01_02-equivalent: every test deployment's median zero fraction is 0.0.
- **Drift:**
  - no band-level flag (largest excursion 3.5 dB, against the 6 dB flag);
  - one embedding flag, `sb03_01`, at 1.008× the train/val maximum nearest-deployment distance. It is
    **reported, not acted on**;
  - Test T deployments sit at 0.36-0.61× that distance and Test S at 0.49-1.01×.
- Outputs: `docs/analysis/drift/drift_test_{T,S}.json`, commit `e571e35`.

## Risk tier and monitoring

These already exist in the frozen plan. They are referenced here, not restated or changed:
- **Risk tier, self-assessed against NAO 216-128:** `docs/evaluation-plan.md` §10. The order defines no risk
  tiers. The self-assessed tier is **not high-risk / research-only**. It needs confirmation against the NOAA
  AI Handbook or the NAIEC framework, which were not available. It must be reassessed before any operational
  or management use.
- **Monitoring and drift plan:** `docs/evaluation-plan.md` §7, implemented in `src/drift_report.py`, with a
  train/val self-check in `docs/analysis/drift/self_check_trainval.json`.

## Readiness

**Research prototype.** It is not validated on held-out data: Stage B has not been run. On train/val it does
not beat the month-prior baseline with confidence. It is **not suitable for any operational use.** A readiness
statement for the write-up will be revisited after Stage B and the owner's results review.
