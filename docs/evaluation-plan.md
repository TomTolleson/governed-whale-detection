# Evaluation plan and freeze (gate for test days)

| | |
|---|---|
| Status | **FROZEN** at git tag **`eval-freeze-v2`** (supersedes `eval-freeze-v1`, `47a0b6f`). Each tag's hash is recorded in `audit_log.jsonl` (`eval_freeze` entries) |
| Written | 2026-11-11 by claude-code, at the owner's instruction |
| v2 change | **[v2 2026-11-11]** Headline metric changed from pooled AUROC to within-site AUROC (§3, §4). Owner decisions D1-D5 in `docs/proposals/eval-freeze-v2-draft.md`, approved 2026-11-11 (`owner_decision` entry). Decided after train/val CV v1 results were seen and before any test day was processed |
| Detailed rules | `docs/eval_plan.md` (frozen 2026-11-09, amendments 1-3), `docs/analysis/sb01_02-sensitivity-plan.md`, `docs/errata/` |
| Test days | **Not processed.** They are processed only after the owner explicitly says so, through the test gate (§8) |

This document draws together everything that must be fixed before test scoring. Where it repeats
`docs/eval_plan.md`, that file's wording governs. New items, which add to it and change nothing in it,
are marked **[new 2026-11-11]**. Items marked *(claude-code)* are proposals that **need owner
confirmation**. If the owner changes any of them before test scoring begins, the change is committed and
tagged `eval-freeze-v2` (then v3 and so on), and the new tag's hash is logged. Test scoring runs at the
latest freeze tag. After test scoring begins, every change is a deviation (§8).

## 1. Question and intended use

- The question: day-level humpback whale presence or absence at Stellwagen Bank, from SanctSound passive
  acoustic recordings, using a pretrained embedding model (Google multispecies whale, v2) with a small classifier.
- **Research use only, non-commercial.** Outputs must not be used for operational, management,
  permitting or regulatory decisions (README).
- Labels are analyst-screened daily presence. 0 means "no confirmed detection", not proof of absence.

## 2. Split design (by time and by location; no leakage)

| Split | Sites and deployments | Sampled days | Tests |
|---|---|---|---|
| Train/val | sb01 + sb02, deployments 01-09 | 300 (189 present / 111 absent) | development only |
| Test T | sb01 + sb02, deployments 10-12 | 150 (111 / 39) | **later in time**, same sites |
| Test S | sb03, deployments 01-12 | 250 (194 / 56) | **new location**, same calendar period |
| Test S 10-12 slice | sb03, deployments 10-12 | subset of S | new location *and* later in time |

Day lists: `data/sample_days.csv`, seed 20261109, SHA-256 `3c47e9bc…201947d`.

**Leakage controls:**
- **Cross-validation:** model selection uses leave-deployment-out CV within train/val. Fold k holds out
  deployment k at **both** sites, so no fold trains on a calendar period that it evaluates.
- **No test choices:** test days are used for no choice at all. That covers model, features, thresholds,
  day rule, QA rules and debugging.
- **Test audio:** none has been processed. When it is, it goes to `data/scores/v2_test/`, which is kept
  apart from `data/scores/v2/`.
- **Test labels:** they were read only to build the day table and to stratify the sample (2026-11-09).
  They have never been compared with any score, and they are not read again until the final evaluation run.
- **Known coupling, not removable:** Test S covers the same dates as train/val, so shared weather, vessel
  traffic and whale movements link the sites. Test S tests a new location, not independence in time.
- **Site and recorder shortcut** (from `docs/analysis/sb01_02-sensitivity-plan.md`): embeddings identify the
  site with AUROC 0.999, and the site present rates differ (sb01 0.53, sb02 0.73). Test T inherits this
  shortcut, and Test S cannot. The diagnostics in §5 are reported every time.
- **Pretraining overlap** (eval plan §6, amendment 1): SanctSound may be in the model's training data. Results
  are an audit of a pretrained model, not evidence of generalisation to unseen data.

## 3. Metrics and thresholds

All metrics are **day-level**: one score and one label per site-day (eval plan §3-§4).

- **[v2 2026-11-11] Primary (headline): within-site AUROC (AUROC_ws)**, with present as the positive class
  (eval_plan §3, amendment 3). For sites *s* with *P_s* present days, *N_s* absent days and AUROC *A_s*:
  AUROC_ws = Σ_s P_s·N_s·A_s / Σ_s P_s·N_s, which is the probability that a present day outscores an absent
  day **from the same site** (ties ½).
  - A site is included only if it has ≥ 5 present and ≥ 5 absent days; if none qualifies, the metric is "n/a".
  - Train/val CV and Test T: sb01 + sb02. Test S and its 10-12 slice: sb03 only, so AUROC_ws equals AUROC.
  - The 95% CI comes from the deployment-block bootstrap (§6). A resample in which no included site has both
    classes is drawn again.
- **Secondary:**
  - **[v2 2026-11-11] pooled AUROC** over all sites (the v1 primary), always reported next to AUROC_ws;
  - PR-AUC with **absent** as the positive class, reported with the absent prevalence;
  - balanced accuracy at a fixed day threshold.
- **Day score:** the primary rule is ≥ 3 window detections within a 10-minute span. The continuous score is
  the 3rd-highest window score in the best 10-minute span. The secondary rules are the max window score
  and the mean of the top 10 windows.
- **Thresholds:**
  - the window threshold and the day threshold are chosen on **pooled out-of-fold train/val predictions
    only**, by maximising balanced accuracy;
  - they are written to the audit log with the model commit **before** test scoring, and applied to
    the tests unchanged;
  - **[v2 2026-11-11]** they stay pooled across sites (decision D4). Per-site thresholds are not used, as
    they cannot be applied to Test S.
- **Breakdowns:** by site, by season (DJF/MAM/JJA/SON, UTC month) and by deployment. A cell is reported
  only when both classes have ≥ 5 days; otherwise it shows "n/a (n present / n absent)".
- **[new 2026-11-11] The final model** is fixed on train/val, with its architecture, hyperparameters,
  features and thresholds. Its commit hash and artefact SHA-256 are logged **before any test label is read**.
  **[v2 2026-11-11]** Inner-CV selection of the final model uses AUROC_ws as its criterion (decision D5).

## 4. Baselines and how an improvement is judged

Every baseline is scored on the same days with the same metrics:

1. **Always-present.** AUROC 0.5 by construction. It anchors balanced accuracy.
2. **Month prior:** the train/val present rate of each UTC month.
3. **Ambient-noise baseline:** logistic regression on band levels, with edges fixed in eval plan §5. The
   features are each day's median and 90th percentile over its 5-minute blocks.
4. **[new 2026-11-11] Zero-shot model:** the pretrained `Mn` score through the day rules above, with no
   training. This shows what the classifier adds.
5. **[new 2026-11-11] Site prior** (a diagnostic): the training present rate of the day's site. For Test S,
   which is a new site, it is the overall rate.
   **[v2 2026-11-11]** It is the headline's reference point: the score that knows only the site. On every
   test split it is constant within each site, so its AUROC_ws is exactly 0.5. In train/val CV it is the
   training-fold rate, which differs by held-out fold, so its AUROC_ws can differ from 0.5 (a leave-out
   artefact). There it is scored like any other method.

**[v2 2026-11-11] Improvement claim** (decision D1, option A). The model **improves** only if **both** hold on
the split:
1. **A signal beyond site.** On test splits, the 95% CI of its AUROC_ws excludes 0.5. In train/val CV, the
   paired 95% CI of AUROC_ws(model) − AUROC_ws(site prior) excludes 0.
2. **It beats the best baseline within site.** The paired 95% CI of AUROC_ws(model) − AUROC_ws(baseline)
   excludes 0, against the **best** non-diagnostic baseline (2-4) **by AUROC_ws** on that split.

Paired CIs come from a deployment-block bootstrap that resamples the same deployments for both scores.
The v1 rule (paired pooled-AUROC difference vs the best non-diagnostic baseline) is still computed and
reported as a secondary result. When the pooled and within-site conclusions differ, both are stated, and
the within-site one is the headline. If the model does not beat the zero-shot model or the ambient-noise
baseline, that is reported as the result.

## 5. QA flags

The flags come from the pipeline, `src/pilot.py` v2. Every flag is listed per split in every report.

| Flag | Rule | Handling |
|---|---|---|
| Zero fraction | `zero_fraction > 0.01` (day) | Kept in primary results. Day-level sensitivity: flagged days excluded (eval plan §7). Deployment-level rule (sb01_02 plan §3c): a test deployment with median zero_fraction > 0.01 is *equivalent to sb01_02*, is identified from QA before any test label is read, and is reported both ways |
| Gaps | windows only inside continuous stretches; `>1 min gap` flag | Kept. The day score uses real window times, so gaps count as time with no detections. Real gaps are not bridged |
| Overlaps | every overlap is cut at the next file's start; flagged when > 2 s | Kept. Trimming is routine |
| Short days | eligibility is `audio_hours ≥ 20` from file names (day table); the pipeline flags `< 20 h` of windows | The day table rule decides eligibility. A day with < 20 h of windows that is still eligible is kept and listed. In train/val that is `sb01_03_2019-04-10`, with 19.999 h |
| Non-finite scores or band levels, decode errors, size mismatch | pipeline flags | *(claude-code)* Re-run the day once. If the flag remains, exclude the day and list it with the reason. It is never replaced by another day |
| sb01_02 (train/val) | deployment-level recorder property | Primary results plus sensitivity S1 (excluded) plus a per-fold table, with materiality rules in the sb01_02 plan §3b |

**Shortcut diagnostics, reported with every result:** per-site AUROC, the site-prior baseline, and a site-ID
probe on the model's day scores (sb01_02 plan §3a.4). **[v2 2026-11-11]** AUROC_ws and pooled AUROC are
shown next to them.

## 6. Uncertainty

- **95% confidence intervals** come from a **deployment-block bootstrap**: deployments are resampled with
  replacement and keep all of their days. There are 2,000 resamples, using the percentile interval. A
  resample with only one class is drawn again.
- Differences between a model and a baseline, or between Primary and S1, use **paired** bootstrap CIs.
- Breakdowns get CIs only when they contain ≥ 3 deployments. Otherwise they show a point estimate and n.
- The number of days, the present count, the absent count and the deployment count are always reported.
  Test T's SON cell has very few absent days, so most of its season breakdowns will be n/a.
- **[new 2026-11-11] Seeds:** the bootstrap uses seed 20261109, and so does any model training seed. When
  training is not deterministic, results are reported as the mean ± SD over 5 seeds.

## 7. Monitoring and drift plan

Research use only, so "monitoring" here means checks that run every time new audio is scored, plus a
pre-evaluation drift report. None of them use labels.

- **Per scoring run:**
  - `score_day` audit entries: hours, windows, flags, zero fraction and stretches;
  - `run_report.json`, with every day's SHA-256 verified by `completed_days`.
- **Pre-evaluation drift report, for each test split, before any test label is read:**
  - the median zero fraction per deployment, with deployment-level flags (§5);
  - band-level medians and 90th percentiles per deployment, against the train/val range. *(claude-code)*
    Flag a deployment whose median level in any band lies **more than 6 dB** outside the train/val
    deployment range;
  - zero-shot `Mn` score distribution per deployment (median, p90, share of windows ≥ 0.5) against train/val.
    This is descriptive only;
  - embedding shift: the distance of each deployment's mean embedding to the nearest train/val deployment
    mean, against the spread among train/val deployments, plus the deployment-ID probe's confidence.
  - The report is logged with its hash. Flags in it are **reported, not acted on**. They do not exclude
    data, which keeps the test set from being changed after the fact.
- **After evaluation:** per-deployment AUROC and calibration where n allows, set against the drift report,
  so any loss of performance can be traced to the drift that explains it.
- **Re-runs:** a new data release, model version or pipeline version gets a new pipeline or model version,
  a new output directory and a fresh drift report. Results are never overwritten.

## 8. Freeze rule and test gate

- **What is frozen at `eval-freeze-v1`:**
  - the pipeline code (`src/pilot.py`, pipeline v2);
  - the QA rules (§5);
  - this plan, `docs/eval_plan.md` and `docs/analysis/sb01_02-sensitivity-plan.md`.
- **[v2 2026-11-11] `eval-freeze-v2`** freezes the same items, with the headline-metric change (§3, §4;
  eval_plan amendment 3; sb01_02 plan amendment of §3a.4 and §3b). `src/pilot.py` and the QA rules are
  unchanged from v1. Test scoring runs from a checkout of the **latest** freeze tag.
- Model development on **train/val** continues after the tag, and the final model is fixed and logged
  before test labels are read (§3).
- **Once test scoring begins,** the pipeline code, QA rules and evaluation plan are **frozen**. Any change
  after that is a **deviation**:
  - it is logged in `audit_log.jsonl` (`deviation` entry) with the reason, the date and the commit;
  - it is noted in the results;
  - results are **reported both ways**, under the frozen rules and under the change.
- **Test gate in code** (`src/pilot.py`, `check_test_gate`). A test split runs only if all of these hold:
  - HEAD carries an `eval-freeze-*` tag;
  - the tree is clean, with no `--allow-dirty`;
  - `--owner-approval` quotes the owner's release, which is logged verbatim as `test_gate_passed`;
  - output goes to `data/scores/v2_test/`.
- Test days are scored by the code at the tag: `pipeline_version` 2, with the tag's commit stamped in each file.
  Later train/val modelling commits move HEAD past the tag, so test scoring runs from a checkout of the tag,
  for example `git worktree add ../noaa-whale-freeze eval-freeze-v1`, with `data/` linked in. The gate then
  sees the tag on HEAD.
- The train/val outputs in `data/scores/v2/` are stamped `d2f4fe5`. The code that produced them is the same
  code as at the tag; the only later changes are the stretch-count fix (ERR-001, shown to leave every
  stored array identical), the test gate and docs. So train/val and test features come from the same
  scoring path.

## 9. Provenance (recorded for every result)

| Item | Value |
|---|---|
| Frozen evaluation commit | latest tag `eval-freeze-v2` (v1: `47a0b6f`); hashes in the `eval_freeze` audit entries |
| Pipeline | `src/pilot.py`, `pipeline_version` "2" |
| Train/val features | `data/scores/v2/*.npz`, 300 days, commit `d2f4fe5`, per-file SHA-256 in `score_day` entries |
| Model | Kaggle `google/multispecies-whale` TF2 v2. `saved_model.pb` `85e47539…8778211c`; `variables.data` `ff4063f1…7836051a` (all files: `model_download` entry) |
| Audio | `gs://noaa-passive-bioacoustic/sanctsound/` (doi 10.25921/saca-sp25). Listing `data/audio_listing.json` `8f2cacd2…e909546cd4`. Audio is never saved to disk |
| Day table | `data/day_table.csv` `82475a1b…1f1dae04` (with zero_fraction for train/val, 2026-11-11) |
| Sample | `data/sample_days.csv` `3c47e9bc…201947d`, seed 20261109 |
| Source documents | `docs/data_sources.md` (SanctSound README, verified against the bucket object) |
| Audit log | `audit_log.jsonl`, append-only and hash-chained (`src.audit.verify_chain`) |

Every result file records the commit, pipeline version, model commit and artefact hashes, and the SHA-256
of its input day list.

## 10. NAO 216-128 ("Artificial Intelligence in NOAA") mapping

**Source:** NAO 216-128, issued and effective 2026-04-16, Office of the Chief Information Officer.
https://www.noaa.gov/nao-216-128-artificial-intelligence-in-noaa. It was read 2026-11-11 from the HTML
page. The PDF could not be text-extracted. The **NOAA AI Handbook** and the **NAIEC AI Risk Management
Framework** that the order refers to were **not available**, so anything that depends on them is unknown.

**Applicability:** §2.1 applies the order to "all NOAA AI development and use, including … scientific
research". This project is **independent, non-commercial research that uses NOAA data**. It is not run by a
NOAA office or program, so the order does not formally bind it. The mapping below is a **voluntary
alignment**, made so that the work could be reviewed against NOAA's AI policy.

**Risk tier (self-assessed):** the order defines **no risk tiers**. §4.6 refers to "high risk use cases"
without defining them, and leaves the definition to the NAIEC framework. On that basis the self-assessed
tier is **not high-risk / research-only**: no operational use, no decisions about people, and no
management, permitting or regulatory use (§1). *This needs confirmation against the Handbook or NAIEC
framework once available.* If the outputs were ever proposed for operational or management use, the tier
would have to be reassessed first.

| NAO 216-128 provision (as published) | How this project addresses it |
|---|---|
| §2.1-2.2: covers AI in scientific research and scientific software | Treated as in scope by analogy (voluntary) |
| §4.4: scientific integrity; transparency, fairness, accountability, trustworthiness | Frozen plans committed before results; deviations logged and reported both ways (§8); public documentation of limits (§2, eval plan §6); hash-chained audit log of every action; results always reported with CIs and baselines |
| §4.5: AI-ready data with sufficient quality, documentation and access methods | `docs/inventory.md`, `docs/data_sources.md`, labeling rules, day table, QA flags (§5), stated limits of the labels |
| §4.6: risk management, operational integrity, safety, security and **data provenance** of systems and training data | Provenance table (§9): commit, pipeline version, model and data hashes, seeds. Pretraining-data overlap disclosed (eval plan amendment 1). Self-assessed tier above |
| §4.7: "continuous monitoring and auditing to assess performance and accuracy" | §7 monitoring and drift plan; per-run QA entries; pre-evaluation drift report; per-deployment post-evaluation analysis; errata process (`docs/errata/`) |
| §5.3.2: track and report on active AI projects | The audit log and the committed plans make a full project record. *Not registered with NCAI; no registration route is published* |
| §5.3.6: guidelines for assessing performance, accuracy, compliance and reporting for monitoring and auditing | This plan; NCAI guidelines not yet published, so alignment is unknown |
| Human oversight, use-case inventory, minimum practices | **Not stated in the published order.** They may be in the Handbook or the NAIEC framework, which were not available. The owner reviews and approves every step that leads to a result (owner decisions logged) |
