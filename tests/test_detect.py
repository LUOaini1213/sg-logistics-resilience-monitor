"""Detector tests on small hand-computed series."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import detect as D  # noqa: E402

P = D.Params(k=3.0, persist=2, window=10, gap=0, tol=2, sustain=100, frac_floor=0.0, abs_floor=0.01, min_hist=6)


def test_robust_scale_exact():
    v = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    assert D.robust_scale(v, 3.0, P) == pytest.approx(1.4826)
    # frac floor wins when MAD is small
    p = D.Params(frac_floor=0.05, abs_floor=0.0)
    assert D.robust_scale(np.array([100.0, 100.0, 101.0]), 100.0, p) == pytest.approx(5.0)
    # absolute floor wins on a flat baseline
    p = D.Params(frac_floor=0.0, abs_floor=1.0)
    assert D.robust_scale(np.array([7.0, 7.0, 7.0]), 7.0, p) == 1.0


def test_drop_alarm_raised_on_second_breach_with_exact_z():
    x = [100, 102, 100, 102, 100, 102, 90, 90, 101, 101, 101]
    f, eps = D.detect(np.array(x, float), "drop", P)
    assert f["median"].iloc[6] == 101.0
    assert f["z"].iloc[6] == pytest.approx(11 / 1.4826)
    assert list(f["breach"].iloc[5:9]) == [False, True, True, False]
    assert len(eps) == 1
    assert eps[0].first_breach == 6 and eps[0].start == 7 and eps[0].end == 7
    # breach values never enter the baseline: median stays 101 (it would be 100 otherwise)
    assert f["median"].iloc[8] == 101.0
    # alarm closes after tol=2 quiet observations
    assert list(f["alarm"].iloc[6:11]) == [False, True, True, False, False]


def test_direction_matters():
    x = np.array([100, 102, 100, 102, 100, 102, 112, 112, 101], float)
    _, eps_drop = D.detect(x, "drop", P)
    _, eps_rise = D.detect(x, "rise", P)
    assert eps_drop == []
    assert len(eps_rise) == 1 and eps_rise[0].start == 7
    with pytest.raises(ValueError):
        D.detect(x, "up", P)


def test_single_breach_does_not_alarm_with_persist_2():
    x = np.array([100, 102, 100, 102, 100, 102, 90, 101, 101], float)
    _, eps = D.detect(x, "drop", P)
    assert eps == []
    _, eps1 = D.detect(x, "drop", D.Params(**{**P.__dict__, "persist": 1}))
    assert len(eps1) == 1 and eps1[0].start == 6


def test_threshold_is_inclusive_and_abs_floor_applies():
    p = D.Params(k=3.0, persist=1, window=10, gap=0, tol=1, sustain=100, frac_floor=0.0, abs_floor=1.0,
                 min_hist=3)
    f, eps = D.detect(np.array([100, 100, 100, 97, 100], float), "drop", p)
    assert f["scale"].iloc[3] == 1.0
    assert f["z"].iloc[3] == 3.0
    assert bool(f["breach"].iloc[3]) and len(eps) == 1


def test_min_hist_and_gap():
    p = D.Params(k=3.0, persist=1, window=10, gap=2, tol=1, sustain=100, frac_floor=0.0, abs_floor=0.5,
                 min_hist=3)
    x = np.array([10, 11, 12, 13, 14, 15, 16], float)
    f, _ = D.detect(x, "drop", p)
    # t=4: baseline indices < 2 -> only 2 values -> below min_hist
    assert math.isnan(f["median"].iloc[4])
    # t=5: baseline indices < 3 -> [10, 11, 12] -> median 11
    assert f["median"].iloc[5] == 11.0
    assert f["median"].iloc[6] == 11.5


def test_window_uses_most_recent_clean_values():
    p = D.Params(k=3.0, persist=1, window=4, gap=0, tol=1, sustain=100, frac_floor=0.0, abs_floor=1.0,
                 min_hist=4)
    x = np.array([1, 1, 1, 1, 50, 50, 50, 50, 50], float)
    # the jump to 50 is a rise; judged as "drop" it never breaches, so everything is clean
    f, _ = D.detect(x, "drop", p)
    assert f["median"].iloc[8] == 50.0


def test_sustained_shift_rebaselines_and_drops_old_regime():
    p = D.Params(k=3.0, persist=1, window=50, gap=0, tol=1, sustain=4, frac_floor=0.0, abs_floor=1.0,
                 min_hist=4)
    x = np.array([100, 100, 100, 100, 100, 50, 52, 50, 52, 51, 30, 30], float)
    f, eps = D.detect(x, "drop", p)
    assert eps[0].start == 5 and eps[0].sustained and eps[0].rebaseline_at == 8
    # after re-baselining only the new regime counts: median of [50, 52, 50, 52] = 51
    assert f["median"].iloc[9] == 51.0
    # a second shock relative to the new normal raises a new alarm
    assert len(eps) == 2 and eps[1].start == 10 and not eps[1].sustained


def test_threshold_level_inclusive_with_persistence():
    x = np.array([0.5, 1.0, 1.1, 0.9, 1.5, 1.6, 0.2])
    f, eps = D.threshold_level(x, 1.0, 2)
    assert [(e.first_breach, e.start, e.end) for e in eps] == [(1, 2, 2), (4, 5, 5)]
    assert eps[1].peak_z == 1.6
    assert list(f["alarm"]) == [False, False, True, False, False, True, False]


def test_zero_scale_gives_no_decision():
    p = D.Params(k=3.0, persist=1, window=10, gap=0, tol=1, sustain=100, frac_floor=0.0, abs_floor=0.0,
                 min_hist=3)
    f, eps = D.detect(np.array([5, 5, 5, 1, 5], float), "drop", p)
    assert math.isnan(f["z"].iloc[3]) and eps == []
