"""Monte Carlo scenarios: distributions, detector and ladder against the repository's own code, the
queue, determinism under a fixed seed, and the committed results."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr import backtest as B  # noqa: E402
from lsr import detect as Dt  # noqa: E402
from lsr.maritime import scenarios as S  # noqa: E402
from lsr.maritime import sd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "maritime"


def test_triangular_inverse_cdf():
    u = (np.arange(20000) + 0.5) / 20000
    x = S.triangular(u, 1.0, 3.0, 10.0)
    assert x.min() >= 1.0 and x.max() <= 10.0 and np.all(np.diff(x) >= 0)
    assert x.mean() == pytest.approx((1.0 + 3.0 + 10.0) / 3.0, abs=1e-3)
    assert S.triangular(np.array([0.0, 1.0]), 1.0, 3.0, 10.0).tolist() == [1.0, 10.0]
    # the mode sits at the CDF value (mode - lo) / (hi - lo)
    assert S.triangular(np.array([2.0 / 9.0]), 1.0, 3.0, 10.0)[0] == pytest.approx(3.0)


def test_draws_respect_their_definitions():
    rng = np.random.default_rng(1)
    ints = S.draw(rng, {"dist": "uniform_int", "a": "0", "b": "3", "c": ""}, 4000)
    assert set(ints.tolist()) == {0.0, 1.0, 2.0, 3.0}
    uni = S.draw(rng, {"dist": "uniform", "a": "0.3", "b": "0.8", "c": ""}, 4000)
    assert uni.min() >= 0.3 and uni.max() <= 0.8
    assert S.draw(rng, {"dist": "fixed", "a": "7", "b": "", "c": ""}, 3).tolist() == [7.0, 7.0, 7.0]
    with pytest.raises(ValueError):
        S.draw(rng, {"dist": "normal", "a": "0", "b": "1", "c": ""}, 3)


def test_alarm_states_match_the_detector_on_a_constant_baseline():
    """With a flat history the detector's baseline stays at 100 and its scale at the floor, so its
    alarm column must equal the vectorised state machine applied to z = (100 - x) / 5."""
    rng = np.random.default_rng(3)
    p = Dt.Params(k=2.5, persist=3, window=364, gap=28, tol=7, sustain=10_000, frac_floor=0.0, abs_floor=5.0,
                  min_hist=182)
    for trial in range(5):
        future = np.where(rng.random(150) < 0.35, 80.0, 100.0)
        x = np.concatenate([np.full(400, 100.0), future])
        f, _ = Dt.detect(x, "drop", p)
        z = ((100.0 - future) / 5.0)[None, :]
        mine = S.alarm_states(z, 2.5, 3, 7)[0]
        assert mine.tolist() == f["alarm"].values[400:].tolist(), trial


def test_ladder_and_lags_match_backtest_posture():
    rng = np.random.default_rng(11)
    horizon = 120
    days = pd.date_range(S.START, periods=horizon, freq="D")
    months, _, known_day = S.month_layout(horizon)
    keys_d = ["cp_bab", "cp_suez", "cp_malacca", "sg_calls_container", "tpp_calls_container"]
    keys_m = ["mpa_teu", "sg_teu_per_call"]
    for trial in range(10):
        alarms = {k: rng.random(horizon) < 0.3 for k in keys_d}
        alarms_m = {k: rng.random(len(months)) < 0.5 for k in keys_m}
        frames = {k: pd.DataFrame({"z": 0.0, "alarm": a}, index=days) for k, a in alarms.items()}
        frames.update({k: pd.DataFrame({"z": 0.0, "alarm": a}, index=months) for k, a in alarms_m.items()})
        want = B.posture(frames, days).level.values
        known = {k: S.known_daily(a[None, :], 7) for k, a in alarms.items()}
        known.update({k: S.known_monthly(a[None, :], known_day, horizon) for k, a in alarms_m.items()})
        assert S.ladder(known)[0].tolist() == want.tolist(), trial


def test_queue_conserves_ships_and_clears():
    service, backlog = S.queue_paths(1, 20, np.array([2.0]), np.array([2.0]), np.array([0.5]), np.array([0.25]))
    # days 2-3 serve half the arrivals: backlog 1.0 day of arrivals, cleared at 0.25 a day in 4 days
    assert backlog[0].tolist()[:8] == pytest.approx([0, 0, 0.5, 1.0, 0.75, 0.5, 0.25, 0.0])
    assert service[0].sum() == pytest.approx(20.0)                       # every arrival is served
    assert S.trailing_mean7(np.array([[0.0] + [1.0] * 9]))[0].tolist()[:3] == pytest.approx([6 / 7, 6 / 7, 6 / 7])
    w = S.ramp_window(np.arange(10.0), np.array([2.0]), np.array([4.0]), 2.0)[0]
    assert w.tolist() == [0.0, 0.0, 0.0, 0.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0]


@pytest.fixture(scope="module")
def frames():
    sel = json.loads((ROOT / "outputs" / "summary.json").read_text(encoding="utf-8"))["selected"]
    return B.evaluate(sel["k"], sel["persist_days"])["frames"], sel


def _sd_params():
    rows = {r["parameter"]: r for r in csv.DictReader(open(OUT / "sd_parameters.csv", encoding="utf-8"))}
    v = lambda n: float(rows[n]["estimate"])  # noqa: E731
    return sd.Params(d_max=v("d_max"), tau_d=v("tau_d"), tau_c=v("tau_c"), kappa=v("kappa"), tau_a=v("tau_a"),
                     beta=v("beta"), tau_u=v("tau_u"), u0=v("u0"), tau_q=v("tau_q"), tau_k=v("tau_q"),
                     adapt=1.0, theta_c=v("theta_c"), theta_t=v("theta_t")), v("B0")


def test_monte_carlo_is_deterministic_and_uses_common_noise(frames):
    fr, sel = frames
    params, events, voy = S.load_params(), B.load_events(), S.V.load_values()
    p, b0 = _sd_params()
    run = lambda name, prm: S.simulate(name, fr, events, prm, p, voy, 0.74, b0, sel["k"], sel["persist_days"], n=40)  # noqa: E731,E501
    a, b = run("strait", params), run("strait", params)
    assert np.array_equal(a["level"], b["level"]) and np.array_equal(a["x_daily"]["cp_malacca"],
                                                                      b["x_daily"]["cp_malacca"])
    ctrl = run("control", params)
    assert np.array_equal(ctrl["rows"], a["rows"])                     # same noise in every scenario
    other = {**params, "all": {**params["all"], "seed": {**params["all"]["seed"], "a": "7"}}}
    c = run("strait", other)
    assert not np.array_equal(c["x_daily"]["cp_malacca"], a["x_daily"]["cp_malacca"])
    assert np.all(a["costs"]["waiting_ship_days"] > 0)
    g = run("gulf", params)
    assert np.all(g["costs"]["cape_usd_per_teu_change"] > 0)           # dearer fuel always costs more


def test_committed_scenario_results_are_coherent():
    lad = {r["scenario"]: r for r in csv.DictReader(open(OUT / "scenario_ladder.csv", encoding="utf-8"))}
    assert float(lad["control"]["p_level2_attributable"]) == 0.0
    assert float(lad["strait"]["p_level2_attributable"]) > 0.2
    assert float(lad["reopen"]["p_level2_attributable"]) == 0.0
    for r in lad.values():
        assert float(r["p_level1"]) >= float(r["p_level2"]) >= float(r["p_level3"])
    for r in csv.DictReader(open(OUT / "scenario_exact_check.csv", encoding="utf-8")):
        assert float(r["breach_day_agreement"]) >= 0.98, r
