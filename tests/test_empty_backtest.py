"""Quiet periods and empty labels must be representable, including strict JSON."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import backtest as B, report
from lsr.indicators import INDICATORS


def quiet_inputs():
    daily = pd.DataFrame({k: 100.0 for k, ind in INDICATORS.items() if ind.freq == "D"},
                         index=pd.date_range("2020-01-01", periods=400))
    monthly = pd.DataFrame({k: 100.0 for k, ind in INDICATORS.items() if ind.freq == "M"},
                           index=pd.date_range("2019-01-01", periods=36, freq="MS"))
    monthly["gscpi"] = 0.0
    events = pd.DataFrame([{"event_id": "e", "onset": pd.Timestamp("2020-02-01"),
                            "window_end": pd.Timestamp("2020-04-01"), "split": "dev",
                            "expected": ["cp_suez"], "upstream_event": "", "sg_reference_date": pd.NaT}])
    return daily, monthly, events


@pytest.mark.parametrize("empty_events", [False, True])
def test_quiet_evaluation_has_stable_empty_tables_and_finite_scores(empty_events):
    daily, monthly, events = quiet_inputs()
    if empty_events:
        events = events.iloc[:0]
    result = B.evaluate(3, 3, daily, monthly, events)
    assert result["matched"].empty
    assert set(result["matched"].columns) >= {"event", "indicator", "raised", "known", "true_alarm", "period"}
    assert result["matched"].true_alarm.dtype == bool
    assert result["det"].detected.dtype == bool
    assert result["det"].empty == empty_events
    assert result["dev"]["detected"] == 0 and result["dev"]["pairs"] == (0 if empty_events else 1)
    assert result["dev"]["recall"] == 0.0
    assert result["dev"]["recall_defined"] == (not empty_events)
    assert not result["holdout"]["recall_defined"]
    assert result["holdout"]["false_alarms"] == 0
    json.dumps([result["dev"], result["holdout"]], allow_nan=False)
    lead = B.sg_lead(result["matched"], events)
    assert lead.empty and set(lead.columns) >= {"event", "indicator", "lead_days"}


def test_zero_coverage_score_has_explicit_zero_denominator():
    daily, monthly, events = quiet_inputs()
    result = B.evaluate(3, 3, daily.iloc[:0], monthly.iloc[:0], events.iloc[:0])
    for split in ("dev", "holdout"):
        assert result[split]["indicator_years"] == 0
        assert result[split]["fa_per_indicator_year"] == 0
        assert not result[split]["false_alarm_rate_defined"]
        assert not result[split]["recall_defined"]
        json.dumps(result[split], allow_nan=False)


def test_empty_event_level_table_keeps_schema():
    _, _, events = quiet_inputs()
    po = B.posture({}, pd.date_range("2024-01-01", periods=2))
    assert po.level.tolist() == [0, 0]
    levels = report.first_level_dates(po, events.iloc[:0])
    assert levels.empty and "first_level2" in levels


@pytest.mark.parametrize("empty_events", [False, True])
def test_full_quiet_report_and_dashboard(tmp_path, monkeypatch, empty_events):
    daily, monthly, events = quiet_inputs()
    if empty_events:
        events = events.iloc[:0]
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "OUT", tmp_path / "outputs")
    monkeypatch.setattr(report, "load_daily", lambda: daily)
    monkeypatch.setattr(report, "load_monthly", lambda: monthly)
    monkeypatch.setattr(B, "load_events", lambda: events)
    monkeypatch.setattr(B, "tune", lambda *args: (pd.DataFrame(), (3, 3)))
    result = report.main()
    assert result["posture_active"] == "" and result["median_lag_known_days_route"] is None
    json.dumps(result, allow_nan=False)
    assert pd.read_csv(tmp_path / "outputs" / "alarms.csv").empty
    assert pd.read_csv(tmp_path / "outputs" / "sg_lead.csv").empty
    assert (tmp_path / "docs" / "index.html").exists()
