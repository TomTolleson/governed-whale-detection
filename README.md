# NOAA SanctSound humpback detection (Stellwagen Bank)

Day-level **humpback whale presence/absence** detection on NOAA–U.S. Navy SanctSound passive
acoustic recordings from Stellwagen Bank National Marine Sanctuary (sites sb01, sb02, sb03).
The plan is a pretrained bioacoustic embedding model plus a small classifier, trained against
analyst-screened daily humpback labels.

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
- Licence terms are not yet confirmed (see `docs/inventory.md`). Raw data is never committed; it
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
