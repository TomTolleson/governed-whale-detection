"""Leave-deployment-out CV on TRAIN/VAL ONLY: baselines and first classifiers (docs/evaluation-plan.md).

    python -m src.cv_eval --actor <name> [--out docs/analysis/cv_v1]

Folds: deployment k (01-09) held out at both sites (9 folds). Variants: Primary (all train/val) and S1
(sb01_02 removed from training and evaluation; docs/analysis/sb01_02-sensitivity-plan.md).

Methods (day scores, out-of-fold):
  always_present  constant score
  month_prior     training-fold present rate of the day's UTC month (overall rate if unseen)
  ambient_noise   L2 logistic regression on band levels (daily median and p90 of 9 bands); C by inner LODO CV
  zero_shot       pretrained Mn window scores -> eval plan day rule (3rd-highest in best 10-min span).
                  Secondary: max, top-10 mean. No training
  site_prior      training-fold present rate of the day's site (diagnostic)
  emb_day_lr      L2 logistic regression on the day's mean block embedding (fixed C, no tuning)
  emb_block_lr    L2 logistic regression on 5-min block embeddings with the day label on every block (weak
                  labels); day score = max / top-3 / top-12 mean / mean of block scores (fixed C, no tuning)

Metrics: headline (eval-freeze-v2) within-site AUROC, pair-weighted over sites with >= 5 days of each class,
with its own deployment-block bootstrap CI and paired differences (incl. vs site_prior); pooled OOF AUROC
(present positive) with a deployment-block bootstrap 95% CI (2000 resamples, seed
20261109); PR-AUC (absent positive); balanced accuracy where each fold's day threshold is chosen on the
pooled OOF scores of the other 8 folds (so it is never tuned on the evaluated days); per-fold and per-site AUROC; site-ID probe; paired
bootstrap differences against the best baseline. Test days are refused.
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.audit import log_event
from src.label_survey import ROOT
from src.pilot_review import primary_day_score

SEED = 20261109
SCORES = ROOT / "data" / "scores" / "v2"
N_BOOT = 2000
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0]
EMB_C = 0.01
AGGS = {"max": lambda s: s.max(), "top3": lambda s: np.sort(s)[-3:].mean(),
        "top12": lambda s: np.sort(s)[-12:].mean(), "mean": lambda s: s.mean()}


# ---------------------------------------------------------------- data

def load():
    s = pd.read_csv(ROOT / "data" / "sample_days.csv", dtype={"deployment": str})
    s = s[s["split"] == "trainval"].reset_index(drop=True)
    if set(s["split"]) != {"trainval"}:
        raise SystemExit("refusing: non-train/val days")
    s["dep"] = s["site"] + "_" + s["deployment"]
    s["month"] = pd.to_datetime(s["date"]).dt.month
    band, emb_day, blocks, block_day, zs = [], [], [], [], {k: [] for k in ["primary", "max", "top10"]}
    for i, r in enumerate(s.itertuples()):
        with np.load(SCORES / f"{r.site}_{r.deployment}_{r.date}.npz") as z:
            b = z["block_band_db"]
            band.append(np.r_[np.median(b, 0), np.percentile(b, 90, 0)])
            e = z["block_emb"].astype(np.float32)
            emb_day.append(e.mean(0))
            blocks.append(e)
            block_day.append(np.full(len(e), i))
            t, hb = z["window_start_s"], z["humpback"].astype(np.float64)
            zs["primary"].append(primary_day_score(t, hb))
            zs["max"].append(hb.max())
            zs["top10"].append(np.sort(hb)[-10:].mean())
    return (s, np.stack(band), np.stack(emb_day), np.concatenate(blocks), np.concatenate(block_day),
            {k: np.array(v) for k, v in zs.items()})


# ---------------------------------------------------------------- metrics

def best_threshold(y, score):
    """Threshold maximising balanced accuracy of (score >= thr)."""
    cand = np.unique(score)
    best, thr = -1, cand[0]
    for c in cand:
        p = score >= c
        ba = 0.5 * (p[y == 1].mean() + (~p[y == 0]).mean())
        if ba > best:
            best, thr = ba, c
    return thr


def bal_acc(y, pred):
    return 0.5 * (pred[y == 1].mean() + (~pred[y == 0]).mean())


def safe_auc(y, s):
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def boot_idx(groups, rng, y):
    """Deployment-block bootstrap: resample deployments with replacement; redraw single-class resamples."""
    u = np.unique(groups)
    pos = {g: np.flatnonzero(groups == g) for g in u}
    while True:
        idx = np.concatenate([pos[g] for g in rng.choice(u, len(u), replace=True)])
        if 0 < y[idx].sum() < len(idx):
            return idx


def boot_ci(y, scores: dict, groups, pairs=()):
    """Percentile 95% CIs for each score's AUROC and for paired differences (a - b)."""
    rng = np.random.default_rng(SEED)
    res = {k: [] for k in scores}
    diff = {f"{a} - {b}": [] for a, b in pairs}
    for _ in range(N_BOOT):
        i = boot_idx(groups, rng, y)
        aucs = {k: roc_auc_score(y[i], v[i]) for k, v in scores.items()}
        for k in scores:
            res[k].append(aucs[k])
        for a, b in pairs:
            diff[f"{a} - {b}"].append(aucs[a] - aucs[b])
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
    return {k: ci(v) for k, v in res.items()}, {k: ci(v) for k, v in diff.items()}


def within_site_auroc(y, s, site, min_n=5):
    """Pair-weighted within-site AUROC (evaluation-plan §3, eval-freeze-v2).

    sum_s P_s*N_s*AUROC_s / sum_s P_s*N_s over sites with >= min_n present and >= min_n absent days:
    the probability that a present day outscores an absent day from the same site (ties count 1/2).
    Returns None if no site qualifies.
    """
    num = den = 0.0
    for st in np.unique(site):
        m = site == st
        p, n = int(y[m].sum()), int(m.sum() - y[m].sum())
        if p >= min_n and n >= min_n:
            num += p * n * roc_auc_score(y[m], s[m])
            den += p * n
    return num / den if den else None


def boot_ci_ws(y, scores: dict, groups, site, pairs=()):
    """As boot_ci, for within-site AUROC. Own RNG stream (seed SEED), so the pooled CIs are unchanged.
    A resample in which no site qualifies is drawn again."""
    rng = np.random.default_rng(SEED)
    res = {k: [] for k in scores}
    diff = {f"{a} - {b}": [] for a, b in pairs}
    for _ in range(N_BOOT):
        while True:
            i = boot_idx(groups, rng, y)
            aucs = {k: within_site_auroc(y[i], v[i], site[i]) for k, v in scores.items()}
            if all(a is not None for a in aucs.values()):
                break
        for k in scores:
            res[k].append(aucs[k])
        for a, b in pairs:
            diff[f"{a} - {b}"].append(aucs[a] - aucs[b])
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
    return {k: ci(v) for k, v in res.items()}, {k: ci(v) for k, v in diff.items()}


# ---------------------------------------------------------------- models

def lr(C):
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000))


def pick_C(X, y, fold_ids):
    """Inner leave-deployment-out CV over the training folds; C maximising pooled inner OOF AUROC."""
    best, bestC = -1, C_GRID[0]
    for C in C_GRID:
        oof = np.zeros(len(y))
        for f in np.unique(fold_ids):
            tr, te = fold_ids != f, fold_ids == f
            oof[te] = lr(C).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        a = roc_auc_score(y, oof)
        if a > best:
            best, bestC = a, C
    return bestC


def run_variant(s, band, emb_day, blocks, block_day, zs, keep):
    """Out-of-fold day scores for every method on days where keep is True."""
    days = np.flatnonzero(keep)
    y_all = s["label"].to_numpy()
    fold = s["deployment"].to_numpy()
    out = {m: np.full(len(s), np.nan) for m in
           ["always_present", "month_prior", "ambient_noise", "site_prior", "emb_day_lr"]
           + [f"zero_shot_{k}" for k in zs] + [f"emb_block_lr_{a}" for a in AGGS]}
    info = {"ambient_C": {}}
    for f in sorted(np.unique(fold[days])):
        te = days[fold[days] == f]
        tr = days[fold[days] != f]
        ytr = y_all[tr]
        sc_te = {}
        sc_te["always_present"] = np.ones(len(te))
        mrate = pd.Series(ytr).groupby(s["month"].to_numpy()[tr]).mean()
        mp = lambda idx: s["month"].iloc[idx].map(mrate).fillna(ytr.mean()).to_numpy()
        sc_te["month_prior"] = mp(te)
        srate = pd.Series(ytr).groupby(s["site"].to_numpy()[tr]).mean()
        sp = lambda idx: s["site"].iloc[idx].map(srate).fillna(ytr.mean()).to_numpy()
        sc_te["site_prior"] = sp(te)
        C = pick_C(band[tr], ytr, fold[tr])
        info["ambient_C"][f] = C
        m = lr(C).fit(band[tr], ytr)
        sc_te["ambient_noise"] = m.predict_proba(band[te])[:, 1]
        m = lr(EMB_C).fit(emb_day[tr], ytr)
        sc_te["emb_day_lr"] = m.predict_proba(emb_day[te])[:, 1]
        for k, v in zs.items():
            sc_te[f"zero_shot_{k}"] = v[te]
        btr, bte = np.isin(block_day, tr), np.isin(block_day, te)
        m = lr(EMB_C).fit(blocks[btr], y_all[block_day[btr]])
        pb = np.zeros(len(blocks))
        pb[bte] = m.predict_proba(blocks[bte])[:, 1]
        for a, fn in AGGS.items():
            sc_te[f"emb_block_lr_{a}"] = np.array([fn(pb[block_day == d]) for d in te])
        for k in out:
            out[k][te] = sc_te[k]
    return out, info


def loo_fold_threshold_pred(y, v, fold):
    """Each fold's threshold is chosen on the pooled OOF scores of the other folds, then applied to it."""
    pred = np.zeros(len(y), bool)
    for f in np.unique(fold):
        o = fold != f
        pred[fold == f] = v[fold == f] >= best_threshold(y[o], v[o])
    return pred


def summarise(s, out, keep, diag_pairs, ws_pairs=()):
    days = np.flatnonzero(keep)
    y = s["label"].to_numpy()[days]
    groups = s["dep"].to_numpy()[days]
    fold = s["deployment"].to_numpy()[days]
    site = s["site"].to_numpy()[days]
    scores = {k: v[days] for k, v in out.items()}
    ci, dci = boot_ci(y, scores, groups, diag_pairs)
    ws_ci, ws_dci = boot_ci_ws(y, scores, groups, site, ws_pairs)
    rnd = lambda a: round(a, 3) if a is not None else None
    res = {"days": int(len(days)), "present": int(y.sum()), "absent": int((1 - y).sum()),
           "deployments": int(len(np.unique(groups))), "absent_prevalence": round(float(1 - y.mean()), 3),
           "methods": {}, "paired_differences": dci, "paired_differences_ws": ws_dci}
    site_label_auc = safe_auc((site == "sb02").astype(int), y)  # what the labels alone give
    for k, v in scores.items():
        r = {"auroc_ws": rnd(within_site_auroc(y, v, site)), "auroc_ws_ci95": ws_ci[k],
             "per_fold_ws": {f: rnd(within_site_auroc(y[fold == f], v[fold == f], site[fold == f]))
                             for f in sorted(np.unique(fold))},
             "auroc": round(safe_auc(y, v), 3), "auroc_ci95": ci[k],
             "pr_auc_absent_pos": round(float(average_precision_score(1 - y, -v)), 3),
             "bal_acc_loo_threshold": round(float(bal_acc(y, loo_fold_threshold_pred(y, v, fold))), 3),
             "pooled_oof_threshold": float(best_threshold(y, v)),
             "per_fold": {f: (round(a, 3) if (a := safe_auc(y[fold == f], v[fold == f])) is not None else None)
                          for f in sorted(np.unique(fold))},
             "per_site": {st: round(safe_auc(y[site == st], v[site == st]), 3) for st in sorted(np.unique(site))},
             "site_id_probe_auroc": round(abs(safe_auc((site == "sb02").astype(int), v) - 0.5) + 0.5, 3)}
        res["methods"][k] = r
    res["site_id_from_labels_auroc"] = round(abs(site_label_auc - 0.5) + 0.5, 3)
    return res


def main(actor, out_dir):
    t0 = time.time()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    s, band, emb_day, blocks, block_day, zs = load()
    baselines = ["month_prior", "ambient_noise", "zero_shot_primary"]
    models = ["emb_day_lr"] + [f"emb_block_lr_{a}" for a in AGGS]
    pairs = [(m, b) for m in models for b in baselines]
    ws_pairs = pairs + [(m, "site_prior") for m in models + ["zero_shot_primary"]]
    results = {"git_commit": commit, "seed": SEED, "n_boot": N_BOOT, "emb_C": EMB_C, "C_grid": C_GRID,
               "scope": "train/val only; out-of-fold, leave-deployment-out (9 folds, both sites)"}
    variants = {"primary": np.ones(len(s), bool), "S1_excl_sb01_02": (s["dep"] != "sb01_02").to_numpy()}
    oof = {}
    for name, keep in variants.items():
        out, info = run_variant(s, band, emb_day, blocks, block_day, zs, keep)
        results[name] = summarise(s, out, keep, pairs, ws_pairs)
        results[name]["ambient_C_by_fold"] = info["ambient_C"]
        oof[name] = out
    # Primary restricted to non-sb01_02 days: separates the training effect from the evaluation-set change
    keep = variants["S1_excl_sb01_02"]
    results["primary_on_S1_days"] = {k: round(safe_auc(s["label"].to_numpy()[keep], v[keep]), 3)
                                     for k, v in oof["primary"].items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / "results.json"
    js.write_text(json.dumps(results, indent=1, default=str))
    days_csv = out_dir / "oof_scores.csv"
    pd.concat([s[["site", "deployment", "date", "label"]]] +
              [pd.DataFrame({f"{v}:{k}": a for k, a in o.items()}) for v, o in oof.items()], axis=1
              ).to_csv(days_csv, index=False)
    log_event(actor, "cv_eval", {"git_commit": commit, "out": str(js.relative_to(ROOT)),
                                 "sha256": hashlib.sha256(js.read_bytes()).hexdigest(),
                                 "oof_csv_sha256": hashlib.sha256(days_csv.read_bytes()).hexdigest(),
                                 "scope": results["scope"], "runtime_s": round(time.time() - t0, 1),
                                 "auroc_primary": {k: v["auroc"] for k, v in results["primary"]["methods"].items()},
                                 "auroc_S1": {k: v["auroc"] for k, v in results["S1_excl_sb01_02"]["methods"].items()}})
    print(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--out", default=str(ROOT / "docs" / "analysis" / "cv_v1"))
    a = p.parse_args()
    main(a.actor, Path(a.out).resolve())
