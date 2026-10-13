"""Mutation check: plant known bugs one at a time; the test suite must fail on every one.

The harness first proves that it *can* report a failure:

1. the unmodified code must pass the tests;
2. a control mutant that changes nothing of substance (a docstring word) must
   SURVIVE. If the control were reported as "caught", the harness would be
   counting something other than real assertion failures (an import error,
   a broken path) and every result below would be meaningless.

Then each planted bug is applied, the tests are run, and the file is restored.
Exit code 1 if any planted bug survives or either control check fails.
Run: ``python tests/mutate.py`` (``--list`` prints the mutants).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "lsr"
PYTEST = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests",
          "--deselect", "tests/test_backtest.py::test_readme_numbers_match_outputs"]

CONTROL = ("detect.py", "Robust, one-sided anomaly detection", "Robust, one-sided anomaly detector")

MUTANTS = [
    ("detect.py", 'sign = -1.0 if direction == "drop" else 1.0', 'sign = 1.0 if direction == "drop" else -1.0',
     "stress sign flipped"),
    ("detect.py", "MAD_TO_SD = 1.4826", "MAD_TO_SD = 1.0", "MAD not scaled to a standard deviation"),
    ("detect.py", "elif run >= p.persist:", "elif run > p.persist:", "persistence off by one"),
    ("detect.py", "idx = np.flatnonzero(clean[:hi])", "idx = np.flatnonzero(np.isfinite(x[:hi]))",
     "breach values leak into the baseline"),
    ("detect.py", "hi = t - p.gap ", "hi = t ", "baseline gap ignored"),
    ("detect.py", "idx = idx[-p.window:]", "idx = idx[:p.window]", "oldest values used instead of latest"),
    ("detect.py", "if quiet >= p.tol:", "if quiet > p.tol:", "alarm closes one observation late"),
    ("detect.py", "clean[:lo] = False ", "pass ", "old regime kept after re-baselining"),
    ("detect.py", "z[t] >= p.k)", "z[t] > p.k)", "threshold made exclusive"),
    ("detect.py", "p.frac_floor * abs(median), p.abs_floor)", "p.frac_floor * abs(median))",
     "absolute scale floor dropped"),
    ("detect.py", "if len(idx) >= p.min_hist:", "if len(idx) > p.min_hist:", "minimum history off by one"),
    ("detect.py", "if s > 0:", "if True:", "zero scale not guarded"),
    ("detect.py", "breach = np.isfinite(x) & (x >= threshold)", "breach = np.isfinite(x) & (x > threshold)",
     "GSCPI threshold made exclusive"),
    ("detect.py", "            if t - active.start + 1 >= p.sustain:", "            if t - active.start >= p.sustain:",
     "sustain length off by one"),
    ("indicators.py", "rolling(7, min_periods=7)", "rolling(7, min_periods=1)", "partial weeks summed"),
    ("indicators.py", "s.shift(12, freq=\"MS\")", "s.shift(11, freq=\"MS\")", "year-on-year lag of 11 months"),
    ("indicators.py", "return m.where(days.values == full_days)", "return m",
     "incomplete months kept in call totals"),
    ("indicators.py", '"Cape of Good Hope transits", "D", "rise"', '"Cape of Good Hope transits", "D", "drop"',
     "Cape diversion direction wrong"),
    ("indicators.py", 'df["sg_teu_per_call"] = df["mpa_teu"] * 1000.0 / calls',
     'df["sg_teu_per_call"] = df["mpa_teu"] / calls', "TEU per call off by 1000"),
    ("indicators.py", 'sg["box"] = sg["import_container"] + sg["export_container"]',
     'sg["box"] = sg["import_container"]', "container volume drops exports"),
    ("backtest.py", 'e["onset"] - pd.Timedelta(days=PRE_ONSET_DAYS) <= a.raised',
     'e["onset"] - pd.Timedelta(days=PRE_ONSET_DAYS) < a.raised', "pre-onset boundary exclusive"),
    ("backtest.py", 'if a.indicator in e["expected"] and \\', 'if True and \\',
     "expected-indicator list ignored"),
    ("backtest.py", "if a.raised < EVAL_START:", "if False:", "pre-2020 alarms counted"),
    ("backtest.py", "known=raised + pd.Timedelta(days=ind.lag_days)", "known=raised",
     "publication lag ignored"),
    ("backtest.py", "alert = (route >= 2) | ((route >= 1) & local)", "alert = (route >= 3) | ((route >= 1) & local)",
     "alert needs three route alarms"),
    ("backtest.py", "            s.index = s.index + lag\n", "            pass\n", "daily posture ignores lag"),
    ("backtest.py", '"dev_fa_per_indicator_year", "k", "persist_days"],\n                         ascending=[False, True,',
     '"dev_fa_per_indicator_year", "k", "persist_days"],\n                         ascending=[False, False,',
     "selection prefers more false alarms"),
    ("backtest.py", '"lag_known_days": (a.known - e.onset).days', '"lag_known_days": (a.raised - e.onset).days',
     "known lag computed from raise date"),
    ("backtest.py", "dates = lambda i: month_end(idx[i])", "dates = lambda i: idx[i]",
     "monthly alarms dated at month start"),
    ("backtest.py", '"lead_days": (e.sg_reference_date - a.known).days', '"lead_days": (a.known - e.sg_reference_date).days',
     "lead sign flipped"),
    ("backtest.py", "level = np.where(alert & outcome, 3, level)", "level = np.where(outcome, 3, level)",
     "activate review without alert"),
]


def run_tests() -> bool:
    r = subprocess.run(PYTEST, cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def apply(fname: str, old: str, new: str) -> str:
    p = SRC / fname
    src = p.read_text(encoding="utf-8")
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"mutant anchor found {n} times in {fname}: {old!r}")
    p.write_text(src.replace(old, new), encoding="utf-8")
    return src


def main() -> int:
    if "--list" in sys.argv:
        for i, m in enumerate(MUTANTS, 1):
            print(f"{i:2d}. {m[0]}: {m[3]}")
        return 0
    ok = True
    if not run_tests():
        print("BASELINE FAILED: the unmodified code does not pass the tests")
        return 1
    print("baseline: tests pass on unmodified code")
    fname, old, new = CONTROL
    orig = apply(fname, old, new)
    try:
        survived = run_tests()
    finally:
        (SRC / fname).write_text(orig, encoding="utf-8")
    print(f"control (no-op) mutant: {'survived - harness can report survivors' if survived else 'CAUGHT - harness broken'}")
    ok &= survived
    caught = 0
    for fname, old, new, desc in MUTANTS:
        orig = apply(fname, old, new)
        try:
            passed = run_tests()
        finally:
            (SRC / fname).write_text(orig, encoding="utf-8")
        status = "SURVIVED" if passed else "caught"
        caught += not passed
        print(f"  {status:8s} {fname}: {desc}")
    print(f"{caught}/{len(MUTANTS)} planted bugs caught")
    ok &= caught == len(MUTANTS)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
