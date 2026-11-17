"""Voyage economics: a hand-worked three-port loop, the SCA toll bands, ETS coverage, break-even."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr.maritime import voyage as V  # noqa: E402
from lsr.maritime.inputs import INPUTS, load_parameters, provenance_problems, read_csv  # noqa: E402

# A: outside the EU; B and C: EU ports. Suez legs cross the canal and the war-risk area.
LEGS = [V.Leg("suez", 1, "A", "B", 2400.0, ("babalmandab", "suez")),
        V.Leg("suez", 2, "B", "C", 240.0, ()),
        V.Leg("suez", 3, "C", "A", 2400.0, ("babalmandab", "suez")),
        V.Leg("cape", 1, "A", "B", 3600.0, ("south_africa",)),
        V.Leg("cape", 2, "B", "C", 240.0, ()),
        V.Leg("cape", 3, "C", "A", 3600.0, ("south_africa",))]
EU = {"A": False, "B": True, "C": True}
SCHEDULE = [(1000.0, 2.0, 1.5), (None, 1.0, 0.8)]
P = dict(capacity_teu=1000, me_fuel_ref_tpd=100.0, ref_speed_kn=20.0, speed_exponent=3.0,
         fuel_lcv_ref_kj_kg=40000.0, fuel_lcv_kj_kg=40000.0, cf_t_co2_per_t=3.0, aux_fuel_sea_tpd=5.0,
         aux_fuel_port_tpd=4.0, speed_suez_kn=20.0, speed_cape_kn=20.0, port_days_per_call=1.0,
         canal_days_per_transit=0.5, cape_distance_factor=1.0, utilisation_head=0.8, utilisation_back=0.5,
         bunker_usd_t=500.0, charter_usd_day=10000.0, scnt=3000.0, sdr_usd=1.5, suez_surcharge=0.1,
         suez_rebate=0.0, war_risk_pct=0.5, hull_value_usd=1_000_000.0, eua_eur_t=50.0, eur_usd=1.2,
         ets_phase_in=1.0, ets_share_extra_eu=0.5, ets_share_intra_eu=1.0)


def test_hand_worked_suez_round_voyage():
    r = V.round_voyage(P, LEGS, EU, SCHEDULE, "suez")
    # sea days 5 + 0.5 + 5; ME 100 t/day + aux 5 t/day at sea; 3 calls x 1 day + 2 canal transits x 0.5 day
    assert r["sea_days"] == pytest.approx(10.5) and r["days"] == pytest.approx(14.5)
    assert r["fuel_t"] == pytest.approx(10.5 * 105 + 4 * 4)                      # 1,118.5 t
    # covered CO2: two half-covered 5-day legs, one fully covered 0.5-day leg, two EU port days
    assert r["co2_covered_t"] == pytest.approx(787.5 + 157.5 + 787.5 + 24.0)      # 1,756.5 t
    assert r["fuel_usd"] == pytest.approx(559_250)
    assert r["charter_usd"] == pytest.approx(145_000)
    # toll: 1,000 x 2.0 + 2,000 x 1.0 = 4,000 SDR x 1.5 USD x 1.1 surcharge, two transits
    assert r["toll_usd_per_transit"] == pytest.approx(6_600) and r["canal_usd"] == pytest.approx(13_200)
    assert r["war_risk_usd"] == pytest.approx(10_000)                             # 2 x 0.5% x 1m
    assert r["eu_ets_usd"] == pytest.approx(1756.5 * 50 * 1.2)                    # 105,390
    assert r["total_usd"] == pytest.approx(832_840)
    assert r["usd_per_teu"] == pytest.approx(832_840 / 1300)
    assert r["ships_weekly"] == pytest.approx(14.5 / 7)


def test_hand_worked_cape_round_voyage_and_breakeven():
    c = V.round_voyage(P, LEGS, EU, SCHEDULE, "cape")
    assert c["days"] == pytest.approx(18.5) and c["fuel_t"] == pytest.approx(15.5 * 105 + 3 * 4)
    assert c["canal_usd"] == 0 and c["war_risk_usd"] == 0
    assert c["eu_ets_usd"] == pytest.approx((1181.25 * 2 + 157.5 + 24.0) * 60)
    assert c["total_usd"] == pytest.approx(1_157_390)
    be = V.breakeven_war_risk_pct(P, LEGS, EU, SCHEDULE)
    assert be == pytest.approx((1_157_390 - 822_840) / 2_000_000 * 100)          # 16.7275 %
    at_be = V.round_voyage({**P, "war_risk_pct": be}, LEGS, EU, SCHEDULE, "suez")
    assert at_be["total_usd"] == pytest.approx(c["total_usd"])


def test_speed_law_lcv_and_distance_factor():
    assert V.me_fuel_per_day(10.0, P) == pytest.approx(12.5)                      # (10/20)^3 x 100
    assert V.me_fuel_per_day(20.0, {**P, "fuel_lcv_kj_kg": 32000.0}) == pytest.approx(125.0)
    assert V.me_fuel_per_day(10.0, {**P, "speed_exponent": 3.5}) == pytest.approx(100 * 0.5 ** 3.5)
    c = V.round_voyage({**P, "cape_distance_factor": 2.0}, LEGS, EU, SCHEDULE, "cape")
    assert c["distance_nm"] == pytest.approx(4800 + 240 + 4800)


def test_ets_share_rules():
    assert V.ets_share(False, False, P) == 0.0
    assert V.ets_share(False, True, P) == 0.5 and V.ets_share(True, False, P) == 0.5
    assert V.ets_share(True, True, P) == 1.0


def test_sca_containership_bands():
    s = V.load_schedule()
    assert V.suez_toll_sdr(150_000, s) == pytest.approx(587_900)                  # laden, hand-summed
    assert V.suez_toll_sdr(150_000, s, laden=False) == pytest.approx(500_550)
    assert V.suez_toll_sdr(5_000, s) == pytest.approx(55_200)
    assert V.suez_toll_sdr(200_000, s) == pytest.approx(587_900 + 30_000 * 2.94 + 20_000 * 2.88)
    with pytest.raises(ValueError):
        V.suez_toll_sdr(5_000, [(1000.0, 1.0, 1.0)])
    with pytest.raises(ValueError):
        V.round_voyage(P, LEGS, EU, SCHEDULE, "panama")


def test_tornado_sorted_and_skips_fixed_parameters():
    params = {k: {"value": v, "low": None, "high": None, "label": "SYNTHETIC", "unit": "-"} for k, v in P.items()}
    params["bunker_usd_t"].update(low=250.0, high=1000.0)
    params["charter_usd_day"].update(low=9000.0, high=11000.0)
    params["war_risk_pct"].update(low=0.1, high=1.0)
    rows = V.tornado(params, LEGS, EU, SCHEDULE)
    assert [r["parameter"] for r in rows] == ["bunker_usd_t", "charter_usd_day", "war_risk_pct"]
    assert rows[-1]["breakeven_swing_pct"] == pytest.approx(0.0)                  # p* does not depend on p
    assert rows[0]["breakeven_pct_high"] > rows[0]["breakeven_pct_low"]           # dearer fuel favours Suez


def test_real_loop_inputs_and_provenance():
    legs = V.load_legs()
    for routing in ("suez", "cape"):
        rows = [g for g in legs if g.routing == routing]
        assert [g.seq for g in rows] == list(range(1, 9))
        assert all(a.dest == b.origin for a, b in zip(rows, rows[1:])) and rows[0].origin == rows[-1].dest
    suez = {g.seq: g for g in legs if g.routing == "suez"}
    assert sum("suez" in g.passages for g in suez.values()) == 2
    assert all(g.nm >= suez[g.seq].nm for g in legs if g.routing == "cape")
    for name in ("voyage_parameters.csv", "suez_toll_schedule.csv", "ports.csv", "voyage_legs.csv"):
        assert provenance_problems(read_csv(INPUTS / name), name) == []
    params = load_parameters(INPUTS / "voyage_parameters.csv")
    for p in params.values():
        if p["low"] is not None:
            assert p["low"] <= p["value"] <= p["high"], p["name"]


def test_searoute_distances_against_published_figures():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from lsr.maritime import report as R
    rows = {(d["from_port"], d["to_port"], d["quantity"]): d for d in R.distance_checks()}
    # within 3% of UNCTAD's rounded Shenzhen-Rotterdam figures ...
    assert abs(rows[("Yantian", "Rotterdam", "suez_nm")]["difference_pct"]) < 3
    assert abs(rows[("Yantian", "Rotterdam", "cape_nm")]["difference_pct"]) < 3
    # ... but well short of the extra distance Notteboom et al. give (the factor 1.38 in the tornado)
    assert rows[("Shanghai", "Rotterdam", "extra_nm")]["difference_pct"] < -20
