"""Stratified day samples for the frozen evaluation plan (docs/eval_plan.md, section 2).

    python -m src.sample_days --actor <name>

Writes data/sample_days.csv (train/val, test_T, test_S) and data/pilot_days.csv (60 days drawn from
the sampled train/val days). Same fraction per deployment x label cell; largest-remainder rounding.
"""

import argparse
import hashlib

import numpy as np
import pandas as pd

from src.audit import log_event
from src.label_survey import ROOT
from src.split_candidates import MONTH_SEASON

SEED = 20261109
TARGETS = {"trainval": 300, "test_T": 150, "test_S": 250}
PILOT_N = 60
SAMPLE_PATH = ROOT / "data" / "sample_days.csv"
PILOT_PATH = ROOT / "data" / "pilot_days.csv"
COLS = ["split", "site", "deployment", "date", "label", "season"]


def eligible():
    df = pd.read_csv(ROOT / "data" / "day_table.csv", dtype={"deployment": str})
    df = df[df.eligible].copy()
    df["season"] = pd.to_datetime(df.date).dt.month.map(MONTH_SEASON)
    dep = df.deployment.astype(int)
    s12 = df.site.isin(["sb01", "sb02"])
    df["split"] = np.select([s12 & (dep <= 9), s12 & (dep >= 10), df.site == "sb03"],
                            ["trainval", "test_T", "test_S"], default="")
    return df[df.split != ""]


def allocate(sizes: pd.Series, n: int) -> pd.Series:
    """Largest-remainder allocation of n proportional to sizes (ties broken by cell order)."""
    exact = sizes * n / sizes.sum()
    base = np.floor(exact).astype(int)
    rem = n - base.sum()
    order = (exact - base).sort_values(ascending=False, kind="stable").index[:rem]
    base[order] += 1
    return base


def stratified(pool: pd.DataFrame, n: int, rng) -> pd.DataFrame:
    pool = pool.sort_values(["site", "deployment", "label", "date"]).reset_index(drop=True)
    keys = ["site", "deployment", "label"]
    counts = allocate(pool.groupby(keys).size(), n)
    parts = []
    for key, k in counts.items():
        cell = pool[(pool[keys] == pd.Series(key, index=keys)).all(axis=1)]
        parts.append(cell.iloc[np.sort(rng.choice(len(cell), size=k, replace=False))])
    return pd.concat(parts)


def run(actor):
    rng = np.random.default_rng(SEED)
    df = eligible()
    sample = pd.concat([stratified(df[df.split == s], n, rng) for s, n in TARGETS.items()])[COLS]
    sample.to_csv(SAMPLE_PATH, index=False)
    pilot = stratified(sample[sample.split == "trainval"], PILOT_N, rng)[COLS]
    pilot.to_csv(PILOT_PATH, index=False)

    def info(path, frame):
        return {"dest": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": len(frame),
                "by_split": {s: {"days": int(len(g)), "present": int(g.label.sum()),
                                 "absent": int((g.label == 0).sum())} for s, g in frame.groupby("split")}}

    log_event(actor, "write_sample_days", {**info(SAMPLE_PATH, sample), "seed": SEED, "targets": TARGETS})
    log_event(actor, "write_pilot_days", {**info(PILOT_PATH, pilot), "seed": SEED,
                                          "drawn_from": "sampled trainval days", "n": PILOT_N})
    for s, g in sample.groupby("split"):
        print(s, len(g), "present", int(g.label.sum()), "absent", int((g.label == 0).sum()),
              dict(g.season.value_counts().sort_index()))
    print("pilot", len(pilot), "present", int(pilot.label.sum()), "deployments",
          pilot.site.str.cat(pilot.deployment, "_").nunique())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", required=True)
    run(ap.parse_args().actor)
