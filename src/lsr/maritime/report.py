"""Build every maritime-scenario output in ``outputs/maritime`` from committed inputs (offline)."""
from __future__ import annotations

import datetime as dt
import math
import sys

from . import calibrate as C
from . import sd
from . import svg
from . import voyage as V
from .inputs import INPUTS, ROOT, load_parameters, read_csv, write_csv, write_json, write_text

OUT = ROOT / "outputs" / "maritime"
FIG = OUT / "figures"

PARAM_LABELS = {
    "bunker_usd_t": "Bunker price (USD/t)", "cape_distance_factor": "Cape extra distance (factor)",
    "speed_cape_kn": "Speed via the Cape (kn)", "hull_value_usd": "Hull value (USD)",
    "charter_usd_day": "Charter rate (USD/day)", "speed_suez_kn": "Speed via Suez (kn)",
    "scnt": "Suez Canal Net Tonnage", "suez_rebate": "Suez rebate (share)",
    "speed_exponent": "Speed-fuel exponent", "canal_days_per_transit": "Canal days per transit",
    "suez_surcharge": "Suez surcharge (share)", "eua_eur_t": "EU allowance (EUR/t)",
    "ets_phase_in": "ETS phase-in (share)", "aux_fuel_sea_tpd": "Auxiliary fuel at sea (t/day)",
    "fuel_lcv_kj_kg": "Fuel calorific value (kJ/kg)", "aux_fuel_port_tpd": "Auxiliary fuel in port (t/day)",
    "cf_t_co2_per_t": "CO2 factor (t/t)", "port_days_per_call": "Days per port call",
    "utilisation_back": "Backhaul utilisation", "utilisation_head": "Headhaul utilisation",
    "war_risk_pct": "War-risk premium (% of hull)",
}


def r0(x: float) -> int:
    return int(round(x))


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def r3(x: float) -> float:
    return round(x + 0.0, 3)


def distance_checks() -> list[dict]:
    """searoute distances (data/inputs/distance_checks_searoute.csv) against published figures."""
    sr = {(d["from_port"], d["to_port"]): d for d in read_csv(INPUTS / "distance_checks_searoute.csv")}
    rows = []
    for p in read_csv(INPUTS / "distance_checks_published.csv"):
        mine = float(sr[(p["from_port"], p["to_port"])][p["quantity"]])
        pub = float(p["published_nm"])
        rows.append({"from_port": p["from_port"], "to_port": p["to_port"], "quantity": p["quantity"],
                     "searoute_nm": round(mine), "published_nm": round(pub),
                     "difference_pct": round((mine / pub - 1.0) * 100.0, 1), "published_source": p["source"]})
    return rows


def voyage_outputs() -> dict:
    r = V.run()
    cost_rows = []
    for k in ("suez", "cape"):
        x = r[k]
        cost_rows.append({
            "routing": k, "speed_kn": x["speed_kn"], "distance_nm": r0(x["distance_nm"]),
            "sea_days": r2(x["sea_days"]), "port_and_canal_days": r2(x["port_days"] + x["canal_days"]),
            "round_voyage_days": r2(x["days"]), "ships_for_weekly_service": r2(x["ships_weekly"]),
            "fuel_t": r0(x["fuel_t"]), "co2_t": r0(x["co2_t"]), "co2_covered_by_eu_ets_t": r0(x["co2_covered_t"]),
            **{f"{c}_usd": r0(x[f"{c}_usd"]) for c in V.COMPONENTS}, "total_usd": r0(x["total_usd"]),
            "teu_carried": r0(x["teu"]), "usd_per_teu": r2(x["usd_per_teu"])})
    write_csv(OUT / "voyage_costs.csv", cost_rows)
    trows = [{"parameter": t["parameter"], "label": t["label"], "unit": t["unit"], "base": t["base"],
              "low": t["low"], "high": t["high"], "breakeven_pct_low": r3(t["breakeven_pct_low"]),
              "breakeven_pct_high": r3(t["breakeven_pct_high"]), "breakeven_swing_pct": r3(t["breakeven_swing_pct"]),
              "cape_minus_suez_usd_per_teu_low": r2(t["cape_minus_suez_usd_per_teu_low"]),
              "cape_minus_suez_usd_per_teu_high": r2(t["cape_minus_suez_usd_per_teu_high"])}
             for t in r["tornado"]]
    write_csv(OUT / "voyage_tornado.csv", trows)
    shown = [t for t in trows if t["breakeven_swing_pct"] > 0][:12]
    chart_rows = [{"parameter": t["parameter"], "out_low": t["breakeven_pct_low"], "out_high": t["breakeven_pct_high"]}
                  for t in shown]
    write_text(FIG / "voyage_tornado.svg", svg.tornado(
        chart_rows, r3(r["breakeven_pct"]),
        "Break-even war-risk premium: one input at a time at its low or high value",
        "War-risk premium (% of hull value per transit) at which Suez and the Cape cost the same",
        PARAM_LABELS))
    checks = distance_checks()
    write_csv(OUT / "distance_checks.csv", checks)
    s, c = r["suez"], r["cape"]
    v = {k: p["value"] for k, p in r["params"].items()}
    return {"voyage": {
        "distance_checks": {f'{d["from_port"]}-{d["to_port"]} {d["quantity"]}': d["difference_pct"] for d in checks},
        "loop": "Shanghai-Ningbo-Yantian-Singapore-Rotterdam-Hamburg-Antwerp-Singapore-Shanghai",
        "ship_teu": r0(v["capacity_teu"]), "war_risk_pct_base": v["war_risk_pct"],
        "suez_total_usd": r0(s["total_usd"]), "cape_total_usd": r0(c["total_usd"]),
        "suez_usd_per_teu": r2(s["usd_per_teu"]), "cape_usd_per_teu": r2(c["usd_per_teu"]),
        "cape_minus_suez_usd_per_teu": r2(c["usd_per_teu"] - s["usd_per_teu"]),
        "suez_days": r2(s["days"]), "cape_days": r2(c["days"]),
        "extra_ships_weekly": r2(c["ships_weekly"] - s["ships_weekly"]),
        "extra_fuel_t": r0(c["fuel_t"] - s["fuel_t"]),
        "suez_toll_usd_per_transit": r0(s["toll_usd_per_transit"]),
        "breakeven_war_risk_pct": r3(r["breakeven_pct"]),
        "breakeven_war_risk_usd_per_transit": r0(r["breakeven_usd_per_transit"]),
        "tornado_top": [t["parameter"] for t in trows[:3]],
        "tornado_top_range_pct": [[t["breakeven_pct_low"], t["breakeven_pct_high"]] for t in trows[:3]],
    }}


SD_META = {
    "d_max": ("routing", "share", "Diverted share of the pre-crisis Bab el-Mandeb container transits"),
    "tau_d": ("routing", "days", "Routing adjustment time"),
    "tau_c": ("routing", "days", "Delay before diverted ships appear at the Cape"),
    "kappa": ("routing", "-", "Cape container transits gained per Bab el-Mandeb transit lost"),
    "beta": ("reliability", "-", "Unreliability (share of late arrivals) per unit of absorbed capacity"),
    "tau_q": ("singapore", "days", "Bunching build-up time = adaptation time (tau_k tied to tau_q)"),
    "theta_c": ("singapore", "-", "Relative fall in Singapore container calls per unit of bunching"),
    "theta_t": ("singapore", "-", "Relative rise in TEU per call per unit of bunching"),
}
SERIES_LABEL = {"bab": "Bab el-Mandeb container transits (7-day sum)",
                "cape": "Cape of Good Hope container transits (7-day sum)",
                "glp": "Global schedule reliability (%)", "calls": "Singapore container-ship calls (7-day sum)",
                "tpc": "Singapore TEU per container-ship call"}


def sd_outputs() -> dict:
    res = C.calibrate()
    p, obs, profile, routing = res["params"], res["obs"], res["profile"], res["routing"]
    stats = C.fit_stats(p, obs)
    covs = {b: C.covariance(p, obs, b) for b in C.BLOCKS}
    infl = {b: (1.0 + c["rho"]) / (1.0 - c["rho"]) for b, c in covs.items()}
    n_routing = len(obs["bab"]) + len(obs["cape"])
    lo, hi = C.onset_interval(profile, n_routing, infl["routing"])
    date = lambda d: str(C.START + dt.timedelta(days=int(d)))  # noqa: E731
    rows = [{"block": "routing", "parameter": "t0", "estimate": date(p.t0), "se": "", "se_ar1": "",
             "ci95_low": date(lo), "ci95_high": date(hi), "status": "estimated (profile over whole days)",
             "unit": "date", "meaning": "Onset of the diversion; data/events.csv documents 2023-12-15"}]
    for b, cv in covs.items():
        for name, est, se, sea in zip(cv["names"], cv["estimate"], cv["se"], cv["se_ar1"]):
            blk, unit, meaning = SD_META[name]
            low = est - 1.96 * sea
            status = "estimated"
            if unit == "days" and low < 0:
                low, status = 0.0, "estimated (Wald interval truncated at zero)"
            rows.append({"block": blk, "parameter": name, "estimate": round(est, 4), "se": round(se, 4),
                         "se_ar1": round(sea, 4), "ci95_low": round(low, 4),
                         "ci95_high": round(est + 1.96 * sea, 4), "status": status, "unit": unit,
                         "meaning": meaning})
    grid = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 14.0, 21.0, 30.0, 45.0, 60.0]
    ta_prof = C.tau_a_profile(obs, routing, grid)
    best = min(r["sse"] for r in ta_prof)
    n_glp = len(obs["glp"])
    ta_ok = [r["tau_a"] for r in ta_prof if n_glp * math.log(r["sse"] / best) <= 3.84 * infl["reliability"]]
    rows.append({"block": "reliability", "parameter": "tau_a", "estimate": round(p.tau_a, 4), "se": "",
                 "se_ar1": "", "ci95_low": round(C.TAU_A_RANGE[0], 4), "ci95_high": max(ta_ok),
                 "status": "estimated, at the lower bound of the search range; the interval is the profile "
                           "bound on a grid", "unit": "days",
                 "meaning": "Delay between diversion and absorbed capacity (carries the whole routing-to-"
                            "reliability delay)"})
    sdi = load_parameters(INPUTS / "sd_parameters.csv")
    fixed = [("tau_u", p.tau_u, "assumed (data/inputs/sd_parameters.csv)", "days", "Reliability response time"),
             ("adapt", p.adapt, "assumed (data/inputs/sd_parameters.csv)", "share",
              "Share of the bunching pressure that adaptation removes"),
             ("tau_k", "= tau_q", "assumed tie (data/inputs/sd_parameters.csv)", "days", "Adaptation time"),
             ("u0", round(p.u0, 4), "fixed from data (mean GLP, Jun-Oct 2023)", "share", "Pre-crisis unreliability"),
             ("B0", round(obs["bab_base"], 2), "fixed from data (1 Jul - 15 Nov 2023)", "transits/week",
              "Pre-crisis Bab el-Mandeb container transits"),
             ("C0", round(obs["cape_base"], 2), "fixed from data (1 Jul - 15 Nov 2023)", "transits/week",
              "Pre-crisis Cape container transits"),
             ("Cb", round(obs["calls_base"], 2), "fixed from data (1 Jul - 15 Nov 2023)", "calls/week",
              "Pre-crisis Singapore container-ship calls"),
             ("Tb", round(obs["tpc_base"], 1), "fixed from data (Jul-Nov 2023)", "TEU/call",
              "Pre-crisis Singapore TEU per call"),
             ("phi", p.phi, "assumed 0 in the calibration (scenario input)", "-", "Re-routing friction")]
    for name, val, status, unit, meaning in fixed:
        rows.append({"block": "fixed", "parameter": name, "estimate": val, "se": "", "se_ar1": "", "ci95_low": "",
                     "ci95_high": "", "status": status, "unit": unit, "meaning": meaning})
    traj = sd.simulate(p, C.N_DAYS)
    A = sd.daily_means(traj, 2)
    june = C.month_means(A, ["2024-06"])[0]
    a_scale = sdi["capacity_absorbed_june_2024"]["value"] / june
    rows.append({"block": "fixed", "parameter": "a_scale", "estimate": round(a_scale, 4), "se": "", "se_ar1": "",
                 "ci95_low": "", "ci95_high": "", "status": "cited: UNCTAD RMT 2024 citing Clarksons (12% in June "
                 "2024)", "unit": "share of demand per unit of A", "meaning": "Absorbed capacity at full diversion"})
    write_csv(OUT / "sd_parameters.csv", rows)
    write_csv(OUT / "sd_fit_stats.csv", [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                                         for r in stats])
    m = C.observables(p, obs, traj)
    fit_rows = []
    for k, dates in (("bab", obs["weeks"]), ("cape", obs["weeks"]), ("calls", obs["weeks"]),
                     ("glp", obs["glp_months"]), ("tpc", obs["tpc_months"])):
        for d, y, f in zip(dates, obs[k], m[k]):
            fit_rows.append({"series": k, "date": str(d), "observed": round(y, 2), "fitted": round(f, 2)})
    write_csv(OUT / "sd_fit_series.csv", fit_rows)
    write_csv(OUT / "sd_onset_profile.csv", [{"onset": date(r["t0"]), "objective": round(r["objective"], 5),
                                               "tau_d": round(r["tau_d"], 3), "tau_c": round(r["tau_c"], 3),
                                               "d_max": round(r["d_max"], 4), "kappa": round(r["kappa"], 4)}
                                              for r in profile])
    write_csv(OUT / "sd_tau_a_profile.csv", [{"tau_a": r["tau_a"], "beta": round(r["beta"], 4),
                                               "glp_sse": round(r["sse"], 3)} for r in ta_prof])
    corr_rows = []
    for b, cv in covs.items():
        for i, a in enumerate(cv["names"]):
            for j, c in enumerate(cv["names"]):
                if j > i:
                    corr_rows.append({"block": b, "parameter_1": a, "parameter_2": c,
                                      "correlation": round(cv["corr"][i][j], 3)})
    write_csv(OUT / "sd_correlations.csv", corr_rows)
    # Sensitivity: absorption delay held at one Asia-Europe voyage instead of fitted.
    ta_alt = sdi["tau_a_sensitivity_days"]["value"]
    alt = C.downstream(obs, routing, ta_alt)
    alt_stats = {r["series"]: r for r in C.fit_stats(alt, obs)}
    st = {r["series"]: r for r in stats}
    write_csv(OUT / "sd_tau_a_sensitivity.csv", [
        {"case": "fitted", "tau_a": round(p.tau_a, 3), "beta": round(p.beta, 4), "tau_q": round(p.tau_q, 2),
         "glp_rmse": round(st["glp"]["rmse"], 3), "calls_r2": round(st["calls"]["r2"], 3),
         "tpc_r2": round(st["tpc"]["r2"], 3)},
        {"case": "held", "tau_a": ta_alt, "beta": round(alt.beta, 4), "tau_q": round(alt.tau_q, 2),
         "glp_rmse": round(alt_stats["glp"]["rmse"], 3), "calls_r2": round(alt_stats["calls"]["r2"], 3),
         "tpc_r2": round(alt_stats["tpc"]["r2"], 3)}])
    # Figure: observed against fitted, plus the (cited-scale) absorbed capacity.
    days = [C.START + dt.timedelta(days=i) for i in range(C.N_DAYS)]
    panels = []
    for k in ("bab", "cape", "glp", "calls", "tpc"):
        dates = obs["weeks"] if k in ("bab", "cape", "calls") else [dt.date(int(x[:4]), int(x[5:]), 15)
                                                                    for x in obs[f"{k}_months"]]
        monthly = k in ("glp", "tpc")
        panels.append({"title": SERIES_LABEL[k], "vline": (C.DOCUMENTED_ONSET, "onset 15 Dec 2023"),
                       "series": [{"name": "observed", "dates": dates, "values": obs[k], "color": svg.SERIES[0],
                                   "points": monthly},
                                  {"name": "model", "dates": dates, "values": m[k], "color": svg.SERIES[1],
                                   "dash": None if monthly else "5 3"}]})
    panels.append({"title": "Capacity absorbed, % of demand (12% in June 2024)",
                   "vline": (C.DOCUMENTED_ONSET, "onset 15 Dec 2023"),
                   "series": [{"name": "model", "dates": days,
                               "values": [100.0 * a_scale * a for a in A], "color": svg.SERIES[1]}]})
    write_text(FIG / "sd_fit.svg", svg.line_panels(panels, "Stock-and-flow model against the 2023-24 observations"))
    est = {r["parameter"]: r for r in rows}
    return {"sd": {
        "fit_window": f"{obs['weeks'][0]} to {obs['weeks'][-1]} (weekly); {obs['tpc_months'][0]} to "
                      f"{obs['tpc_months'][-1]} (monthly)",
        "onset": date(p.t0), "onset_ci95": [date(lo), date(hi)],
        "r2": {k: round(st[k]["r2"], 3) for k in st}, "mape_pct": {k: round(st[k]["mape_pct"], 1) for k in st},
        "params": {n: est[n]["estimate"] for n in SD_META},
        "ci95": {n: [est[n]["ci95_low"], est[n]["ci95_high"]] for n in SD_META},
        "rho": {b: round(c["rho"], 3) for b, c in covs.items()},
        "tau_a_days": round(p.tau_a, 2), "tau_a_profile_max_days": max(ta_ok),
        "a_scale": round(a_scale, 4),
        "tau_a_held": {"tau_a": ta_alt, "glp_rmse": round(alt_stats["glp"]["rmse"], 3),
                       "tau_q": round(alt.tau_q, 2)},
        "glp_rmse_fitted": round(st["glp"]["rmse"], 3),
        "peak_calls_drop_pct": round(100.0 * (1.0 - min(m["calls"]) / obs["calls_base"]), 1),
        "peak_tpc_rise_pct": round(100.0 * (max(m["tpc"]) / obs["tpc_base"] - 1.0), 1),
    }}


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    summary.update(voyage_outputs())
    summary.update(sd_outputs())
    write_json(OUT / "summary.json", summary)
    return summary


if __name__ == "__main__":
    out = main()
    sys.stdout.write(str(out) + "\n")
