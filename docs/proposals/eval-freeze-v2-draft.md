# DRAFT: eval-freeze-v2, within-site AUROC as the headline metric

| | |
|---|---|
| Status | **D1-D5 approved by the owner 2026-11-11** ("Approve as proposed"; `owner_decision` entry). Applied to the plan files (§6 steps 1-3). In force once tagged `eval-freeze-v2`; until then `eval-freeze-v1` (`47a0b6f`) governs |
| Drafted | 2026-11-11 by claude-code, at the owner's request |
| Needs | Owner decisions D1-D5 (§5), then the owner's explicit go-ahead to apply (§6) |
| Test days | Not processed and not read. This change is allowed before test scoring (evaluation-plan §8): it is committed and tagged `eval-freeze-v2`, and is **not** a deviation |

## 1. What changes, in one paragraph

The headline metric changes from **pooled AUROC** to **within-site AUROC**: how well the model ranks a
present day above an absent day **from the same site**. The site prior becomes the headline's named
reference point: it is the score that knows only the site. Pooled AUROC is still reported every time, as a
secondary metric. Nothing changes in the pipeline, QA rules, splits, sampling, day rules, thresholds,
bootstrap or the sb01_02 variants. No data is re-scored.

## 2. Why

- Embeddings identify the deployment (18-way balanced accuracy **0.947**) and the site (sb01 vs sb02
  AUROC **0.999**, with calendar dates held fixed) (`docs/analysis/sb01_02-sensitivity-plan.md` §2b).
- The two sites have different present rates (sb01 0.53, sb02 0.73). Pooled AUROC therefore rewards a model
  that scores sb02 days higher without hearing any whale. **Test T** inherits this shortcut, and **Test S**
  (one site) cannot.
- Within-site AUROC compares only days from the same site, so a site offset in the scores cannot raise it.
  The headline then measures the humpback signal, which is the intended use (evaluation-plan §1).

## 3. Disclosure: what had been seen when this was drafted

- **Train/val CV v1 results had been seen** (`docs/analysis/cv_v1/README.md`, commit `97aadbd`), including
  each method's pooled AUROC and its sb01-only and sb02-only AUROC.
- **The within-site AUROC defined in §4.1 has not been computed** for any method, on purpose, so that the
  owner decides without its values. It is computed after the v2 tag (§6, step 6).
- **No test day** has been processed, scored or compared with a label.
- This text goes, word for word, into the `eval_freeze` v2 audit entry and into the amendment in
  `docs/eval_plan.md`.

## 4. Proposed definitions

### 4.1 Within-site AUROC (headline)

For each site *s* with *P_s* present days, *N_s* absent days and per-site AUROC *A_s*:

> **AUROC_ws = Σ_s (P_s · N_s · A_s) / Σ_s (P_s · N_s)**

This is the probability that a randomly chosen present day scores higher than a randomly chosen absent day
**at the same site**, with ties counted as ½. Every same-site present/absent pair has the same weight.
*(claude-code, D2)*

- A site is included only if it has **≥ 5 present and ≥ 5 absent days** in the evaluated set. This is the
  same rule as for breakdowns (eval_plan §3). If no site qualifies, the metric is "n/a".
- **Per split:**
  - Train/val CV: sb01 and sb02, computed on pooled out-of-fold scores.
  - Test T: sb01 and sb02.
  - Test S and its 10-12 slice: one site (sb03), so AUROC_ws is the same as the ordinary AUROC on sb03.
- **95% CI:** the same deployment-block bootstrap (eval_plan §3, evaluation-plan §6), with AUROC_ws
  recomputed on each resample. A resample in which no included site has both classes is drawn again, the same
  way a single-class resample is now. Deployments belong to one site, so resampling deployments keeps the
  site structure.

### 4.2 Site-prior reference point (what "vs the site prior" means)

The site prior gives every day at a site the same score, the training present rate of that site.
- **On every test split, its within-site AUROC is exactly 0.5 by construction.** So "the model beats the
  site prior within site" is the same as "**the 95% CI of AUROC_ws excludes 0.5**".
- **In train/val CV it is not exactly 0.5.** The out-of-fold site prior is the *training-fold* rate, which
  is different for each held-out fold (9 different values per site in `oof_scores.csv`). A held-out
  deployment with a high present rate lowers its own training rate, so this creates a small leave-out
  artefact that pushes the score below 0.5. That is why its pooled CV AUROC is 0.455. In CV it is compared
  as a scored baseline, with a paired CI, like any other method.

### 4.3 Improvement claim (replaces evaluation-plan §4, "Improvement claim")

*(claude-code, D1: option A is proposed.)* A model **improves** only if **both** of these hold on the split:
1. **It shows a signal beyond site:** the 95% CI of its AUROC_ws excludes 0.5 on test splits. In CV, the
   paired CI of AUROC_ws(model) − AUROC_ws(site prior) excludes 0.
2. **It beats the best real baseline within site:** the paired 95% CI of AUROC_ws(model) − AUROC_ws(baseline)
   excludes 0 for the **best non-diagnostic baseline (2-4) by AUROC_ws** on that split. The baselines are the
   month prior, ambient-noise and zero-shot, each scored within site in the same way.

Pooled AUROC and its paired comparisons are still reported in full, as **secondary** results. When the
pooled and within-site conclusions differ, both are stated and the within-site one is the headline.

### 4.4 Other items affected

| Item | Proposed rule |
|---|---|
| Thresholds (window, day) | **Unchanged.** Pooled out-of-fold train/val, maximising balanced accuracy, logged before test scoring *(D4)* |
| Balanced accuracy, PR-AUC (absent+) | Unchanged, pooled. Per-site values are reported in the breakdown, as now |
| sb01_02 materiality (sb01_02 plan §3b) | Applied to **AUROC_ws** as well as pooled AUROC. "Material" if either metric meets the existing rule (|Δ| ≥ 0.03, or outside the Primary CI) *(D3)* |
| Test-deployment rule (sb01_02 plan §3c) | Unchanged |
| Shortcut diagnostics | Unchanged and still reported every time: per-site AUROC, site prior, site-ID probe. AUROC_ws is added next to them |
| Model selection on train/val | Inner-CV selection of the final model uses **AUROC_ws** as its criterion *(D5)* |

## 5. Decisions for the owner

| # | Decision | Proposed | Alternative |
|---|---|---|---|
| D1 | What the headline is compared with | **A:** both conditions in §4.3: beyond site (vs the site prior or 0.5) **and** vs the best real baseline within site | **B:** vs the site prior only. On tests that is a test against 0.5, which is a weak bar, and it drops the month-prior and zero-shot comparison from the headline |
| D2 | How per-site AUROCs are combined | Pair-weighted (§4.1), with one number and one CI | Unweighted mean of sb01 and sb02. Or no single number: report sb01 and sb02 separately as co-headlines |
| D3 | Materiality for sb01_02 | Material if pooled **or** within-site meets the rule | Within-site only |
| D4 | Thresholds | Keep pooled | Per-site thresholds. Not proposed: they cannot be applied to Test S (a new site) |
| D5 | Selection criterion for the final model | AUROC_ws | Pooled AUROC (selection may then favour site-using models) |

## 6. How it would be applied (only after the owner's go-ahead)

1. Edit `docs/evaluation-plan.md` §3 (primary metric), §4 (site-prior item 5, improvement claim), §5
   (diagnostics line), §8 (list of frozen items: add this amendment) and the header (freeze tag).
2. Add **Amendment 3** to `docs/eval_plan.md` §3, with the date, owner instruction, reason (§2) and
   disclosure (§3). Under evaluation-plan's own rule, eval_plan.md's wording governs where the two repeat, so
   the amendment has to be made there.
3. Edit `docs/analysis/sb01_02-sensitivity-plan.md` §3a.4 and §3b, marked as an amendment dated 2026-11-11.
4. Append the `owner_decision` audit entries (D1-D5, verbatim), commit, tag **`eval-freeze-v2`**, and append
   the `eval_freeze` entry with the new tag hash. `src/pilot.py` is not changed. Test scoring then runs from a
   checkout of `eval-freeze-v2` (evaluation-plan §8).
5. Add `within_site_auroc` (with bootstrap and paired CIs) to `src/cv_eval.py`, with a unit test. This is
   train/val development code, not a frozen item.
6. Re-run CV on train/val only, as **cv_v1.1**: the same models and the same outputs, plus AUROC_ws. Write it
   to a new directory, leaving `docs/analysis/cv_v1/` as it is.

## 7. Correction to a claim in the session brief

The 0.947 figure is the **18-way deployment-ID balanced accuracy**. Site ID (sb01 vs sb02) is AUROC
**0.999**. Write-ups should quote each one for the task it measures.
