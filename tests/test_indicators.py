"""Indicator construction, plus checks of the raw data against official statements."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import indicators as I  # noqa: E402

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_rolling7_needs_seven_complete_days():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, np.nan, 10], dtype=float,
                  index=pd.date_range("2024-01-01", periods=10))
    r = I.rolling7(s)
    assert np.isnan(r.iloc[5])
    assert r.iloc[6] == 28 and r.iloc[7] == 35
    assert np.isnan(r.iloc[8]) and np.isnan(r.iloc[9])


def test_log_yoy_uses_twelve_month_lag():
    idx = pd.date_range("2020-01-01", periods=25, freq="MS")
    s = pd.Series(np.arange(1, 26, dtype=float), index=idx)
    g = I.log_yoy(s)
    assert np.isnan(g.iloc[11])
    assert g.iloc[12] == pytest.approx(np.log(13 / 1))
    assert g.iloc[24] == pytest.approx(np.log(25 / 13))


def test_every_indicator_has_valid_metadata():
    for key, ind in I.INDICATORS.items():
        assert ind.key == key
        assert ind.direction in ("drop", "rise") and ind.freq in ("D", "M")
        assert ind.family in ("route", "regional", "singapore", "global")
        assert ind.lag_days > 0
    assert I.INDICATORS["cp_cape"].direction == "rise"
    assert I.INDICATORS["sg_teu_per_call"].direction == "rise"
    assert I.INDICATORS["cp_suez"].direction == "drop"


# ---- real data -------------------------------------------------------------

@pytest.fixture(scope="module")
def daily():
    return I.load_daily(RAW)


@pytest.fixture(scope="module")
def monthly():
    return I.load_monthly(RAW)


def test_portwatch_coverage(daily):
    raw = pd.read_csv(RAW / "portwatch_chokepoints_daily.csv")
    assert not raw.duplicated(["portid", "date"]).any()
    assert daily.index.min() <= pd.Timestamp("2019-01-07")
    assert daily.index.max() >= pd.Timestamp("2026-10-01")
    assert set(I.CP_COLS.values()) <= set(daily.columns)


def test_portwatch_7day_sum_matches_raw(daily):
    raw = pd.read_csv(RAW / "portwatch_chokepoints_daily.csv", parse_dates=["date"])
    suez = raw[raw.portname == "Suez Canal"].set_index("date")["n_total"]
    want = suez.loc["2021-03-22":"2021-03-28"].sum()
    assert daily.loc["2021-03-28", "cp_suez"] == want


def test_monthly_calls_drop_incomplete_month(monthly):
    calls = I.load_portwatch_monthly_calls(RAW)
    raw = pd.read_csv(RAW / "portwatch_ports_daily.csv", parse_dates=["date"])
    sg = raw[raw.portname == "Singapore"].set_index("date")["portcalls_container"]
    assert calls.loc["2024-06-01"] == sg.loc["2024-06"].sum()
    last = sg.index.max()
    if last.day != last.days_in_month:
        assert np.isnan(calls.loc[last.to_period("M").to_timestamp()])


def test_mpa_throughput_matches_official_statements(monthly):
    teu = monthly["mpa_teu"]   # thousand TEU
    # MPA, 30 May 2024: first four months of 2024 = 13.36 million TEU
    assert round(teu.loc["2024-01":"2024-04"].sum() / 1000, 2) == 13.36
    # MOT written reply, 2 Jul 2024: January-May 2024 = 16.9 million TEU, up 7.7% from 15.7 million
    jm24 = teu.loc["2024-01":"2024-05"].sum()
    jm23 = teu.loc["2023-01":"2023-05"].sum()
    assert round(jm24 / 1000, 1) == 16.9 and round(jm23 / 1000, 1) == 15.7
    assert round((jm24 / jm23 - 1) * 100, 1) == 7.7
    # MPA, 4 Sep 2024: first seven months of 2024 = 23.82 million TEU
    assert round(teu.loc["2024-01":"2024-07"].sum() / 1000, 2) == 23.82


def test_teu_per_call_is_ratio(monthly):
    calls = I.load_portwatch_monthly_calls(RAW)
    v = monthly.loc["2024-06-01", "sg_teu_per_call"]
    assert v == pytest.approx(monthly.loc["2024-06-01", "mpa_teu"] * 1000 / calls.loc["2024-06-01"])
