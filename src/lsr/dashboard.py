"""Static Plotly dashboard written to docs/index.html (served by GitHub Pages)."""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs_version
from plotly.subplots import make_subplots

from .indicators import INDICATORS

SERIES = "#2a78d6"
ALARM = "#d03b3b"
BAND = "rgba(137,135,129,0.16)"
INK2 = "#52514e"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
LEVEL_COLORS = {0: "#0ca30c", 1: "#fab219", 2: "#ec835a", 3: "#d03b3b"}
LEVEL_NAMES = {0: "Normal", 1: "Watch", 2: "Alert", 3: "Activate review"}
SHORT = {"covid_china": "COVID", "pandemic_congestion": "Pandemic congestion", "ever_given": "Ever Given",
         "panama_drought": "Panama drought", "red_sea_2023": "Red Sea", "sg_congestion_2024": "SG congestion",
         "hormuz_2026": "Hormuz", "red_sea_2026": "Red Sea 2026"}


def _layout(fig: go.Figure, height: int) -> None:
    fig.update_layout(height=height, margin=dict(l=56, r=16, t=36, b=32), paper_bgcolor=SURFACE,
                      plot_bgcolor=SURFACE, font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                                                      size=12, color=INK2),
                      hovermode="x unified", legend=dict(orientation="h", y=1.06, x=0))
    fig.update_xaxes(showgrid=False, linecolor="#c3c2b7")
    fig.update_yaxes(gridcolor=GRID, zeroline=False)


def _bands(fig: go.Figure, events: pd.DataFrame, start: pd.Timestamp, rows: int | None = None) -> None:
    for _, e in events.iterrows():
        x0 = max(e.onset, start)
        kw = dict(x0=x0, x1=e.window_end, fillcolor=BAND, line_width=0, layer="below")
        if rows:
            for r in range(1, rows + 1):
                fig.add_vrect(row=r, col=1, **kw)
        else:
            fig.add_vrect(**kw)
    if not rows:   # label the bands at three staggered heights so neighbours do not collide
        for i, (_, e) in enumerate(events.sort_values("onset").iterrows()):
            fig.add_annotation(x=max(e.onset, start), y=(1.05, 1.21, 1.37)[i % 3], xanchor="left",
                               yanchor="bottom", text=SHORT.get(e.event_id, e.event_id), showarrow=False,
                               font=dict(size=10, color=INK2))


def _alarm_overlay(frame: pd.DataFrame, values: pd.Series) -> pd.Series:
    return values.where(frame["alarm"].reindex(values.index).fillna(False).astype(bool))


def posture_figure(po: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for lvl, name in LEVEL_NAMES.items():
        y = po.level.where(po.level == lvl)
        fig.add_trace(go.Bar(x=po.index, y=(y * 0 + 1), name=f"{lvl} {name}", marker_color=LEVEL_COLORS[lvl],
                             marker_line_width=0, customdata=po.active,
                             hovertemplate=f"%{{x|%d %b %Y}}<br>Level {lvl}: {name}<br>%{{customdata}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0)
    fig.update_yaxes(visible=False, range=[0, 1.58])
    _bands(fig, events, po.index[0])
    _layout(fig, 270)
    fig.update_layout(legend=dict(orientation="h", y=-0.18, x=0, traceorder="normal"), hovermode="closest",
                      margin=dict(t=12, b=56))
    return fig


def indicator_grid(keys: list[str], frames: dict, events: pd.DataFrame, start: pd.Timestamp,
                   title_suffix: str) -> go.Figure:
    titles = [f"{INDICATORS[k].label} ({'7-day sum' if INDICATORS[k].freq == 'D' else 'monthly'}, "
              f"stress = {INDICATORS[k].direction})" for k in keys]
    fig = make_subplots(rows=len(keys), cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        subplot_titles=titles)
    for i, k in enumerate(keys, start=1):
        f = frames[k]
        v = f["value"]
        if INDICATORS[k].freq == "M" and INDICATORS[k].transform == "yoy":
            v = v * 100.0
        v = v[v.index >= start]
        fig.add_trace(go.Scatter(x=v.index, y=v, mode="lines", line=dict(color=SERIES, width=1.5),
                                 name="value" if i == 1 else None, showlegend=(i == 1),
                                 legendgroup="v"), row=i, col=1)
        a = _alarm_overlay(f, v)
        fig.add_trace(go.Scatter(x=a.index, y=a, mode="lines", line=dict(color=ALARM, width=2.5),
                                 name="alarm active" if i == 1 else None, showlegend=(i == 1),
                                 legendgroup="a", connectgaps=False), row=i, col=1)
    _bands(fig, events, start, rows=len(keys))
    for ann in fig.layout.annotations:
        ann.font.size = 11
        ann.font.color = INK2
        ann.x = 0
        ann.xanchor = "left"
    _layout(fig, 150 * len(keys) + 60)
    return fig


def _table(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, classes="tbl", na_rep="-", escape=True)


def build_dashboard(frames, matched, events, po, det, fa_tab, lead, summary, path: Path) -> None:
    start = pd.Timestamp("2020-01-01")
    figs = {
        "posture": posture_figure(po, events),
        "route": indicator_grid(["cp_bab", "cp_suez", "cp_cape", "cp_hormuz", "cp_panama", "cp_malacca",
                                 "cp_taiwan"], frames, events, start, "route"),
        "sg": indicator_grid(["sg_calls_container", "sg_box_volume", "sg_teu_per_call", "mpa_teu",
                              "changi_air_cargo", "gscpi"], frames, events, start, "sg"),
    }
    divs = {k: f.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False,
                                                                           "responsive": True})
            for k, f in figs.items()}
    lvl = summary["posture_level"]
    det_view = det.assign(indicator=det.indicator.map(lambda k: INDICATORS[k].label))
    det_view = det_view[["event", "split", "indicator", "detected", "known", "lag_known_days"]]
    fa_view = fa_tab[["label", "family", "dev_false_alarms", "dev_per_year", "holdout_false_alarms",
                      "holdout_per_year"]]
    lead_view = lead.assign(indicator=lead.indicator.map(lambda k: INDICATORS[k].label))
    active = ", ".join(INDICATORS[k].label for k in summary["posture_active"].split(";") if k) or "none"
    de = summary["data_end"]
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singapore Logistics Resilience Monitor</title>
<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>
<style>
:root{{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9}}
body{{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
line-height:1.45}}
main{{max-width:1100px;margin:0 auto;padding:16px}}
h1{{font-size:1.5rem;margin:.6rem 0 .2rem}} h2{{font-size:1.1rem;margin:1.6rem 0 .4rem}}
p,li{{color:var(--ink2);font-size:.95rem}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0;
overflow-x:auto}}
.tile{{display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.lvl{{font-size:1.6rem;font-weight:600;color:var(--ink)}}
.dot{{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:8px;vertical-align:middle}}
.tbl{{border-collapse:collapse;font-size:.85rem;width:100%}}
.tbl th,.tbl td{{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}}
.small{{font-size:.82rem;color:var(--muted)}}
</style></head><body><main>
<h1>Singapore Logistics Resilience Monitor</h1>
<p>Leading indicators for Singapore's logistics sector from public data, with alarms backtested against
{summary['n_events']} documented disruptions (2020&ndash;2026). Code, sources and method:
<a href="https://github.com/LUOaini1213/sg-logistics-resilience-monitor">GitHub repository</a>.</p>
<div class="card tile"><div><span class="dot" style="background:{LEVEL_COLORS[lvl]}"></span>
<span class="lvl">Level {lvl}: {html.escape(summary['posture_label'])}</span></div>
<div><p style="margin:0">As of {summary['posture_as_of']} (PortWatch data to {de['portwatch']}; MPA to {de['mpa']};
Changi to {de['changi']}; GSCPI to {de['gscpi']}).<br>Indicators in alarm: {html.escape(active)}.</p></div></div>
<h2>Alert level over time</h2>
<p>Watch: any indicator in alarm. Alert: two route indicators, or a route indicator plus a Singapore or regional
one. Activate review: Alert plus a Singapore monthly outcome in alarm. Each day uses only data that had been
published by then. Grey bands are the labelled events.</p>
<div class="card">{divs['posture']}</div>
<h2>Shipping routes (IMF PortWatch)</h2><div class="card">{divs['route']}</div>
<h2>Singapore and global pressure</h2>
<p class="small">TEU per call = MPA container throughput divided by PortWatch container-ship calls.
Container throughput and air cargo are plotted as year-on-year log change x100 (close to % change), the form the detector uses.</p>
<div class="card">{divs['sg']}</div>
<h2>Backtest: first alarm per event and indicator</h2>
<p class="small">Selected setting (tuned on 2020&ndash;2022 only): z &ge; {summary['selected']['k']},
{summary['selected']['persist_days']} consecutive days. "known" = the day the alarm could have been read,
including the source's publication lag. Lag is counted from the documented onset.</p>
<div class="card">{_table(det_view)}</div>
<h2>Lead over the Singapore congestion statement (MPA, 30 May 2024)</h2>
<div class="card">{_table(lead_view)}</div>
<h2>False alarms by indicator</h2>
<div class="card">{_table(fa_view)}</div>
<p class="small">Sources: IMF PortWatch; Maritime and Port Authority of Singapore via data.gov.sg; SingStat
Table Builder M650031 (Civil Aviation Authority of Singapore); Federal Reserve Bank of New York GSCPI.
Event sources are listed in data/events.csv.</p>
</main></body></html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
