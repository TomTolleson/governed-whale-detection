"""Final-model selection on TRAIN/VAL ONLY (docs/analysis/final-model-protocol.md, confirmed P1-P7).

    python -m src.final_model --actor <name> [--jobs N]

Resumable: every fit is checkpointed to data/models/final_v1_ckpt/ (manifest.jsonl with SHA-256 and fit
diagnostics); a rerun verifies each checkpoint's SHA-256 and fits only what is missing. Thermal guard: CPU Tctl
is logged every 15 s to docs/analysis/final_model/cpu_temp.csv; dispatching pauses at 85 C (Tjmax 95 C) until
70 C, and stops cleanly after 30 min. A fit that hits max_iter, warns or gives non-finite output is logged as
fit_anomaly and the run stops; the grid and rules are never changed.

Candidates (P1): block LR x {mean, top12, top3, max} and day-mean LR, each x C in C_GRID (25 configurations).
Selection (P2): highest pooled out-of-fold within-site AUROC over the 9 leave-deployment-out folds (Primary).
Ties (P3): within 0.005 of the best; then smallest C, block before day-mean, aggregation mean > top12 > top3 > max.
Nested estimate (P2): for each outer fold k, select on the other 8 deployment numbers, score fold k with the fit
on those 8. S1 (sb01_02 excluded) repeats selection and the nested estimate. Thresholds (P4): day threshold by
balanced accuracy on pooled OOF scores; baselines' thresholds fixed from their cv_v1.1 OOF scores. Artefacts (P5):
data/models/final_v1.joblib (git-ignored) and docs/analysis/final_model/spec.json + results.json.

Every fit trains on all train/val days except a held-out set of deployment numbers. A fit is shared by every
use that holds out the same set (e.g. inner fold j of outer fold k == inner fold k of outer fold j), so each
(held-out set, C) is fitted once. Test days are refused (src.cv_eval.load).
"""

import argparse
import hashlib
import itertools
import json
import platform
import subprocess
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from joblib import Parallel, delayed

from src.audit import log_event
from src.cv_eval import (AGGS, C_GRID, SEED, SCORES, bal_acc, best_threshold, boot_ci, boot_ci_ws, load, lr,
                         pick_C, safe_auc, within_site_auroc)
from src.label_survey import ROOT

TIE_TOL = 0.005
AGG_ORDER = ["mean", "top12", "top3", "max"]  # P3: most blocks used -> fewest
CONFIGS = ([("block", a, C) for C in C_GRID for a in AGG_ORDER] + [("day", "day", C) for C in C_GRID])
OUT_DIR = ROOT / "docs" / "analysis" / "final_model"
MODEL_PATH = ROOT / "data" / "models" / "final_v1.joblib"
CV11 = ROOT / "docs" / "analysis" / "cv_v1.1"
BASELINES = ["month_prior", "ambient_noise", "zero_shot_primary"]


def cfg_name(c):
    fam, agg, C = c
    return f"emb_block_lr_{agg}_C{C:g}" if fam == "block" else f"emb_day_lr_C{C:g}"


def select(ws: dict):
    """P3 tie rule. ws maps config -> AUROC_ws. Returns the chosen config."""
    best = max(ws.values())
    tied = [c for c, v in ws.items() if v >= best - TIE_TOL]
    key = lambda c: (c[2], 0 if c[0] == "block" else 1, AGG_ORDER.index(c[1]) if c[0] == "block" else 0)
    return sorted(tied, key=key)[0]


def aggregate(pb_by_day, agg):
    return np.array([AGGS[agg](p) for p in pb_by_day])


def fit_heldout(heldout, C, keep, fold, y, blocks, block_day, emb_day, diag=False):
    """Train on keep-days whose fold is not in heldout; predict keep-days whose fold is in heldout."""
    import warnings
    t0 = time.time()
    tr = np.flatnonzero(keep & ~np.isin(fold, list(heldout)))
    te = np.flatnonzero(keep & np.isin(fold, list(heldout)))
    btr, bte = np.isin(block_day, tr), np.isin(block_day, te)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        m = lr(C).fit(blocks[btr], y[block_day[btr]])
        pb = m.predict_proba(blocks[bte])[:, 1]
        md = lr(C).fit(emb_day[tr], y[tr])
        pd_day = md.predict_proba(emb_day[te])[:, 1]
    bd = block_day[bte]
    pb_by_day = [pb[bd == d] for d in te]
    if not diag:
        return te, pb_by_day, pd_day
    return te, pb_by_day, pd_day, {
        "n_iter_block": int(m[-1].n_iter_[0]), "n_iter_day": int(md[-1].n_iter_[0]),
        "max_iter": int(m[-1].max_iter), "warnings": sorted({f"{x.category.__name__}: {str(x.message)[:200]}" for x in w
                             if not issubclass(x.category, (DeprecationWarning, FutureWarning))}),
        "finite": bool(np.isfinite(pb).all() and np.isfinite(pd_day).all()), "fit_s": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- checkpoints, thermal guard

CKPT = ROOT / "data" / "models" / "final_v1_ckpt"
MANIFEST = CKPT / "manifest.jsonl"
TEMP_CSV = OUT_DIR / "cpu_temp.csv"
PAUSE_C = 85.0    # Ryzen 7 3800X Tjmax is 95 C (Tctl); pause dispatching at 85 C
RESUME_C = 70.0   # resume after two consecutive readings at or below 70 C
COOL_WAIT_S = 1800  # if not cool within 30 min, stop cleanly (resumable)


class Anomaly(SystemExit):
    pass


def read_tctl():
    """CPU Tctl in deg C from the k10temp hwmon sensor, or None if unavailable."""
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (h / "name").read_text().strip() == "k10temp":
                for lab in h.glob("temp*_label"):
                    if lab.read_text().strip() == "Tctl":
                        return int((h / lab.name.replace("label", "input")).read_text()) / 1000
        except OSError:
            continue
    return None


class TempLogger:
    """Samples Tctl every 15 s to TEMP_CSV (append) from a background thread; tracks the max since last reset."""

    def __init__(self):
        import threading
        self.stop, self.last, self.window_max, self.all = threading.Event(), None, None, []
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        if not TEMP_CSV.exists():
            TEMP_CSV.write_text("utc,tctl_c\n")
        self.t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stop.is_set():
            t = read_tctl()
            self.last = t
            if t is not None:
                self.window_max = t if self.window_max is None else max(self.window_max, t)
                self.all.append(t)
                with open(TEMP_CSV, "a") as f:
                    f.write(f"{pd.Timestamp.utcnow().isoformat()},{t:.1f}\n")
            self.stop.wait(15)

    def take_window_max(self):
        m, self.window_max = self.window_max, None
        return m


def ckpt_file(variant, h, C):
    return CKPT / f"{variant}__{'-'.join(sorted(h))}__C{C:g}.npz"


def read_manifest():
    rec = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rec[(r["variant"], frozenset(r["heldout"]), float(r["C"]))] = r
    return rec


def save_ckpt(variant, h, C, res):
    te, pb_by_day, pd_day, diag = res
    f = ckpt_file(variant, h, C)
    np.savez(f, te=te, pb=np.concatenate(pb_by_day), lens=np.array([len(p) for p in pb_by_day]), pd_day=pd_day)
    rec = {"variant": variant, "heldout": sorted(h), "C": C, "file": f.name,
           "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), **diag}
    with open(MANIFEST, "a") as m:
        m.write(json.dumps(rec) + "\n")
    return rec


def load_ckpt(rec):
    with np.load(CKPT / rec["file"]) as z:
        te, pb, lens, pd_day = z["te"], z["pb"], z["lens"], z["pd_day"]
    return te, np.split(pb, np.cumsum(lens)[:-1]), pd_day


def check_fit(rec, actor):
    """Log and stop on anything odd: non-convergence, warnings, non-finite output (owner condition 5)."""
    odd = []
    if rec["n_iter_block"] >= rec["max_iter"] or rec["n_iter_day"] >= rec["max_iter"]:
        odd.append("hit max_iter (not converged)")
    if rec["warnings"]:
        odd.append("warnings: " + "; ".join(rec["warnings"]))
    if not rec["finite"]:
        odd.append("non-finite predictions")
    if odd:
        log_event(actor, "fit_anomaly", {"fit": rec, "problems": odd, "action": "stopped; grid and rules unchanged"})
        raise Anomaly(f"fit anomaly in {rec['file']}: {odd}. Logged; stopping to ask the owner.")


def thermal_gate(tl, actor):
    """Before each batch: pause while the CPU is hot; stop cleanly if it does not cool."""
    hot = max([t for t in (tl.take_window_max(), read_tctl()) if t is not None], default=None)
    if hot is None or hot < PAUSE_C:
        return
    log_event(actor, "thermal_pause", {"tctl_c": hot, "pause_c": PAUSE_C, "resume_c": RESUME_C})
    t0, ok = time.time(), 0
    while time.time() - t0 < COOL_WAIT_S:
        time.sleep(30)
        t = read_tctl()
        ok = ok + 1 if (t is not None and t <= RESUME_C) else 0
        if ok >= 2:
            log_event(actor, "thermal_resume", {"tctl_c": t, "paused_s": round(time.time() - t0)})
            tl.take_window_max()
            return
    log_event(actor, "thermal_stop", {"tctl_c": read_tctl(), "waited_s": COOL_WAIT_S,
                                      "resume": "rerun the same command; finished fits are kept"})
    raise SystemExit(3)


def run_fits(variant, tasks, keep, fold, y, blocks, block_day, emb_day, jobs, actor, tl):
    """Fit every (held-out set, C) not already checkpointed, in batches of `jobs`; verify existing checkpoints."""
    CKPT.mkdir(parents=True, exist_ok=True)
    man = read_manifest()
    done, todo = {}, []
    for h, C in tasks:
        r = man.get((variant, h, float(C)))
        if r is None:
            todo.append((h, C))
            continue
        f = CKPT / r["file"]
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != r["sha256"]:
            log_event(actor, "fit_anomaly", {"fit": r, "problems": ["checkpoint missing or SHA-256 mismatch"],
                                             "action": "stopped"})
            raise Anomaly(f"checkpoint {r['file']} missing or SHA-256 mismatch. Logged; stopping to ask the owner.")
        done[(h, C)] = r
    print(f"[{variant}] {len(done)} fits verified from checkpoints, {len(todo)} to fit", flush=True)
    todo.sort(key=lambda t: (t[1], sorted(t[0])))  # similar C per batch, so batch members finish together
    t0 = time.time()
    for i in range(0, len(todo), jobs):
        thermal_gate(tl, actor)
        batch = todo[i:i + jobs]
        res = Parallel(n_jobs=jobs)(delayed(fit_heldout)(h, C, keep, fold, y, blocks, block_day, emb_day, True)
                                    for h, C in batch)
        for (h, C), r in zip(batch, res):
            rec = save_ckpt(variant, h, C, r)
            check_fit(rec, actor)
            done[(h, C)] = rec
        el = time.time() - t0
        n = i + len(batch)
        print(f"[{variant}] {len(done)}/{len(tasks)} fits; {el / n:.0f} s per fit; "
              f"~{el / n * (len(todo) - n) / 60:.0f} min left; Tctl {tl.last}", flush=True)
    return {t: load_ckpt(done[t]) for t in tasks}


def oof_scores(cache, cfg, excluded, folds, n):
    """Out-of-fold day scores for cfg over folds not in `excluded`, using fits that hold out excluded | {f}."""
    fam, agg, C = cfg
    out = np.full(n, np.nan)
    for f in folds:
        if f in excluded:
            continue
        te, pb_by_day, pd_day = cache[(frozenset(excluded) | {f}, C)]
        sc = aggregate(pb_by_day, agg) if fam == "block" else pd_day
        mask = np.isin(te, np.flatnonzero(cache["fold"] == f))
        out[te[mask]] = sc[mask]
    return out


def run_variant(name, keep, s, y, fold, site, blocks, block_day, emb_day, jobs, actor, tl):
    folds = sorted(np.unique(fold[keep]))
    sets = [frozenset([f]) for f in folds] + [frozenset(p) for p in itertools.combinations(folds, 2)]
    tasks = [(h, C) for h in sets for C in C_GRID]
    t0 = time.time()
    cache = run_fits(name, tasks, keep, fold, y, blocks, block_day, emb_day, jobs, actor, tl)
    cache["fold"] = fold
    n = len(y)
    # Step 1: selection on the full 9-fold OOF
    oof = {c: oof_scores(cache, c, set(), folds, n) for c in CONFIGS}
    ws_all = {c: within_site_auroc(y[keep], oof[c][keep], site[keep]) for c in CONFIGS}
    chosen = select(ws_all)
    # Step 3: nested estimate
    nested = np.full(n, np.nan)
    per_outer = {}
    for k in folds:
        inner_keep = keep & (fold != k)
        inner = {c: oof_scores(cache, c, {k}, folds, n) for c in CONFIGS}
        ws_in = {c: within_site_auroc(y[inner_keep], inner[c][inner_keep], site[inner_keep]) for c in CONFIGS}
        ck = select(ws_in)
        per_outer[k] = {"chosen": cfg_name(ck), "inner_auroc_ws": round(ws_in[ck], 4)}
        fam, agg, C = ck
        te, pb_by_day, pd_day = cache[(frozenset([k]), C)]
        sc = aggregate(pb_by_day, agg) if fam == "block" else pd_day
        nested[te] = sc
    return {"name": name, "folds": folds, "fits": len(tasks), "fit_runtime_s": round(time.time() - t0, 1),
            "oof": oof, "ws_all": ws_all, "chosen": chosen, "nested": nested, "per_outer": per_outer}


def summarise(v, keep, y, s, site, base):
    days = np.flatnonzero(keep)
    yy, gg, ss = y[days], s["dep"].to_numpy()[days], site[days]
    scores = {"final_selected_oof": v["oof"][v["chosen"]][days], "nested_selection": v["nested"][days]}
    scores.update({b: base[b][days] for b in BASELINES + ["site_prior"]})
    pairs = [(m, b) for m in ["nested_selection", "final_selected_oof"] for b in BASELINES + ["site_prior"]]
    ci, dci = boot_ci(yy, scores, gg, pairs)
    ws_ci, ws_dci = boot_ci_ws(yy, scores, gg, ss, pairs)
    r = lambda a: round(float(a), 3) if a is not None else None
    meth = {}
    for k, sc in scores.items():
        meth[k] = {"auroc_ws": r(within_site_auroc(yy, sc, ss)), "auroc_ws_ci95": ws_ci[k],
                   "auroc": r(safe_auc(yy, sc)), "auroc_ci95": ci[k],
                   "per_site": {st: r(safe_auc(yy[ss == st], sc[ss == st])) for st in sorted(np.unique(ss))},
                   "site_id_probe_auroc": r(abs(safe_auc((ss == "sb02").astype(int), sc) - 0.5) + 0.5)}
    return {"days": int(len(days)), "present": int(yy.sum()), "absent": int(len(yy) - yy.sum()),
            "deployments": int(len(np.unique(gg))),
            "site_id_from_labels_auroc": r(abs(safe_auc((ss == "sb02").astype(int), yy) - 0.5) + 0.5),
            "methods": meth, "paired_differences_ws": ws_dci, "paired_differences_pooled": dci,
            "all_configs_oof_auroc_ws": {cfg_name(c): round(a, 4) for c, a in v["ws_all"].items()},
            "selected": cfg_name(v["chosen"]), "per_outer_fold": v["per_outer"],
            "fits": v["fits"], "fit_runtime_s": v["fit_runtime_s"]}


def rel(p):
    p = Path(p)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(actor, jobs):
    t0 = time.time()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    s, band, emb_day, blocks, block_day, zs = load()
    y, fold, site = s["label"].to_numpy(), s["deployment"].to_numpy(), s["site"].to_numpy()
    base_csv = pd.read_csv(CV11 / "oof_scores.csv", dtype={"site": str, "deployment": str, "date": str})
    if not (base_csv[["site", "deployment", "date"]].to_numpy() == s[["site", "deployment", "date"]].to_numpy()).all():
        raise SystemExit("cv_v1.1 oof_scores.csv rows do not match the train/val day order")
    variants = {"primary": np.ones(len(s), bool), "S1_excl_sb01_02": (s["dep"] != "sb01_02").to_numpy()}
    results = {"git_commit": commit, "protocol": "docs/analysis/final-model-protocol.md (P1-P7 confirmed)",
               "scope": "train/val only", "seed": SEED, "tie_tol": TIE_TOL, "configs": [cfg_name(c) for c in CONFIGS],
               "baseline_scores": f"{CV11.relative_to(ROOT)}/oof_scores.csv sha256 {sha(CV11 / 'oof_scores.csv')}"}
    tl = TempLogger()
    tl.t.start()
    log_event(actor, "final_model_run_start", {"git_commit": commit, "jobs": jobs, "tctl_c": read_tctl(),
                                               "pause_c": PAUSE_C, "resume_c": RESUME_C,
                                               "checkpoints_already": len(read_manifest()), "scope": "train/val only"})
    out = {}
    for name, keep in variants.items():
        base = {b: base_csv[f"{name}:{b}"].to_numpy() for b in BASELINES + ["site_prior"]}
        v = run_variant(name, keep, s, y, fold, site, blocks, block_day, emb_day, jobs, actor, tl)
        out[name] = v
        results[name] = summarise(v, keep, y, s, site, base)
    chosen = out["primary"]["chosen"]
    fam, agg, C = chosen
    # P4 thresholds: final model from its pooled 9-fold OOF scores (Primary); baselines from cv_v1.1 OOF scores
    thr = float(best_threshold(y, out["primary"]["oof"][chosen]))
    base_thr = {b: float(best_threshold(y, base_csv[f"primary:{b}"].to_numpy())) for b in BASELINES}
    # Final fits on all 300 train/val days (Primary)
    thermal_gate(tl, actor)
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        model = lr(C).fit(blocks, y[block_day]) if fam == "block" else lr(C).fit(emb_day, y)
    final_diag = {"variant": "final_fit", "heldout": [], "C": C, "file": "final_v1.joblib",
                  "n_iter_block": int(model[-1].n_iter_[0]), "n_iter_day": 0, "max_iter": int(model[-1].max_iter),
                  "warnings": sorted({f"{x.category.__name__}: {str(x.message)[:200]}" for x in w
                                      if not issubclass(x.category, (DeprecationWarning, FutureWarning))}),
                  "finite": True}
    check_fit(final_diag, actor)
    amb_C = pick_C(band, y, fold)
    ambient = lr(amb_C).fit(band, y)
    month_rate = pd.Series(y).groupby(s["month"].to_numpy()).mean().to_dict()
    site_rate = pd.Series(y).groupby(site).mean().to_dict()
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "family": fam, "aggregation": agg, "C": C, "day_threshold": thr,
                 "ambient_noise": {"model": ambient, "C": amb_C, "threshold": base_thr["ambient_noise"]},
                 "month_prior": {"rate": month_rate, "overall": float(y.mean()), "threshold": base_thr["month_prior"]},
                 "zero_shot_primary": {"threshold": base_thr["zero_shot_primary"]},
                 "site_prior": {"rate": site_rate, "overall": float(y.mean())},
                 "git_commit": commit}, MODEL_PATH)
    feat = {f.name: sha(f) for f in sorted(SCORES.glob("*.npz"))
            if f.stem in set(s["site"] + "_" + s["deployment"] + "_" + s["date"])}
    spec = {"selected": cfg_name(chosen), "family": fam, "aggregation": agg, "C": C,
            "features": "1280-d block embedding (5-min blocks), standardised" if fam == "block"
                        else "day-mean 1280-d block embedding, standardised",
            "weak_labels": "every block takes its day's label" if fam == "block" else None,
            "day_threshold": thr, "day_threshold_rule": "max balanced accuracy on pooled 9-fold OOF (Primary)",
            "window_threshold": "not applicable (plan_clarification 2026-11-11, protocol P4)",
            "baseline_thresholds": base_thr, "ambient_noise_C": amb_C, "month_prior_rate": month_rate,
            "site_prior_rate": site_rate,
            "trained_on": {"days": int(len(y)), "present": int(y.sum()), "sample_days_sha256": sha(ROOT / "data" / "sample_days.csv"),
                           "feature_files": len(feat), "feature_files_sha256": hashlib.sha256(
                               json.dumps(feat, sort_keys=True).encode()).hexdigest()},
            "artefact": rel(MODEL_PATH), "artefact_sha256": sha(MODEL_PATH),
            "git_commit": commit, "python": platform.python_version(), "sklearn": sklearn.__version__,
            "numpy": np.__version__, "joblib": joblib.__version__,
            "deterministic": "L2 logistic regression (lbfgs); no random seed involved, so the 5-seed rule does not apply",
            "S1_selected": cfg_name(out["S1_excl_sb01_02"]["chosen"])}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "spec.json").write_text(json.dumps(spec, indent=1, default=str))
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=1, default=str))
    (OUT_DIR / "feature_files_sha256.json").write_text(json.dumps(feat, indent=1))
    pd.concat([s[["site", "deployment", "date", "label"]],
               pd.DataFrame({f"{n}:{k}": a for n, v in out.items()
                             for k, a in [("final_selected_oof", v["oof"][v["chosen"]]), ("nested_selection", v["nested"])]})],
              axis=1).to_csv(OUT_DIR / "oof_scores.csv", index=False)
    log_event(actor, "final_model_selection", {
        "git_commit": commit, "selected": spec["selected"], "S1_selected": spec["S1_selected"],
        "per_outer_fold_primary": results["primary"]["per_outer_fold"],
        "per_outer_fold_S1": results["S1_excl_sb01_02"]["per_outer_fold"],
        "results_sha256": sha(OUT_DIR / "results.json"), "oof_csv_sha256": sha(OUT_DIR / "oof_scores.csv"),
        "checkpoint_manifest_sha256": sha(MANIFEST), "checkpoints": len(read_manifest()),
        "final_fit_n_iter": final_diag["n_iter_block"],
        "tctl_c": {"max": max(tl.all, default=None), "mean": round(float(np.mean(tl.all)), 1) if tl.all else None,
                   "samples": len(tl.all), "pause_c": PAUSE_C, "log": rel(TEMP_CSV)},
        "runtime_s": round(time.time() - t0, 1), "scope": "train/val only"})
    tl.stop.set()
    log_event(actor, "final_model", {
        "git_commit": commit, "spec": rel(OUT_DIR / "spec.json"),
        "spec_sha256": sha(OUT_DIR / "spec.json"), "artefact": spec["artefact"],
        "artefact_sha256": spec["artefact_sha256"], "selected": spec["selected"], "day_threshold": thr,
        "baseline_thresholds": base_thr, "before": "any Stage A or Stage B release; no test label read"})
    print(json.dumps({"selected": spec["selected"], "S1_selected": spec["S1_selected"], "threshold": thr,
                      "nested_primary": results["primary"]["methods"]["nested_selection"]}, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--jobs", type=int, default=6)
    a = p.parse_args()
    main(a.actor, a.jobs)
