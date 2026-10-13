"""Robust, one-sided anomaly detection with persistence and re-baselining.

For each observation t the baseline is the median of up to ``window`` earlier
*clean* observations (those that were not themselves in breach), ending
``gap`` observations before t. The scale is 1.4826 x MAD with a floor.
The stress score is signed so that a positive z always means stress:

    z_t = sign * (x_t - median) / scale,  sign = -1 for "drop", +1 for "rise"

A breach is z_t >= k. An alarm is raised once ``persist`` consecutive
observations breach. It stays active until ``tol`` consecutive observations
are quiet. If an alarm stays active for ``sustain`` observations the shift is
declared *sustained*: the alarm closes, and the last ``sustain`` observations
are admitted into the baseline, so the series is judged against its new
normal from then on. Without that step a lasting shift (the Red Sea
diversions, for example) would keep one alarm open forever and hide any
second shock on the same route.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MAD_TO_SD = 1.4826


@dataclass(frozen=True)
class Params:
    k: float = 3.0
    persist: int = 3
    window: int = 364
    gap: int = 28
    tol: int = 7
    sustain: int = 182
    frac_floor: float = 0.05
    abs_floor: float = 5.0
    min_hist: int = 182


DAILY = Params()
MONTHLY = Params(k=3.0, persist=1, window=36, gap=0, tol=1, sustain=12,
                 frac_floor=0.0, abs_floor=0.02, min_hist=12)        # on log year-on-year change
MONTHLY_LEVEL = Params(k=3.0, persist=1, window=24, gap=0, tol=1, sustain=12,
                       frac_floor=0.02, abs_floor=0.0, min_hist=12)  # on the level itself


@dataclass
class Episode:
    start: int                 # index at which the alarm was raised
    first_breach: int          # index of the first breach in the run
    end: int                   # index of the last breach before the alarm closed
    peak_z: float
    sustained: bool = False
    rebaseline_at: int | None = None
    extra: dict = field(default_factory=dict)


def robust_scale(values: np.ndarray, median: float, p: Params) -> float:
    mad = float(np.median(np.abs(values - median)))
    return max(MAD_TO_SD * mad, p.frac_floor * abs(median), p.abs_floor)


def detect(x: np.ndarray, direction: str, p: Params) -> tuple[pd.DataFrame, list[Episode]]:
    """Run the detector over a 1-D array. Returns a per-observation frame and episodes."""
    if direction not in ("drop", "rise"):
        raise ValueError(direction)
    sign = -1.0 if direction == "drop" else 1.0
    x = np.asarray(x, dtype=float)
    n = len(x)
    clean = np.zeros(n, dtype=bool)
    med = np.full(n, np.nan)
    scl = np.full(n, np.nan)
    z = np.full(n, np.nan)
    breach = np.zeros(n, dtype=bool)
    active_arr = np.zeros(n, dtype=bool)

    episodes: list[Episode] = []
    run = 0                # consecutive breaches
    run_start = -1
    active: Episode | None = None
    quiet = 0
    for t in range(n):
        if not np.isfinite(x[t]):
            continue
        hi = t - p.gap                      # baseline uses indices < hi
        if hi > 0:
            idx = np.flatnonzero(clean[:hi])
            idx = idx[-p.window:]
            if len(idx) >= p.min_hist:
                base = x[idx]
                m = float(np.median(base))
                s = robust_scale(base, m, p)
                med[t], scl[t] = m, s
                if s > 0:                       # a zero scale gives no decision
                    z[t] = sign * (x[t] - m) / s
        is_breach = bool(np.isfinite(z[t]) and z[t] >= p.k)
        breach[t] = is_breach
        if not is_breach:
            clean[t] = True
            run = 0
            if active is not None:
                quiet += 1
                if quiet >= p.tol:
                    episodes.append(active)
                    active = None
        else:
            if run == 0:
                run_start = t
            run += 1
            if active is not None:
                quiet = 0
                active.end = t
                active.peak_z = max(active.peak_z, float(z[t]))
            elif run >= p.persist:
                active = Episode(start=t, first_breach=run_start, end=t,
                                 peak_z=float(np.nanmax(z[run_start:t + 1])))
                quiet = 0
        if active is not None:
            active_arr[t] = True
            if t - active.start + 1 >= p.sustain:
                lo = t - p.sustain + 1
                clean[:lo] = False                      # forget the old regime
                clean[lo:t + 1] = np.isfinite(x[lo:t + 1])
                active.sustained = True
                active.rebaseline_at = t
                episodes.append(active)
                active = None
                run = 0
    if active is not None:
        episodes.append(active)
    frame = pd.DataFrame({"value": x, "median": med, "scale": scl, "z": z,
                          "breach": breach, "alarm": active_arr})
    return frame, episodes


def threshold_level(x: np.ndarray, threshold: float, persist: int) -> tuple[pd.DataFrame, list[Episode]]:
    """For an index that is already in standard-deviation units (GSCPI)."""
    x = np.asarray(x, dtype=float)
    breach = np.isfinite(x) & (x >= threshold)
    episodes: list[Episode] = []
    alarm = np.zeros(len(x), dtype=bool)
    run, active = 0, None
    for t in range(len(x)):
        if breach[t]:
            run += 1
            if active is None and run >= persist:
                active = Episode(start=t, first_breach=t - run + 1, end=t, peak_z=float(x[t]))
            elif active is not None:
                active.end = t
                active.peak_z = max(active.peak_z, float(x[t]))
        else:
            run = 0
            if active is not None:
                episodes.append(active)
                active = None
        alarm[t] = active is not None
    if active is not None:
        episodes.append(active)
    frame = pd.DataFrame({"value": x, "median": np.nan, "scale": np.nan, "z": x,
                          "breach": breach, "alarm": alarm})
    return frame, episodes
