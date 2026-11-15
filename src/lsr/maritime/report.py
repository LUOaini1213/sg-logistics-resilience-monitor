"""Build every maritime-scenario output in ``outputs/maritime`` from committed inputs (offline)."""
from __future__ import annotations

import sys

from . import svg
from . import voyage as V
from .inputs import INPUTS, ROOT, read_csv, write_csv, write_json, write_text

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


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    summary.update(voyage_outputs())
    write_json(OUT / "summary.json", summary)
    return summary


if __name__ == "__main__":
    out = main()
    sys.stdout.write(str(out) + "\n")
