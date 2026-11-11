"""Deployment / recorder confound check on train/val v2 features. LABELS ARE NOT MODEL INPUTS HERE.

    python -m src.deployment_check --actor <name> [--out docs/analysis/deployment_check.json]

Question: can deployment (recorder) identity be predicted from the features alone? If it can, a
classifier could learn the recorder rather than the humpback signal, especially where the label rate
differs between deployments. Labels are used only to describe class balance per deployment and to
measure how much label information deployment identity alone carries (deployment-prior AUROC).

Features per day (data/scores/v2): the mean 1280-d block embedding, plus the daily median and 90th
percentile of each band level (18 values). The zero fraction is NOT a feature. Every classifier is a
fixed L2 logistic regression (C=1, standardised features) in 5-fold stratified CV over days
(seed 20261109). No tuning, and nothing here is reused for modelling.
"""

import argparse
import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.audit import log_event
from src.label_survey import ROOT

SEED = 20261109
SCORES = ROOT / "data" / "scores" / "v2"


def load_days():
    s = pd.read_csv(ROOT / "data" / "sample_days.csv", dtype={"deployment": str})
    s = s[s["split"] == "trainval"].reset_index(drop=True)
    if set(s["split"]) != {"trainval"}:
        raise SystemExit("refusing: non-train/val days")
    emb, band = [], []
    for r in s.itertuples():
        with np.load(SCORES / f"{r.site}_{r.deployment}_{r.date}.npz") as z:
            emb.append(z["block_emb"].astype(np.float32).mean(0))
            b = z["block_band_db"]
            band.append(np.r_[np.median(b, 0), np.percentile(b, 90, 0)])
    s["dep"] = s["site"] + "_" + s["deployment"]
    return s, np.stack(emb), np.stack(band)


def clf():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))


def cv_proba(X, y):
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    return cross_val_predict(clf(), X, y, cv=cv, method="predict_proba")


def multiclass(X, y):
    p = cv_proba(X, y)
    classes = np.unique(y)
    pred = classes[p.argmax(1)]
    return {"balanced_accuracy": round(balanced_accuracy_score(y, pred), 3),
            "chance": round(1 / len(classes), 3), "n_classes": int(len(classes))}


def binary(X, y):
    p = cv_proba(X, y.astype(int))[:, 1]
    return {"auroc": round(roc_auc_score(y, p), 3), "n_pos": int(y.sum()), "n_neg": int((~y).sum())}


def main(actor, out):
    s, emb, band = load_days()
    both = np.c_[emb, band]
    res = {"days": len(s), "features": {"embedding": emb.shape[1], "band": band.shape[1]}}

    # class balance per deployment (train/val sample and all eligible train/val days)
    t = pd.read_csv(ROOT / "data" / "day_table.csv", dtype={"deployment": str})
    t = t[t["eligible"] & t["site"].isin(["sb01", "sb02"]) & t["deployment"].isin([f"{i:02d}" for i in range(1, 10)])]
    t["dep"] = t["site"] + "_" + t["deployment"]
    bal = pd.DataFrame({"sample_days": s.groupby("dep").size(), "sample_present": s.groupby("dep")["label"].sum(),
                        "eligible_days": t.groupby("dep").size(), "eligible_present": t.groupby("dep")["label"].sum()})
    bal["sample_present_rate"] = (bal.sample_present / bal.sample_days).round(3)
    bal["eligible_present_rate"] = (bal.eligible_present / bal.eligible_days).round(3)
    res["class_balance"] = bal.reset_index().rename(columns={"index": "dep"}).to_dict("records")
    res["overall_present_rate"] = round(s["label"].mean(), 3)

    # how much label information deployment identity carries: leave-one-day-out deployment present rate
    g = s.groupby("dep")["label"]
    loo = (g.transform("sum") - s["label"]) / (g.transform("count") - 1)
    res["deployment_prior_auroc_loo"] = round(roc_auc_score(s["label"], loo), 3)

    # A. 18-way deployment ID
    y = s["dep"].to_numpy()
    res["deployment_id"] = {k: multiclass(X, y) for k, X in
                            [("embedding", emb), ("band", band), ("embedding+band", both)]}
    # B. site ID (sb01 vs sb02; same calendar dates, so season is balanced)
    site = (s["site"] == "sb01").to_numpy()
    res["site_id_auroc"] = {k: binary(X, site) for k, X in [("embedding", emb), ("band", band)]}
    # C. sb01_02 vs every other deployment
    is02 = (s["dep"] == "sb01_02").to_numpy()
    res["sb01_02_vs_rest"] = {k: binary(X, is02) for k, X in [("embedding", emb), ("band", band)]}
    # D. sb01_02 vs sb02_02 (same deployment period at the other site: season controlled)
    m = s["dep"].isin(["sb01_02", "sb02_02"]).to_numpy()
    res["sb01_02_vs_sb02_02"] = {k: binary(X[m], is02[m]) for k, X in [("embedding", emb), ("band", band)]}
    res["notes"] = ["Deployments are disjoint in time, so 18-way ID is confounded with season and date;"
                    " site ID (B) and sb01_02 vs sb02_02 (D) control for calendar time."]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    log_event(actor, "deployment_check", {"dest": str(out.relative_to(ROOT)),
                                          "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                                          "scope": "300 train/val days; features only; labels used for class balance and deployment-prior AUROC only",
                                          "summary": {k: res[k] for k in ["deployment_prior_auroc_loo", "deployment_id", "site_id_auroc",
                                                                          "sb01_02_vs_rest", "sb01_02_vs_sb02_02"]}})
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--out", default=str(ROOT / "docs" / "analysis" / "deployment_check.json"))
    a = p.parse_args()
    from pathlib import Path
    main(a.actor, Path(a.out).resolve())
