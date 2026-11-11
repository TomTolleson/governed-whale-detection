from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.pilot import (BANDS, SR, WIN, band_power_np, day_pieces, plan_tasks, select_days, trim_target,
                       zeros_by_day)

UTC = timezone.utc
NAMES = [b[0] for b in BANDS]


def tone(f, amp=0.5):
    t = np.arange(WIN) / SR
    return (amp * np.sin(2 * np.pi * f * t))[None]


def test_band_power_tone_lands_in_its_band():
    p = band_power_np(tone(1000.0))[0]
    assert p[NAMES.index("800-1600")] == pytest.approx(0.125, rel=1e-3)  # mean square of 0.5 sin = 0.125
    others = [i for i, n in enumerate(NAMES) if n != "800-1600"]
    assert p[others].max() < 1e-6


def test_band_power_low_band_and_combined_band():
    p = band_power_np(tone(70.0, 1.0))[0]
    assert p[NAMES.index("50-100")] == pytest.approx(0.5, rel=1e-3)
    assert p[NAMES.index("50-500")] == pytest.approx(0.5, rel=1e-3)


def test_band_power_white_noise_total():
    x = np.random.default_rng(0).normal(0, 0.1, (4, WIN))
    p = band_power_np(x)
    octaves = p[:, : NAMES.index("6400-12000") + 1].sum(1)
    # white noise spreads 0.01 evenly over 0-12 kHz; the octaves cover 50-12000 Hz
    assert octaves.mean() == pytest.approx(0.01 * 11950 / 12000, rel=0.01)


def test_band_edges_contiguous_and_below_nyquist():
    octs = [b for b in BANDS if b[0] != "50-500"]
    assert octs[0][1] == 50 and octs[-1][2] == SR / 2
    assert all(a[2] == b[1] for a, b in zip(octs, octs[1:]))


def test_trim_target():
    assert trim_target(1000, 0.04) == (960, True)       # overlap: cut at next start, contiguous
    assert trim_target(960, 0.04) == (960, True)        # exact fit
    assert trim_target(959, 0.04) == (959, False)       # short by one sample: real gap, not bridged
    assert trim_target(500, None) == (500, False)       # last file


def test_day_pieces_split_at_midnight():
    t0 = datetime(2019, 1, 1, 23, 59, 57, 500000, tzinfo=UTC)
    n = 10 * SR
    p = list(day_pieces(t0, n))
    assert p[0] == ("2019-01-01", 86397.5, 0, round(2.5 * SR))
    assert p[1] == ("2019-01-02", 0.0, round(2.5 * SR), n)


def test_day_pieces_single_day():
    t0 = datetime(2019, 1, 1, 6, tzinfo=UTC)
    assert list(day_pieces(t0, 3 * SR)) == [("2019-01-01", 6 * 3600.0, 0, 3 * SR)]


def test_zeros_by_day():
    start = datetime(2019, 1, 1, 23, 59, 58, tzinfo=UTC)
    out = zeros_by_day(start, np.array([1, 2, 3, 4]), np.array([10, 10, 10, 10]))
    assert out["2019-01-01"] == [3, 20] and out["2019-01-02"] == [7, 20]


def test_plan_tasks_links_neighbours_and_days():
    listing = {"sb01_01": [["SanctSound_SB01_01_x_20190101T180000Z.flac", 1],
                           ["SanctSound_SB01_01_x_20190102T000000Z.flac", 1],
                           ["SanctSound_SB01_01_x_20190102T060000Z.flac", 1],
                           ["SanctSound_SB01_01_x_20190103T060000Z.flac", 1]]}
    days = pd.DataFrame({"split": ["trainval"], "site": ["sb01"], "deployment": ["01"], "date": ["2019-01-02"]})
    tasks = plan_tasks(days, listing)
    assert [t["name"][-21:-5] for t in tasks] == ["20190102T000000Z", "20190102T060000Z"]
    assert tasks[1]["prev_name"] == tasks[0]["name"]
    assert tasks[0]["prev_name"].endswith("20190101T180000Z.flac")
    assert all(t["days"] == ["sb01_01_2019-01-02"] for t in tasks)


def test_select_days_keeps_only_trainval(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame({"split": ["trainval", "test_T", "test_S"], "site": ["sb01", "sb01", "sb03"],
                  "deployment": ["01", "10", "01"], "date": ["2019-01-01"] * 3,
                  "label": [0, 1, 0], "season": ["DJF"] * 3}).to_csv(p, index=False)
    d = select_days(p)
    assert list(d["split"]) == ["trainval"] and "label" not in d.columns


def test_primary_day_score_needs_three_in_ten_minutes():
    from src.pilot_review import primary_day_score

    t = np.array([0.0, 5, 10, 700, 705])
    s = np.array([0.9, 0.8, 0.7, 0.99, 0.99])
    assert primary_day_score(t, s) == pytest.approx(0.7)       # 3rd best inside the first span
    assert primary_day_score(np.array([0.0, 600, 1200]), np.ones(3)) == 0.0  # never 3 within 10 min


def test_auroc_and_ap():
    from src.pilot_review import auroc, average_precision

    assert auroc([0, 0, 1, 1], [0.1, 0.2, 0.3, 0.4]) == 1.0
    assert auroc([0, 1], [0.5, 0.5]) == 0.5
    assert average_precision([1, 0, 1], [0.9, 0.8, 0.7]) == pytest.approx((1 + 2 / 3) / 2)


def test_count_stretches():
    from src.pilot import count_stretches

    assert count_stretches(np.array([])) == 0
    assert count_stretches(np.arange(0, 86400, 5.0)) == 1                       # one grid all day
    assert count_stretches(np.r_[np.arange(0, 100, 5.0), np.arange(107, 200, 5.0)]) == 2  # 7 s real gap
