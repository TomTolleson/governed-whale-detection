import numpy as np

from src.cv_eval import bal_acc, best_threshold, boot_idx, loo_fold_threshold_pred


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
