# Data sheet: ESIP AI-Ready Data Checklist (v1.0), self-assessed

| | |
|---|---|
| Written | **2026-11-16** by claude-code, at the owner's instruction. This is a **late artifact**: it should have been written before modeling. It was written **after** train/val modeling (final model fixed 2026-11-12) and **after** Stage A (test audio scored 2026-11-13/14), **before** Stage B (no test label has been read for evaluation) |
| Sources used | Train/val outputs and Stage A QA and drift outputs only: `docs/inventory.md`, `docs/data_sources.md`, `docs/labeling_rules.md`, `docs/evaluation-plan.md`, `docs/eval_plan.md`, the `score_day` audit entries, `docs/analysis/drift/*.json`, `docs/analysis/final_model/spec.json`. **No test label was read** to write it |
| Checklist | ESIP Data Readiness Cluster (2023), *Checklist to Examine AI-readiness for Open Environmental Datasets*, v1.0. DOI https://doi.org/10.6084/m9.figshare.19983722. Read 2026-11-16 from the PolarWatch mirror, https://polarwatch.github.io/datamanagement/guidelines/ai-ready-data-checklist-v.1.0.html. That page says it mirrors `ESIPFed/data-readiness`, `checklist-published/ai-ready-data-checklist-v.1.0.md`. It gives two dates, "Updated 04/03/2024" in its header and "Last updated: June 21, 2023" in its history |
| Wording | The item wording below is **paraphrased**, in the checklist's order. The source above has the exact text |
| Changes to frozen work | **None.** This document describes the data. It changes nothing in the pipeline, QA rules, plans, P1-P7 or D5 |

## What is assessed

The checklist asks to be applied to one dataset at the file level. It is applied here to **this project's
derived day-level dataset**, the data the classifier was trained and evaluated on. It has three parts:

| Part | File(s) | Content |
|---|---|---|
| Day table | `data/day_table.csv` (`82475a1b…1f1dae04`) | One row per deployment-day: site, deployment, date, label, audio hours, eligibility flags, zero fraction |
| Sampled day list | `data/sample_days.csv` (`3c47e9bc…201947d`, seed 20261109) | 300 train/val days, 150 Test T days and 250 Test S days |
| Per-day features | `data/scores/v2/*.npz` (300 train/val), `data/scores/v2_test/*.npz` (400 test) | Per 5 s window: the 12 class scores of the Google multispecies whale model. Per 5-min block: the mean 1280-d embedding and 9 band levels. Per day: the zero fraction |

The source it is built from is **SanctSound Raw Passive Acoustic Data** (NOAA ONMS and U.S. Navy, 2020,
NCEI, doi 10.25921/saca-sp25), with its `humpbackwhale_1d` detection products.

**Scores (strict):**
- **The derived dataset is scored on its own.** The source's DOI, landing page, public bucket and ISO
  metadata are noted in the answers, but they **do not raise a score**. The only exception is 5.5, which asks
  about the original sampling.
- **Met** means satisfied for the derived dataset, with the evidence named. For a purely descriptive item
  (for example "raw or derived"), Met means the answer is documented.
- **Partly met** means satisfied only in part.
- **Not met** means not satisfied.
- **N/A** is used only for items that are conditional on something absent (no updates, no API, no restricted
  data). No credit is given for them.

## Summary

| Section | Met | Partly met | Not met | N/A |
|---|---|---|---|---|
| 1. General information | 3 | 0 | 1 | 0 |
| 2. Data quality | 9 | 4 | 2 | 2 |
| 3. Data documentation | 1 | 7 | 7 | 0 |
| 4. Data access | 3 | 0 | 5 | 5 |
| 5. Data preparation | 6 | 0 | 1 | 0 |
| **Total (56 items)** | **22** | **11** | **16** | **7** |

Of the 49 items that apply, 22 are met (45%), 11 are partly met and 16 are not met. Most of the Met scores in
sections 1 and 5 are descriptive: the answer is documented. They are not quality achievements.

**The weakest areas are access, persistent identity, licence and standard metadata.**
- The derived dataset is not published. It sits in git-ignored `data/` on one machine, and the repository is
  private.
- It has no DOI, no landing page and no confirmed licence.
- Its metadata follows no community standard.

**Quality and provenance are the strongest areas:** per-file SHA-256 hashes, a hash-chained audit log, QA
flags on every day, and a known-bias analysis that is reported with every result.

## 1. General information

| # | Item (paraphrased) | Answer | Score |
|---|---|---|---|
| 1.1 | Landing page, with name, version, contact and publication date | **None for the derived dataset.** The source has an NCEI DOI landing page. The project repository is private. Name: SanctSound Stellwagen humpback day-level features. Version: pipeline v2 (`src/pilot.py` at `eval-freeze-v2`, `e204ff9`). Contact: the project owner. Not published | **Not met** |
| 1.2 | Raw or derived | Derived | **Met** (stated) |
| 1.3 | Observed, modeled or synthetic | Observed audio, with model-derived features (pretrained embeddings and scores) and analyst-derived labels | **Met** (stated) |
| 1.4 | Single-source or aggregated | Aggregated: SanctSound audio, SanctSound `humpbackwhale_1d` labels, and features from Google's `multispecies-whale` model (TF2 v2, file hashes in the `model_download` audit entry) | **Met** (stated) |

## 2. Data quality

| # | Item (paraphrased) | Answer | Score |
|---|---|---|---|
| 2.1 | Will the dataset be updated? | No. It is a fixed snapshot for one evaluation. A new data release, model or pipeline would get a new version and output directory (evaluation-plan §7) | **Met** (stated) |
| 2.2 | If updated: frequency, staged updates and delay | Not updated | **N/A** |
| 2.3 | If a new version is released: does it supersede the old one? | No new version planned. If one were made, versions would sit side by side and results would never be overwritten (evaluation-plan §7) | **N/A** |
| 2.4 | Documentation about completeness | Yes: `docs/inventory.md` (all 63 deployments, 36 with humpback labels), `docs/eligible_summary.md`, and the day-table eligibility rule in `docs/labeling_rules.md` | **Met** |
| 2.5 | Completeness against the expected spatial coverage | Partial. There are 3 fixed sites (sb01, sb02, sb03), one recorder each, and no spatial field | **Partly met** |
| 2.6 | Completeness against the expected temporal coverage | Partial by design. Deployments 01-12 (Nov 2018 to Nov 2020) have labels, and 13-21 do not. The dataset is a **stratified sample** of eligible days (≥ 20 h of audio), not every day. 2 of the 300 train/val days have under 23.99 h of windows (sb01_03_2019-04-10 at 20.0 h; sb01_01_2018-12-02 at 23.96 h). The shortest test day has 23.74 h | **Partly met** |
| 2.7 | Self-consistent in units, types and names over time and space | Yes. One pipeline version for all 700 days. Fixed band edges, window (5 s) and block (5 min). Every file records `pipeline_version` and `git_commit` | **Met** |
| 2.8 | Consistent with similar collections | **Not assessed.** It has not been compared with any other humpback day-presence dataset | **Not met** |
| 2.9 | Processes to monitor consistency | Yes, automated: QA flags on every `score_day` entry (evaluation-plan §5), a drift report per test split (§7), and a train/val self-check of the drift report (`docs/analysis/drift/self_check_trainval.json`) | **Met** |
| 2.10 | Known bias, with details | **Yes**, see *Known bias* below: the recorder and site shortcut, site and season label imbalance, the meaning of label 0, recorder dropouts in sb01_02, and pretraining overlap | **Met** (disclosed) |
| 2.11 | Measures taken to examine bias, and whether the bias is metrologically traceable | Measures: yes. The deployment-ID and site-ID probes, within-site AUROC as the headline metric, the site-prior and month-prior baselines, and zero-flag and sb01_02 sensitivity analyses. **Metrological traceability: no.** Band levels are uncalibrated (dB re full scale). The recorder calibration files in the bucket's `ancillary/calibration/` were not applied | **Partly met** |
| 2.12 | Reported bias status | **Bias found and reported**: README, eval_plan §6, `docs/analysis/sb01_02-sensitivity-plan.md` | **Met** |
| 2.13 | Quantitative spatial and temporal resolution | Temporal: 5 s windows (24 kHz input), 5-min blocks, UTC days. Spatial: one point per site. Coordinates are in the source's deployment metadata JSON, not in the derived files | **Partly met** |
| 2.14 | Published data-quality procedures or reports | The procedures are written and committed: evaluation-plan §5, `docs/header_check.md`, `docs/errata/`. But the repository is private, so they are **not published** | **Not met** |
| 2.15 | Provenance tracked and documented | Yes. Every file, input and model is logged with its SHA-256 in the hash-chained `audit_log.jsonl`. See the provenance table in evaluation-plan §9 | **Met** |
| 2.16 | Checksums or other integrity checks | Yes. Per-file SHA-256 in each `score_day` entry, checked on resume and before evaluation. Chain verified with `src.audit.verify_chain` | **Met** |
| 2.17 | Dataset size | 700 day files: 300 train/val (441 MB) and 400 test (587 MB). Each holds 17,280 windows × 12 scores, and 288 blocks × (1280-d embedding + 9 bands). Source audio read: about 675 GB (train/val) plus 830 GB (test), streamed and never stored | **Met** (stated) |

## 3. Data documentation

| # | Item (paraphrased) | Answer | Score |
|---|---|---|---|
| 3.1 | Metadata follows a community standard (e.g. CF) | **No.** The derived files carry ad-hoc fields. (The source labels have ISO 19115 XML.) | **Not met** |
| 3.2 | Metadata is machine-readable | Partly. The `.npz` files embed `pipeline_version`, `git_commit`, file lists and band edges, and the audit log is JSON Lines. There is no schema or standard vocabulary | **Partly met** |
| 3.3 | Metadata includes spatial and temporal extent | Temporal: yes (day key, window and block start times). Spatial: no, only the site code | **Partly met** |
| 3.4 | Comprehensive data dictionary | Partly. `docs/labeling_rules.md` defines every day-table column, and `docs/model_notes.md` gives the 12 class names. **There is no single dictionary of the `.npz` arrays** | **Partly met** |
| 3.5 | Dictionary is standardized | No | **Not met** |
| 3.6 | Dictionary is machine-readable | No (Markdown) | **Not met** |
| 3.7 | Parameters follow a defined standard | Partly. Species codes follow the model's class names (`Mn` = *Megaptera novaeangliae*). Band edges are octaves in Hz. No formal standard | **Partly met** |
| 3.8 | Parameters crosswalked to an ontology or common vocabulary | No | **Not met** |
| 3.9 | Unique persistent identifier (DOI) | **None for the derived dataset.** Source: doi 10.25921/saca-sp25 | **Not met** |
| 3.10 | Contact for subject-matter experts | The project owner, privately. No public contact | **Partly met** |
| 3.11 | Mechanism for user feedback | None. The repository is private, so there are no public issues | **Not met** |
| 3.12 | Example code, notebooks or toolkits | The full pipeline and evaluator are in `src/`, with tests in `tests/`. They are private | **Partly met** |
| 3.13 | Licence: standardized and machine-readable | **Not confirmed.** The source's ISO XML says "otherRestrictions", with a required citation and no CC0 statement (`docs/inventory.md`). The derived dataset has no licence. The model features carry the model's Apache 2.0 licence and terms of use (research and conservation) | **Not met** |
| 3.14 | Already used in AI/ML work | Yes, in this project only: train/val nested CV and Stage A. Not published | **Partly met** |
| 3.15 | Recommended and non-recommended uses stated | Yes. **Research use only.** Not for operational, management, permitting or regulatory decisions (README; evaluation-plan §1) | **Met** |

Not scored, because they are not checklist rows, but documented:
- the label definition: `Presence` 0/1 from analyst screening, where **0 means "no confirmed detection", not
  proof of absence** (eval_plan §6);
- an errata record: `docs/errata/`, ERR-001, which affected a logged count only, not the features.

## 4. Data access

| # | Item (paraphrased) | Answer | Score |
|---|---|---|---|
| 4.1 | File formats | NumPy `.npz`, CSV, JSON, JSON Lines | **Met** (stated) |
| 4.2 | Machine-readable formats | Yes | **Met** |
| 4.3 | At least one open, non-proprietary format | Yes (CSV, JSON, and `.npz`, NumPy's documented open format) | **Met** |
| 4.4 | Tools or services for format conversion | None | **Not met** |
| 4.5 | Access requires authentication | The derived data is **not distributed at all**: it sits in git-ignored `data/` on one machine, and the repository is private. (The source bucket is public and anonymous.) | **Not met** |
| 4.6 | Direct download or ordering | No. (The source can be downloaded from the public GCS bucket and NCEI.) | **Not met** |
| 4.7 | API or web service | None | **Not met** |
| 4.8 | If an API: open standard protocol | No API | **N/A** |
| 4.9 | If an API: documentation | No API | **N/A** |
| 4.10 | Publicly available through cloud services | No. (The source is a Google Cloud public dataset.) | **Not met** |
| 4.11 | Restricted data: aggregated to reduce granularity | No personal or restricted data | **N/A** |
| 4.12 | Restricted data: anonymized | No personal data | **N/A** |
| 4.13 | Restricted data: secure access for authorized users | No restricted data | **N/A** |

## 5. Data preparation

| # | Item (paraphrased) | Answer | Score |
|---|---|---|---|
| 5.1 | Nulls or gaps filled | **No, by design.** Gaps between files count as time with no detections and are never bridged. Each is flagged (`>1 min gap`). Exact-zero samples are counted in `zero_fraction`, not filled | **Met** (handling documented) |
| 5.2 | Outliers identified | **Yes, tagged, not removed.** QA flags for zero fraction > 0.01, gaps, overlaps > 2 s, short days and non-finite values (evaluation-plan §5). Train/val: 17 zero-flag days, all in sb01_02. Stage A: 4 soft-flagged Test S days, no hard failures, no exclusions | **Met** |
| 5.3 | Gridded at constant time frequency | Yes: 5 s windows and 5-min blocks on a UTC-day grid. Not gridded in space | **Met** |
| 5.4 | Transformed from different original sampling | Yes: 48 kHz audio resampled to 24 kHz, framed into 5 s windows | **Met** (stated) |
| 5.5 | Original sampling also available | Yes, as the public source audio | **Met** |
| 5.6 | Labels for supervised learning | Yes: daily presence (0/1) from SanctSound `humpbackwhale_1d`, analyst-screened | **Met** |
| 5.7 | If labelled: community labeling standard | **None** (no STAC label extension, AIREO or similar) | **Not met** |

## Known bias (item 2.10, in detail)

All of the following come from train/val or audio-only analysis.

- **Recorder and site identity.** The embeddings identify the recorder deployment (18-way balanced accuracy
  **0.947**) and the site (AUROC 0.999).
  - The site present rates differ (train/val: sb01 0.53, sb02 0.73).
  - A classifier can therefore score well by recognising the site. The headline metric is within-site AUROC,
    and every result reports the site-prior baseline and a site-ID probe.
- **Season.** Train/val present rates by month range from 0.11 (July) to 1.0 (November). The month-prior
  baseline is reported with every result.
- **Meaning of label 0.** 0 means no confirmed detection by the original analysts, not proof of absence.
- **Recorder dropouts.** sb01_02 has 1.4-2.2% exact-zero samples on 17 train/val days.
  - Sensitivity analyses exclude them (eval_plan §7; sb01_02 plan).
  - No test deployment is sb01_02-equivalent: every test deployment's median zero fraction is 0.0 (Stage A
    drift report).
- **Pretraining overlap.** The Google model card lists SanctSound among its training data, with sites and
  dates not stated. Results are an audit of a pretrained model, not evidence of generalisation to unseen data.
- **Distribution shift at the new site.** The Stage A drift report flags `sb03_01`. Its embedding distance to
  the nearest train/val deployment is 1.008× the largest within train/val. The flag is reported, not acted on.
- **Uncalibrated levels.** Band levels are relative (dB re full scale). No recorder calibration is applied.
