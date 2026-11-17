"""Voyage economics of a representative Asia-North Europe loop, via Suez or via the Cape.

Costs per round voyage of one ship. With the fleet sized to the round-voyage time, one round
voyage is one weekly departure, so this is also the cost per departure of the service.

* fuel      = (main engine at sea + auxiliaries at sea, in port and in canal) x bunker price
* charter   = round-voyage days x time-charter rate
* canal     = Suez transits x SCA toll (SDR per Suez Canal Net Ton, in bands) x USD per SDR
              x (1 + surcharge - rebate)
* war risk  = transits of the Red Sea / Gulf of Aden high-risk area x premium x hull value
* EU ETS    = covered CO2 x phase-in x EU allowance price x USD per EUR

Main-engine fuel follows a power law in speed from one published reference point:
``fuel(v) = fuel_ref x (v / v_ref) ** exponent x LCV_ref / LCV``. Costs that do not depend on
the routing (port and terminal charges, containers, overheads, crew war bonuses) are left out.
Inputs and their provenance are in ``data/inputs/voyage_parameters.csv``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .inputs import INPUTS, load_parameters, read_csv

COMPONENTS = ("fuel", "charter", "canal", "war_risk", "eu_ets")


@dataclass(frozen=True)
class Leg:
    routing: str
    seq: int
    origin: str
    dest: str
    nm: float
    passages: tuple[str, ...]


def load_legs(path: Path = INPUTS / "voyage_legs.csv") -> list[Leg]:
    return [Leg(r["routing"], int(r["seq"]), r["from_port"], r["to_port"], float(r["distance_nm"]),
                tuple(p for p in r["passages"].split(";") if p)) for r in read_csv(path)]


def load_ports(path: Path = INPUTS / "ports.csv") -> dict[str, bool]:
    """Port name -> True if its emissions fall under the EU ETS as an EU port of call."""
    return {r["port"]: r["eu_ets_port"] == "1" for r in read_csv(path)}


def load_schedule(path: Path = INPUTS / "suez_toll_schedule.csv") -> list[tuple[float | None, float, float]]:
    rows = sorted(read_csv(path), key=lambda r: int(r["band"]))
    return [(float(r["band_scnt"]) if r["band_scnt"] else None, float(r["laden_sdr_per_scnt"]),
             float(r["ballast_sdr_per_scnt"])) for r in rows]


def load_values(path: Path = INPUTS / "voyage_parameters.csv") -> dict[str, float]:
    return {k: v["value"] for k, v in load_parameters(path).items()}


def suez_toll_sdr(scnt: float, schedule: list[tuple[float | None, float, float]], laden: bool = True) -> float:
    """Transit dues in SDR: each band of Suez Canal Net Tonnage is charged at its own rate."""
    if scnt < 0:
        raise ValueError("negative tonnage")
    total, remaining = 0.0, float(scnt)
    for band, laden_rate, ballast_rate in schedule:
        take = remaining if band is None else min(remaining, band)
        total += take * (laden_rate if laden else ballast_rate)
        remaining -= take
        if remaining <= 0:
            return total
    raise ValueError("tonnage exceeds the schedule's bands")


def ets_share(origin_eu: bool, dest_eu: bool, v: dict[str, float]) -> float:
    """Share of a voyage's emissions covered by the EU ETS."""
    if origin_eu and dest_eu:
        return v["ets_share_intra_eu"]
    if origin_eu or dest_eu:
        return v["ets_share_extra_eu"]
    return 0.0


def me_fuel_per_day(speed_kn: float, v: dict[str, float]) -> float:
    """Main-engine fuel in tonnes per day at sea (actual fuel, corrected from the ISO reference LCV)."""
    return (v["me_fuel_ref_tpd"] * (speed_kn / v["ref_speed_kn"]) ** v["speed_exponent"]
            * v["fuel_lcv_ref_kj_kg"] / v["fuel_lcv_kj_kg"])


def leg_distance(leg: Leg, suez_leg: Leg, v: dict[str, float]) -> float:
    """A Cape leg's distance with its extra distance over the Suez leg scaled by ``cape_distance_factor``."""
    if leg.routing == "suez":
        return leg.nm
    return suez_leg.nm + v["cape_distance_factor"] * (leg.nm - suez_leg.nm)


def round_voyage(v: dict[str, float], legs: list[Leg], eu: dict[str, bool],
                 schedule: list[tuple[float | None, float, float]], routing: str) -> dict:
    """Physical quantities and costs (USD) of one round voyage on ``routing`` ("suez" or "cape")."""
    if routing not in ("suez", "cape"):
        raise ValueError(routing)
    speed = v["speed_suez_kn"] if routing == "suez" else v["speed_cape_kn"]
    rows = sorted((g for g in legs if g.routing == routing), key=lambda g: g.seq)
    suez = {g.seq: g for g in legs if g.routing == "suez"}
    me = me_fuel_per_day(speed, v)
    sea_days = fuel_sea = co2_covered = distance = 0.0
    canal_transits = war_transits = 0
    for g in rows:
        nm = leg_distance(g, suez[g.seq], v)
        days = nm / (speed * 24.0)
        fuel = days * (me + v["aux_fuel_sea_tpd"])
        distance += nm
        sea_days += days
        fuel_sea += fuel
        co2_covered += fuel * v["cf_t_co2_per_t"] * ets_share(eu[g.origin], eu[g.dest], v)
        canal_transits += "suez" in g.passages
        war_transits += "babalmandab" in g.passages
    calls = len(rows)
    port_days = calls * v["port_days_per_call"]
    canal_days = canal_transits * v["canal_days_per_transit"]
    fuel_port = (port_days + canal_days) * v["aux_fuel_port_tpd"]
    eu_calls = sum(eu[g.dest] for g in rows)
    co2_covered += eu_calls * v["port_days_per_call"] * v["aux_fuel_port_tpd"] * v["cf_t_co2_per_t"] * \
        v["ets_share_intra_eu"]
    days = sea_days + port_days + canal_days
    fuel_t = fuel_sea + fuel_port
    toll_usd = suez_toll_sdr(v["scnt"], schedule, laden=True) * v["sdr_usd"] * \
        (1.0 + v["suez_surcharge"] - v["suez_rebate"])
    costs = {
        "fuel": fuel_t * v["bunker_usd_t"],
        "charter": days * v["charter_usd_day"],
        "canal": canal_transits * toll_usd,
        "war_risk": war_transits * v["war_risk_pct"] / 100.0 * v["hull_value_usd"],
        "eu_ets": co2_covered * v["ets_phase_in"] * v["eua_eur_t"] * v["eur_usd"],
    }
    total = sum(costs[c] for c in COMPONENTS)
    teu = v["capacity_teu"] * (v["utilisation_head"] + v["utilisation_back"])
    return {"routing": routing, "speed_kn": speed, "distance_nm": distance, "sea_days": sea_days,
            "port_days": port_days, "canal_days": canal_days, "days": days, "ships_weekly": days / 7.0,
            "fuel_t": fuel_t, "co2_t": fuel_t * v["cf_t_co2_per_t"], "co2_covered_t": co2_covered,
            "canal_transits": canal_transits, "war_risk_transits": war_transits, "toll_usd_per_transit":
            toll_usd, **{f"{c}_usd": costs[c] for c in COMPONENTS}, "total_usd": total, "teu": teu,
            "usd_per_teu": total / teu}


def breakeven_war_risk_pct(v: dict[str, float], legs, eu, schedule) -> float:
    """War-risk premium (% of hull value per transit) at which the Suez round voyage costs the same
    as the Cape round voyage. Below it Suez is cheaper; a negative value means Suez is dearer even
    with no premium. Suez cost is linear in the premium, so the solution is exact."""
    cape = round_voyage(v, legs, eu, schedule, "cape")["total_usd"]
    suez0 = round_voyage({**v, "war_risk_pct": 0.0}, legs, eu, schedule, "suez")
    if suez0["war_risk_transits"] == 0:
        raise ValueError("the Suez routing crosses no war-risk area")
    return (cape - suez0["total_usd"]) / (suez0["war_risk_transits"] * v["hull_value_usd"]) * 100.0


def cape_minus_suez_per_teu(v: dict[str, float], legs, eu, schedule) -> float:
    c = round_voyage(v, legs, eu, schedule, "cape")
    s = round_voyage(v, legs, eu, schedule, "suez")
    return c["usd_per_teu"] - s["usd_per_teu"]


def tornado(params: dict[str, dict], legs, eu, schedule) -> list[dict]:
    """One-at-a-time sensitivity of the break-even premium and of the Cape-minus-Suez cost per TEU
    to every parameter with a low and a high value; sorted by the break-even swing, then by name."""
    base = {k: p["value"] for k, p in params.items()}
    rows = []
    for name, p in params.items():
        if p["low"] is None or p["high"] is None or p["low"] == p["high"]:
            continue
        out = {"parameter": name, "label": p["label"], "unit": p["unit"], "base": p["value"],
               "low": p["low"], "high": p["high"]}
        for side in ("low", "high"):
            w = {**base, name: p[side]}
            out[f"breakeven_pct_{side}"] = breakeven_war_risk_pct(w, legs, eu, schedule)
            out[f"cape_minus_suez_usd_per_teu_{side}"] = cape_minus_suez_per_teu(w, legs, eu, schedule)
        out["breakeven_swing_pct"] = abs(out["breakeven_pct_high"] - out["breakeven_pct_low"])
        rows.append(out)
    return sorted(rows, key=lambda r: (-round(r["breakeven_swing_pct"], 9), r["parameter"]))


def run(params_path: Path = INPUTS / "voyage_parameters.csv") -> dict:
    params = load_parameters(params_path)
    v = {k: p["value"] for k, p in params.items()}
    legs, eu, schedule = load_legs(), load_ports(), load_schedule()
    suez = round_voyage(v, legs, eu, schedule, "suez")
    cape = round_voyage(v, legs, eu, schedule, "cape")
    be = breakeven_war_risk_pct(v, legs, eu, schedule)
    return {"params": params, "suez": suez, "cape": cape, "breakeven_pct": be,
            "breakeven_usd_per_transit": be / 100.0 * v["hull_value_usd"],
            "tornado": tornado(params, legs, eu, schedule)}
