"""Backtest bookkeeping on synthetic inputs, plus regression checks on the real run."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import backtest as B  # noqa: E402
from lsr.indicators import load_daily, load_monthly  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
T = pd.Timestamp


def _events():
    return pd.DataFrame([
        {"event_id": "e1", "onset": T("2021-03-01"), "window_end": T("2021-05-31"), "split": "dev",
         "expected": ["cp_suez", "cp_bab"], "upstream_event": "", "sg_reference_date": pd.NaT},
        {"event_id": "e2", "onset": T("2024-03-01"), "window_end": T("2024-07-31"), "split": "holdout",
         "expected": ["sg_calls_container"], "upstream_event": "e1", "sg_reference_date": T("2024-05-30")},
    ])


def _alarm(ind, raised, lag=7):
    raised = T(raised)
    return B.Alarm(ind, raised, raised + pd.Timedelta(days=lag), raised, raised, 4.0, False, None)


def test_match_window_boundaries_and_expected_list():
    alarms = [
        _alarm("cp_suez", "2021-02-01"),   # exactly onset - 28 days: true
        _alarm("cp_suez", "2021-01-31"),   # one day earlier: false
        _alarm("cp_bab", "2021-05-31"),    # last day of window: true
        _alarm("cp_bab", "2021-06-01"),    # day after: false
        _alarm("cp_cape", "2021-03-10"),   # inside window but not expected: false
        _alarm("cp_suez", "2019-06-01"),   # before EVAL_START: dropped
    ]
    m = B.match(alarms, _events())
    assert len(m) == 5
    assert list(m.true_alarm) == [True, False, True, False, False]
    assert list(m.event.fillna("-")) == ["e1", "-", "e1", "-", "-"]
    assert list(m.period) == ["dev"] * 5


def test_detections_lags_and_misses():
    alarms = [_alarm("cp_suez", "2021-03-05"), _alarm("cp_suez", "2021-03-20"),
              _alarm("sg_calls_container", "2024-03-21", lag=7)]
    m = B.match(alarms, _events())
    d = B.detections(m, _events()).set_index(["event", "indicator"])
    assert d.loc[("e1", "cp_suez"), "lag_raised_days"] == 4
    assert d.loc[("e1", "cp_suez"), "lag_known_days"] == 11
    assert not d.loc[("e1", "cp_bab"), "detected"]
    assert d.loc[("e2", "sg_calls_container"), "lag_known_days"] == 27


def test_sg_lead_counts_upstream_event():
    alarms = [_alarm("cp_suez", "2021-03-05"), _alarm("sg_calls_container", "2024-03-21")]
    lead = B.sg_lead(B.match(alarms, _events()), _events())
    got = dict(zip(lead.indicator, lead.lead_days))
    assert got == {"cp_suez": (T("2024-05-30") - T("2021-03-12")).days, "sg_calls_container": 63}


def test_select_prefers_recall_then_fewer_false_alarms():
    g = pd.DataFrame([
        {"k": 2.5, "persist_days": 1, "dev_recall": 1.0, "dev_fa_per_indicator_year": 1.2},
        {"k": 3.0, "persist_days": 3, "dev_recall": 1.0, "dev_fa_per_indicator_year": 0.5},
        {"k": 4.0, "persist_days": 7, "dev_recall": 0.6, "dev_fa_per_indicator_year": 0.1},
    ])
    assert B.select(g) == (3.0, 3)


def _frame(days, on):
    a = pd.Series(False, index=days)
    for lo, hi in on:
        a.loc[lo:hi] = True
    return pd.DataFrame({"z": 0.0, "alarm": a})


def test_posture_levels_and_publication_lag():
    days = pd.date_range("2024-01-01", "2024-03-31")
    frames = {
        "cp_suez": _frame(days, [("2024-01-10", "2024-01-31")]),
        "cp_bab": _frame(days, [("2024-01-20", "2024-01-31")]),
        "sg_calls_container": _frame(days, [("2024-02-10", "2024-02-20")]),
        "cp_cape": _frame(days, [("2024-02-01", "2024-02-28")]),
    }
    mdays = pd.date_range("2023-12-01", "2024-03-01", freq="MS")
    frames["mpa_teu"] = pd.DataFrame({"z": 0.0, "alarm": [False, False, True, False]}, index=mdays)
    po = B.posture(frames, days)
    lv = po.level
    assert lv["2024-01-16"] == 0 and lv["2024-01-17"] == 1     # alarm 10 Jan + 7-day lag
    assert lv["2024-01-26"] == 1 and lv["2024-01-27"] == 2     # second route alarm known 27 Jan
    assert lv["2024-02-10"] == 1                                # only cp_cape known
    assert lv["2024-02-17"] == 2                                # cp_cape + Singapore calls
    # mpa_teu alarm for February is known 31 Mar + 15 days -> after this window; January value is clean
    assert lv["2024-02-20"] == 2
    frames["mpa_teu"] = pd.DataFrame({"z": 0.0, "alarm": [True, False, False, False]}, index=mdays)
    po = B.posture(frames, days)
    # December alarm known 31 Dec + 15 = 15 Jan, replaced by January's clean value on 15 Feb
    assert po.level["2024-01-27"] == 3 and po.level["2024-02-17"] == 2
    # an outcome alarm on its own (no route alarm yet) is only Watch, never Activate review
    assert po.level["2024-01-14"] == 0 and po.level["2024-01-16"] == 1


# ---- real run --------------------------------------------------------------

@pytest.fixture(scope="module")
def real():
    return B.evaluate(2.5, 3, load_daily(), load_monthly(), B.load_events())


def test_ever_given_detected_within_days(real):
    d = real["det"].set_index(["event", "indicator"])
    assert d.loc[("ever_given", "cp_suez"), "detected"]
    assert d.loc[("ever_given", "cp_suez"), "raised"] == T("2021-03-27").date()


def test_red_sea_route_alarms_lead_singapore_statement(real):
    lead = B.sg_lead(real["matched"], B.load_events()).set_index("indicator")
    assert lead.loc["cp_bab", "lead_days"] == 152
    assert lead.loc["sg_calls_container", "lead_days"] == 63


def test_dev_and_holdout_scores(real):
    assert real["dev"]["detected"] == 11 and real["dev"]["pairs"] == 11
    assert real["holdout"]["detected"] == 8 and real["holdout"]["pairs"] == 8
    assert real["holdout"]["false_alarms"] == 50


def test_readme_numbers_match_outputs():
    s = json.loads((ROOT / "outputs" / "summary.json").read_text())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sel = s["selected"]
    assert f"z ≥ {sel['k']}" in readme and f"{sel['persist_days']} consecutive days" in readme
    h, d = s["holdout"], s["dev"]
    assert f"{h['detected']} of {h['pairs']}" in readme
    assert f"{d['detected']} of {d['pairs']}" in readme
    assert f"{h['false_alarms']} false alarms" in readme
    assert f"{h['fa_per_indicator_year']:.2f} per indicator-year" in readme
    leads = {r["indicator"]: r["lead_days"] for r in s["sg_lead"]}
    assert f"{leads['cp_bab']} days" in readme and f"{leads['sg_calls_container']} days" in readme
    assert re.search(rf"Level {s['posture_level']}", readme)
