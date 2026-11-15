"""Build every maritime-scenario output in ``outputs/maritime`` from committed inputs (offline)."""
from __future__ import annotations

import datetime as dt
import json
import math
import sys

import numpy as np

from .. import backtest as B
from ..indicators import INDICATORS
from . import calibrate as C
from . import cld
from . import scenarios as S
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


def sd_outputs(res: dict) -> dict:
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


def cld_outputs() -> dict:
    write_text(FIG / "cld.svg", cld.render())
    labels = {n.key: n.label.replace("|", " ") for n in cld.NODES}
    write_csv(OUT / "cld_links.csv", [{"from": lk.src, "to": lk.dst, "from_label": labels[lk.src],
                                       "to_label": labels[lk.dst], "polarity": "+" if lk.sign > 0 else "-",
                                       "status": lk.status, "delay": lk.delay, "evidence": lk.evidence}
                                      for lk in cld.LINKS])
    loops = cld.loops_table()
    write_csv(OUT / "cld_loops.csv", loops)
    counts = {s: sum(lk.status == s for lk in cld.LINKS) for s in ("estimated", "model", "cited", "assumed")}
    return {"cld": {"nodes": len(cld.NODES), "links": len(cld.LINKS), "links_by_status": counts,
                    "loops": {r["loop"]: r["polarity"] for r in loops if r["loop"]},
                    "unnamed_loops": sum(1 for r in loops if not r["loop"])}}


SCEN_INDICATORS = {
    "control": ("cp_malacca", "sg_calls_container", "sg_box_volume", "cp_bab", "cp_cape", "sg_teu_per_call"),
    "gulf": ("cp_malacca", "cp_hormuz", "sg_calls_container"),
    "strait": ("sg_calls_container", "sg_box_volume", "cp_malacca", "sg_teu_per_call"),
    "reopen": ("cp_bab", "cp_suez", "cp_cape", "sg_calls_container", "sg_teu_per_call"),
}


def _q(a) -> list[float]:
    return [round(v, 3) for v in S.pct(np.asarray(a, dtype=float))]


def scenario_outputs(cal: dict) -> dict:
    sel = json.loads((ROOT / "outputs" / "summary.json").read_text(encoding="utf-8"))["selected"]
    k, persist = sel["k"], sel["persist_days"]
    events = B.load_events()
    frames = B.evaluate(k, persist, events=events)["frames"]
    p, obs = cal["params"], cal["obs"]
    d_now, d_date = S.diverted_share_now(obs["bab_base"])
    res = S.run_all(frames, events, p, obs["bab_base"], d_now, k, persist)
    ctrl = res["control"]
    n = ctrl["n"]
    c_max = ctrl["level"].max(axis=1)
    ladder_rows, ind_rows, cost_rows = [], [], []
    for name, r in res.items():
        mx = r["level"].max(axis=1)
        row = {"scenario": name, "title": S.TITLES[name], "draws": n}
        for lv in (1, 2, 3):
            row[f"p_level{lv}"] = round(int((mx >= lv).sum()) / n, 3)
            row[f"p_level{lv}_attributable"] = round(int(((mx >= lv) & (c_max < lv)).sum()) / n, 3)
        attr = (mx >= 2) & (c_max < 2)
        if name != "control" and attr.any():
            first = S.first_day(r["level"] >= 2)
            lag = first[attr] - r["onset"][attr]
            row.update({f"days_to_level2_p{q}": round(v, 1) for q, v in zip((10, 50, 90),
                                                                              S.pct(lag, (10, 50, 90)))})
        else:
            row.update({"days_to_level2_p10": "", "days_to_level2_p50": "", "days_to_level2_p90": ""})
        for key in ("cp_malacca", "sg_calls_container", "sg_box_volume", "sg_teu_per_call"):
            a = r["alarms"][key] if key in r["alarms"] else r["alarms_monthly"][key]
            ca = ctrl["alarms"][key] if key in ctrl["alarms"] else ctrl["alarms_monthly"][key]
            row[f"alarm_{key}_attributable"] = round(int((a.any(axis=1) & ~ca.any(axis=1)).sum()) / n, 3)
        ladder_rows.append(row)
        for key in SCEN_INDICATORS[name]:
            b = r["base"][key]
            x = r["x_daily"][key] if key in r["x_daily"] else r["x_monthly"][key]
            rel = (x - b["median"]) / b["median"] * 100.0 if b["level"] else (x - b["median"]) * 100.0
            unit = "% vs baseline" if b["level"] else "log-points x100 vs baseline"
            lo, hi = rel.min(axis=1), rel.max(axis=1)
            ind_rows.append({"scenario": name, "indicator": key, "unit": unit,
                             "baseline": round(b["median"], 4), "baseline_date": str(b["date"].date()),
                             "min_p5": _q(lo)[0], "min_p50": _q(lo)[2], "min_p95": _q(lo)[4],
                             "max_p5": _q(hi)[0], "max_p50": _q(hi)[2], "max_p95": _q(hi)[4]})
        for metric, vals in r["costs"].items():
            qv = _q(vals)
            cost_rows.append({"scenario": name, "metric": metric, "p5": qv[0], "p25": qv[1], "p50": qv[2],
                              "p75": qv[3], "p95": qv[4],
                              "mean": round(math.fsum(float(v) for v in vals) / len(vals), 3),
                              "share_below_zero": round(int((np.asarray(vals) < 0).sum()) / len(vals), 3)})
    write_csv(OUT / "scenario_ladder.csv", ladder_rows)
    write_csv(OUT / "scenario_indicators.csv", ind_rows)
    write_csv(OUT / "scenario_costs.csv", cost_rows)
    # noise check: control alarm shares against the real holdout false-alarm rates
    fa = {r["indicator"]: r for r in read_csv(ROOT / "outputs" / "false_alarms_by_indicator.csv")}
    horizon = ctrl["horizon"]
    noise_rows = []
    for key in S.DAILY + S.MONTHLY:
        a = ctrl["alarms"][key] if key in ctrl["alarms"] else ctrl["alarms_monthly"][key]
        rate = float(fa[key]["holdout_per_year"] or 0.0)
        noise_rows.append({"indicator": key, "control_p_alarm": round(int(a.any(axis=1).sum()) / n, 3),
                           "holdout_false_alarms_per_year": rate,
                           "poisson_p_alarm_same_horizon": round(1.0 - math.exp(-rate * horizon / 365.25), 3)})
    write_csv(OUT / "scenario_noise_check.csv", noise_rows)
    exact = []
    for name, keys in (("control", ("cp_malacca", "sg_calls_container")),
                       ("strait", ("cp_malacca", "sg_calls_container")),
                       ("reopen", ("cp_bab", "sg_calls_container"))):
        exact += S.exact_check(res[name], frames, k, persist, keys)
    write_csv(OUT / "scenario_exact_check.csv", [{**e, "breach_day_agreement": round(e["breach_day_agreement"], 4),
                                                  "median_abs_z_difference": round(e["median_abs_z_difference"], 3)}
                                                 for e in exact])
    write_text(FIG / "scenario_ladder.svg", svg.grouped_bars(
        [{"label": S.TITLES[r["scenario"]], "values": [r["p_level2"], r["p_level3"], r["p_level2_attributable"]]}
         for r in ladder_rows],
        ["Level 2 (Alert) or higher", "Level 3 (Activate review)", "Level 2, attributable to the scenario"],
        "Activation ladder within 26 weeks: share of 2,000 draws", "Share of draws"))
    stress = []
    for name, key, side, label in (("gulf", "cp_malacca", "min", "Gulf: Malacca transits, trough"),
                                   ("strait", "sg_calls_container", "min", "Strait: Singapore calls, trough"),
                                   ("strait", "cp_malacca", "min", "Strait: Malacca transits, trough"),
                                   ("reopen", "sg_calls_container", "max", "Reopening: Singapore calls, peak"),
                                   ("reopen", "sg_teu_per_call", "min", "Reopening: TEU per call, trough"),
                                   ("control", "sg_calls_container", "min", "Control: Singapore calls, trough")):
        r = res[name]
        b = r["base"][key]
        x = r["x_daily"][key] if key in r["x_daily"] else r["x_monthly"][key]
        rel = (x - b["median"]) / b["median"] * 100.0
        v = rel.min(axis=1) if side == "min" else rel.max(axis=1)
        q = S.pct(v)
        stress.append({"label": label, "p5": q[0], "p25": q[1], "p50": q[2], "p75": q[3], "p95": q[4]})
    write_text(FIG / "scenario_ranges.svg", svg.range_rows(
        stress, "Indicator extremes over 26 weeks (P5-P95 bar, P25-P75 box, median tick)",
        "% change against the detector baseline at the data cut-off"))
    cm = {(r["scenario"], r["metric"]): r for r in cost_rows}
    lad = {r["scenario"]: r for r in ladder_rows}
    return {"scenarios": {
        "start": str(S.START.date()), "horizon_days": horizon, "draws": n,
        "diverted_share_now": round(d_now, 3), "diverted_share_date": str(d_date.date()),
        "ladder": {name: {kk: lad[name][kk] for kk in ("p_level1", "p_level2", "p_level3", "p_level2_attributable",
                                                       "p_level3_attributable", "days_to_level2_p50")}
                   for name in lad},
        "gulf_cape_cost_change_usd_per_teu": [cm[("gulf", "cape_usd_per_teu_change")][q] for q in ("p5", "p50", "p95")],
        "strait_waiting_cost_usd_m": [cm[("strait", "waiting_cost_usd_m")][q] for q in ("p5", "p50", "p95")],
        "strait_waiting_ship_days": [cm[("strait", "waiting_ship_days")][q] for q in ("p5", "p50", "p95")],
        "reopen_suez_minus_cape_usd_per_teu": [cm[("reopen", "suez_minus_cape_usd_per_teu")][q]
                                               for q in ("p5", "p50", "p95")],
        "reopen_p_suez_cheaper": cm[("reopen", "suez_minus_cape_usd_per_teu")]["share_below_zero"],
        "exact_check_min_agreement": round(min(e["breach_day_agreement"] for e in exact), 4),
    }}


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    summary.update(voyage_outputs())
    cal = C.calibrate()
    summary.update(sd_outputs(cal))
    summary.update(cld_outputs())
    summary.update(scenario_outputs(cal))
    write_json(OUT / "summary.json", summary)
    return summary


if __name__ == "__main__":
    out = main()
    sys.stdout.write(str(out) + "\n")
