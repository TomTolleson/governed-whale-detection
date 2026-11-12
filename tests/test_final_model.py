import numpy as np

from src.final_model import CONFIGS, TIE_TOL, aggregate, oof_scores, select


def test_select_tie_rule_prefers_small_C_then_block_then_agg_order():
    ws = {c: 0.70 for c in CONFIGS}
    best = ("block", "max", 1.0)
    ws[best] = 0.80
    assert select(ws) == best  # a clear winner wins
    ws[("block", "top3", 1.0)] = 0.80 - TIE_TOL / 2  # tied, same C: agg order mean>top12>top3>max
    assert select(ws) == ("block", "top3", 1.0)
    ws[("day", "day", 0.1)] = 0.80 - TIE_TOL / 2  # tied with smaller C: smallest C first
    assert select(ws) == ("day", "day", 0.1)
    ws[("block", "max", 0.1)] = 0.80 - TIE_TOL / 2  # same C: block before day-mean
    assert select(ws) == ("block", "max", 0.1)
    ws[("block", "mean", 0.001)] = 0.80 - 2 * TIE_TOL  # outside the tolerance: ignored
    assert select(ws) == ("block", "max", 0.1)


def test_oof_scores_uses_fit_that_holds_out_excluded_plus_fold():
    fold = np.array(["1", "1", "2", "2", "3", "3"])
    cache = {"fold": fold}
    # Each fit's "prediction" encodes its held-out set, so we can check which fit was used.
    for h in [frozenset(["1"]), frozenset(["2"]), frozenset(["3"]), frozenset(["1", "2"]),
              frozenset(["1", "3"]), frozenset(["2", "3"])]:
        te = np.flatnonzero(np.isin(fold, list(h)))
        code = float("".join(sorted(h)))
        cache[(h, 1.0)] = (te, [np.array([code])] * len(te), np.full(len(te), code))
    full = oof_scores(cache, ("day", "day", 1.0), set(), ["1", "2", "3"], 6)
    assert list(full) == [1, 1, 2, 2, 3, 3]  # single held-out fits
    inner = oof_scores(cache, ("block", "max", 1.0), {"3"}, ["1", "2", "3"], 6)
    assert list(inner[:4]) == [13, 13, 23, 23] and np.isnan(inner[4:]).all()  # pair fits, outer fold left out


def test_aggregate():
    p = [np.array([0.1, 0.9, 0.5]), np.array([0.2])]
    assert np.allclose(aggregate(p, "max"), [0.9, 0.2])
    assert np.allclose(aggregate(p, "mean"), [0.5, 0.2])
