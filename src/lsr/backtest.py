"""Backtest the indicator set against labelled disruptions.

Protocol
--------
* Events are labelled in ``data/events.csv`` with a documented onset, an
  assessment window, a dev/holdout split, and the indicators *expected* to
  move. The expected list was written from the event descriptions, before
  the detector was tuned.
* Two detector settings are tuned on the development period only
  (alarms raised up to 2022-12-31): the z threshold ``k`` and the daily
  persistence. The monthly detector uses the same ``k``. GSCPI uses a fixed
  rule (>= 1.0 standard deviation for two months).
* Every alarm is dated by when it could have been known: the day the rule
  fires plus the publication lag of its source.
* An alarm is a **true alarm** if its indicator is in an event's expected list
  and it was raised between 28 days before onset and the end of that event's
  window. Every other alarm is a **false alarm**, including alarms that
  coincide with an event but on an indicator that was not expected to move.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import detect as D
from .indicators import INDICATORS, load_daily, load_monthly, log_yoy

ROOT = Path(__file__).resolve().parents[2]
EVAL_START = pd.Timestamp("2020-01-01")   # first year with a full PortWatch baseline
DEV_END = pd.Timestamp("2022-12-31")
PRE_ONSET_DAYS = 28
GSCPI_THRESHOLD = 1.0
GSCPI_PERSIST = 2


@dataclass
class Alarm:
    indicator: str
    raised: pd.Timestamp       # date the rule fired (end of the observed period)
    known: pd.Timestamp        # raised + publication lag
    first_breach: pd.Timestamp
    end: pd.Timestamp
    peak_z: float
    sustained: bool
    rebaseline: pd.Timestamp | None


def load_events(path: Path | None = None) -> pd.DataFrame:
    e = pd.read_csv(path or ROOT / "data" / "events.csv", dtype=str, keep_default_na=False)
    for c in ("onset", "window_end", "sg_reference_date"):
        e[c] = pd.to_datetime(e[c].replace("", None))
    e["expected"] = e["expected"].str.split(";")
    return e


def month_end(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.offsets.MonthEnd(0)


def run_detectors(daily: pd.DataFrame, monthly: pd.DataFrame, pd_: D.Params, pm: D.Params,
                  pml: D.Params | None = None, transforms: dict[str, str] | None = None):
    frames: dict[str, pd.DataFrame] = {}
    alarms: list[Alarm] = []
    for key, ind in INDICATORS.items():
        if ind.freq == "D":
            s = daily[key]
            frame, eps = D.detect(s.values, ind.direction, pd_)
            idx = s.index
            dates = lambda i: idx[i]  # noqa: E731
        else:
            s = monthly[key].dropna()
            tr = (transforms or {}).get(key, ind.transform)
            if key == "gscpi":
                frame, eps = D.threshold_level(s.values, GSCPI_THRESHOLD, GSCPI_PERSIST)
            elif tr == "level":
                frame, eps = D.detect(s.values, ind.direction, pml or replace(D.MONTHLY_LEVEL, k=pm.k))
            else:
                frame, eps = D.detect(log_yoy(s).values, ind.direction, pm)
            idx = s.index
            dates = lambda i: month_end(idx[i])  # noqa: E731
        frame.index = idx
        frames[key] = frame
        for ep in eps:
            raised = dates(ep.start)
            alarms.append(Alarm(
                indicator=key, raised=raised, known=raised + pd.Timedelta(days=ind.lag_days),
                first_breach=dates(ep.first_breach), end=dates(ep.end), peak_z=ep.peak_z,
                sustained=ep.sustained,
                rebaseline=dates(ep.rebaseline_at) if ep.rebaseline_at is not None else None))
    return frames, alarms


def match(alarms: list[Alarm], events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for a in alarms:
        if a.raised < EVAL_START:
            continue
        hit = None
        for _, e in events.iterrows():
            if a.indicator in e["expected"] and \
               e["onset"] - pd.Timedelta(days=PRE_ONSET_DAYS) <= a.raised <= e["window_end"]:
                hit = e["event_id"]
                break
        rows.append({**a.__dict__, "event": hit, "true_alarm": hit is not None,
                     "period": "dev" if a.raised <= DEV_END else "holdout"})
    return pd.DataFrame(rows)


def evaluated_years(frames: dict[str, pd.DataFrame], period: str) -> dict[str, float]:
    out = {}
    for key, f in frames.items():
        ok = f.index[np.isfinite(f["z"].values)]
        if INDICATORS[key].freq == "M":
            ok = ok + pd.offsets.MonthEnd(0)
        ok = ok[ok >= EVAL_START]
        sel = ok[ok <= DEV_END] if period == "dev" else ok[ok > DEV_END]
        unit = 365.25 if INDICATORS[key].freq == "D" else 12.0
        out[key] = len(sel) / unit
    return out


def detections(matched: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, e in events.iterrows():
        for ind in e["expected"]:
            m = matched[(matched.event == e.event_id) & (matched.indicator == ind)].sort_values("raised")
            if len(m):
                a = m.iloc[0]
                rows.append({"event": e.event_id, "split": e.split, "indicator": ind, "detected": True,
                             "raised": a.raised.date(), "known": a.known.date(),
                             "lag_raised_days": (a.raised - e.onset).days,
                             "lag_known_days": (a.known - e.onset).days, "peak_z": round(a.peak_z, 1)})
            else:
                rows.append({"event": e.event_id, "split": e.split, "indicator": ind, "detected": False,
                             "raised": None, "known": None, "lag_raised_days": None,
                             "lag_known_days": None, "peak_z": None})
    return pd.DataFrame(rows)


def score(matched: pd.DataFrame, det: pd.DataFrame, frames, period: str) -> dict:
    d = det[det.split == period]
    fa = matched[(matched.period == period) & (~matched.true_alarm)]
    years = sum(evaluated_years(frames, period).values())
    return {"pairs": len(d), "detected": int(d.detected.sum()),
            "recall": float(d.detected.mean()) if len(d) else float("nan"),
            "false_alarms": len(fa), "indicator_years": round(years, 1),
            "fa_per_indicator_year": len(fa) / years if years else float("nan")}


GRID_K = (2.5, 3.0, 3.5, 4.0)
GRID_PERSIST = (1, 3, 5, 7)


def evaluate(k: float, persist: int, daily=None, monthly=None, events=None,
             transforms: dict[str, str] | None = None) -> dict:
    daily = load_daily() if daily is None else daily
    monthly = load_monthly() if monthly is None else monthly
    events = load_events() if events is None else events
    pd_ = replace(D.DAILY, k=k, persist=persist)
    pm = replace(D.MONTHLY, k=k)
    pml = replace(D.MONTHLY_LEVEL, k=k)
    frames, alarms = run_detectors(daily, monthly, pd_, pm, pml, transforms)
    matched = match(alarms, events)
    det = detections(matched, events)
    return {"frames": frames, "matched": matched, "det": det,
            "dev": score(matched, det, frames, "dev"), "holdout": score(matched, det, frames, "holdout")}


def tune(daily, monthly, events) -> tuple[pd.DataFrame, tuple[float, int]]:
    rows = []
    for k, p in itertools.product(GRID_K, GRID_PERSIST):
        r = evaluate(k, p, daily, monthly, events)
        rows.append({"k": k, "persist_days": p,
                     **{f"dev_{a}": b for a, b in r["dev"].items()},
                     **{f"holdout_{a}": b for a, b in r["holdout"].items()}})
    grid = pd.DataFrame(rows)
    best = select(grid)
    return grid, best


def select(grid: pd.DataFrame) -> tuple[float, int]:
    """Max dev recall; then fewest dev false alarms per indicator-year; then larger k, longer persistence."""
    g = grid.sort_values(["dev_recall", "dev_fa_per_indicator_year", "k", "persist_days"],
                         ascending=[False, True, False, False])
    r = g.iloc[0]
    return float(r.k), int(r.persist_days)


def sg_lead(matched: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Lead of alarms over a documented Singapore-side reference date."""
    rows = []
    for _, e in events[events.sg_reference_date.notna()].iterrows():
        ids = [e.event_id] + ([e.upstream_event] if e.upstream_event else [])
        m = matched[matched.event.isin(ids)].sort_values("known")
        for ind, g in m.groupby("indicator", sort=False):
            a = g.iloc[0]
            rows.append({"event": e.event_id, "reference": e.sg_reference_date.date(),
                         "via_event": a.event, "indicator": ind, "known": a.known.date(),
                         "lead_days": (e.sg_reference_date - a.known).days})
    return pd.DataFrame(rows).sort_values(["event", "lead_days"], ascending=[True, False])


# ---------------------------------------------------------------- posture
LEVELS = {0: "Normal", 1: "Watch", 2: "Alert", 3: "Activate review"}
SG_OUTCOMES = ("mpa_teu", "sg_teu_per_call", "mpa_vessel_arrivals", "changi_air_cargo", "mpa_cargo")


def posture(frames: dict[str, pd.DataFrame], days: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily alert level using only what was known on each day.

    Watch: any indicator in alarm. Alert: two or more route indicators, or a
    route indicator together with a Singapore or regional one. Activate review:
    Alert plus a Singapore monthly outcome (throughput, TEU per call, arrivals,
    cargo, air cargo) in alarm.
    """
    known = {}
    for key, f in frames.items():
        ind = INDICATORS[key]
        lag = pd.Timedelta(days=ind.lag_days)
        if ind.freq == "D":
            s = f["alarm"].astype(float)
            s.index = s.index + lag
        else:
            s = f["alarm"].astype(float)
            s.index = s.index + pd.offsets.MonthEnd(0) + lag
        known[key] = s.reindex(days, method="ffill").fillna(0.0).astype(bool)
    k = pd.DataFrame(known)
    fam = {key: INDICATORS[key].family for key in k.columns}
    route = k[[c for c in k if fam[c] == "route"]].sum(axis=1)
    local = k[[c for c in k if fam[c] in ("singapore", "regional")]].any(axis=1)
    outcome = k[[c for c in SG_OUTCOMES if c in k]].any(axis=1)
    level = np.where(k.any(axis=1), 1, 0)
    alert = (route >= 2) | ((route >= 1) & local)
    level = np.where(alert, 2, level)
    level = np.where(alert & outcome, 3, level)
    out = pd.DataFrame({"level": level, "route_alarms": route, "local_alarm": local,
                        "outcome_alarm": outcome}, index=days)
    out["active"] = k.apply(lambda r: ";".join(c for c in k.columns if r[c]), axis=1)
    return out
