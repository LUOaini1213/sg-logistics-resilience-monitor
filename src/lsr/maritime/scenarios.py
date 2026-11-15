"""Seeded Monte Carlo of three forward scenarios, read through the repository's detector and ladder.

Design (all choices are listed with their provenance in ``data/inputs/scenario_parameters.csv``):

* **Start.** 26 weeks from 5 Oct 2026, the day after the last PortWatch observation. Every indicator
  starts at its detector baseline (median and robust scale) as of the data cut-off, *not* at its
  latest value: the ladder readings show what each scenario would trigger on its own from a quiet
  start. (The actual posture at the cut-off is Level 3; see the README.)
* **Noise.** Daily indicators are resampled in 28-day blocks from their 2025 residuals (value / detector
  median - 1), using the same dates for every indicator so co-movements are kept; monthly outcomes
  resample whole 2025 months. A control scenario with noise only measures the false-alarm background.
* **Shocks.** Each scenario multiplies daily rates (7-day sums average the factor over the week) or
  shifts monthly values. The reopening scenario drives the calibrated stock-and-flow model.
* **Detector and ladder.** The selected setting (z >= k for ``persist`` days; monthly: one month),
  against the baseline frozen at the cut-off, then the publication lags and the three-level ladder of
  ``backtest.posture``. ``exact_check`` re-runs the repository's own detector on history plus simulated
  paths for a subsample to measure what freezing the baseline changes.
* **Costs.** Fuel-price and toll/premium draws go through ``voyage.py``; the incident's waiting
  ship-days through a queue.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import replace

import numpy as np
import pandas as pd

from .. import detect as Dt
from ..indicators import INDICATORS, RAW
from . import sd
from . import voyage as V
from .inputs import INPUTS, read_csv

START = pd.Timestamp("2026-10-05")
SCENARIOS = ("control", "gulf", "strait", "reopen")
TITLES = {"control": "Control (noise only)", "gulf": "Gulf escalation, second fuel shock",
          "strait": "Singapore Strait incident", "reopen": "Red Sea reopening"}
DAILY = [k for k, i in INDICATORS.items() if i.freq == "D"]
MONTHLY = [k for k, i in INDICATORS.items() if i.freq == "M" and k != "gscpi"]
ROUTE = [k for k in DAILY if INDICATORS[k].family == "route"]
LOCAL = [k for k in DAILY if INDICATORS[k].family in ("singapore", "regional")]
BLOCK = 28


# ------------------------------------------------------------------ parameters and draws
def diverted_share_now(b0_weekly: float, raw=RAW, days: int = 28) -> tuple[float, pd.Timestamp]:
    """Share of the pre-crisis Bab el-Mandeb container transits that is still missing over the last
    ``days`` days of PortWatch data (1 - recent weekly rate / B0)."""
    cp = pd.read_csv(raw / "portwatch_chokepoints_daily.csv", parse_dates=["date"])
    s = cp[cp.portname == "Bab el-Mandeb Strait"].set_index("date")["n_container"].astype(float).sort_index()
    last = s.iloc[-days:]
    return 1.0 - math.fsum(last.values) / days * 7.0 / b0_weekly, last.index[-1]


def load_params(path=INPUTS / "scenario_parameters.csv") -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in read_csv(path):
        out.setdefault(r["scenario"], {})[r["name"]] = r
    return out


def triangular(u: np.ndarray, lo: float, mode: float, hi: float) -> np.ndarray:
    """Inverse CDF of the triangular distribution (only arithmetic and sqrt, both exact in IEEE 754)."""
    fc = (mode - lo) / (hi - lo)
    left = lo + np.sqrt(u * (hi - lo) * (mode - lo))
    right = hi - np.sqrt((1.0 - u) * (hi - lo) * (hi - mode))
    return np.where(u < fc, left, right)


def draw(rng: np.random.Generator, row: dict, n: int) -> np.ndarray:
    a = float(row["a"])
    if row["dist"] == "fixed":
        return np.full(n, a)
    if row["dist"] == "uniform_int":
        return rng.integers(int(a), int(float(row["b"])) + 1, size=n).astype(float)
    u = rng.random(n)
    if row["dist"] == "uniform":
        return a + (float(row["b"]) - a) * u
    if row["dist"] == "triangular":
        return triangular(u, a, float(row["b"]), float(row["c"]))
    raise ValueError(row["dist"])


# ------------------------------------------------------------------ baselines and noise
def baselines(frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Detector median and scale at the last observation that had both (the frozen baseline)."""
    out = {}
    for k in DAILY + MONTHLY:
        f = frames[k]
        ok = f[np.isfinite(f["median"].values) & np.isfinite(f["scale"].values)]
        last = ok.iloc[-1]
        out[k] = {"median": float(last["median"]), "scale": float(last["scale"]), "date": ok.index[-1],
                  "sign": -1.0 if INDICATORS[k].direction == "drop" else 1.0,
                  "level": INDICATORS[k].freq == "D" or INDICATORS[k].transform == "level"}
    return out


def residuals(frames: dict[str, pd.DataFrame], base: dict, events: pd.DataFrame,
              year: int = 2025) -> tuple[np.ndarray, np.ndarray]:
    """Short-term noise, detrended so that it carries no level shift or season.

    Daily: value / centred 91-day rolling median - 1, for every day of ``year`` (a year with no
    labelled event). Monthly: value / centred 13-month rolling median - 1 (log-change series: value -
    median), for the months of 2021-2025 outside every labelled event window, the same months for
    every indicator. Returns matrices [days, DAILY] and [months, MONTHLY].
    """
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    d = np.zeros((len(days), len(DAILY)))
    for j, k in enumerate(DAILY):
        v = frames[k]["value"]
        med = v.rolling(91, center=True, min_periods=61).median()
        r = (v / med - 1.0).reindex(days).values
        d[:, j] = np.where(np.isfinite(r), r, 0.0)
    months = pd.date_range("2021-01-01", "2025-12-01", freq="MS")
    keep = np.ones(len(months), dtype=bool)
    for _, e in events.iterrows():
        lo = e["onset"] - pd.Timedelta(days=28)
        keep &= ~((months + pd.offsets.MonthEnd(0) >= lo) & (months <= e["window_end"]))
    months = months[keep]
    m = np.zeros((len(months), len(MONTHLY)))
    for j, k in enumerate(MONTHLY):
        v = frames[k]["value"]
        med = v.rolling(13, center=True, min_periods=9).median()
        r = (v / med - 1.0) if base[k]["level"] else (v - med)
        r = r.reindex(months).values
        m[:, j] = np.where(np.isfinite(r), r, 0.0)
    return d, m


def month_layout(horizon: int) -> tuple[list[pd.Timestamp], np.ndarray, list[int]]:
    """Months touched by the horizon, the month index of each day, and the day each month's value
    becomes known (month end + 15 days, MPA's publication lag)."""
    days = pd.date_range(START, periods=horizon, freq="D")
    months = sorted({d.to_period("M").to_timestamp() for d in days})
    idx = np.array([months.index(d.to_period("M").to_timestamp()) for d in days])
    lag = INDICATORS["mpa_teu"].lag_days
    known = [((m + pd.offsets.MonthEnd(0)) + pd.Timedelta(days=lag) - START).days for m in months]
    return months, idx, known


def trailing_mean7(factor: np.ndarray) -> np.ndarray:
    """7-day trailing mean of daily factors [n, H], with factor 1 before day 0."""
    n, h = factor.shape
    padded = np.concatenate([np.ones((n, 6)), factor], axis=1)
    acc = padded[:, 0:h].copy()
    for s in range(1, 7):
        acc = acc + padded[:, s:s + h]
    return acc / 7.0


# ------------------------------------------------------------------ detector and ladder
def alarm_states(z: np.ndarray, k: float, persist: int, tol: int) -> np.ndarray:
    """Alarm state per draw and step for a frozen baseline; same rules as ``detect.detect``."""
    n, h = z.shape
    run = np.zeros(n, dtype=int)
    quiet = np.zeros(n, dtype=int)
    active = np.zeros(n, dtype=bool)
    out = np.zeros((n, h), dtype=bool)
    for t in range(h):
        b = z[:, t] >= k
        run = np.where(b, run + 1, 0)
        quiet = np.where(active & ~b, quiet + 1, np.where(active & b, 0, quiet))
        close = active & ~b & (quiet >= tol)
        open_ = ~active & b & (run >= persist)
        active = (active & ~close) | open_
        quiet = np.where(open_ | close, 0, quiet)
        out[:, t] = active
    return out


def known_daily(alarm: np.ndarray, lag: int) -> np.ndarray:
    out = np.zeros_like(alarm)
    out[:, lag:] = alarm[:, :alarm.shape[1] - lag]
    return out


def known_monthly(alarm_m: np.ndarray, known_day: list[int], horizon: int) -> np.ndarray:
    n = alarm_m.shape[0]
    out = np.zeros((n, horizon), dtype=bool)
    for j, kd in enumerate(known_day):
        if kd >= horizon:
            continue
        end = min([d for d in known_day[j + 1:] if d > kd] + [horizon])
        out[:, max(kd, 0):end] = alarm_m[:, j:j + 1]
    return out


def ladder(known: dict[str, np.ndarray]) -> np.ndarray:
    """Daily level per draw, the rules of ``backtest.posture``."""
    any_alarm = np.zeros_like(next(iter(known.values())))
    route = np.zeros(any_alarm.shape, dtype=int)
    local = np.zeros_like(any_alarm)
    outcome = np.zeros_like(any_alarm)
    for k, a in known.items():
        any_alarm = any_alarm | a
        if k in ROUTE:
            route = route + a
        elif k in LOCAL:
            local = local | a
        elif k in MONTHLY:
            outcome = outcome | a
    alert = (route >= 2) | ((route >= 1) & local)
    level = np.where(any_alarm, 1, 0)
    level = np.where(alert, 2, level)
    return np.where(alert & outcome, 3, level)


# ------------------------------------------------------------------ scenario shocks
def ramp_window(t: np.ndarray, onset: np.ndarray, duration: np.ndarray, ramp: float) -> np.ndarray:
    """0 before onset, linear to 1 over ``ramp`` days, 1 until onset + duration, linear back to 0."""
    up = np.clip((t[None, :] - onset[:, None]) / ramp, 0.0, 1.0)
    down = np.clip((onset[:, None] + duration[:, None] - t[None, :]) / ramp, 0.0, 1.0)
    return np.minimum(up, down)


def queue_paths(n: int, horizon: int, onset, closure, severity, extra) -> tuple[np.ndarray, np.ndarray]:
    """Daily service factor (served / normal arrivals) and backlog (in days of normal arrivals) of a
    port whose service drops to 1 - severity during the closure and then runs at 1 + extra."""
    service = np.ones((n, horizon))
    backlog = np.zeros((n, horizon))
    b = np.zeros(n)
    for t in range(horizon):
        # fraction of day t inside the closure window [onset, onset + closure)
        inside = np.clip(np.minimum(t + 1.0, onset + closure) - np.maximum(float(t), onset), 0.0, 1.0)
        cap = 1.0 - severity * inside + extra * (1.0 - inside)
        served = np.minimum(cap, 1.0 + b)
        b = b + 1.0 - served
        service[:, t] = served
        backlog[:, t] = b
    return service, backlog


def monthly_mean(daily: np.ndarray, mon_idx: np.ndarray, n_months: int) -> np.ndarray:
    """Mean of daily values [n, H] over each month's days, summed in day order."""
    out = np.zeros((daily.shape[0], n_months))
    for j in range(n_months):
        days = [d for d in range(daily.shape[1]) if mon_idx[d] == j]
        acc = np.zeros(daily.shape[0])
        for d in days:
            acc = acc + daily[:, d]
        out[:, j] = acc / len(days)
    return out


def simulate(name: str, frames, events: pd.DataFrame, params: dict, sd_params: sd.Params, voyage_values: dict,
             d_now: float, b0_containers: float, k: float, persist: int, n: int | None = None) -> dict:
    """One scenario: returns paths, alarms, levels and the cost draws."""
    allp = params["all"]
    n = n or int(float(allp["n_draws"]["a"]))
    horizon = int(float(allp["horizon_days"]["a"]))
    seed = int(float(allp["seed"]["a"]))
    # Common random numbers: every scenario draws the same noise (its own generator, stream 99), so a
    # difference from the control on the same draw is caused by the scenario's shock.
    noise_rng = np.random.default_rng([seed, 99])
    rng = np.random.default_rng([seed, SCENARIOS.index(name)])
    base = baselines(frames)
    res_d, res_m = residuals(frames, base, events, int(float(allp["noise_window"]["a"])))
    nblocks = -(-horizon // BLOCK)
    starts = noise_rng.integers(0, res_d.shape[0] - BLOCK, size=(n, nblocks))
    rows = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(n, nblocks * BLOCK)[:, :horizon]
    months, mon_idx, known_day = month_layout(horizon)
    mrows = noise_rng.integers(0, res_m.shape[0], size=(n, len(months)))
    t = np.arange(horizon, dtype=float)
    F = {key: np.ones((n, horizon)) for key in DAILY}           # daily-rate factors
    G = {key: np.zeros((n, len(months))) for key in MONTHLY}    # monthly shifts (relative or log)
    p = params.get(name, {})
    costs: dict[str, np.ndarray] = {}
    onset = np.zeros(n)
    if name == "gulf":
        onset, dur = draw(rng, p["onset_day"], n), draw(rng, p["duration_days"], n)
        w = ramp_window(t, onset, dur, float(p["ramp_days"]["a"]))
        F["cp_malacca"] = 1.0 - draw(rng, p["malacca_drop"], n)[:, None] * w
        F["sg_calls_container"] = 1.0 - draw(rng, p["sg_calls_change"], n)[:, None] * w
        F["cp_hormuz"] = 1.0 - draw(rng, p["hormuz_drop"], n)[:, None] * w
        dp = draw(rng, p["bunker_increase_usd_t"], n)
        cape0 = _route_cost(voyage_values, "cape")
        costs["cape_usd_per_teu_change"] = np.array([
            _route_cost(voyage_values, "cape", bunker_usd_t=voyage_values["bunker_usd_t"] + x) - cape0 for x in dp])
        costs["bunker_increase_usd_t"] = dp
    elif name == "strait":
        onset, closure = draw(rng, p["onset_day"], n), draw(rng, p["closure_days"], n)
        sev, mshare = draw(rng, p["severity"], n), draw(rng, p["malacca_share"], n)
        extra, tpc = draw(rng, p["catchup_extra"], n), draw(rng, p["tpc_rise"], n)
        service, backlog = queue_paths(n, horizon, onset, closure, sev, extra)
        F["sg_calls_container"] = service
        F["sg_box_volume"] = service
        mal, _ = queue_paths(n, horizon, onset, closure, sev * mshare, extra)
        F["cp_malacca"] = mal
        inc_month = np.minimum(np.floor(onset).astype(int), horizon - 1)
        G["sg_teu_per_call"][np.arange(n), mon_idx[inc_month]] = tpc
        calls_per_day = base["sg_calls_container"]["median"] / 7.0
        ship_days = np.array([math.fsum(row) for row in backlog]) * calls_per_day
        day_cost = voyage_values["charter_usd_day"] + voyage_values["aux_fuel_port_tpd"] * voyage_values["bunker_usd_t"]
        costs["waiting_ship_days"] = ship_days
        costs["waiting_cost_usd_m"] = ship_days * day_cost / 1e6
    elif name == "reopen":
        start, ramp = draw(rng, p["start_day"], n), draw(rng, p["ramp_days"], n)
        share, phi = draw(rng, p["return_share"], n), draw(rng, p["friction"], n)
        onset = start
        q = replace(sd_params, phi=phi, tau_n=float(p["tau_n_days"]["a"]))
        target = lambda tt: d_now * (1.0 - share * np.clip((tt - start) / ramp, 0.0, 1.0))  # noqa: E731
        y0 = tuple(np.full(n, v) for v in sd.initial_state(sd_params, d_now))
        traj = sd.simulate(q, horizon, target=target, y0=y0)
        D = np.stack(sd.daily_means(traj, 0), axis=1)
        Dc = np.stack(sd.daily_means(traj, 1), axis=1)
        Q = np.stack(sd.daily_means(traj, 4), axis=1)
        per_day = b0_containers / 7.0           # pre-crisis Bab el-Mandeb container transits per day
        for key in ("cp_bab", "cp_suez"):       # returning container ships pass both
            F[key] = 1.0 + per_day * (d_now - D) / (base[key]["median"] / 7.0)
        F["cp_cape"] = 1.0 - sd_params.kappa * per_day * (d_now - Dc) / (base["cp_cape"]["median"] / 7.0)
        F["sg_calls_container"] = 1.0 - sd_params.theta_c * Q
        G["sg_teu_per_call"] = sd_params.theta_t * monthly_mean(Q, mon_idx, len(months))
        war, mult = draw(rng, p["war_risk_pct"], n), draw(rng, p["toll_multiplier"], n)
        cape = _route_cost(voyage_values, "cape")
        suez = np.array([_route_cost(voyage_values, "suez", war_risk_pct=w, suez_surcharge=m_ - 1.0,
                                     suez_rebate=0.0) for w, m_ in zip(war, mult)])
        costs["suez_minus_cape_usd_per_teu"] = suez - cape
        costs["war_risk_pct"] = war
        costs["peak_bunching_q"] = Q.max(axis=1)
        costs["lowest_bunching_q"] = Q.min(axis=1)
    # ---- indicator paths and z-scores against the frozen baseline
    z_d, x_d = {}, {}
    for j, key in enumerate(DAILY):
        b = base[key]
        x = b["median"] * (1.0 + res_d[rows, j]) * trailing_mean7(F[key])
        x_d[key] = x
        z_d[key] = b["sign"] * (x - b["median"]) / b["scale"]
    z_m, x_m = {}, {}
    for j, key in enumerate(MONTHLY):
        b = base[key]
        r = res_m[mrows, j]
        if b["level"]:
            x = b["median"] * (1.0 + r) * (1.0 + G[key])
        else:
            x = b["median"] + r + G[key]
        x_m[key] = x
        z_m[key] = b["sign"] * (x - b["median"]) / b["scale"]
    alarms = {key: alarm_states(z_d[key], k, persist, 7) for key in DAILY}
    alarms_m = {key: alarm_states(z_m[key], k, 1, 1) for key in MONTHLY}
    known = {key: known_daily(a, INDICATORS[key].lag_days) for key, a in alarms.items()}
    known.update({key: known_monthly(a, known_day, horizon) for key, a in alarms_m.items()})
    level = ladder(known)
    return {"name": name, "n": n, "horizon": horizon, "onset": onset, "x_daily": x_d, "z_daily": z_d, "x_monthly": x_m,
            "alarms": alarms, "alarms_monthly": alarms_m, "level": level, "costs": costs, "base": base,
            "rows": rows, "factors": F}


def _route_cost(v: dict, routing: str, **override) -> float:
    w = {**v, **override}
    legs, eu, schedule = _CACHE["legs"], _CACHE["eu"], _CACHE["schedule"]
    return V.round_voyage(w, legs, eu, schedule, routing)["usd_per_teu"]


_CACHE = {"legs": V.load_legs(), "eu": V.load_ports(), "schedule": V.load_schedule()}


# ------------------------------------------------------------------ summaries
def pct(a: np.ndarray, q=(5, 25, 50, 75, 95)) -> list[float]:
    return [float(v) for v in np.percentile(a, q)]


def first_day(mask: np.ndarray) -> np.ndarray:
    """First day each row is True, -1 if never."""
    any_ = mask.any(axis=1)
    return np.where(any_, mask.argmax(axis=1), -1)


def exact_check(res: dict, frames: dict, k: float, persist: int, keys=("cp_malacca", "sg_calls_container"),
                draws: int = 20, history_days: int = 600) -> list[dict]:
    """Re-run ``detect.detect`` on the last ``history_days`` of real history plus the simulated path for
    ``draws`` draws, and compare the breach days (z >= k) in the horizon with the frozen-baseline run."""
    out = []
    params = Dt.Params(**{**Dt.DAILY.__dict__, "k": k, "persist": persist})
    for key in keys:
        hist = frames[key]["value"].values[-history_days:]
        agree = total = 0
        dz = []
        for i in range(min(draws, res["n"])):
            series = np.concatenate([hist, res["x_daily"][key][i]])
            f, _ = Dt.detect(series, INDICATORS[key].direction, params)
            exact = f["breach"].values[-res["horizon"]:]
            frozen = res["z_daily"][key][i] >= k
            agree += int((exact == frozen).sum())
            total += res["horizon"]
            ze = f["z"].values[-res["horizon"]:]
            dz.extend(abs(a - b) for a, b in zip(ze, res["z_daily"][key][i]) if np.isfinite(a))
        out.append({"scenario": res["name"], "indicator": key, "draws": min(draws, res["n"]),
                    "breach_day_agreement": agree / total, "median_abs_z_difference": float(np.median(dz))})
    return out


def run_all(frames, events: pd.DataFrame, sd_params: sd.Params, b0_containers: float, d_now: float, k: float,
            persist: int, n: int | None = None) -> dict:
    params = load_params()
    voyage_values = V.load_values()
    return {name: simulate(name, frames, events, params, sd_params, voyage_values, d_now, b0_containers, k,
                           persist, n) for name in SCENARIOS}


def start_date_of(day: int) -> dt.date:
    return (START + pd.Timedelta(days=int(day))).date()
