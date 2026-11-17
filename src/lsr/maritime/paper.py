"""Render the working paper's Markdown from its template and the results files.

``paper/working_paper.template.md`` holds the prose. ``{{a.b.c}}`` is replaced by that entry of
``outputs/maritime/summary.json`` (``{{a.b|.2f}}`` adds a format), ``{{main.x}}`` by an entry of the
monitor's ``outputs/summary.json``, and ``{{table:name}}`` by a table built from the CSV outputs. The
result, ``paper/working_paper.md``, is rebuilt by ``run_all.py`` and checked by CI like any other
output; ``scripts/build_paper.py`` turns it into the PDF.
"""
from __future__ import annotations

import json
import re

from .inputs import ROOT, read_csv

PAPER = ROOT / "paper"
OUT = ROOT / "outputs" / "maritime"


def lookup(data: dict, path: str):
    v = data
    for part in path.split("."):
        v = v[int(part)] if isinstance(v, list) else v[part]
    return v


def md_table(header: list[str], rows: list[list], align: str | None = None) -> str:
    align = align or "l" + "r" * (len(header) - 1)
    sep = ["---:" if a == "r" else "---" for a in align]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def sig3(text: str) -> str:
    """Three significant digits for numbers; dates and other text unchanged."""
    try:
        return f"{float(text):.3g}"
    except ValueError:
        return text


def t_sd_parameters() -> str:
    rows = [r for r in read_csv(OUT / "sd_parameters.csv") if r["block"] in ("routing", "reliability", "singapore")]
    out = []
    for r in rows:
        ci = f"{sig3(r['ci95_low'])} to {sig3(r['ci95_high'])}" if r["ci95_low"] else ""
        out.append([f"`{r['parameter']}`", r["block"], sig3(r["estimate"]), ci, r["meaning"]])
    return md_table(["Parameter", "Block", "Estimate", "95% interval", "Meaning"], out, "lllll")


def t_sd_fit() -> str:
    names = {"bab": "Bab el-Mandeb container transits (weekly)", "cape": "Cape container transits (weekly)",
             "glp": "Global schedule reliability (monthly, %)", "calls": "Singapore container calls (weekly)",
             "tpc": "Singapore TEU per call (monthly)"}
    rows = [[names[r["series"]], r["n"], f"{float(r['r2']):.2f}", f"{float(r['mape_pct']):.1f}"]
            for r in read_csv(OUT / "sd_fit_stats.csv")]
    return md_table(["Series", "n", "R²", "MAPE %"], rows)


def t_voyage() -> str:
    c = {r["routing"]: r for r in read_csv(OUT / "voyage_costs.csv")}
    lines = [("Round-voyage days", "round_voyage_days", "{:.1f}"), ("Ships for a weekly service", "ships_for_weekly_service", "{:.1f}"),
             ("Fuel burnt (t)", "fuel_t", "{:,.0f}"), ("Fuel (USD)", "fuel_usd", "{:,.0f}"),
             ("Charter (USD)", "charter_usd", "{:,.0f}"), ("Suez tolls (USD)", "canal_usd", "{:,.0f}"),
             ("War-risk premium at 1% (USD)", "war_risk_usd", "{:,.0f}"), ("EU ETS (USD)", "eu_ets_usd", "{:,.0f}"),
             ("Total (USD)", "total_usd", "{:,.0f}"), ("Per TEU carried (USD)", "usd_per_teu", "{:,.2f}")]
    rows = [[label, fmt.format(float(c["suez"][k])), fmt.format(float(c["cape"][k]))] for label, k, fmt in lines]
    return md_table(["Per round voyage", "Via Suez", "Via the Cape"], rows)


def t_scenarios() -> str:
    lad = {r["scenario"]: r for r in read_csv(OUT / "scenario_ladder.csv")}
    rows = []
    for name, r in lad.items():
        days = f"{float(r['days_to_level2_p50']):.0f}" if r["days_to_level2_p50"] else "-"
        rows.append([r["title"], f"{float(r['p_level2']):.2f}", f"{float(r['p_level2_attributable']):.2f}",
                     f"{float(r['p_level3']):.2f}", days])
    return md_table(["Scenario", "P(Alert)", "P(Alert) due to the scenario", "P(Activate review)",
                     "Median days, onset to Alert"], rows)


def t_extraction() -> str:
    rows = []
    for r in read_csv(OUT / "extraction_scores.csv"):
        rows.append([f"`{r['model']}`", r["predicted_links"], r["tp"],
                     f"{float(r['precision']):.2f} ({r['precision_ci95']})",
                     f"{float(r['recall']):.2f} ({r['recall_ci95']})", f"{float(r['f1']):.2f}",
                     f"{float(r['polarity_agreement']):.2f}", f"{float(r['quote_verbatim_share']):.2f}"])
    return md_table(["Model", "Links", "Matched", "Precision (95% CI)", "Recall (95% CI)", "F1", "Polarity agreement",
                     "Verbatim quotes"], rows, "lrrrrrrr")


TABLES = {"sd_parameters": t_sd_parameters, "sd_fit": t_sd_fit, "voyage": t_voyage, "scenarios": t_scenarios,
          "extraction": t_extraction}


def render(template: str, data: dict, main: dict) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1).strip()
        if key.startswith("table:"):
            return TABLES[key[6:]]()
        path, _, fmt = key.partition("|")
        v = lookup(main, path[5:]) if path.startswith("main.") else lookup(data, path)
        return format(v, fmt) if fmt else str(v)
    out = re.sub(r"\{\{([^{}]+)\}\}", repl, template)
    if "{{" in out or "}}" in out:
        raise ValueError("unrendered placeholder in the paper template")
    return out


def build(summary: dict) -> str:
    main = json.loads((ROOT / "outputs" / "summary.json").read_text(encoding="utf-8"))
    template = (PAPER / "working_paper.template.md").read_text(encoding="utf-8")
    return render(template, summary, main)
