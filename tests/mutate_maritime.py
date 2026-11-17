"""Mutation check for the maritime modules: plant known bugs one at a time; tests must fail on each.

Same protocol as ``tests/mutate.py``: the unmodified code must pass, a no-op control mutant must
SURVIVE (otherwise the harness would be counting import errors as catches), and then every planted
bug must make its tests fail. Each mutant runs only the test files of the module it changes, which is
stricter than running the whole suite and keeps the check to a few minutes.
Run: ``python tests/mutate_maritime.py`` (``--list`` prints the mutants).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "lsr" / "maritime"
TESTS = {
    "voyage.py": ["tests/test_maritime_voyage.py"],
    "sd.py": ["tests/test_maritime_sd.py"],
    "calibrate.py": ["tests/test_maritime_sd.py"],
    "scenarios.py": ["tests/test_maritime_scenarios.py"],
    "extraction.py": ["tests/test_maritime_extraction.py"],
    "cld.py": ["tests/test_maritime_cld.py"],
    "inputs.py": ["tests/test_maritime_docs.py"],
    "paper.py": ["tests/test_maritime_docs.py"],
}
CONTROL = ("voyage.py", "Costs per round voyage of one ship.", "Costs per round voyage of a ship.")

MUTANTS = [
    # voyage economics
    ("voyage.py", '        return v["ets_share_intra_eu"]\n    if origin_eu or dest_eu:',
     '        return v["ets_share_extra_eu"]\n    if origin_eu or dest_eu:', "intra-EU voyages only half covered by the ETS"),
    ("voyage.py", "    if origin_eu or dest_eu:\n", "    if origin_eu and dest_eu:\n", "extra-EU voyages not covered by the ETS"),
    ("voyage.py", '** v["speed_exponent"]', "** 2.0", "speed-fuel exponent ignored"),
    ("voyage.py", '* v["fuel_lcv_ref_kj_kg"] / v["fuel_lcv_kj_kg"])', '* v["fuel_lcv_kj_kg"] / v["fuel_lcv_ref_kj_kg"])',
     "calorific-value correction inverted"),
    ("voyage.py", "take = remaining if band is None else min(remaining, band)",
     "take = remaining if band is None else band", "toll band charged in full even when tonnage runs out"),
    ("voyage.py", "(laden_rate if laden else ballast_rate)", "(ballast_rate if laden else laden_rate)",
     "laden and ballast toll rates swapped"),
    ("voyage.py", 'v["war_risk_pct"] / 100.0 * v["hull_value_usd"]', 'v["war_risk_pct"] * v["hull_value_usd"]',
     "war-risk premium not converted from percent"),
    ("voyage.py", '(suez0["war_risk_transits"] * v["hull_value_usd"])', '(v["hull_value_usd"])',
     "break-even counts one war-risk transit per round voyage"),
    ("voyage.py", "    days = sea_days + port_days + canal_days\n", "    days = sea_days + port_days\n",
     "canal days not charged"),
    ("voyage.py", "(1.0 + v[\"suez_surcharge\"] - v[\"suez_rebate\"])", "(1.0 - v[\"suez_surcharge\"] - v[\"suez_rebate\"])",
     "Suez surcharge applied as a rebate"),
    ("voyage.py", 'v["capacity_teu"] * (v["utilisation_head"] + v["utilisation_back"])',
     'v["capacity_teu"] * v["utilisation_head"]', "backhaul TEU left out of cost per TEU"),
    ("voyage.py", 'return suez_leg.nm + v["cape_distance_factor"] * (leg.nm - suez_leg.nm)',
     'return v["cape_distance_factor"] * leg.nm', "distance factor scales the whole Cape leg"),
    # stock-and-flow model and integrator
    ("sd.py", "(a + 2.0 * b + 2.0 * c + d)", "(a + b + c + d)", "RK4 weights wrong"),
    ("sd.py", "k3 = f(t + 0.5 * dt, tuple(yi + 0.5 * dt * ki for yi, ki in zip(y, k2)))",
     "k3 = f(t + 0.5 * dt, tuple(yi + dt * ki for yi, ki in zip(y, k2)))", "RK4 third stage takes a full step"),
    ("sd.py", "(D - Dc) / p.tau_c,", "(Dc - D) / p.tau_c,", "Cape pipeline sign flipped"),
    ("sd.py", "(du - K - Q) / p.tau_q,", "(du + K - Q) / p.tau_q,", "adaptation adds to bunching"),
    ("sd.py", "(1.0 - p.adapt) * du, p.adapt * du", "p.adapt * du, p.adapt * du", "steady-state bunching wrong"),
    ("sd.py", "0.5 * (traj[i][idx] + traj[i + 1][idx])", "traj[i][idx]", "daily mean uses the start of day only"),
    # calibration
    ("calibrate.py", "math.fsum(daily[day(w) - 6: day(w) + 1]) / 7.0", "math.fsum(daily[day(w) - 7: day(w)]) / 7.0",
     "weekly window shifted by a day"),
    ("calibrate.py", "    den = math.fsum(v * v for v in x)\n", "    den = math.fsum(abs(v) for v in x)\n",
     "least-squares denominator wrong"),
    ("calibrate.py", "    return (1.0 + rho) / (1.0 - rho)\n", "    return 1.0\n", "autocorrelation inflation dropped"),
    ("calibrate.py", "xr = clip([c[j] + (c[j] - pts[-1][j]) for j in range(n)])",
     "xr = clip([c[j] - (c[j] - pts[-1][j]) for j in range(n)])", "Nelder-Mead reflects toward the worst point"),
    ("calibrate.py", "        if fc <= fd:\n", "        if fc >= fd:\n", "golden-section keeps the wrong side"),
    ("calibrate.py", "<= 3.84 * inflation]", "<= 3.84]", "onset interval ignores autocorrelation"),
    # scenarios
    ("scenarios.py", "open_ = ~active & b & (run >= persist)", "open_ = ~active & b & (run > persist)",
     "alarm persistence off by one"),
    ("scenarios.py", "close = active & ~b & (quiet >= tol)", "close = active & ~b & (quiet > tol)",
     "alarm closes a day late"),
    ("scenarios.py", "    alert = (route >= 2) | ((route >= 1) & local)\n", "    alert = (route >= 2)\n",
     "route plus port alarm no longer an Alert"),
    ("scenarios.py", "    out[:, lag:] = alarm[:, :alarm.shape[1] - lag]\n", "    out[:, :] = alarm\n",
     "publication lag ignored"),
    ("scenarios.py", "    return np.where(u < fc, left, right)\n", "    return np.where(u < fc, right, left)\n",
     "triangular inverse CDF branches swapped"),
    ("scenarios.py", "        cap = 1.0 - severity * inside + extra * (1.0 - inside)\n",
     "        cap = 1.0 - severity * inside\n", "no catch-up after the closure"),
    ("scenarios.py", "    return acc / 7.0\n", "    return acc / 6.0\n", "weekly factor averaged over six days"),
    ("scenarios.py", "    starts = noise_rng.integers(", "    starts = rng.integers(", "scenarios draw different noise"),
    # extraction scoring
    ("extraction.py", "        fp += len(set(q) - set(r))\n", "        fp += len(set(r) - set(q))\n",
     "false positives counted from the reference"),
    ("extraction.py", 'pr = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0',
     'pr = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0', "precision uses false negatives"),
    ("extraction.py", 'out.setdefault(r["passage_id"], {}).setdefault((r["cause"], r["effect"]), r["polarity"])',
     'out.setdefault(r["passage_id"], {})[(r["cause"], r["effect"])] = r["polarity"]',
     "repeated pair keeps the last polarity"),
    ("extraction.py", "        pol += sum(r[k] == q[k] for k in hit)\n", "        pol += len(hit)\n",
     "polarity agreement always perfect"),
    # causal loop diagram
    ("cld.py", '    return "R" if sign > 0 else "B"\n', '    return "B" if sign > 0 else "R"\n', "loop polarity flipped"),
    ("cld.py", "allowed = {k for k in keys if k >= start}", "allowed = set(keys)", "cycles counted more than once"),
    # provenance check and paper rendering
    ("inputs.py", "        if label not in LABELS:", "        if False:", "unknown provenance labels accepted"),
    ("inputs.py", 'elif label == "REAL" and not (', 'elif label == "SYNTHETIC" and not (',
     "REAL rows no longer need a URL and an access date"),
    ("inputs.py", 'len(r.get("accessed", "")) == 10)', 'len(r.get("accessed", "")) >= 0)', "access date not required"),
    ("paper.py", "        return format(v, fmt) if fmt else str(v)", "        return str(v)",
     "number formats ignored in the paper"),
    ("paper.py", 'v = v[int(part)] if isinstance(v, list) else v[part]', 'v = v[0] if isinstance(v, list) else v[part]',
     "list index ignored in paper placeholders"),
]


def run_tests(files: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *files]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).returncode == 0


def apply(fname: str, old: str, new: str) -> str:
    p = SRC / fname
    src = p.read_text(encoding="utf-8")
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"mutant anchor found {n} times in {fname}: {old!r}")
    p.write_text(src.replace(old, new), encoding="utf-8", newline="\n")
    return src


def main() -> int:
    if "--list" in sys.argv:
        for i, m in enumerate(MUTANTS, 1):
            print(f"{i:2d}. {m[0]}: {m[3]}")
        return 0
    every = sorted({f for files in TESTS.values() for f in files})
    if not run_tests(every):
        print("BASELINE FAILED: the unmodified code does not pass the maritime tests")
        return 1
    print("baseline: maritime tests pass on unmodified code")
    fname, old, new = CONTROL
    orig = apply(fname, old, new)
    try:
        survived = run_tests(TESTS[fname])
    finally:
        (SRC / fname).write_text(orig, encoding="utf-8", newline="\n")
    print(f"control (no-op) mutant: {'survived - harness can report survivors' if survived else 'CAUGHT - harness broken'}")
    ok = survived
    caught = 0
    for fname, old, new, desc in MUTANTS:
        orig = apply(fname, old, new)
        try:
            passed = run_tests(TESTS[fname])
        finally:
            (SRC / fname).write_text(orig, encoding="utf-8", newline="\n")
        caught += not passed
        print(f"  {'SURVIVED' if passed else 'caught':8s} {fname}: {desc}", flush=True)
    print(f"{caught}/{len(MUTANTS)} planted bugs caught")
    ok &= caught == len(MUTANTS)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
