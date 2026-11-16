"""Pre-evaluation drift report (docs/evaluation-plan.md section 7). READS NO LABELS.

    python -m src.drift_report --actor <name> --split test_T|test_S     # Stage A, after test audio is scored
    python -m src.drift_report --actor <name> --self-check              # train/val only: calibrate the flags

For each target deployment, against the train/val (reference) deployments:
  * zero fraction: median over its days; sb01_02-equivalent if > 0.01 (sb01_02 plan section 3c)
  * band levels: per band, the median over days of the daily median (and of the daily p90). FLAG if the
    median level in any band lies more than 6 dB outside the reference deployments' range (plan section 7)
  * zero-shot Mn window scores: median, p90 and share >= 0.5 (descriptive only)
  * embedding shift: distance of the deployment's mean day embedding (standardised on reference days) to the
    nearest reference deployment mean, against the nearest-neighbour distances among reference deployments;
    plus a deployment-ID probe (L2 LR, C=1, on reference day embeddings) and its confidence on target days
Flags are REPORTED, NOT ACTED ON (plan section 7). The day list is read without its label column.

--self-check treats each train/val deployment in turn as the target and the other 17 as the reference, to show
how often each flag fires with no real shift. It uses train/val features only.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.audit import log_event
from src.label_survey import ROOT

DAYS_CSV = ROOT / "data" / "sample_days.csv"
TRAIN_DIR = ROOT / "data" / "scores" / "v2"
TEST_DIR = ROOT / "data" / "scores" / "v2_test"
OUT_DIR = ROOT / "docs" / "analysis" / "drift"
ZERO_EQUIV = 0.01
BAND_DB = 6.0
COLS = ["split", "site", "deployment", "date"]  # never the label column


def day_list(split):
    d = pd.read_csv(DAYS_CSV, usecols=COLS, dtype={"deployment": str})
    assert "label" not in d.columns
    d = d[d["split"] == split].reset_index(drop=True)
    if d.empty:
        raise SystemExit(f"no {split} days")
    d["dep"] = d["site"] + "_" + d["deployment"]
    return d


def load_features(days, scores_dir):
    rows, emb, mn = [], [], {}
    for r in days.itertuples():
        f = scores_dir / f"{r.site}_{r.deployment}_{r.date}.npz"
        if not f.exists():
            raise SystemExit(f"missing features: {f.name}")
        with np.load(f, allow_pickle=True) as z:
            b = z["block_band_db"]
            rows.append({"dep": r.dep, "zero_fraction": float(z["zero_fraction"]),
                         **{f"med_{i}": v for i, v in enumerate(np.median(b, 0))},
                         **{f"p90_{i}": v for i, v in enumerate(np.percentile(b, 90, 0))}})
            emb.append(z["block_emb"].astype(np.float32).mean(0))
            mn.setdefault(r.dep, []).append(z["humpback"].astype(np.float64))
            bands = [str(x) for x in z["band_names"]]
    return pd.DataFrame(rows), np.stack(emb), {k: np.concatenate(v) for k, v in mn.items()}, bands


def dep_stats(feat, mn, nb):
    g = feat.groupby("dep")
    out = pd.DataFrame({"zero_fraction_median": g["zero_fraction"].median(), "days": g.size()})
    for i in range(nb):
        out[f"med_{i}"] = g[f"med_{i}"].median()
        out[f"p90_{i}"] = g[f"p90_{i}"].median()
    for d, v in mn.items():
        out.loc[d, "mn_median"] = np.median(v)
        out.loc[d, "mn_p90"] = np.percentile(v, 90)
        out.loc[d, "mn_share_ge_0_5"] = float((v >= 0.5).mean())
    return out


def report(ref_feat, ref_emb, ref_mn, tgt_feat, tgt_emb, tgt_mn, bands):
    nb = len(bands)
    R, T = dep_stats(ref_feat, ref_mn, nb), dep_stats(tgt_feat, tgt_mn, nb)
    sc = StandardScaler().fit(ref_emb)
    rz, tz = sc.transform(ref_emb), sc.transform(tgt_emb)
    rdeps, tdeps = ref_feat["dep"].to_numpy(), tgt_feat["dep"].to_numpy()
    rmean = {d: rz[rdeps == d].mean(0) for d in R.index}
    rm = np.stack([rmean[d] for d in R.index])
    nn_ref = []
    for i in range(len(rm)):
        dist = np.linalg.norm(rm - rm[i], axis=1)
        dist[i] = np.inf
        nn_ref.append(dist.min())
    nn_ref = np.array(nn_ref)
    probe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000)).fit(ref_emb, rdeps)
    pp = probe.predict_proba(tgt_emb)
    cls = probe.classes_
    ref_range = {b: [float(R[f"med_{i}"].min()), float(R[f"med_{i}"].max())] for i, b in enumerate(bands)}
    deps = {}
    for d in T.index:
        t = T.loc[d]
        out_db = {}
        for i, b in enumerate(bands):
            lo, hi = ref_range[b]
            v = float(t[f"med_{i}"])
            out_db[b] = round(max(lo - v, v - hi, 0.0), 2)
        tm = tz[tdeps == d].mean(0)
        dist = float(np.linalg.norm(rm - tm, axis=1).min())
        m = tdeps == d
        top = pd.Series(cls[pp[m].argmax(1)]).value_counts()
        deps[d] = {
            "days": int(t["days"]),
            "zero_fraction_median": round(float(t["zero_fraction_median"]), 5),
            "sb01_02_equivalent": bool(t["zero_fraction_median"] > ZERO_EQUIV),
            "band_median_db": {b: round(float(t[f"med_{i}"]), 2) for i, b in enumerate(bands)},
            "band_p90_db": {b: round(float(t[f"p90_{i}"]), 2) for i, b in enumerate(bands)},
            "band_db_outside_reference_range": out_db,
            "band_flag": bool(max(out_db.values()) > BAND_DB),
            "zero_shot_mn": {k: round(float(t[k]), 4) for k in ["mn_median", "mn_p90", "mn_share_ge_0_5"]},
            "embedding_nn_distance": round(dist, 3),
            "embedding_nn_distance_vs_reference_max": round(dist / float(nn_ref.max()), 3),
            "embedding_beyond_reference_spread": bool(dist > nn_ref.max()),
            "deployment_probe_mean_max_prob": round(float(pp[m].max(1).mean()), 3),
            "deployment_probe_top": {k: int(v) for k, v in top.head(3).items()},
        }
    return {"reference_deployments": list(R.index), "band_reference_range_db": ref_range,
            "reference_nn_distance": {"min": round(float(nn_ref.min()), 3), "median": round(float(np.median(nn_ref)), 3),
                                      "max": round(float(nn_ref.max()), 3)},
            "reference_zero_shot_mn": {k: [round(float(R[k].min()), 4), round(float(R[k].max()), 4)]
                                       for k in ["mn_median", "mn_p90", "mn_share_ge_0_5"]},
            "deployments": deps,
            "flags": {"sb01_02_equivalent": [d for d, v in deps.items() if v["sb01_02_equivalent"]],
                      "band_flag": [d for d, v in deps.items() if v["band_flag"]],
                      "embedding_beyond_reference_spread": [d for d, v in deps.items() if v["embedding_beyond_reference_spread"]]}}


def main(actor, split, self_check):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    ref_days = day_list("trainval")
    ref_feat, ref_emb, ref_mn, bands = load_features(ref_days, TRAIN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if self_check:
        res = {"mode": "self-check (train/val only; each deployment vs the other 17)", "deployments": {}}
        for d in sorted(ref_days["dep"].unique()):
            r, t = (ref_feat["dep"] != d).to_numpy(), (ref_feat["dep"] == d).to_numpy()
            rep = report(ref_feat[r], ref_emb[r], {k: v for k, v in ref_mn.items() if k != d},
                         ref_feat[t], ref_emb[t], {d: ref_mn[d]}, bands)
            res["deployments"][d] = rep["deployments"][d]
        res["flag_counts"] = {k: [d for d, v in res["deployments"].items() if v[k]]
                              for k in ["sb01_02_equivalent", "band_flag", "embedding_beyond_reference_spread"]}
        out = OUT_DIR / "self_check_trainval.json"
    else:
        tgt_days = day_list(split)
        tgt_feat, tgt_emb, tgt_mn, _ = load_features(tgt_days, TEST_DIR)
        res = {"mode": f"Stage A drift report, {split} (no labels read)", **report(ref_feat, ref_emb, ref_mn,
                                                                                  tgt_feat, tgt_emb, tgt_mn, bands)}
        out = OUT_DIR / f"drift_{split}.json"
    res.update({"git_commit": commit, "bands": bands, "zero_equiv_cut": ZERO_EQUIV, "band_flag_db": BAND_DB,
                "note": "flags are reported, not acted on (evaluation-plan section 7)"})
    out.write_text(json.dumps(res, indent=1))
    log_event(actor, "drift_report", {"git_commit": commit, "mode": res["mode"], "out": str(out.relative_to(ROOT)),
                                      "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                                      "labels_read": False,
                                      "flags": res.get("flags", res.get("flag_counts"))})
    print(json.dumps(res.get("flags", res.get("flag_counts")), indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--split", choices=["test_T", "test_S"])
    g.add_argument("--self-check", action="store_true")
    a = p.parse_args()
    main(a.actor, a.split, a.self_check)
