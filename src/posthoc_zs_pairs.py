"""POST-HOC SENSITIVITY CHECK, train/val only. Not part of the pre-specified analysis.

    python -m src.posthoc_zs_pairs --actor <name> [--cv docs/analysis/cv_v1.1]

Baseline 4 is the primary-rule zero-shot model (owner plan_clarification, 2026-11-11). This script adds paired
bootstrap CIs of each embedding model against the zero-shot **top-10** and **max** day rules, which were noticed
as slightly stronger only after results were in. It reads the committed out-of-fold scores (oof_scores.csv) and
uses the same bootstrap functions, seed and resample stream as src.cv_eval. Before writing anything it
reproduces the pre-specified pairs already in results.json, and it stops if any of them differs.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.audit import log_event
from src.cv_eval import AGGS, boot_ci, boot_ci_ws
from src.label_survey import ROOT

MODELS = ["emb_day_lr"] + [f"emb_block_lr_{a}" for a in AGGS]
NEW_BASELINES = ["zero_shot_top10", "zero_shot_max"]
CHECK_BASELINE = "zero_shot_primary"  # already in results.json; reproduced as a check
VARIANTS = {"primary": lambda d: np.ones(len(d), bool), "S1_excl_sb01_02": lambda d: (d["dep"] != "sb01_02").to_numpy()}


def main(actor, cv_dir):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    csv = cv_dir / "oof_scores.csv"
    d = pd.read_csv(csv, dtype={"site": str, "deployment": str, "date": str})
    d["dep"] = d["site"] + "_" + d["deployment"]
    prior = json.loads((cv_dir / "results.json").read_text())
    out = {"label": "post-hoc sensitivity checks, not part of the pre-specified analysis",
           "reason": "owner plan_clarification 2026-11-11: baseline 4 is zero_shot_primary only; the top-10 and max "
                     "rules were noticed as slightly stronger after results were in",
           "git_commit": commit, "input": str(csv.relative_to(ROOT)),
           "input_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(), "reproduction_check": {}}
    for v, mask in VARIANTS.items():
        keep = mask(d)
        y = d["label"].to_numpy()[keep]
        groups = d["dep"].to_numpy()[keep]
        site = d["site"].to_numpy()[keep]
        bases = NEW_BASELINES + [CHECK_BASELINE]
        scores = {k: d[f"{v}:{k}"].to_numpy()[keep] for k in MODELS + bases}
        pairs = [(m, b) for m in MODELS for b in bases]
        _, pooled = boot_ci(y, scores, groups, pairs)
        _, ws = boot_ci_ws(y, scores, groups, site, pairs)
        # Same scores, seed and stream as cv_eval, so the pre-specified pairs must come out identical
        chk = {k: (pooled[k] == prior[v]["paired_differences"][k] and ws[k] == prior[v]["paired_differences_ws"][k])
               for k in pooled if k.endswith(CHECK_BASELINE)}
        out["reproduction_check"][v] = chk
        if not all(chk.values()):
            raise SystemExit(f"reproduction check failed for {v}: {chk}")
        out[v] = {"paired_differences_ws": {k: c for k, c in ws.items() if not k.endswith(CHECK_BASELINE)},
                  "paired_differences_pooled": {k: c for k, c in pooled.items() if not k.endswith(CHECK_BASELINE)}}
    js = cv_dir / "posthoc_zero_shot_pairs.json"
    js.write_text(json.dumps(out, indent=1))
    log_event(actor, "posthoc_analysis", {"label": out["label"], "git_commit": commit, "out": str(js.relative_to(ROOT)),
                                          "sha256": hashlib.sha256(js.read_bytes()).hexdigest(),
                                          "input_sha256": out["input_sha256"], "reproduction_check": "passed",
                                          "scope": "train/val only"})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--cv", default=str(ROOT / "docs" / "analysis" / "cv_v1.1"))
    a = p.parse_args()
    main(a.actor, Path(a.cv).resolve())
