# NOAA SanctSound humpback detection (Stellwagen Bank)

**Summary.**
- **What it is.** An independent research audit of day-level **humpback whale presence** detection on NOAA–U.S.
  Navy SanctSound recordings from Stellwagen Bank (sites sb01, sb02, sb03). It uses a pretrained bioacoustic
  embedding model (Google `multispecies-whale`) plus a small classifier, trained against analyst-screened daily
  humpback labels, under an evaluation plan frozen before any test day was processed.
- **Headline result.** On Test S (a site not used to train the classifier), within-site AUROC is
  **0.883 [0.814, 0.936]**, against **0.829** for the month-prior baseline.
- **Pretrained model.** The embedding model's own training data includes SanctSound, so this is an audit of a
  pretrained model, not evidence of generalisation to unseen audio.
- **Verdict.** The pre-specified **improvement rule is not met** on any test split: the model does not beat the
  best simple baseline (on Test S, the calendar-month prior) with confidence.
- **Readiness.** **Research prototype. Not for operational use**, and not for management, permitting or
  regulatory decisions.

> **Independent project. No NOAA affiliation or endorsement.** This is an independent, non-commercial research
> project. It uses **public NOAA data**: SanctSound, collected by NOAA's Office of National Marine Sanctuaries
> and the U.S. Navy and distributed by NOAA NCEI. It is **not affiliated with, sponsored by or endorsed by NOAA,
> NCEI, the U.S. Navy or Google**, and nothing here represents their views. The data are cited as the source
> asks: see [References](#references), `CITATION.cff` and `docs/licensing-and-citation.md`. The source data
> states no licence.
>
> **Licence:** this project's own code and documentation are under **Apache 2.0** (`LICENSE`). Per `NOTICE`,
> that does not cover the SanctSound data, the Google model, or the derived features and model artefacts.

**AI assistance.** Built with Claude Code (an AI coding assistant) under the author's direction and review;
pipeline runs, plan changes and author decisions are logged in `audit_log.jsonl`, each with an `actor` field
saying who took it.

**Research use only.** Outputs are experimental and must not be used for operational,
management, permitting or regulatory decisions.

**Non-commercial research.** This project is non-commercial research. It uses Google's multispecies
whale model (Kaggle `google/multispecies-whale`, Apache 2.0), whose Terms of Use ask that it be used only for
applications with societal and/or environmental benefit, as well as
"wildlife conservation for not-for-profit decision-making, education, or research". The clause is quoted in
[`docs/model_notes.md`](docs/model_notes.md#terms-of-use-as-read-2026-11-16).

**This repository is a rewritten copy** of a private original, with one email address removed; see
[Provenance](#provenance-of-this-repository).

## Data

- Audio and labels: public GCS bucket `gs://noaa-passive-bioacoustic/sanctsound/`, read anonymously.
  See `docs/inventory.md`.
- Cite (as printed by the source, including "U.S Navy"): NOAA Office of National Marine Sanctuaries and
  U.S Navy. 2020. SanctSound Raw Passive Acoustic Data. NOAA National Centers for Environmental Information.
  https://doi.org/10.25921/saca-sp25 [accessed 2026-11-09 to 2026-11-16]. See [References](#references).
- Licence terms are not yet confirmed. The source states none, and requires a citation for the raw data and
  for each of the 36 label products: see `docs/licensing-and-citation.md`. Raw data is never committed; it
  lives in `data/`, which git ignores.

## Evaluation and governance

- **The plan comes first.** The evaluation rules were frozen before any test day was processed:
  - git tag `eval-freeze-v1` (`47a0b6f`);
  - then `eval-freeze-v2` (`e204ff9`).

  The original repository's tags were pushed to GitHub between 2026-11-11 and 2026-11-13; those push times
  can be checked in the original's GitHub **Activity** view (read access on request, see
  [Provenance](#provenance-of-this-repository)). In this copy, GitHub's timestamps date only from this
  copy's own push. The hashes quoted here and elsewhere in the text are the **original** hashes; translate
  them with `provenance/commit-map`.
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
  - The author therefore moved the headline to within-site AUROC: the chance that a present day outscores an
    absent day **from the same site**. Pooled AUROC is still reported every time, as a secondary metric.
  - The change is **Amendment 3** in `docs/eval_plan.md` §3. The reasoning, the author's decisions D1-D5 and the
    disclosure are in `docs/proposals/eval-freeze-v2-draft.md`.
  - It was frozen as `eval-freeze-v2` before any test day was processed. It is therefore a logged pre-test
    amendment (`owner_decision` and `eval_freeze` audit entries), not a deviation. Under the plan (§8), a
    deviation is a change made after test scoring begins.
- **Headline split.** The evaluation plan (`docs/evaluation-plan.md`, `docs/eval_plan.md`) **names no headline
  split**: it applies its rules to Test T and Test S alike. The author chose **Test S as the headline and Test T
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
- **The audit log:** pipeline runs, plan changes and author decisions are logged in `audit_log.jsonl`, which
  is append-only and hash-chained
  (`src/audit.py`, `verify_chain`).

## Stage B test results (as produced, 2026-11-16)

**Verdict: the improvement rule is NOT met on any test split.** The model does not show an improvement over
the best non-diagnostic baseline. Condition 2 (paired AUROC_ws CI against the best baseline excludes 0) fails
on Test S (the headline), Test T and the Test S 10-12 slice.

**How the run was done:**
- One pass of `src/test_eval.py` at tag `eval-tool-v1`, with the frozen model (`final_v1`, SHA-256
  `3f7ed715…`) and plans (`eval-freeze-v2`, `test-plan-v2`). Exit 0, 184 s, no crash, no re-run.
- The author's release is logged verbatim (`stage_b_release`).
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

- **SanctSound is in the embedding model's training data** (eval plan amendment 1). The Kaggle model card for
  Google `multispecies-whale` (read 2026-11-16) lists *SanctSound Raw Passive Acoustic Data*
  (doi 10.25921/saca-sp25) among its training-data citations, along with a NOAA NEFSC Stellwagen Bank dataset
  (doi 10.25921/g3vk-v972). Which sites, deployments and dates were used is not stated, so any train/val or
  test day here may have been seen in pretraining. These results are an **audit of a pretrained model**, not
  evidence of generalisation to unseen audio. See `docs/model_notes.md`.
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
- **Site-level AUROC above the deployments inside it.** On Test T, sb01's within-site AUROC is 0.825, but its
  only evaluable deployment, sb01_10, scores 0.49. At sb02 the figures are 0.920 and 0.784 (sb02_10). A
  within-site AUROC well above that of the site's only evaluable deployment is consistent with pooling
  deployments within a site still rewarding differences between deployments, not only the humpback signal.
  This is a reading of the numbers already reported; no new analysis was run.
- **Test S is less independent than "new site" suggests.** Test S covers the same calendar dates as train/val,
  at a site in the same sanctuary. Humpback presence, and so the daily labels, can be expected to be
  correlated across sites on the same dates (this was not measured). Test S tests a new recorder location,
  not a later period or an independent population of days.
- **Labels.** 0 means no confirmed detection, not proof of absence.

## Provenance of this repository

This repository is a **rewritten copy** of a private original repository. The original is the authoritative,
hash-verified record and has not been changed. The two differ in exactly two ways:

1. **Commit, tag and tagger email.** Every author, committer and tagger email is mapped to the author's GitHub
   `users.noreply.github.com` address. Names, dates and messages are unchanged byte for byte, so commit
   messages still quote the **original** commit hashes. Use the commit map (below) to translate them.
2. **One audit-log redaction, plus re-chaining.** In `audit_log.jsonl`, line 127 (a `correction` entry)
   held a personal email address, as the sender of an email to NCEI. In every version of the file, that
   address is replaced by `[redacted]`. Nothing else on that line, or on any other line, was removed.
   - The log is hash-chained: each line's `prev_hash` is the SHA-256 of the previous line's text. Changing
     line 127 changes its hash, so the `prev_hash` of every later line was recomputed. No other field of any
     line changed.
   - `src.audit.verify_chain()` passes on every version of the file in this copy. In the private original,
     the chain verifies with the original line 127.

So every commit from original `a79667a` onward (the commit that added line 127), and every tag, has a
different hash here than in the original. Trees are identical apart from `audit_log.jsonl`. Commits made
after the rewrite, starting with the one that added `provenance/`, exist only in this copy.

### Original tags

The tags were meant as independent timestamps. In the private original, they are:

| Tag | Original tag object | Original commit | Tagger date (UTC) |
|---|---|---|---|
| `eval-freeze-v1` | `31082b6a4b91993bac66553d3df8b439c467642a` | `47a0b6f994017789505a04fe3b3e0167235cf127` | 2026-11-11 22:12:46 |
| `eval-freeze-v2` | `5c6a1ee207ce652fff8766092dfe0a975dce7a05` | `e204ff945e215d25de845494fe0b370187024d61` | 2026-11-11 22:55:34 |
| `eval-tool-v1` | `4832abb276ee320fd44ba45805cde27daf7db6cd` | `356505187d8863670d3e5a417e631643578eb480` | 2026-11-13 02:03:47 |
| `test-plan-v1` | `445adcda1db4821dacb0bc00a166611b1ee5832f` | `201f249bd81e59ed7fdb4a448905b3f58cdbb569` | 2026-11-13 02:09:15 |
| `test-plan-v2` | `ca85a99c3a09a765f2dd23fc56706183dfdcefb1` | `d988daaa70987ba599c97ed0588a7d8d5abea4f2` | 2026-11-13 16:38:28 |

The last original commit in this copy is `0fdde3c2653e3b16985fa3a976f25634ca5976d5`.

- **About these dates.** They are **tagger dates**: the time stored inside each tag object by the machine
  that created it. They are not times recorded by GitHub. The tags here carry the same names, messages and
  tagger dates, and point to the mapped commits.
- **Push times.** When each branch and tag actually reached GitHub can be seen in the original repository's
  **Activity** view on GitHub, which anyone given read access can open.

### Commit map

`provenance/commit-map` (67 commits) and `provenance/ref-map` (branch heads and the five tag objects) map
each original hash to its hash here. They were written by `git filter-repo` when the copy was made, and
committed unchanged.

```bash
# original commit quoted in a message or in the audit log -> this copy
awk '$1 ~ /^47a0b6f/ {print $2}' provenance/commit-map
# this copy -> original
awk '$2 ~ /^209598f/ {print $1}' provenance/commit-map
# original tag objects -> tag objects here
grep refs/tags/ provenance/ref-map
```

See `provenance/README.md` for the file format and what each row guarantees.

### Checking against the original

**Read access to the private original is available on request**, for anyone who wants to check this copy
against it: the tag hashes above, the unredacted chain, and both maps. To ask, **open an issue on this
repository** on GitHub, or contact the author through their GitHub profile,
[github.com/TomTolleson](https://github.com/TomTolleson). Please do not post personal contact details in an
issue.

## References

Cite the sources below if you use this work. The data citations follow the wording each NOAA source asks for
(`useLimitation`: "Cite as: …"). See `docs/licensing-and-citation.md` for how they were found.

### Embedding model

- Harvey, M., Allen, A., and Harrell, L. *multispecies-whale* (Google; TensorFlow 2, variation `default`,
  version 2). Kaggle. https://doi.org/10.34740/kaggle/m/94838
  - Authors and DOI as shown on the Kaggle model page (read 2026-11-16). The page's citation box was empty, so
    this format is the project's own. Licence Apache 2.0. Its Terms of Use ask for applications with societal and/or
    environmental benefit, as well as "wildlife conservation for not-for-profit decision-making, education, or research"
    ([`docs/model_notes.md`](docs/model_notes.md#terms-of-use-as-read-2026-11-16)).

### SanctSound raw audio

- NOAA Office of National Marine Sanctuaries and U.S Navy. 2020. SanctSound Raw Passive Acoustic Data.
  NOAA National Centers for Environmental Information. https://doi.org/10.25921/saca-sp25 [accessed 2026-11-09 to 2026-11-16]

### SanctSound humpback label products (36)

Each product has its own DOI and is cited as:

> NOAA Office of National Marine Sanctuaries and U.S Navy. 2021. Humpback Whale Sound Production Recorded at
> SanctSound Site SB0X_NN, SanctSound Data Products. NOAA National Centers for Environmental Information.
> https://doi.org/10.25921/… [accessed 2026-11-09 to 2026-11-16].

The citation text says 2021; the NCEI page for sb02_01 shows a publication date of 2023-06-15. Citations are
reproduced as printed, including "U.S Navy" (without the second full stop), here and in [Data](#data).

| Site | DOI | Site | DOI | Site | DOI |
|---|---|---|---|---|---|
| `SB01_01` | https://doi.org/10.25921/34s0-d728 | `SB02_01` | https://doi.org/10.25921/3hf1-jk31 | `SB03_01` | https://doi.org/10.25921/54er-1b93 |
| `SB01_02` | https://doi.org/10.25921/031d-yg11 | `SB02_02` | https://doi.org/10.25921/jzda-0t10 | `SB03_02` | https://doi.org/10.25921/akgp-8228 |
| `SB01_03` | https://doi.org/10.25921/smbv-jy13 | `SB02_03` | https://doi.org/10.25921/4s42-t075 | `SB03_03` | https://doi.org/10.25921/c6n2-4s25 |
| `SB01_04` | https://doi.org/10.25921/582k-4c86 | `SB02_04` | https://doi.org/10.25921/m3as-x078 | `SB03_04` | https://doi.org/10.25921/4er4-2e90 |
| `SB01_05` | https://doi.org/10.25921/j65a-9k58 | `SB02_05` | https://doi.org/10.25921/4401-dd56 | `SB03_05` | https://doi.org/10.25921/hddv-5d43 |
| `SB01_06` | https://doi.org/10.25921/b44a-gf17 | `SB02_06` | https://doi.org/10.25921/s8yq-mn89 | `SB03_06` | https://doi.org/10.25921/xbbq-xp09 |
| `SB01_07` | https://doi.org/10.25921/q812-0b80 | `SB02_07` | https://doi.org/10.25921/mgms-1a35 | `SB03_07` | https://doi.org/10.25921/884g-vz82 |
| `SB01_08` | https://doi.org/10.25921/gj0x-vj92 | `SB02_08` | https://doi.org/10.25921/0sq0-c417 | `SB03_08` | https://doi.org/10.25921/aa7j-gp09 |
| `SB01_09` | https://doi.org/10.25921/2745-1n07 | `SB02_09` | https://doi.org/10.25921/1dbv-qg42 | `SB03_09` | https://doi.org/10.25921/fkxj-d643 |
| `SB01_10` | https://doi.org/10.25921/12mx-er78 | `SB02_10` | https://doi.org/10.25921/4bdh-jn58 | `SB03_10` | https://doi.org/10.25921/n9pc-dn32 |
| `SB01_11` | https://doi.org/10.25921/14pp-9d51 | `SB02_11` | https://doi.org/10.25921/nz8m-4451 | `SB03_11` | https://doi.org/10.25921/q3x6-ga83 |
| `SB01_12` | https://doi.org/10.25921/9zhe-se70 | `SB02_12` | https://doi.org/10.25921/34pc-z289 | `SB03_12` | https://doi.org/10.25921/26yy-w670 |

## Layout

```
README.md, LICENSE, NOTICE, CITATION.cff
requirements-recorded.txt   versions used for every recorded run (requirements.txt is stale)
audit_log.jsonl      append-only, hash-chained log of pipeline runs, plan changes and decisions (src/audit.py)
provenance/          commit-map and ref-map from the rewrite (see provenance/README.md)
src/
  audit.py           audit log: log_event, verify_chain
  inventory.py, header_check.py, flac_header.py, label_survey.py, day_table.py
                     bucket listing, FLAC header checks, label survey, deployment-day table
  sample_days.py, split_candidates.py
                     stratified day samples and train/val vs test splits
  throughput.py      streaming throughput measurement
  pilot.py           scores days with the Google model (pipeline v2): streams audio, resamples to 24 kHz,
                     writes per-block embeddings and scores. Used for train/val and, frozen, for Stage A
  pilot_review.py, deployment_check.py, posthoc_zs_pairs.py
                     exploratory and diagnostic checks, train/val only
  cv_eval.py         leave-deployment-out CV, baselines and first classifiers, train/val only
  final_model.py     final-model selection and fit (protocol P1-P7), train/val only
  drift_report.py    pre-evaluation drift report on test audio (reads no labels)
  test_eval.py       Stage B test evaluation, frozen at tag eval-tool-v1; the only code that reads test labels
tools/
  dryrun_test_eval.py   dry run of test_eval.py with fake labels on non-test data
  thermal_watchdog.py   thermal watchdog used during Stage A scoring: records CPU Tctl (k10temp) and GPU
                        temperature (nvidia-smi) every 15 s, and pauses the run at 85 °C
tests/               pytest tests
docs/                plans (evaluation-plan.md, eval_plan.md), errata/, proposals/, model card, data sheet,
                     licensing and citation, and analysis/ outputs (cv, final_model, drift, stage_a, test_results)
data/                git-ignored: listings, day tables, embeddings, scores, the downloaded model
```

## Setup

**What is and is not here.**
- The fitted model artefact (`final_v1.joblib`) is **not published**. Its SHA-256 and specification are in
  `docs/analysis/final_model/spec.json` and `docs/model-card.md`.
- No audio, embeddings or scores are committed (`data/` is git-ignored). The Google model is downloaded from
  Kaggle.
- **Full reproduction is heavy.** The 700 scored days (300 train/val, 400 test) stream about **1.3 TB** of
  audio from the public bucket (audio is streamed, not stored), and scoring takes many hours on a GPU: Stage A
  alone scored 400 days in about 7.4 hours on one GPU.

**Environment used for every recorded run:** Python 3.10.12 with tensorflow 2.17.1, numpy 1.26.4,
scikit-learn 1.5.2, scipy 1.15.3, pandas 2.3.3, soundfile 0.14.0, soxr 0.5.0.post1, joblib 1.6.0,
kagglehub 0.3.12, gcsfs 2026.10.1 and pytest 9.2.0, on one GPU. These are pinned in
`requirements-recorded.txt`. **`requirements.txt` is out of date** (it pins numpy 2.2.6 and omits tensorflow,
soxr, joblib and kagglehub); it is kept unchanged as part of the frozen record.

```bash
python3.10 -m venv .venv
.venv/bin/pip install -r requirements-recorded.txt
.venv/bin/python -m pytest -q
```

**Running the pipeline** (every script below except `src.inventory` takes `--actor` and logs to `audit_log.jsonl`):
1. `src.inventory`, `src.label_survey`, `src.day_table`, `src.sample_days`: build the listings, day table and
   day samples.
2. `src.pilot --split trainval`: score the train/val days.
3. `src.cv_eval`, then `src.final_model`: cross-validation and the final model.
4. `src.pilot --split test_T|test_S` and `src.drift_report --split test_T|test_S`: Stage A test scoring and
   drift.
5. `src.test_eval`: Stage B. It requires an explicit `--owner-approval` text, and is meant to be run once.

## Audit log

Pipeline runs, plan changes and author decisions are appended to `audit_log.jsonl` through
`src.audit.log_event`. Each line stores
the SHA-256 of the line before it, so `src.audit.verify_chain()` will detect any edit or deletion.
