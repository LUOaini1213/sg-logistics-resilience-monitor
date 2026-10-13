"""Run the whole backtest and write every output table plus the dashboard."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest as B
from .dashboard import build_dashboard
from .indicators import INDICATORS, load_daily, load_monthly

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"


def first_level_dates(po: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, e in events.iterrows():
        lo = e.onset - pd.Timedelta(days=B.PRE_ONSET_DAYS)
        w = po.loc[lo:e.window_end]
        row = {"event": e.event_id, "onset": e.onset.date()}
        for lvl in (2, 3):
            hit = w.index[w.level >= lvl]
            row[f"first_level{lvl}"] = hit[0].date() if len(hit) else None
            row[f"days_from_onset_level{lvl}"] = (hit[0] - e.onset).days if len(hit) else None
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> dict:
    OUT.mkdir(exist_ok=True)
    daily, monthly, events = load_daily(), load_monthly(), B.load_events()
    grid, (k, p) = B.tune(daily, monthly, events)
    grid.round(4).to_csv(OUT / "tuning_grid.csv", index=False)

    r = B.evaluate(k, p, daily, monthly, events)
    matched, det, frames = r["matched"], r["det"], r["frames"]
    det.to_csv(OUT / "detections.csv", index=False)
    al = matched.copy()
    for c in ("raised", "known", "first_breach", "end", "rebaseline"):
        al[c] = pd.to_datetime(al[c]).dt.date
    al["peak_z"] = al["peak_z"].round(2)
    al.sort_values(["indicator", "raised"]).to_csv(OUT / "alarms.csv", index=False)

    fa = matched[~matched.true_alarm]
    yrs = {per: B.evaluated_years(frames, per) for per in ("dev", "holdout")}
    fa_tab = []
    for key, ind in INDICATORS.items():
        row = {"indicator": key, "label": ind.label, "family": ind.family, "direction": ind.direction}
        for per in ("dev", "holdout"):
            n = int(((fa.indicator == key) & (fa.period == per)).sum())
            row[f"{per}_false_alarms"] = n
            row[f"{per}_years"] = round(yrs[per][key], 2)
            row[f"{per}_per_year"] = round(n / yrs[per][key], 2) if yrs[per][key] else None
        fa_tab.append(row)
    fa_tab = pd.DataFrame(fa_tab)
    fa_tab.to_csv(OUT / "false_alarms_by_indicator.csv", index=False)

    lead = B.sg_lead(matched, events)
    lead.to_csv(OUT / "sg_lead.csv", index=False)

    # The TEU-per-call transform comparison (see indicators.py).
    alt = B.evaluate(k, p, daily, monthly, events, transforms={"sg_teu_per_call": "yoy"})
    cmp_rows = []
    for name, res in (("level (used)", r), ("year-on-year (first version)", alt)):
        d = res["det"][res["det"].indicator == "sg_teu_per_call"]
        n_fa = int(((~res["matched"].true_alarm) & (res["matched"].indicator == "sg_teu_per_call")).sum())
        for _, x in d.iterrows():
            cmp_rows.append({"version": name, "event": x.event, "detected": x.detected,
                             "known": x.known, "lag_known_days": x.lag_known_days,
                             "false_alarms_2020_2026": n_fa})
    pd.DataFrame(cmp_rows).to_csv(OUT / "teu_per_call_transform_check.csv", index=False)

    end = max(daily.index.max(), monthly.dropna(how="all").index.max() + pd.offsets.MonthEnd(0))
    days = pd.date_range(B.EVAL_START, end + pd.Timedelta(days=7), freq="D")
    po = B.posture(frames, days)
    po.to_csv(OUT / "posture_daily.csv", index_label="date")
    by_year = po.groupby([po.index.year, "level"]).size().unstack(fill_value=0)
    by_year.columns = [B.LEVELS[c] for c in by_year.columns]
    by_year.to_csv(OUT / "posture_days_by_year.csv", index_label="year")
    fl = first_level_dates(po, events)
    fl.to_csv(OUT / "posture_first_level_by_event.csv", index=False)

    # Alert-or-above days that fall outside every labelled event window.
    in_window = pd.Series(False, index=po.index)
    for _, e in events.iterrows():
        in_window |= (po.index >= e.onset - pd.Timedelta(days=B.PRE_ONSET_DAYS)) & (po.index <= e.window_end)
    alert_days = po.level >= 2
    as_of = po.index[-1]
    data_end = {"portwatch": str(daily.index.max().date()),
                "mpa": str(monthly["mpa_teu"].dropna().index.max().date())[:7],
                "changi": str(monthly["changi_air_cargo"].dropna().index.max().date())[:7],
                "gscpi": str(monthly["gscpi"].dropna().index.max().date())[:7]}
    dev, hold = r["dev"], r["holdout"]
    summary = {
        "selected": {"k": k, "persist_days": p},
        "dev": {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in dev.items()},
        "holdout": {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in hold.items()},
        "n_indicators": len(INDICATORS),
        "n_events": len(events),
        "data_end": data_end,
        "detections": json.loads(det.to_json(orient="records", date_format="iso")),
        "sg_lead": json.loads(lead.to_json(orient="records", date_format="iso")),
        "alert_days_total": int(alert_days.sum()),
        "alert_days_outside_events": int((alert_days & ~in_window).sum()),
        "posture_as_of": str(as_of.date()),
        "posture_level": int(po.level.iloc[-1]),
        "posture_label": B.LEVELS[int(po.level.iloc[-1])],
        "posture_active": po.active.iloc[-1],
        "false_alarms_total": int(len(fa)),
        "median_lag_known_days_route": float(np.median(
            det[det.detected & det.indicator.str.startswith("cp_")].lag_known_days)),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    build_dashboard(frames, matched, events, po, det, fa_tab, lead, summary, ROOT / "docs" / "index.html")
    return summary


if __name__ == "__main__":
    s = main()
    print(json.dumps({k: s[k] for k in ("selected", "dev", "holdout", "posture_label", "posture_active")},
                     indent=1, default=str))
