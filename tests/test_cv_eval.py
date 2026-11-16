import numpy as np

from sklearn.metrics import roc_auc_score

from src.cv_eval import bal_acc, best_threshold, boot_idx, loo_fold_threshold_pred, within_site_auroc


def test_within_site_auroc_ignores_site_offset_and_weights_pairs():
    rng = np.random.default_rng(1)
    y = np.array([1] * 6 + [0] * 5 + [1] * 8 + [0] * 5)
    site = np.array(["a"] * 11 + ["b"] * 13)
    s = rng.random(len(y))
    a, b = site == "a", site == "b"
    expected = (6 * 5 * roc_auc_score(y[a], s[a]) + 8 * 5 * roc_auc_score(y[b], s[b])) / (6 * 5 + 8 * 5)
    assert np.isclose(within_site_auroc(y, s, site), expected)
    # adding a constant per site never changes it (the site shortcut cannot raise it)
    assert np.isclose(within_site_auroc(y, s + 10 * b, site), expected)
    # a score that is constant within each site scores exactly 0.5
    assert within_site_auroc(y, b.astype(float), site) == 0.5


def test_within_site_auroc_min_n_rule():
    y = np.array([1] * 6 + [0] * 5 + [1] * 8 + [0] * 4)  # site b has only 4 absent days
    site = np.array(["a"] * 11 + ["b"] * 12)
    s = np.arange(len(y), dtype=float)
    a = site == "a"
    assert np.isclose(within_site_auroc(y, s, site), roc_auc_score(y[a], s[a]))
    assert within_site_auroc(y[~a], s[~a], site[~a]) is None


def test_best_threshold_and_bal_acc():
    y = np.array([0, 0, 1, 1])
    s = np.array([0.1, 0.2, 0.8, 0.9])
    assert best_threshold(y, s) == 0.8
    assert bal_acc(y, s >= 0.8) == 1.0


def test_boot_idx_keeps_whole_deployments_and_two_classes():
    groups = np.array(["a", "a", "b", "b", "c"])
    y = np.array([1, 1, 0, 0, 1])
    rng = np.random.default_rng(0)
    for _ in range(50):
        i = boot_idx(groups, rng, y)
        assert 0 < y[i].sum() < len(i)
        for g in np.unique(groups[i]):  # a chosen deployment brings all its days
            assert (groups[i] == g).sum() % (groups == g).sum() == 0


def test_loo_threshold_never_uses_own_fold():
    y = np.array([0, 1, 0, 1])
    v = np.array([0.1, 0.9, 0.6, 0.7])
    fold = np.array(["1", "1", "2", "2"])
    pred = loo_fold_threshold_pred(y, v, fold)
    assert pred[3] == (0.7 >= best_threshold(y[:2], v[:2]))
