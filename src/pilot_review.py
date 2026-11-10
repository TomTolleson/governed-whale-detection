"""EXPLORATORY, TRAIN/VAL DAYS ONLY, NO MODEL OR THRESHOLD CHOICES MADE.

    python -m src.pilot_review [--dir data/pilot] [--days data/pilot_days.csv] [--csv out.csv]

Compares zero-shot day scores with labels on the 60 pilot days (train/val) and checks completeness
against docs/eval_plan.md. The results are descriptive. Nothing here is used to pick a model, a threshold,
features or a day rule. Test days are refused.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.label_survey import ROOT

SPAN = 600.0  # eval plan section 4.1: 10-minute span


def auroc(y, s):
    """Mann-Whitney AUROC with average ranks for ties; label 1 is the positive class."""
    y, r = np.asarray(y), pd.Series(s).rank().to_numpy()
    n1 = y.sum()
    n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def average_precision(y, s):
    y, s = np.asarray(y), np.asarray(s)
    y = y[np.argsort(-s, kind="stable")]
    prec = np.cumsum(y) / np.arange(1, len(y) + 1)
    return (prec * y).sum() / y.sum()


def primary_day_score(t, s, span=SPAN):
    """Largest k such that some span holds >= 3 windows scoring >= k (eval plan section 4.1).

    t: window start times (s, sorted). The span is (t_i - span, t_i], measured on real start times.
    """
    best, j = 0.0, 0
    for i in range(len(t)):
        while t[j] <= t[i] - span:
            j += 1
        if i - j + 1 >= 3:
            best = max(best, np.partition(s[j:i + 1], -3)[-3])
    return best


def review(pilot_dir: Path, days_csv: Path) -> tuple[dict, pd.DataFrame]:
    days = pd.read_csv(days_csv, dtype={"deployment": str})
    if set(days["split"]) != {"trainval"}:
        raise SystemExit("day list contains non-train/val days; refusing")
    rep = json.loads((pilot_dir / "pilot_report.json").read_text())
    rows = []
    for d in days.itertuples():
        day = f"{d.site}_{d.deployment}_{d.date}"
        z = np.load(pilot_dir / f"{day}.npz")
        t, hb = z["window_start_s"], z["humpback"].astype(np.float64)
        rows.append(dict(day=day, site=d.site, deployment=d.deployment, season=d.season, label=d.label,
                         hours=len(t) * 5 / 3600, blocks=len(z["block_start_s"]),
                         emb_finite=bool(np.isfinite(z["block_emb"].astype(np.float32)).all()),
                         primary=primary_day_score(t, hb), max=hb.max(), top10=np.sort(hb)[-10:].mean()))
    df = pd.DataFrame(rows)
    out = {"days": len(df), "present": int(df.label.sum()), "absent": int((1 - df.label).sum()),
           "flagged": {r["day"]: r["flags"] for r in rep["days"] if r["flags"]},
           "hours_min": round(df.hours.min(), 3), "blocks_min": int(df.blocks.min()),
           "emb_all_finite": bool(df.emb_finite.all()), "absent_prevalence": round(1 - df.label.mean(), 3),
           "scores": {}}
    for c in ["primary", "max", "top10"]:
        out["scores"][c] = {"auroc": round(auroc(df.label, df[c]), 3),
                            "pr_auc_absent_pos": round(average_precision(1 - df.label, -df[c]), 3),
                            "median_present": round(df.loc[df.label == 1, c].median(), 3),
                            "median_absent": round(df.loc[df.label == 0, c].median(), 3)}
    return out, df


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default=str(ROOT / "data" / "pilot"))
    p.add_argument("--days", default=str(ROOT / "data" / "pilot_days.csv"))
    p.add_argument("--csv", help="optional per-day output CSV")
    a = p.parse_args()
    summary, table = review(Path(a.dir), Path(a.days))
    print(json.dumps(summary, indent=1))
    if a.csv:
        table.to_csv(a.csv, index=False)
