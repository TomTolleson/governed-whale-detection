# NOAA SanctSound humpback detection (Stellwagen Bank)

Day-level **humpback whale presence/absence** detection on NOAA–U.S. Navy SanctSound passive
acoustic recordings from Stellwagen Bank National Marine Sanctuary (sites sb01, sb02, sb03).
The plan is a pretrained bioacoustic embedding model plus a small classifier, trained against
analyst-screened daily humpback labels.

> **Independent project. No NOAA affiliation or endorsement.** *(Draft header, 2026-11-16, for owner review;
> not yet published.)* This is an independent, non-commercial research project. It uses **public NOAA data**:
> SanctSound, collected by NOAA's Office of National Marine Sanctuaries and the U.S. Navy and distributed by
> NOAA NCEI. It is **not affiliated with, sponsored by or endorsed by NOAA, NCEI, the U.S. Navy or Google**,
> and nothing here represents their views. The data are cited as the source asks: see `CITATION.cff` and
> `docs/licensing-and-citation.md`. The source states no licence, and the licence for this project's own code
> is still to be chosen.

**Research use only.** Outputs are experimental and must not be used for operational,
management, permitting or regulatory decisions.

**Non-commercial research.** This project is non-commercial research. It uses Google's multispecies
whale model (Kaggle `google/multispecies-whale`, Apache 2.0), whose Terms of Use ask that it be used for
wildlife conservation, research or education, not for profit (`docs/model_notes.md`).

## Data

- Audio and labels: public GCS bucket `gs://noaa-passive-bioacoustic/sanctsound/`, read anonymously.
  See `docs/inventory.md`.
- Cite: NOAA Office of National Marine Sanctuaries and U.S. Navy. 2020. SanctSound Raw Passive
  Acoustic Data. NOAA National Centers for Environmental Information.
  https://doi.org/10.25921/saca-sp25
- Licence terms are not yet confirmed. The source states none, and requires a citation for the raw data and
  for each of the 36 label products: see `docs/licensing-and-citation.md`. Raw data is never committed; it
  lives in `data/`, which git ignores.

## Evaluation and governance

- **The plan comes first.** The evaluation rules were frozen before any test day was processed:
  - git tag `eval-freeze-v1` (`47a0b6f`);
  - then `eval-freeze-v2` (`e204ff9`).

  Both tags are pushed, so their timestamps can be checked independently.
- **The plan files:**
  - Start at `docs/evaluation-plan.md`.
  - Where it repeats `docs/eval_plan.md`, the wording in `docs/eval_plan.md` governs.
  - Details are in `docs/analysis/sb01_02-sensitivity-plan.md` and `docs/errata/`.
- **Headline metric: within-site AUROC.** This is a **pre-test amendment, made after the train/val CV v1
  results had been seen.**
  - Under `eval-freeze-v1` the headline was pooled AUROC.
  - The embeddings identify the recorder deployment (18-way balanced accuracy 0.947) and the site (AUROC
    0.999), and the two sites' present rates differ. So pooled AUROC can reward site identity instead of
    the humpback signal.
  - The owner therefore moved the headline to within-site AUROC: the chance that a present day outscores an
    absent day **from the same site**. Pooled AUROC is still reported every time, as a secondary metric.
  - The change is **Amendment 3** in `docs/eval_plan.md` §3. The reasoning, owner decisions D1-D5 and the
    disclosure are in `docs/proposals/eval-freeze-v2-draft.md`.
  - It was frozen as `eval-freeze-v2` before any test day was processed. It is therefore a logged pre-test
    amendment (`owner_decision` and `eval_freeze` audit entries), not a deviation. Under the plan (§8), a
    deviation is a change made after test scoring begins.
- **Headline split.** The evaluation plan (`docs/evaluation-plan.md`, `docs/eval_plan.md`) **names no headline
  split**: it applies its rules to Test T and Test S alike. The owner chose **Test S as the headline and Test T
  as secondary** before any test day was processed. That choice is recorded **only in the test-processing plan**
  (`docs/analysis/test-processing-plan.md` §4 [A3], tag `test-plan-v1`). The evaluation plan was not amended,
  and there is no `eval-freeze-v3`. All three splits are always reported.
- **Stage B evaluator.** `src/test_eval.py` is frozen at tag `eval-tool-v1` before any test release. It is the
  only code that reads test labels.
- **Stage A drift note (reported, not excluding).** The Stage A drift report on Test S
  (`docs/analysis/drift/drift_test_S.json`, commit `e571e35`) flags one deployment, **`sb03_01`**.
  - Its embedding distance to the nearest train/val deployment is 30.36. That is **1.008×** the largest
    nearest-deployment distance within train/val (30.11).
  - No other test deployment exceeds 0.90× that distance.
  - Under the plan (evaluation-plan §7; test-processing plan §2.6), drift flags are **reported, not acted on**.
    `sb03_01` stays in every Stage B result, and nothing is excluded or re-weighted because of the flag.
  - The same report found no band-level flags and no sb01_02-equivalent deployment, in Test T or Test S.
- **Late artifacts: an omission, found and fixed on 2026-11-16.** Two documents that should have existed before
  modeling were missing. They were written on 2026-11-16, after train/val modeling and Stage A and before
  Stage B, from train/val and Stage A QA outputs only, with no test label read:
  - `docs/datasheet-esip-ai-ready.md`: a data sheet scored against the ESIP AI-Ready Data Checklist v1.0.
    Of 49 applicable items, 22 are met, 11 partly met and 16 not met. Access, persistent identifier, licence
    and standard metadata are the gaps.
  - `docs/model-card.md`: the model card for `final_v1`, with train/val results only.

  The risk tier mapped to NAO 216-128 (`docs/evaluation-plan.md` §10) and the monitoring and drift plan (§7)
  already existed. They are unchanged. Each late document is logged in the audit chain as a
  `late_artifact` entry with its SHA-256. Nothing frozen was changed.
- **What every result carries:** per-site AUROC, the site-prior baseline and a site-ID probe, because of the
  site and recorder shortcut.
- **The audit log:** every step is logged in `audit_log.jsonl`, which is append-only and hash-chained
  (`src/audit.py`, `verify_chain`).

## Stage B test results (as produced, 2026-11-16)

**Verdict: the improvement rule is NOT met on any test split.** The model does not show an improvement over
the best non-diagnostic baseline. Condition 2 (paired AUROC_ws CI against the best baseline excludes 0) fails
on Test S (the headline), Test T and the Test S 10-12 slice.

**How the run was done:**
- One pass of `src/test_eval.py` at tag `eval-tool-v1`, with the frozen model (`final_v1`, SHA-256
  `3f7ed715…`) and plans (`eval-freeze-v2`, `test-plan-v2`). Exit 0, 184 s, no crash, no re-run.
- The owner's release is logged verbatim (`stage_b_release`).
- Outputs: `docs/analysis/test_results/results.json` (`f2e0e32d…`) and `test_day_scores.csv`
  (`0fcbed30…`), commit `5c684fb`, unedited.
- 400 days, 0 QA exclusions.
- No sensitivity variant applied: no test day has a zero fraction above 0.01, and no test deployment is
  sb01_02-equivalent.

### Headline and secondary

| Split | Days (present / absent) | Final model AUROC_ws [95% CI] | Pooled AUROC [95% CI] | Best baseline (AUROC_ws) | Paired AUROC_ws difference vs best | Verdict |
|---|---|---|---|---|---|---|
| **Test S** (sb03, new site; headline) | 250 (194 / 56) | **0.883 [0.814, 0.936]** | same (one site) | month prior 0.829 [0.747, 0.892] | [−0.013, 0.150] | **not met** |
| Test T (sb01/sb02 deployments 10-12, later in time) | 150 (111 / 39) | 0.870 [0.623, 0.929] | 0.873 [0.728, 0.945] | zero-shot `Mn` 0.790 [0.746, 0.853] | [−0.219, 0.184] | **not met** |
| Test S 10-12 slice (*exploratory*) | 58 (43 / 15) | 0.778 [0.45, 0.968] | same | zero-shot `Mn` 0.854 [0.75, 1.0] | **[−0.367, −0.025]**: the final model is **worse** | **not met** (condition 1 also fails) |

**Comparison with the month prior** (the calendar-month presence rate):

| | Final model minus month prior (AUROC_ws) | Paired 95% CI |
|---|---|---|
| Train/val (nested CV) | 0.726 − 0.688 = **+0.04** | [−0.099, 0.171], includes 0 |
| **Test S** | 0.883 − 0.829 = **+0.05** | [−0.013, 0.150], includes 0 |
| Test T | 0.870 − 0.755 = +0.12 | [0.024, 0.311], excludes 0. Not the verdict's comparison: the month prior is not Test T's best baseline. Zero-shot is, and that comparison includes 0 |

All other baselines and paired comparisons, pooled and within-site, are in `results.json`
(`splits.<split>.primary`). The site-prior baseline is 0.5 by construction within a site. The site-ID probe on
Test T is 0.585.

### Per deployment

AUROC is computed only where a deployment has at least 5 absent days. `eval-tool-v1` reports **no
per-deployment CIs**, and none were computed afterwards.

| Split | Deployment | Days | Present / absent | AUROC |
|---|---|---|---|---|
| Test T | sb01_10 | 29 | 11 / 18 | **0.49** |
| Test T | sb01_11 | 16 | 14 / 2 | n/a |
| Test T | sb01_12 | 30 | 29 / 1 | n/a |
| Test T | sb02_10 | 29 | 12 / 17 | 0.784 |
| Test T | sb02_11 | 15 | 15 / 0 | n/a |
| Test T | sb02_12 | 31 | 30 / 1 | n/a |
| Test S | sb03_01 | 25 | 24 / 1 | n/a |
| Test S | sb03_02 | 23 | 13 / 10 | 0.938 |
| Test S | sb03_03 | 21 | 19 / 2 | n/a |
| Test S | sb03_04 | 22 | 12 / 10 | 0.875 |
| Test S | sb03_05 | 23 | 17 / 6 | 0.980 |
| Test S | sb03_06 | 22 | 21 / 1 | n/a |
| Test S | sb03_07 | 10 | 9 / 1 | n/a |
| Test S | sb03_08 | 23 | 13 / 10 | 0.869 |
| Test S | sb03_09 | 23 | 23 / 0 | n/a |
| Test S | sb03_10 | 22 | 12 / 10 | **0.542** |
| Test S | sb03_11 | 12 | 10 / 2 | n/a |
| Test S | sb03_12 | 24 | 21 / 3 | n/a |

The 10-12 slice is sb03_10 (22 days, 12 / 10), sb03_11 (12 days, 10 / 2) and sb03_12 (24 days, 21 / 3): 58
days in all. Only sb03_10 has enough absent days for an AUROC.

Per-site AUROC on Test T: sb01 0.825 [0.49, 0.931]; sb02 0.920 [0.683, 0.938].

**Open question, deployment 10.** Deployment 10 (June to August 2020) is the weakest deployment at two of the
three sites: sb01_10 scores 0.49 (chance) and sb03_10 scores 0.542. sb02_10 scores 0.784. Its cause is **not
investigated**. Doing so would be a new analysis, and it is not part of the frozen plan.

### Limitations, stated with these results

- **Few independent deployments.** Only 7 of the 18 test deployments have at least 5 absent days. CIs are
  wide (the Test T within-site lower bound is 0.623; the 10-12 slice spans 0.45 to 0.968).
- **Uncalibrated scores.** Mean daily scores per deployment are 0.87-0.997, against present rates of 0.38-1.0.
  The scores bunch near 1, and the 0.9804 threshold sits in that narrow band.
- **Recorder identifiability.** The embeddings identify the recorder deployment (18-way balanced accuracy
  0.947 on train/val) and the site. Within-site metrics and the site-prior baseline are reported for this
  reason, but they cannot rule the shortcut out.
- **Baselines rose too.** The month prior scores 0.829 on Test S, against 0.688 on train/val. Higher test
  AUROCs therefore partly reflect easier test days for every method, not only the model.
- **Post-hoc thresholded table.** The per-site sensitivity, specificity and balanced-accuracy table
  (`docs/analysis/test_results/derived/`, commit `edadc3e`) is a **logged deviation**.
  - It was computed after the one pass, from the committed day scores, using only the frozen thresholds:
    final model 0.9804, and the month-prior, ambient-noise and zero-shot thresholds from `spec.json`.
  - Nothing was tuned. Its split totals reproduce `results.json`.
- **Headline change before test.** The headline metric moved from pooled AUROC to within-site AUROC at
  `eval-freeze-v2`. That was after the train/val CV results were seen and before any test day was processed.
  It is a logged pre-test amendment, not a deviation, but it was a choice made with knowledge of train/val
  results.
- **Pretraining overlap** (eval plan amendment 1). SanctSound may be in the pretrained model's training data,
  so these are an audit of a pretrained model, not evidence of generalisation to unseen audio.
- **Same dates.** Test S covers the same calendar dates as train/val. It tests a new site, not a later period.
- **Labels.** 0 means no confirmed detection, not proof of absence.

## Layout

```
docs/             inventory and design notes
src/audit.py      append-only, hash-chained audit log (audit_log.jsonl)
src/inventory.py  bucket listing -> data/inventory.json
tests/            pytest tests
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## Audit log

Every action is appended to `audit_log.jsonl` through `src.audit.log_event`. Each line stores
the SHA-256 of the line before it, so `src.audit.verify_chain()` will detect any edit or deletion.
