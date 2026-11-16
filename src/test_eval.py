"""STAGE B test evaluation (docs/evaluation-plan.md v2 sections 3-6; docs/analysis/test-processing-plan.md).

    python -m src.test_eval --actor <name> --owner-approval "<owner's Stage B release, verbatim, with date>"

THIS IS THE ONLY CODE THAT READS TEST LABELS. It refuses to run unless:
  * the owner's Stage B release is given (logged verbatim as `stage_b_release`);
  * the final-model artefact's SHA-256 matches docs/analysis/final_model/spec.json and the `final_model` entry;
  * a Stage A `drift_report` entry exists for test_T and for test_S;
  * every test day's .npz exists, carries the freeze-tag commit, and matches the SHA-256 in its `score_day` entry.
Nothing here is tuned: the model, aggregation, thresholds and baselines all come from the frozen spec/artefact.
Days excluded under the QA rule (`qa_exclusion` audit entries) are dropped and listed, with counts per
deployment and a concentration flag (test-processing plan section 2.5).
Headline split: Test S, with Test T secondary (test-processing plan section 4, owner decision 2026-11-13).
Labels are read only after every check has passed and the Stage B release has been logged; until then the day
list is read without its label column.

Splits: test_T (sb01+sb02, deployments 10-12), test_S (sb03, 01-12), test_S_10_12 (sb03, 10-12; a slice of S).
Variants per split: primary (all days); zero_flag_days_excluded (eval_plan section 7);
sb01_02_equivalent_excluded (sb01_02 plan section 3c; only where Stage A flagged a deployment).
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from src.audit import DEFAULT_LOG, log_event
from src.cv_eval import AGGS, bal_acc, boot_ci, boot_ci_ws, safe_auc, within_site_auroc
from src.label_survey import ROOT
from src.pilot_review import primary_day_score

SPEC = ROOT / "docs" / "analysis" / "final_model" / "spec.json"
TEST_DIR = ROOT / "data" / "scores" / "v2_test"
DAYS_CSV = ROOT / "data" / "sample_days.csv"
OUT_DIR = ROOT / "docs" / "analysis" / "test_results"
BASELINES = ["month_prior", "ambient_noise", "zero_shot_primary"]  # non-diagnostic (2-4); best chosen per split
SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA",
          9: "SON", 10: "SON", 11: "SON"}
MIN_N = 5
HEADLINE_SPLIT = "test_S"
CONC_SHARE, CONC_MIN, CONC_DEP_FRAC = 0.5, 2, 0.2  # QA-exclusion concentration flag (plan section 2.5)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    """Path relative to the repo root where possible (scratch dry runs write outside it)."""
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def audit_entries(log=DEFAULT_LOG):
    return [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()]


def preflight(entries, spec):
    """Refuse unless the frozen artefact, the Stage A reports and the scored test files all check out."""
    problems = []
    art = ROOT / spec["artefact"]
    fm = [e for e in entries if e["action"] == "final_model"]
    if not fm:
        problems.append("no final_model audit entry")
    elif not art.exists() or sha(art) != spec["artefact_sha256"] or fm[-1]["details"]["artefact_sha256"] != spec["artefact_sha256"]:
        problems.append("final-model artefact SHA-256 does not match spec and audit entry")
    if fm and sha(SPEC) != fm[-1]["details"]["spec_sha256"]:
        problems.append("spec.json SHA-256 does not match the final_model entry")
    for split in ["test_T", "test_S"]:
        if not any(e["action"] == "drift_report" and split in e["details"].get("mode", "") for e in entries):
            problems.append(f"no Stage A drift_report for {split}")
    scored = {}
    for e in entries:
        d = e["details"]
        if e["action"] == "score_day" and str(d.get("npz", "")).startswith("data/scores/v2_test/"):
            scored[d["day"]] = d
    return problems, scored


def day_scores(days, model, scored, problems):
    fam, agg = model["family"], model["aggregation"]
    rows = []
    for r in days.itertuples():
        key = f"{r.site}_{r.deployment}_{r.date}"
        f = TEST_DIR / f"{key}.npz"
        rep = scored.get(key)
        if rep is None or not f.exists() or sha(f) != rep["sha256"]:
            problems.append(f"{key}: missing, unlogged or SHA-256 mismatch")
            continue
        with np.load(f, allow_pickle=True) as z:
            e = z["block_emb"].astype(np.float32)
            if fam == "block":
                s = float(AGGS[agg](model["model"].predict_proba(e)[:, 1]))
            else:
                s = float(model["model"].predict_proba(e.mean(0, keepdims=True))[0, 1])
            b = z["block_band_db"]
            band = np.r_[np.median(b, 0), np.percentile(b, 90, 0)][None, :]
            amb = float(model["ambient_noise"]["model"].predict_proba(band)[0, 1])
            zs = float(primary_day_score(z["window_start_s"], z["humpback"].astype(np.float64)))
            commit = str(z["git_commit"])
            zf = float(z["zero_fraction"])
        month = pd.Timestamp(r.date).month
        rows.append({"day": key, "final_model": s, "ambient_noise": amb, "zero_shot_primary": zs,
                     "month_prior": model["month_prior"]["rate"].get(month, model["month_prior"]["overall"]),
                     "site_prior": model["site_prior"]["rate"].get(r.site, model["site_prior"]["overall"]),
                     "always_present": 1.0, "zero_fraction": zf, "git_commit": commit})
    return pd.DataFrame(rows)


def exclusion_concentration(excluded_keys, days):
    """Exclusions per deployment, per split, and the deployments where they concentrate (reported, not acted on).

    A deployment is flagged if it holds at least CONC_SHARE of its split's exclusions (with at least CONC_MIN
    of them), or if at least CONC_DEP_FRAC of its own sampled days are excluded."""
    out = {}
    for split, g in days.groupby("split"):
        n_dep = g.groupby("dep").size()
        ex = g[g["key"].isin(excluded_keys)].groupby("dep").size()
        total = int(ex.sum())
        flagged = sorted(k for k, n in ex.items()
                         if (total and n >= CONC_MIN and n / total >= CONC_SHARE) or n / n_dep[k] >= CONC_DEP_FRAC)
        out[split] = {"excluded": total, "by_deployment": {k: int(n) for k, n in ex.items()},
                      "sampled_by_deployment": {k: int(n) for k, n in n_dep.items() if k in ex.index},
                      "concentrated": flagged}
    return out


def cell(y, s, groups, n_boot_ok=3):
    p, n = int(y.sum()), int(len(y) - y.sum())
    if p < MIN_N or n < MIN_N:
        return f"n/a ({p} present / {n} absent)"
    out = {"auroc": round(safe_auc(y, s), 3), "present": p, "absent": n, "deployments": int(len(np.unique(groups)))}
    if out["deployments"] >= n_boot_ok:
        ci, _ = boot_ci(y, {"m": s}, groups)
        out["auroc_ci95"] = ci["m"]
    return out


def evaluate(d, thresholds):
    y, g, site = d["label"].to_numpy(), d["dep"].to_numpy(), d["site"].to_numpy()
    methods = ["final_model"] + BASELINES + ["site_prior", "always_present"]
    sc = {m: d[m].to_numpy() for m in methods}
    pairs = [("final_model", b) for b in BASELINES + ["site_prior"]]
    ci, dci = boot_ci(y, sc, g, pairs)
    ws_ci, ws_dci = boot_ci_ws(y, sc, g, site, pairs)
    r = lambda a: round(float(a), 3) if a is not None else None
    res = {"days": int(len(y)), "present": int(y.sum()), "absent": int(len(y) - y.sum()),
           "deployments": int(len(np.unique(g))), "absent_prevalence": r(1 - y.mean()), "methods": {},
           "paired_differences_ws": ws_dci, "paired_differences_pooled": dci}
    for m in methods:
        v = sc[m]
        t = thresholds.get(m)
        res["methods"][m] = {
            "auroc_ws": r(within_site_auroc(y, v, site)), "auroc_ws_ci95": ws_ci[m],
            "auroc": r(safe_auc(y, v)), "auroc_ci95": ci[m],
            "pr_auc_absent_pos": r(average_precision_score(1 - y, -v)),
            "bal_acc_fixed_threshold": r(bal_acc(y, v >= t)) if t is not None else None, "threshold": t,
            "per_site": {s: cell(y[site == s], v[site == s], g[site == s]) for s in sorted(np.unique(site))},
            "per_season": {s: cell(y[d["season"] == s], v[d["season"] == s], g[d["season"] == s])
                           for s in ["DJF", "MAM", "JJA", "SON"]},
            "per_deployment": {k: cell(y[g == k], v[g == k], g[g == k]) for k in sorted(np.unique(g))},
            "calibration_per_deployment": {k: {"mean_score": r(v[g == k].mean()), "present_rate": r(y[g == k].mean()),
                                               "days": int((g == k).sum())} for k in sorted(np.unique(g))}}
        if len(np.unique(site)) > 1:
            res["methods"][m]["site_id_probe_auroc"] = r(abs(safe_auc((site == "sb02").astype(int), v) - 0.5) + 0.5)
    if len(np.unique(site)) > 1:
        res["site_id_from_labels_auroc"] = r(abs(safe_auc((site == "sb02").astype(int), y) - 0.5) + 0.5)
    # Improvement claim (evaluation-plan v2 section 4): both conditions on this split
    ws = {b: res["methods"][b]["auroc_ws"] for b in BASELINES}
    best = max(ws, key=lambda b: (ws[b] if ws[b] is not None else -1))
    lo1 = res["methods"]["final_model"]["auroc_ws_ci95"][0]
    lo2 = ws_dci[f"final_model - {best}"][0]
    res["improvement_claim"] = {"best_baseline_by_auroc_ws": best,
                                "condition_1_auroc_ws_ci_excludes_0_5": bool(lo1 > 0.5),
                                "condition_2_paired_ws_ci_vs_best_excludes_0": bool(lo2 > 0),
                                "improves": bool(lo1 > 0.5 and lo2 > 0)}
    return res


def main(actor, approval, out_dir=OUT_DIR, log=DEFAULT_LOG):
    t0 = time.time()
    if not (approval and approval.strip()):
        raise SystemExit("refused: --owner-approval (the owner's Stage B release) is required")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    spec = json.loads(SPEC.read_text())
    entries = audit_entries(log)
    problems, scored = preflight(entries, spec)
    if problems:
        raise SystemExit("refused: " + "; ".join(problems))
    model = joblib.load(ROOT / spec["artefact"])
    freeze = {e["details"]["commit"] for e in entries if e["action"] == "eval_freeze"}
    equiv = set()
    for e in entries:
        if e["action"] == "drift_report" and "Stage A" in e["details"].get("mode", ""):
            equiv |= set(e["details"]["flags"].get("sb01_02_equivalent", []))
    excluded = {e["details"]["day"]: e["details"]["reason"] for e in entries if e["action"] == "qa_exclusion"}
    # Day list WITHOUT labels: every check below runs before any test label is read.
    days = pd.read_csv(DAYS_CSV, dtype={"deployment": str}, usecols=["split", "site", "deployment", "date"])
    days = days[days["split"].isin(["test_T", "test_S"])].reset_index(drop=True)
    days["dep"] = days["site"] + "_" + days["deployment"]
    days["key"] = days["dep"] + "_" + days["date"]
    days["season"] = pd.to_datetime(days["date"]).dt.month.map(SEASON)
    listed_excl = days[days["key"].isin(excluded)]
    concentration = exclusion_concentration(set(excluded), days)
    days = days[~days["key"].isin(excluded)].reset_index(drop=True)
    problems = []
    sc = day_scores(days, model, scored, problems)
    if problems:
        raise SystemExit("refused: " + "; ".join(problems))
    bad = sorted(set(sc["git_commit"]) - freeze)
    if bad:
        raise SystemExit(f"refused: test features not stamped with a freeze-tag commit: {bad}")
    log_event(actor, "stage_b_release", {"owner_approval": approval, "git_commit": commit,
                                         "spec_sha256": sha(SPEC), "artefact_sha256": spec["artefact_sha256"],
                                         "days_scored": int(len(sc)), "qa_excluded": len(listed_excl)}, log)
    # Labels are read from here on, once.
    lab = pd.read_csv(DAYS_CSV, dtype={"deployment": str}, usecols=["split", "site", "deployment", "date", "label"])
    lab["key"] = lab["site"] + "_" + lab["deployment"] + "_" + lab["date"]
    days = days.merge(lab[["key", "label"]], on="key", how="left", validate="one_to_one")
    if days["label"].isna().any():
        raise SystemExit("refused: a scored test day has no label row")
    days["label"] = days["label"].astype(int)
    d = days.merge(sc, left_on="key", right_on="day")
    thresholds = {"final_model": spec["day_threshold"], **spec["baseline_thresholds"], "always_present": 1.0}
    splits = {"test_T": d["split"] == "test_T", "test_S": d["split"] == "test_S",
              "test_S_10_12": (d["split"] == "test_S") & d["deployment"].isin(["10", "11", "12"])}
    results = {"git_commit": commit, "spec_sha256": sha(SPEC), "artefact_sha256": spec["artefact_sha256"],
               "selected_model": spec["selected"], "thresholds": thresholds,
               "headline_split": HEADLINE_SPLIT, "secondary_split": "test_T",
               "qa_excluded_days": {k: excluded[k] for k in listed_excl["key"]},
               "qa_exclusion_concentration": concentration,
               "sb01_02_equivalent_deployments": sorted(equiv), "splits": {}}
    for name, m in splits.items():
        dd = d[m.to_numpy()].reset_index(drop=True)
        res = {"primary": evaluate(dd, thresholds)}
        zf = dd["zero_fraction"] > 0.01
        res["zero_flag_days"] = sorted(dd.loc[zf, "key"])
        if zf.any():
            res["zero_flag_days_excluded"] = evaluate(dd[~zf].reset_index(drop=True), thresholds)
        eq = dd["dep"].isin(equiv)
        if eq.any():
            res["sb01_02_equivalent_excluded"] = evaluate(dd[~eq].reset_index(drop=True), thresholds)
        results["splits"][name] = res
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / "results.json"
    js.write_text(json.dumps(results, indent=1, default=str))
    d[["split", "site", "deployment", "date", "label", "final_model"] + BASELINES + ["site_prior", "zero_fraction"]].to_csv(
        out_dir / "test_day_scores.csv", index=False)
    log_event(actor, "test_eval", {"git_commit": commit, "out": rel(js), "sha256": sha(js),
                                   "csv_sha256": sha(out_dir / "test_day_scores.csv"),
                                   "headline": {k: v["primary"]["methods"]["final_model"]["auroc_ws"]
                                                for k, v in results["splits"].items()},
                                   "runtime_s": round(time.time() - t0, 1)}, log)
    print(json.dumps({k: v["primary"]["improvement_claim"] for k, v in results["splits"].items()}, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--owner-approval", required=True)
    a = p.parse_args()
    main(a.actor, a.owner_approval)
