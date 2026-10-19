"""Missing data is neither consecutive support for stress nor proof of recovery."""
from dataclasses import replace
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import backtest as B, detect as D
from lsr.indicators import INDICATORS

P = D.Params(k=3, persist=2, window=10, gap=0, tol=2, sustain=100,
             frac_floor=0, abs_floor=1, min_hist=3)


@pytest.mark.parametrize("missing", [np.nan, np.inf, -np.inf])
def test_missing_breaks_unconfirmed_persistence(missing):
    f, eps = D.detect([100, 100, 100, 90, missing, 90, 90], "drop", P)
    assert [(e.first_breach, e.start) for e in eps] == [(5, 6)]
    assert f.observed.tolist() == [True, True, True, True, False, True, True]


@pytest.mark.parametrize("missing", [np.nan, np.inf, -np.inf])
def test_active_alarm_survives_missing_but_recovery_must_be_consecutive(missing):
    f, eps = D.detect([100, 100, 100, 90, 90, 100, missing, 100, 100], "drop", P)
    assert f.alarm.tolist() == [False, False, False, False, True, True, True, True, False]
    assert len(eps) == 1 and eps[0].end == 4


def test_missing_resets_sustained_support_without_closing_alarm():
    f, eps = D.detect([100, 100, 100, 90, 90, np.nan, np.nan, 90, 90, 90],
                      "drop", replace(P, sustain=3))
    assert eps[0].sustained and eps[0].rebaseline_at == 9
    assert f.alarm.iloc[5:9].all()


def test_threshold_level_requires_consecutive_observed_periods():
    f, eps = D.threshold_level([1.2, np.nan, 1.3, 1.4, np.nan, 0.9], 1, 2)
    assert [(e.first_breach, e.start, e.end) for e in eps] == [(2, 3, 3)]
    assert f.alarm.tolist() == [False, False, False, True, True, False]
    assert f.observed.tolist() == [True, False, True, True, False, True]


@pytest.mark.parametrize("missing_row", [False, True])
def test_monthly_calendar_is_not_compressed(missing_row):
    days = pd.date_range("2021-01-01", periods=10)
    months = pd.date_range("2021-01-01", periods=4, freq="MS")
    daily = pd.DataFrame({k: 100.0 for k, ind in INDICATORS.items() if ind.freq == "D"}, index=days)
    monthly = pd.DataFrame({k: 100.0 for k, ind in INDICATORS.items() if ind.freq == "M"}, index=months)
    monthly["gscpi"] = [1.2, np.nan, 1.3, 1.4]
    if missing_row:
        monthly = monthly.drop(pd.Timestamp("2021-02-01"))
    frames, alarms = B.run_detectors(daily, monthly, D.DAILY, D.MONTHLY)
    gscpi = [a for a in alarms if a.indicator == "gscpi"]
    assert len(gscpi) == 1
    assert gscpi[0].first_breach == pd.Timestamp("2021-03-31")
    assert gscpi[0].raised == pd.Timestamp("2021-04-30")
    assert not frames["gscpi"].loc["2021-02-01", "observed"]


def test_posture_marks_missing_without_false_recovery_after_publication_lag():
    f, _ = D.detect([100, 100, 100, 90, 90, np.nan, 90], "drop", P)
    f.index = pd.date_range("2024-01-01", periods=len(f))
    po = B.posture({"cp_suez": f}, pd.date_range("2024-01-11", "2024-01-14"))
    assert po.level.tolist() == [0, 1, 1, 1]
    assert po.unavailable.tolist() == ["", "", "cp_suez", ""]
    # Before any publication there is no affirmative Normal observation.
    first = B.posture({"cp_suez": f}, pd.date_range("2024-01-01", "2024-01-08"))
    assert first.unavailable.iloc[0] == "cp_suez" and first.unavailable.iloc[-1] == ""


def test_synthetic_legacy_frames_still_work_without_observed_column():
    days = pd.date_range("2024-01-01", periods=2)
    f = pd.DataFrame({"alarm": [True, False], "z": [3.0, 0.0]}, index=days)
    po = B.posture({"cp_suez": f}, days + pd.Timedelta(days=7))
    assert po.level.tolist() == [1, 0]
    assert po.unavailable.tolist() == ["", ""]


def test_daily_missing_date_is_preserved_before_persistence():
    days = pd.date_range("2021-01-01", periods=7)
    daily = pd.DataFrame({k: 100.0 for k, ind in INDICATORS.items() if ind.freq == "D"}, index=days)
    daily["cp_suez"] = [100, 100, 100, 90, np.nan, 90, 90]
    daily = daily.drop(days[4])
    monthly = pd.DataFrame({k: 0.0 for k, ind in INDICATORS.items() if ind.freq == "M"},
                           index=pd.date_range("2021-01-01", periods=1, freq="MS"))
    frames, alarms = B.run_detectors(daily, monthly, P, D.MONTHLY)
    assert not frames["cp_suez"].loc[days[4], "observed"]
    assert [a.raised for a in alarms if a.indicator == "cp_suez"] == [days[6]]
