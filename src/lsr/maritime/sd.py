"""Stock-and-flow model of the Red Sea diversion and its echo in Singapore, with its own integrators.

Seven stocks, one day per step (time unit: days):

* ``D``  share of the pre-crisis Bab el-Mandeb container traffic that is diverted,
          ``dD/dt = (target(t) - D) / tau_d``; in the calibration ``target = d_max`` from the onset.
* ``Dc`` diverted ships reaching the Cape (a pipeline delay of D), ``dDc/dt = (D - Dc) / tau_c``.
* ``A``  capacity absorbed by the longer routes, in units of D, ``dA/dt = (D - A) / tau_a``.
          ``a_scale x A`` is the extra container-ship demand as a share of the fleet.
* ``U``  schedule unreliability (1 - share of arrivals on time),
          ``dU/dt = (u0 + beta (A + phi |D - N|) - U) / tau_u``. ``phi`` adds unreliability while the
          service network has not caught up with the routing (D away from N); it is 0 in the calibration.
* ``Q``  bunching pressure at Singapore, ``dQ/dt = ((U - u0) - K - Q) / tau_q``.
* ``K``  adaptation at Singapore (berths and yard brought into use, re-sequenced calls),
          ``dK/dt = (adapt (U - u0) - K) / tau_k``. ``K`` and ``Q`` form the balancing loop that lets the
          congestion fade while the diversion persists; ``1 - adapt`` of the pressure remains.
* ``N``  position of the service network (rotations, schedules), ``dN/dt = (D - N) / tau_n``; it only
          matters through ``phi`` (scenarios).

Observation equations (7-day sums or monthly means of the daily values):
``Bab = B0 (1 - D)``, ``Cape = C0 + kappa B0 Dc``, ``GLP = 1 - U``,
``calls = Cb (1 - theta_c Q)``, ``TEU/call = Tb (1 + theta_t Q)``.

The integrators work on tuples whose entries are floats or numpy arrays of equal shape, so the same
code runs the calibration (floats) and the Monte Carlo (one array element per draw). Only +, -, *, /
and abs() are used, which IEEE 754 rounds identically on every platform.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Sequence

STOCKS = ("D", "Dc", "A", "U", "Q", "K", "N")


def euler_step(f: Callable, t: float, y: tuple, dt: float) -> tuple:
    k = f(t, y)
    return tuple(yi + dt * ki for yi, ki in zip(y, k))


def rk4_step(f: Callable, t: float, y: tuple, dt: float) -> tuple:
    k1 = f(t, y)
    k2 = f(t + 0.5 * dt, tuple(yi + 0.5 * dt * ki for yi, ki in zip(y, k1)))
    k3 = f(t + 0.5 * dt, tuple(yi + 0.5 * dt * ki for yi, ki in zip(y, k2)))
    k4 = f(t + dt, tuple(yi + dt * ki for yi, ki in zip(y, k3)))
    return tuple(yi + dt / 6.0 * (a + 2.0 * b + 2.0 * c + d) for yi, a, b, c, d in zip(y, k1, k2, k3, k4))


def integrate(f: Callable, y0: Sequence, n_steps: int, dt: float = 1.0, t0: float = 0.0,
              method: str = "rk4") -> list[tuple]:
    """States at t0, t0 + dt, ..., t0 + n_steps * dt (n_steps + 1 rows)."""
    step = {"rk4": rk4_step, "euler": euler_step}[method]
    y = tuple(y0)
    out = [y]
    for i in range(n_steps):
        y = step(f, t0 + i * dt, y, dt)
        out.append(y)
    return out


@dataclass(frozen=True)
class Params:
    t0: float = 0.0        # onset (day index)
    d_max: float = 0.8     # diverted share after the onset
    tau_d: float = 7.0     # routing adjustment time (days)
    tau_c: float = 10.0    # Cape pipeline delay (days)
    kappa: float = 0.9     # Cape transits gained per Bab el-Mandeb transit lost
    tau_a: float = 30.0    # capacity-absorption delay (days) - ASSUMED, not estimated
    beta: float = 0.1      # unreliability per unit of absorbed capacity
    tau_u: float = 20.0    # unreliability adjustment time (days)
    u0: float = 0.36       # pre-crisis unreliability (from the 2023 GLP level)
    phi: float = 0.0       # re-routing friction (0 in the calibration; scenario input)
    tau_q: float = 30.0    # Singapore bunching adjustment time (days)
    tau_k: float = 60.0    # Singapore adaptation time (days)
    tau_n: float = 78.5    # time for the service network to follow the routing (days) - scenario input
    adapt: float = 0.7     # share of the pressure that adaptation eventually removes
    theta_c: float = 1.0   # fall in calls per unit of Q
    theta_t: float = 1.0   # rise in TEU per call per unit of Q


def step_target(p: Params) -> Callable[[float], float]:
    """Calibration driver: no diversion before the onset, d_max from the onset on."""
    return lambda t: p.d_max if t >= p.t0 else 0.0


def derivatives(p: Params, target: Callable) -> Callable:
    def f(t, y):
        D, Dc, A, U, Q, K, N = y
        du = U - p.u0
        return ((target(t) - D) / p.tau_d,
                (D - Dc) / p.tau_c,
                (D - A) / p.tau_a,
                (p.u0 + p.beta * (A + p.phi * abs(D - N)) - U) / p.tau_u,
                (du - K - Q) / p.tau_q,
                (p.adapt * du - K) / p.tau_k,
                (D - N) / p.tau_n)
    return f


def initial_state(p: Params, d_start: float = 0.0) -> tuple:
    """Steady state for a constant diversion share ``d_start``."""
    du = p.beta * d_start
    return (d_start, d_start, d_start, p.u0 + du, (1.0 - p.adapt) * du, p.adapt * du, d_start)


def simulate(p: Params, n_days: int, target: Callable | None = None, y0: tuple | None = None,
             method: str = "rk4") -> list[tuple]:
    target = target or step_target(p)
    return integrate(derivatives(p, target), y0 or initial_state(p), n_days, 1.0, 0.0, method)


def daily_means(traj: list[tuple], idx: int) -> list:
    """Mean of stock ``idx`` over each day (trapezoid of the states at its start and end)."""
    return [0.5 * (traj[i][idx] + traj[i + 1][idx]) for i in range(len(traj) - 1)]


def trailing_sum(daily: list, window: int = 7) -> list:
    """Trailing ``window``-day sum; None until the window is full."""
    out: list = [None] * len(daily)
    for i in range(window - 1, len(daily)):
        acc = daily[i - window + 1]
        for j in range(i - window + 2, i + 1):
            acc = acc + daily[j]
        out[i] = acc
    return out


def with_values(p: Params, **kw) -> Params:
    return replace(p, **kw)


def steady_state_check(p: Params, d: float) -> float:
    """Largest absolute derivative at the steady state for diversion share ``d`` (should be 0)."""
    f = derivatives(p, lambda t: d)
    return max(abs(x) for x in f(0.0, initial_state(p, d)))


def first_order_step_exact(t: float, tau: float, target: float, y0: float = 0.0) -> float:
    """Analytic step response of dy/dt = (target - y)/tau (used by the tests)."""
    return target + (y0 - target) * math.exp(-t / tau)
