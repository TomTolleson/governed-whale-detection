"""Scratch dry run of src/test_eval.py with FAKE labels on NON-TEST data (no test day is read or touched).

    python -m tools.dryrun_test_eval <scratch_dir>

- Train/val feature files (data/scores/v2) are copied into <scratch>/v2_test under fake test keys:
  sb01/sb02 deployments 01-03 -> "test_T" deployments 10-12 (same sites);
  sb02 deployments 04-09 -> "test_S" sb03 04-09; sb01 deployments 07-09 -> "test_S" sb03 10-12.
- Labels are fake (seeded). Train/val labels are never read: data/sample_days.csv and the cv_v1.1 OOF file
  are read here without their label columns.
- Every pandas.read_csv call made by src/test_eval.py is recorded, to show that a label column is read only
  after `stage_b_release` is in the log, and never in a refused run.
- All audit entries go to a scratch log. The real audit_log.jsonl is hashed before and after and must not change.
- Scenarios: random labels (expect AUROC near 0.5), known-answer labels (expect final-model AUROC 1.0),
  independent recomputation of every score and the headline AUROC, QA exclusion and concentration,
  and the refusal paths.
Writes <scratch>/dryrun_summary.json and prints it.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import src.test_eval as te
from src.audit import DEFAULT_LOG, log_event
from src.cv_eval import AGGS, within_site_auroc
from src.label_survey import ROOT
from src.pilot_review import primary_day_score

SEED = 20261113
sha = te.sha
READS = []
_read_csv = pd.read_csv


def tracked_read_csv(path, *a, **k):
    df = _read_csv(path, *a, **k)
    if "label" in df.columns:
        released = any(json.loads(l)["action"] == "stage_b_release" for l in open(CURRENT_LOG[0]) if l.strip())
        READS.append({"file": str(path), "label_column": True, "stage_b_release_already_logged": released})
    return df


CURRENT_LOG = [None]


def build(scratch):
    src_dir = ROOT / "data" / "scores" / "v2"
    days = pd.read_csv(ROOT / "data" / "sample_days.csv", dtype={"deployment": str},
                       usecols=["split", "site", "deployment", "date"])
    tv = days[days["split"] == "trainval"].reset_index(drop=True)
    rows = []
    for r in tv.itertuples():
        dep = int(r.deployment)
        if dep <= 3:
            new = ("test_T", r.site, f"{dep + 9:02d}")
        elif r.site == "sb02":
            new = ("test_S", "sb03", f"{dep:02d}")
        elif dep >= 7:
            new = ("test_S", "sb03", f"{dep + 3:02d}")
        else:
            continue
        rows.append({"split": new[0], "site": new[1], "deployment": new[2], "date": r.date,
                     "orig": f"{r.site}_{r.deployment}_{r.date}"})
    fake = pd.DataFrame(rows)
    fake["key"] = fake["site"] + "_" + fake["deployment"] + "_" + fake["date"]
    assert fake["key"].is_unique
    test_dir = scratch / "v2_test"
    test_dir.mkdir(parents=True)
    for r in fake.itertuples():
        shutil.copyfile(src_dir / f"{r.orig}.npz", test_dir / f"{r.key}.npz")  # copies, never links
    return fake, test_dir


def write_log(path, fake, test_dir, freeze_commit=True, drift_splits=("test_T", "test_S"), exclusions=(),
              equivalent=(), fm_override=None):
    real = te.audit_entries(DEFAULT_LOG)
    path.unlink(missing_ok=True)
    fm = {**[e for e in real if e["action"] == "final_model"][-1]["details"], **(fm_override or {})}
    log_event("dryrun", "final_model", fm, path)
    for e in real:
        if e["action"] == "eval_freeze":
            log_event("dryrun", "eval_freeze", e["details"], path)
    if freeze_commit:  # the train/val features carry their scoring commit, not a freeze commit
        with np.load(next(test_dir.glob("*.npz"))) as z:
            log_event("dryrun", "eval_freeze", {"commit": str(z["git_commit"]), "note": "dry run only"}, path)
    for s in drift_splits:
        log_event("dryrun", "drift_report", {"mode": f"Stage A drift report, {s} (no labels read)",
                                             "flags": {"sb01_02_equivalent": list(equivalent)}}, path)
    for r in fake.itertuples():
        f = test_dir / f"{r.key}.npz"
        log_event("dryrun", "score_day", {"day": r.key, "npz": f"data/scores/v2_test/{r.key}.npz",
                                          "sha256": sha(f)}, path)
    for k in exclusions:
        log_event("dryrun", "qa_exclusion", {"day": k, "reason": "dry run"}, path)


def run(scratch, name, fake, labels, test_dir, approval="DRY RUN - fake labels", spec=None, tamper=None,
        **log_kw):
    """One test_eval.main call against scratch copies. `tamper(test_dir)` runs after the log is written."""
    d = scratch / name
    d.mkdir()
    csv = d / "days.csv"
    fake.assign(label=labels)[["split", "site", "deployment", "date", "label"]].to_csv(csv, index=False)
    log = d / "audit.jsonl"
    write_log(log, fake, test_dir, **log_kw)
    undo = tamper(test_dir) if tamper else None
    real_spec = te.SPEC
    te.DAYS_CSV, te.TEST_DIR, te.SPEC = csv, test_dir, spec or real_spec
    CURRENT_LOG[0] = log
    n0 = len(READS)
    pd.read_csv = te.pd.read_csv = tracked_read_csv
    try:
        te.main("dryrun", approval, out_dir=d / "out", log=log)
        res = json.loads((d / "out" / "results.json").read_text())
    except SystemExit as e:
        res = {"refused": str(e)[:300]}
    finally:
        pd.read_csv = te.pd.read_csv = _read_csv
        te.SPEC = real_spec
        if undo:
            undo()
    entries = [json.loads(l) for l in open(log) if l.strip()]
    res["_label_reads"] = READS[n0:]
    res["_stage_b_release_logged"] = any(e["action"] == "stage_b_release" for e in entries)
    res["_label_field_in_scratch_log"] = any('"label"' in json.dumps(e) for e in entries)
    return res


def main(scratch):
    scratch = Path(scratch)
    if scratch.exists():
        raise SystemExit(f"{scratch} exists; use a fresh directory")
    real_log_sha = sha(DEFAULT_LOG)
    fake, test_dir = build(scratch)
    rng = np.random.default_rng(SEED)
    out = {"days": {s: int((fake["split"] == s).sum()) for s in ["test_T", "test_S"]}, "checks": {}}
    chk = out["checks"]

    # Independent scores, computed here without test_eval code paths.
    m = joblib.load(ROOT / json.loads(te.SPEC.read_text())["artefact"])
    ind = {}
    for r in fake.itertuples():
        with np.load(test_dir / f"{r.key}.npz") as z:
            e = z["block_emb"].astype(np.float32)
            b = z["block_band_db"]
            ind[r.key] = (float(AGGS[m["aggregation"]](m["model"].predict_proba(e)[:, 1])),
                          float(m["ambient_noise"]["model"].predict_proba(
                              np.r_[np.median(b, 0), np.percentile(b, 90, 0)][None])[0, 1]),
                          float(primary_day_score(z["window_start_s"], z["humpback"].astype(np.float64))))
    fm_score = fake["key"].map(lambda k: ind[k][0]).to_numpy()

    # 1. Random labels.
    y_rand = rng.integers(0, 2, len(fake))
    r1 = run(scratch, "random", fake, y_rand, test_dir)
    csv = pd.read_csv(scratch / "random" / "out" / "test_day_scores.csv", dtype={"deployment": str})
    csv["key"] = csv["site"] + "_" + csv["deployment"] + "_" + csv["date"]
    diffs = {c: float(np.max(np.abs(csv[c].to_numpy() - csv["key"].map(lambda k: ind[k][i]).to_numpy())))
             for i, c in enumerate(["final_model", "ambient_noise", "zero_shot_primary"])}
    chk["scores_match_independent_recompute_max_abs_diff"] = diffs
    # zero-shot cross-check against the committed cv_v1.1 OOF file (zero-shot is not fitted)
    oof = pd.read_csv(ROOT / "docs/analysis/cv_v1.1/oof_scores.csv", dtype={"deployment": str},
                      usecols=["site", "deployment", "date", "primary:zero_shot_primary"])
    oof["orig"] = oof["site"] + "_" + oof["deployment"] + "_" + oof["date"]
    zs = fake.merge(oof[["orig", "primary:zero_shot_primary"]], on="orig")
    chk["zero_shot_matches_cv_v1_1_max_abs_diff"] = float(np.max(np.abs(
        zs["primary:zero_shot_primary"].to_numpy() - zs["key"].map(lambda k: ind[k][2]).to_numpy())))
    hl = {}
    for s in ["test_T", "test_S"]:
        msk = (csv["split"] == s).to_numpy()
        hl[s] = {"test_eval": r1["splits"][s]["primary"]["methods"]["final_model"]["auroc_ws"],
                 "independent": round(float(within_site_auroc(csv["label"].to_numpy()[msk],
                                                               csv["final_model"].to_numpy()[msk],
                                                               csv["site"].to_numpy()[msk])), 3),
                 "pooled_independent": round(float(roc_auc_score(csv["label"][msk], csv["final_model"][msk])), 3),
                 "pooled_test_eval": r1["splits"][s]["primary"]["methods"]["final_model"]["auroc"],
                 "improves": r1["splits"][s]["primary"]["improvement_claim"]["improves"]}
    chk["random_labels"] = hl
    chk["headline_split"] = r1["headline_split"]
    chk["zero_flag_variant_present"] = {s: "zero_flag_days_excluded" in r1["splits"][s] for s in r1["splits"]}

    # 2. Known answer: label = final-model score >= its median within each split -> AUROC 1.0.
    y_known = np.zeros(len(fake), int)
    for s in ["test_T", "test_S"]:
        msk = (fake["split"] == s).to_numpy()
        y_known[msk] = (fm_score[msk] >= np.median(fm_score[msk])).astype(int)
    r2 = run(scratch, "known_answer", fake, y_known, test_dir)
    chk["known_answer"] = {s: {"auroc_ws": r2["splits"][s]["primary"]["methods"]["final_model"]["auroc_ws"],
                               "claim": r2["splits"][s]["primary"]["improvement_claim"]} for s in r2["splits"]}

    # 3. QA exclusions, concentration flag and sb01_02-equivalent variant.
    s_keys = fake[fake["deployment"] == "05"]["key"].tolist()
    excl = s_keys[:3] + [fake[fake["split"] == "test_T"]["key"].iloc[0]]
    r3 = run(scratch, "exclusions", fake, y_rand, test_dir, exclusions=excl, equivalent=["sb03_06"])
    chk["exclusions"] = {"listed": sorted(r3["qa_excluded_days"]), "expected": sorted(excl),
                         "concentration": r3["qa_exclusion_concentration"],
                         "days_after": r3["splits"]["test_S"]["primary"]["days"],
                         "sb01_02_equivalent_variant": "sb01_02_equivalent_excluded" in r3["splits"]["test_S"]}

    # 4. Refusal paths: one tamper per check, on scratch copies only. Each must refuse with no label read
    #    and no stage_b_release logged.
    spec_real = json.loads(te.SPEC.read_text())
    art_copy = scratch / "tampered_artefact.joblib"
    art_copy.write_bytes((ROOT / spec_real["artefact"]).read_bytes() + b"x")
    spec_art = scratch / "spec_points_to_tampered_artefact.json"
    spec_art.write_text(json.dumps({**spec_real, "artefact": str(art_copy)}, indent=1))
    spec_mod = scratch / "spec_modified.json"
    spec_mod.write_text(json.dumps({**spec_real, "day_threshold": 0.5}, indent=1))
    victim_key = fake["key"].iloc[5]

    def tamper_npz(test_dir):
        f = test_dir / f"{victim_key}.npz"
        orig = f.read_bytes()
        f.write_bytes(orig + b"x")
        return lambda: f.write_bytes(orig)

    ref = {
        "artefact_tampered": run(scratch, "ref_artefact", fake, y_rand, test_dir, spec=spec_art,
                                 fm_override={"spec_sha256": sha(spec_art)}),
        "spec_tampered": run(scratch, "ref_spec", fake, y_rand, test_dir, spec=spec_mod),
        "drift_report_missing_test_S": run(scratch, "ref_drift", fake, y_rand, test_dir, drift_splits=("test_T",)),
        "score_file_tampered": run(scratch, "ref_npz", fake, y_rand, test_dir, tamper=tamper_npz),
        "features_not_freeze_tag_commit": run(scratch, "ref_stamp", fake, y_rand, test_dir, freeze_commit=False),
        "stage_b_release_missing": run(scratch, "ref_no_release", fake, y_rand, test_dir, approval="  "),
    }
    chk["refusals"] = {k: {"refused": v.get("refused"), "label_columns_read": len(v["_label_reads"]),
                           "stage_b_release_logged": v["_stage_b_release_logged"]} for k, v in ref.items()}
    happy = {"random": r1, "known_answer": r2, "exclusions": r3}
    chk["label_reads_in_completed_runs"] = {k: v["_label_reads"] for k, v in happy.items()}
    chk["label_field_in_any_scratch_log"] = any(v["_label_field_in_scratch_log"] for v in [*happy.values(), *ref.values()])
    chk["npz_restored_after_tamper_test"] = sha(test_dir / f"{victim_key}.npz") == sha(
        ROOT / "data" / "scores" / "v2" / f"{fake.set_index('key').loc[victim_key, 'orig']}.npz")
    chk["real_audit_log_unchanged"] = sha(DEFAULT_LOG) == real_log_sha
    ok = (all(v < 1e-9 for v in diffs.values()) and chk["zero_shot_matches_cv_v1_1_max_abs_diff"] < 1e-6
          and all(abs(h["test_eval"] - h["independent"]) < 1e-9 and abs(h["pooled_test_eval"] - h["pooled_independent"]) < 1e-9
                  for h in hl.values())
          and all(v["auroc_ws"] == 1.0 for v in chk["known_answer"].values())
          and chk["exclusions"]["listed"] == chk["exclusions"]["expected"]
          and "sb03_05" in r3["qa_exclusion_concentration"]["test_S"]["concentrated"]
          and chk["exclusions"]["sb01_02_equivalent_variant"]
          and all(v["refused"] and not v["stage_b_release_logged"] and v["label_columns_read"] == 0
                  for v in chk["refusals"].values())
          and all(len(r) == 1 and r[0]["stage_b_release_already_logged"]
                  for r in chk["label_reads_in_completed_runs"].values())
          and not chk["label_field_in_any_scratch_log"] and chk["npz_restored_after_tamper_test"]
          and chk["real_audit_log_unchanged"])
    out["all_checks_pass"] = bool(ok)
    out["note"] = ("Dry-run metrics are MEANINGLESS as performance: the labels are fake, and the final model was "
                   "trained on these very train/val features. The run checks plumbing, recomputation and refusals only.")
    out["test_eval_sha256"] = sha(ROOT / "src" / "test_eval.py")
    (scratch / "dryrun_summary.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) else 1)
