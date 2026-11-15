"""Calibrate the stock-and-flow model (``sd.py``) to the 2023-24 observations, block by block.

Blocks follow the causal order, so each is fitted to its own data with the upstream block fixed:

1. routing: onset ``t0`` (profiled over whole days), ``tau_d``, ``tau_c`` by Nelder-Mead; ``d_max`` and
   ``kappa`` in closed form (they enter the Bab el-Mandeb and Cape equations linearly). Data: IMF
   PortWatch container-ship transits, weekly (non-overlapping 7-day sums).
2. reliability: ``tau_a`` by golden-section search, ``beta`` in closed form, with ``tau_u`` fixed at one
   day (ASSUMED). A is not observed, so only the combined delay of capacity absorption and the
   reliability response is identified; it is reported as ``tau_a``. Data: Sea-Intelligence global
   schedule reliability, monthly (data/inputs/schedule_reliability_glp.csv).
3. Singapore: ``tau_q`` by golden-section search with ``tau_k = tau_q`` and ``adapt = 1`` (ASSUMED: an
   unconstrained fit put ``adapt`` at its bound of 1, and with full adaptation the two time constants
   are interchangeable, so only one is identified); ``theta_c`` and ``theta_t`` in closed form. Data:
   PortWatch Singapore container-ship calls (weekly) and MPA TEU per PortWatch call (monthly).

Uncertainty: Gauss-Newton covariance of each block's parameters with one residual variance per
series, inflated by (1 + rho) / (1 - rho) for lag-1 residual autocorrelation rho > 0, and a profile
over the onset day. Sums use math.fsum and the optimisers use only arithmetic, so the fit is the
same on every platform.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import replace

import pandas as pd

from ..indicators import RAW, load_monthly
from . import sd
from .inputs import INPUTS, load_parameters, read_csv

START = dt.date(2023, 6, 1)            # day 0 of the simulation
END = dt.date(2024, 12, 31)
N_DAYS = (END - START).days + 1
FIRST_WEEK = dt.date(2023, 7, 2)       # weekly samples: Sundays, each the end of a 7-day sum
PRE_END = dt.date(2023, 11, 15)        # baseline window for the weekly series: 1 Jul - 15 Nov 2023
PRE_MONTHS_TPC = ("2023-07", "2023-08", "2023-09", "2023-10", "2023-11")
PRE_MONTHS_GLP = ("2023-06", "2023-07", "2023-08", "2023-09", "2023-10")
ONSET_GRID = [dt.date(2023, 11, 20) + dt.timedelta(days=i) for i in range(42)]   # 20 Nov - 31 Dec 2023
DOCUMENTED_ONSET = dt.date(2023, 12, 15)                                     # data/events.csv


def day(d: dt.date) -> int:
    return (d - START).days


def mean(xs) -> float:
    xs = list(xs)
    return math.fsum(xs) / len(xs)


def sd_(xs) -> float:
    xs = list(xs)
    m = mean(xs)
    return math.sqrt(math.fsum((x - m) * (x - m) for x in xs) / (len(xs) - 1))


# ------------------------------------------------------------------ data
def observed(raw=RAW) -> dict:
    cp = pd.read_csv(raw / "portwatch_chokepoints_daily.csv", parse_dates=["date"])
    pt = pd.read_csv(raw / "portwatch_ports_daily.csv", parse_dates=["date"])

    def seven(frame, name, col):
        s = frame[frame.portname == name].set_index("date")[col].astype(float)
        s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
        return s.rolling(7, min_periods=7).sum()

    series = {"bab": seven(cp, "Bab el-Mandeb Strait", "n_container"),
              "cape": seven(cp, "Cape of Good Hope", "n_container"),
              "calls": seven(pt, "Singapore", "portcalls_container")}
    weeks = [FIRST_WEEK + dt.timedelta(days=7 * i) for i in range((END - FIRST_WEEK).days // 7 + 1)]
    out = {"weeks": weeks}
    for k, s in series.items():
        out[k] = [float(s.loc[pd.Timestamp(w)]) for w in weeks]
        pre = [float(v) for d, v in s.loc[pd.Timestamp("2023-07-01"):pd.Timestamp(PRE_END)].items()]
        out[f"{k}_base"] = mean(pre)
        out[f"{k}_pre_sd"] = sd_(pre[::7])
    m = load_monthly(raw)["sg_teu_per_call"]
    months = [f"{y}-{mo:02d}" for y in (2023, 2024) for mo in range(1, 13)
              if (y, mo) >= (2023, 7)]
    out["tpc_months"] = months
    out["tpc"] = [float(m.loc[pd.Timestamp(mo + "-01")]) for mo in months]
    out["tpc_base"] = mean(float(m.loc[pd.Timestamp(mo + "-01")]) for mo in PRE_MONTHS_TPC)
    out["tpc_pre_sd"] = sd_(float(m.loc[pd.Timestamp(mo + "-01")]) for mo in PRE_MONTHS_TPC)
    glp = [r for r in read_csv(INPUTS / "schedule_reliability_glp.csv") if r["reliability_pct"]]
    out["glp_months"] = [r["month"] for r in glp if r["used_in_fit"] == "1"]
    out["glp"] = [float(r["reliability_pct"]) for r in glp if r["used_in_fit"] == "1"]
    out["u0"] = 1.0 - mean(float(r["reliability_pct"]) for r in glp if r["month"] in PRE_MONTHS_GLP) / 100.0
    out["glp_pre_sd"] = sd_(float(r["reliability_pct"]) for r in glp if r["month"] in PRE_MONTHS_GLP)
    return out


def month_days(month: str) -> tuple[int, int]:
    y, m = map(int, month.split("-"))
    first = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return day(first), day(nxt)


# ------------------------------------------------------------------ model observables
def week_means(daily: list, weeks: list[dt.date]) -> list[float]:
    """Mean of the daily values over the 7 days ending on each sample day."""
    return [math.fsum(daily[day(w) - 6: day(w) + 1]) / 7.0 for w in weeks]


def month_means(daily: list, months: list[str]) -> list[float]:
    out = []
    for mo in months:
        a, b = month_days(mo)
        out.append(math.fsum(daily[a:b]) / (b - a))
    return out


def observables(p: sd.Params, obs: dict, traj=None) -> dict:
    traj = traj or sd.simulate(p, N_DAYS)
    D, Dc, U, Q = (sd.daily_means(traj, i) for i in (0, 1, 3, 4))
    b0, c0 = obs["bab_base"], obs["cape_base"]
    return {"bab": [b0 * (1.0 - x) for x in week_means(D, obs["weeks"])],
            "cape": [c0 + p.kappa * b0 * x for x in week_means(Dc, obs["weeks"])],
            "glp": [100.0 * (1.0 - x) for x in month_means(U, obs["glp_months"])],
            "calls": [obs["calls_base"] * (1.0 - p.theta_c * x) for x in week_means(Q, obs["weeks"])],
            "tpc": [obs["tpc_base"] * (1.0 + p.theta_t * x) for x in month_means(Q, obs["tpc_months"])]}


# ------------------------------------------------------------------ optimisers
def nelder_mead(fun, x0, step, lo, hi, max_iter=600, tol=1e-9):
    """Bounded Nelder-Mead: candidates are clipped into [lo, hi]. Returns (x, f, iterations)."""
    def clip(x):
        return [min(max(v, a), b) for v, a, b in zip(x, lo, hi)]

    n = len(x0)
    pts = [clip(list(x0))]
    for i in range(n):
        x = list(x0)
        x[i] = x[i] + step[i]
        pts.append(clip(x))
    vals = [fun(x) for x in pts]
    it = 0
    for it in range(1, max_iter + 1):
        order = sorted(range(n + 1), key=lambda i: (vals[i], i))
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        spread = max(abs(v - vals[0]) for v in vals)
        size = max(abs(pts[i][j] - pts[0][j]) for i in range(1, n + 1) for j in range(n))
        if spread <= tol * (1.0 + abs(vals[0])) and size <= 1e-6:
            break
        c = [math.fsum(pts[i][j] for i in range(n)) / n for j in range(n)]
        xr = clip([c[j] + (c[j] - pts[-1][j]) for j in range(n)])
        fr = fun(xr)
        if fr < vals[0]:
            xe = clip([c[j] + 2.0 * (xr[j] - c[j]) for j in range(n)])
            fe = fun(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            if fr < vals[-1]:
                xc = clip([c[j] + 0.5 * (xr[j] - c[j]) for j in range(n)])
            else:
                xc = clip([c[j] + 0.5 * (pts[-1][j] - c[j]) for j in range(n)])
            fc = fun(xc)
            if fc < min(fr, vals[-1]):
                pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    pts[i] = clip([pts[0][j] + 0.5 * (pts[i][j] - pts[0][j]) for j in range(n)])
                    vals[i] = fun(pts[i])
    best = min(range(n + 1), key=lambda i: (vals[i], i))
    return pts[best], vals[best], it


def golden(fun, a, b, tol=1e-6, max_iter=200):
    g = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = fun(c), fun(d)
    for _ in range(max_iter):
        if b - a <= tol * (1.0 + abs(a) + abs(b)):
            break
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = fun(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = fun(d)
    x = (a + b) / 2.0
    return x, fun(x)


def ls_coef(y: list[float], x: list[float]) -> float:
    """Least-squares coefficient of y = b x (no intercept)."""
    den = math.fsum(v * v for v in x)
    return math.fsum(a * b for a, b in zip(y, x)) / den if den > 0 else 0.0


def sse(r: list[float]) -> float:
    return math.fsum(v * v for v in r)


# ------------------------------------------------------------------ blocks
def fit_routing(obs: dict, base: sd.Params, onset_days: list[int]) -> tuple[sd.Params, list[dict]]:
    b0, c0 = obs["bab_base"], obs["cape_base"]
    yb = [b0 - v for v in obs["bab"]]
    yc = [v - c0 for v in obs["cape"]]
    wb, wc = 1.0 / (obs["bab_pre_sd"] ** 2 * len(yb)), 1.0 / (obs["cape_pre_sd"] ** 2 * len(yc))

    def solve(t0, tau_d, tau_c):
        p = replace(base, t0=float(t0), d_max=1.0, tau_d=tau_d, tau_c=tau_c, kappa=1.0)
        traj = sd.simulate(p, N_DAYS)
        gb = [b0 * x for x in week_means(sd.daily_means(traj, 0), obs["weeks"])]
        gc = [b0 * x for x in week_means(sd.daily_means(traj, 1), obs["weeks"])]
        a, bk = ls_coef(yb, gb), ls_coef(yc, gc)
        f = wb * sse([y - a * g for y, g in zip(yb, gb)]) + wc * sse([y - bk * g for y, g in zip(yc, gc)])
        return f, a, bk

    profile, best = [], None
    x0 = [5.0, 10.0]
    for t0 in onset_days:
        x, f, _ = nelder_mead(lambda z: solve(t0, z[0], z[1])[0], x0, [2.0, 4.0], [0.5, 0.5], [60.0, 90.0])
        _, a, bk = solve(t0, x[0], x[1])
        profile.append({"t0": t0, "objective": f, "tau_d": x[0], "tau_c": x[1], "d_max": a, "kappa": bk / a})
        if best is None or f < best["objective"]:
            best = profile[-1]
        x0 = x
    p = replace(base, t0=float(best["t0"]), d_max=best["d_max"], tau_d=best["tau_d"], tau_c=best["tau_c"],
                kappa=best["kappa"])
    return p, profile


SD_INPUTS = load_parameters(INPUTS / "sd_parameters.csv")
TAU_U = SD_INPUTS["tau_u_days"]["value"]          # ASSUMED (see data/inputs/sd_parameters.csv)
TAU_A_RANGE = (SD_INPUTS["tau_a_search_days"]["low"], SD_INPUTS["tau_a_search_days"]["high"])
TAU_Q_RANGE = (SD_INPUTS["tau_q_search_days"]["low"], SD_INPUTS["tau_q_search_days"]["high"])


def fit_reliability(obs: dict, p: sd.Params, tau_a: float | None = None) -> sd.Params:
    """Fit ``beta`` (closed form) and ``tau_a`` (golden section), or only ``beta`` if ``tau_a`` is given."""
    y = [100.0 * (1.0 - p.u0) - v for v in obs["glp"]]

    def solve(ta):
        q = replace(p, beta=1.0, tau_u=TAU_U, tau_a=ta)
        traj = sd.simulate(q, N_DAYS)
        x = [100.0 * (m - p.u0) for m in month_means(sd.daily_means(traj, 3), obs["glp_months"])]
        b = ls_coef(y, x)
        return sse([a - b * c for a, c in zip(y, x)]), b

    if tau_a is None:
        tau_a, _ = golden(lambda t: solve(t)[0], *TAU_A_RANGE)
    return replace(p, tau_u=TAU_U, tau_a=tau_a, beta=solve(tau_a)[1])


def fit_singapore(obs: dict, p: sd.Params) -> sd.Params:
    yc = [1.0 - v / obs["calls_base"] for v in obs["calls"]]
    yt = [v / obs["tpc_base"] - 1.0 for v in obs["tpc"]]
    wc = 1.0 / ((obs["calls_pre_sd"] / obs["calls_base"]) ** 2 * len(yc))
    wt = 1.0 / ((obs["tpc_pre_sd"] / obs["tpc_base"]) ** 2 * len(yt))

    def solve(tau):
        q = replace(p, tau_q=tau, tau_k=tau, adapt=1.0)
        Q = sd.daily_means(sd.simulate(q, N_DAYS), 4)
        qw, qm = week_means(Q, obs["weeks"]), month_means(Q, obs["tpc_months"])
        tc, tt = ls_coef(yc, qw), ls_coef(yt, qm)
        fc = sse([y - tc * a for y, a in zip(yc, qw)])
        ft = sse([y - tt * a for y, a in zip(yt, qm)])
        return wc * fc + wt * ft, tc, tt

    tau, _ = golden(lambda t: solve(t)[0], *TAU_Q_RANGE)
    _, tc, tt = solve(tau)
    return replace(p, tau_q=tau, tau_k=tau, adapt=1.0, theta_c=tc, theta_t=tt)


def calibrate(obs: dict | None = None, tau_a: float | None = None, onset_days: list[int] | None = None) -> dict:
    """Fit all three blocks. ``tau_a`` given: hold it fixed (used for the sensitivity check)."""
    obs = obs or observed()
    base = sd.Params(u0=obs["u0"])
    routing, profile = fit_routing(obs, base, onset_days or [day(d) for d in ONSET_GRID])
    p = fit_singapore(obs, fit_reliability(obs, routing, tau_a))
    return {"params": p, "routing": routing, "profile": profile, "obs": obs}


def downstream(obs: dict, routing: sd.Params, tau_a: float | None) -> sd.Params:
    """Refit the reliability and Singapore blocks on a fixed routing fit."""
    return fit_singapore(obs, fit_reliability(obs, routing, tau_a))


# ------------------------------------------------------------------ uncertainty
BLOCKS = {"routing": ("d_max", "tau_d", "tau_c", "kappa"), "reliability": ("beta",),
          "singapore": ("tau_q", "theta_c", "theta_t")}
BLOCK_SERIES = {"routing": ("bab", "cape"), "reliability": ("glp",), "singapore": ("calls", "tpc")}


def set_param(p: sd.Params, name: str, value: float) -> sd.Params:
    """Set one parameter; ``tau_q`` carries ``tau_k`` with it (they are tied in the calibration)."""
    if name == "tau_q":
        return replace(p, tau_q=value, tau_k=value)
    return replace(p, **{name: value})


def residuals(p: sd.Params, obs: dict) -> dict:
    m = observables(p, obs)
    return {k: [a - b for a, b in zip(obs[k], m[k])] for k in m}


def invert(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    m = [list(r) + [1.0 if i == j else 0.0 for j in range(n)] for i, r in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: (abs(m[r][c]), -r))
        if m[piv][c] == 0:
            raise ValueError("singular matrix")
        m[c], m[piv] = m[piv], m[c]
        pv = m[c][c]
        m[c] = [v / pv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0:
                fac = m[r][c]
                m[r] = [v - fac * w for v, w in zip(m[r], m[c])]
    return [r[n:] for r in m]


def lag1(xs: list[float]) -> float:
    m = mean(xs)
    num = math.fsum((a - m) * (b - m) for a, b in zip(xs, xs[1:]))
    den = math.fsum((a - m) * (a - m) for a in xs)
    return num / den if den > 0 else 0.0


def covariance(p: sd.Params, obs: dict, block: str) -> dict:
    names, series = BLOCKS[block], BLOCK_SERIES[block]
    r0 = residuals(p, obs)
    var = {s: sse(r0[s]) / len(r0[s]) for s in series}
    theta = [getattr(p, n) for n in names]
    cols = []
    for j, n in enumerate(names):
        h = 1e-4 * max(abs(theta[j]), 1e-2)
        up = residuals(set_param(p, n, theta[j] + h), obs)
        dn = residuals(set_param(p, n, theta[j] - h), obs)
        cols.append([(u - d) / (2.0 * h) / math.sqrt(var[s]) for s in series for u, d in zip(up[s], dn[s])])
    k = len(names)
    jtj = [[math.fsum(a * b for a, b in zip(cols[i], cols[j])) for j in range(k)] for i in range(k)]
    cov = invert(jtj)
    rho = max(0.0, mean(lag1([v / math.sqrt(var[s]) for v in r0[s]]) for s in series))
    infl = (1.0 + rho) / (1.0 - rho)
    se = [math.sqrt(cov[i][i]) for i in range(k)]
    corr = [[cov[i][j] / (se[i] * se[j]) for j in range(k)] for i in range(k)]
    return {"names": names, "estimate": theta, "se": se, "se_ar1": [s * math.sqrt(infl) for s in se],
            "rho": rho, "corr": corr}


def fit_stats(p: sd.Params, obs: dict) -> list[dict]:
    m = observables(p, obs)
    rows = []
    for k in ("bab", "cape", "glp", "calls", "tpc"):
        y, f = obs[k], m[k]
        r = [a - b for a, b in zip(y, f)]
        ybar = mean(y)
        sst = math.fsum((a - ybar) * (a - ybar) for a in y)
        rows.append({"series": k, "n": len(y), "rmse": math.sqrt(sse(r) / len(r)),
                     "mae": math.fsum(abs(v) for v in r) / len(r),
                     "mape_pct": 100.0 * math.fsum(abs(a - b) / abs(a) for a, b in zip(y, f)) / len(y),
                     "r2": 1.0 - sse(r) / sst})
    return rows


def onset_interval(profile: list[dict], n_obs: int, inflation: float = 1.0) -> tuple[int, int]:
    """Onset days whose profile objective is within the chi-square(1) 95% bound of the best; the
    bound is widened by ``inflation`` (the autocorrelation factor) when given."""
    best = min(r["objective"] for r in profile)
    ok = [r["t0"] for r in profile if n_obs * math.log(r["objective"] / best) <= 3.84 * inflation]
    return min(ok), max(ok)


def tau_a_profile(obs: dict, p: sd.Params, grid: list[float]) -> list[dict]:
    """Reliability-block objective with ``tau_a`` held at each grid value (``beta`` refitted)."""
    out = []
    for ta in grid:
        q = fit_reliability(obs, p, ta)
        r = residuals(q, obs)["glp"]
        out.append({"tau_a": ta, "beta": q.beta, "sse": sse(r)})
    return out
