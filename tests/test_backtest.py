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


def test_outcome_alarm_does_not_count_as_the_alerts_port_indicator():
    """One route alarm plus one Singapore monthly outcome is Watch, not Alert or Activate review.

    The ladder needs a route alarm plus a *port* indicator for Alert, and an outcome on top of that
    for Activate review; a single outcome alarm cannot satisfy both steps.
    """
    days = pd.date_range("2024-02-01", "2024-03-31")
    mdays = pd.date_range("2023-12-01", "2024-03-01", freq="MS")
    for outcome in ("mpa_teu", "changi_air_cargo", "sg_teu_per_call"):
        frames = {
            "cp_bab": _frame(days, [("2024-01-25", "2024-03-31")]),          # known from 1 Feb
            outcome: pd.DataFrame({"z": 0.0, "alarm": [False, True, True, True]}, index=mdays),
        }
        po = B.posture(frames, days)
        assert po.level["2024-03-02"] == 1, outcome               # route + outcome only: Watch
        assert po.outcome_alarm["2024-03-02"] and not po.local_alarm["2024-03-02"], outcome
        frames["sg_calls_container"] = _frame(days, [("2024-02-25", "2024-03-31")])  # known 3 Mar
        po = B.posture(frames, days)
        assert po.level["2024-03-02"] == 1 and po.level["2024-03-03"] == 3, outcome
        frames.pop(outcome)
        po = B.posture(frames, days)
        assert po.level["2024-03-03"] == 2, outcome               # route + port, no outcome: Alert


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


def _fmt_date(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def test_readme_cited_numbers_match_output_tables():
    """Every other number the README cites, read back from the committed outputs and raw data."""
    s = json.loads((ROOT / "outputs" / "summary.json").read_text())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    out = ROOT / "outputs"

    def has(text):
        assert text in readme, f"README does not contain {text!r}"

    # Detection lags (README "Route alarms came quickly").
    has(f"alarm was **{s['median_lag_known_days_route']:.0f} days**")
    det = pd.read_csv(out / "detections.csv").set_index(["event", "indicator"]).lag_known_days
    has(f"Ever Given, Suez: {det[('ever_given', 'cp_suez')]:.0f} days.")
    has(f"Red Sea 2023, Bab el-Mandeb: {det[('red_sea_2023', 'cp_bab')]:.0f} days.")
    has(f"Hormuz 2026: {det[('hormuz_2026', 'cp_hormuz')]:.0f} days.")
    has(f"Panama drought: {det[('panama_drought', 'cp_panama')]:.0f} days.")
    has(f"raised a fresh alarm {det[('red_sea_2026', 'cp_bab')]:.0f} days after the")
    leads = {r["indicator"]: r["lead_days"] for r in s["sg_lead"]}
    has(f"alarm came {-leads['sg_teu_per_call']} days *after* the statement")

    # False alarms.
    h, d = s["holdout"], s["dev"]
    has(f"across {h['indicator_years']:.1f} indicator-years")
    has(f"or about {round(h['fa_per_indicator_year'] * s['n_indicators'])} a year across all {s['n_indicators']}")
    has(f"The development period had {d['false_alarms']} ({d['fa_per_indicator_year']:.2f} per indicator-year)")
    fa = pd.read_csv(out / "false_alarms_by_indicator.csv").set_index("indicator")
    hfa = fa.holdout_false_alarms
    has(f"Cape of Good Hope ({hfa['cp_cape']}), Taiwan Strait ({hfa['cp_taiwan']}) and "
        f"Tanjung Pelepas ({hfa['tpp_calls_container']})")
    has(f"({fa.dev_false_alarms['klang_calls_container']} development false alarms)")
    al = pd.read_csv(out / "alarms.csv", parse_dates=["raised"])
    fal = al[~al.true_alarm]
    cape = fal[(fal.indicator == "cp_cape") & (fal.period == "holdout")]
    has(f"{cape.raised.dt.month.between(6, 9).sum()} of the {len(cape)} holdout false alarms were raised "
        "between June and")
    tw = fal[fal.indicator == "cp_taiwan"]
    has(f"{tw.raised.dt.month.between(7, 10).sum()} of its {len(tw)} false alarms (2020–2026) fall in July–October")

    # Chance baseline and grid.
    c = s["chance_expected_detections"]
    has(f"would catch about {c['dev']}\nand {c['holdout']})")
    has(f"hit about {c['dev']} of the {d['pairs']} and {c['holdout']} of the {h['pairs']} windows")
    ch = pd.read_csv(out / "chance_baseline.csv").set_index(["event", "indicator"])
    has(f"(up to {ch.window_days.max()} days)")
    has(f"Cape of Good Hope alone has a {ch.p_chance_hit[('red_sea_2023', 'cp_cape')]:.2f} chance")
    has(f"{s['holdout_full_recall_settings']} of the {s['grid_settings']} grid settings also reach "
        f"{h['pairs']} of {h['pairs']}")
    g = pd.read_csv(out / "tuning_grid.csv").set_index(["k", "persist_days"]).loc[(3.0, 7)]
    has(f"(z ≥ 3, 7 days) would have done better on the holdout: {g.holdout_detected} of {g.holdout_pairs} "
        f"detected with {g.holdout_false_alarms} false\n  alarms. It caught only {g.dev_detected} of {g.dev_pairs}")

    # Posture day counts.
    po = pd.read_csv(out / "posture_daily.csv")
    assert int((po.level >= 2).sum()) == s["alert_days_total"]
    has(f"spent {s['alert_days_total']} days at Alert or above, {int((po.level == 3).sum())} of them at\n"
        "Activate review")
    has(f"{s['alert_days_outside_events']} of the {s['alert_days_total']} days fell outside every labelled event")
    fl = pd.read_csv(out / "posture_first_level_by_event.csv").set_index("event")
    has(f"The first Alert near the Red Sea event came on {_fmt_date(fl.first_level2['red_sea_2023'])}")

    # TEU-per-call transform check.
    tc = pd.read_csv(out / "teu_per_call_transform_check.csv").set_index(["version", "event"])
    has(f"alarmed {tc.lag_known_days[('year-on-year (first version)', 'pandemic_congestion')]:.0f} days after the")
    has(f"alarmed after {tc.lag_known_days[('level (used)', 'pandemic_congestion')]:.0f} days and "
        f"{tc.lag_known_days[('level (used)', 'sg_congestion_2024')]:.0f} days respectively")

    # Posture inputs from the raw data.
    m = load_monthly()
    tpc = m["sg_teu_per_call"].dropna()
    assert tpc.idxmax() == tpc.index[-1] == T("2026-08-01")
    has(f"{tpc.iloc[-1]:,.0f} in August 2026, the highest value in the series")
    g_ = m["gscpi"].dropna()
    has(f"The GSCPI at {g_.iloc[-1]:.2f} ({_fmt_date(g_.index[-1]).split(' ', 1)[1]})")
    cp = pd.read_csv(ROOT / "data" / "raw" / "portwatch_chokepoints_daily.csv", parse_dates=["date"])
    mal = cp[cp.portname == "Malacca Strait"].set_index("date").n_total
    has(f"2022 averaged {(mal['2022'].mean() / mal['2021-01':'2021-10'].mean() - 1) * 100:.0f}% above")
    has(f"extend to {pd.Timestamp(s['data_end']['portwatch']).day} October")

    # Mutation harness count.
    sys.path.insert(0, str(ROOT / "tests"))
    import mutate  # noqa: E402
    n = len(mutate.MUTANTS)
    has(f"plants {n} bugs one at a time")
    has(f"the current run catches {n} of {n}")
    assert f"{n}/{n} planted bugs caught" in (out / "mutation_run.txt").read_text(encoding="utf-8")
