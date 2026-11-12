import numpy as np
import pandas as pd

from src.drift_report import report


def _feat(deps, zf, band_shift, rng):
    rows, emb = [], []
    for d in deps:
        for _ in range(6):
            rows.append({"dep": d, "zero_fraction": zf.get(d, 0.0),
                         **{f"med_{i}": -60 + band_shift.get(d, 0) + rng.normal(0, .1) for i in range(2)},
                         **{f"p90_{i}": -50 + band_shift.get(d, 0) for i in range(2)}})
            emb.append(rng.normal(0, 1, 8) + (hash(d) % 5))
    return pd.DataFrame(rows), np.array(emb)


def test_flags_fire_only_beyond_cuts():
    rng = np.random.default_rng(0)
    ref, remb = _feat(["a", "b", "c"], {}, {"b": 2.0}, rng)
    tgt, temb = _feat(["x", "y", "z"], {"y": 0.02, "z": 0.005}, {"x": 8.5, "z": 7.9}, rng)
    mn = {d: rng.random(50) for d in ["a", "b", "c", "x", "y", "z"]}
    r = report(ref, remb, {k: mn[k] for k in "abc"}, tgt, temb, {k: mn[k] for k in "xyz"}, ["lo", "hi"])
    assert r["flags"]["sb01_02_equivalent"] == ["y"]  # 0.02 > 0.01; 0.005 is not
    # reference range is about [-60, -58]; x at -51.5 is ~6.5 dB above it, z at -52.1 ~5.9 dB: only x flags
    assert r["flags"]["band_flag"] == ["x"]
    assert set(r["deployments"]) == {"x", "y", "z"}
