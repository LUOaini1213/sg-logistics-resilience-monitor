"""Minimal, deterministic SVG charts for the README and the working paper.

Hand-written rather than matplotlib so that the files are byte-identical on Windows and Linux
(CI rebuilds and diffs them). Coordinates are printed with fixed decimals; no fonts are embedded.
Colours follow the dashboard's palette (series blue and orange, hairline grid, muted axis ink).
"""
from __future__ import annotations

import datetime as dt
import html

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6")
FONT = "system-ui, -apple-system, Segoe UI, sans-serif"


def f(x: float) -> str:
    s = f"{x:.1f}"
    return "0.0" if s == "-0.0" else s


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


class Svg:
    def __init__(self, width: int, height: int, title: str):
        self.w, self.h = width, height
        self.parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="{SURFACE}"/>']
        self.title = title

    def add(self, s: str) -> None:
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, color=AXIS, width=1.0, dash: str | None = None) -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{color}" '
                 f'stroke-width="{width}"{d}/>')

    def rect(self, x, y, w, h, color, rx=0.0) -> None:
        if w < 0:
            x, w = x + w, -w
        self.add(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{f(rx)}" fill="{color}"/>')

    def polyline(self, pts, color, width=2.0, dash: str | None = None) -> None:
        if len(pts) < 2:
            return
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{f(x)},{f(y)}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{width}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def circle(self, x, y, r, color) -> None:
        self.add(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="{color}" stroke="{SURFACE}" stroke-width="1.5"/>')

    def text(self, x, y, s, size=11, color=INK2, anchor="start", weight="normal") -> None:
        w = ' font-weight="600"' if weight != "normal" else ""
        self.add(f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" fill="{color}" text-anchor="{anchor}"{w}>'
                 f'{esc(s)}</text>')

    def render(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}" role="img">\n'
                f'<title>{esc(self.title)}</title>\n')
        return head + "\n".join(self.parts) + "\n</svg>\n"


def nice_step(span: float, target: int = 5) -> float:
    """Smallest step in {1, 2, 5} x 10^k giving at most ``target`` intervals over ``span``."""
    if span <= 0:
        return 1.0
    for k in range(-6, 13):
        base = 10.0 ** k
        for m in (1.0, 2.0, 5.0):
            if span / (m * base) <= target:
                return m * base
    return 10.0 ** 13


def ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    step = nice_step(hi - lo, target)
    start = int(lo // step)
    out = []
    i = start
    while i * step <= hi + 1e-9 * step:
        if i * step >= lo - 1e-9 * step:
            out.append(i * step)
        i += 1
    return out


def fmt_tick(v: float, step: float) -> str:
    if step >= 1:
        return f"{v:,.0f}"
    if step >= 0.1:
        return f"{v:.1f}"
    if step >= 0.01:
        return f"{v:.2f}"
    return f"{v:.3f}"


def _ordinal(d: dt.date) -> int:
    return d.toordinal()


def line_panels(panels: list[dict], title: str, width: int = 760, panel_h: int = 150, cols: int = 2) -> str:
    """Small multiples of time series. Each panel: ``{"title", "series": [{"name", "dates", "values",
    "color", "dash", "points"}], "ylabel", "vline": (date, label) | None}``. Panels share no axes."""
    rows = (len(panels) + cols - 1) // cols
    top, gap_y, left_pad, right_pad = 34, 62, 54, 14
    pw = (width - 16) // cols
    height = top + rows * (panel_h + gap_y) + 8
    s = Svg(width, height, title)
    s.text(8, 20, title, size=13, color=INK, weight="bold")
    for n, p in enumerate(panels):
        r, c = divmod(n, cols)
        x0 = 8 + c * pw + left_pad
        x1 = 8 + (c + 1) * pw - right_pad
        y0 = top + r * (panel_h + gap_y) + 40
        y1 = y0 + panel_h - 22
        s.text(x0 - left_pad + 4, y0 - 24, p["title"], size=11, color=INK, weight="bold")
        xs = [_ordinal(d) for ser in p["series"] for d in ser["dates"]]
        ys = [v for ser in p["series"] for v in ser["values"] if v is not None]
        xlo, xhi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        pad = (yhi - ylo) * 0.08 or 1.0
        ylo, yhi = ylo - pad, yhi + pad
        step = nice_step(yhi - ylo, 4)
        ylo, yhi = (ylo // step) * step, -((-yhi) // step) * step

        def px(d):
            return x0 + (_ordinal(d) - xlo) / max(xhi - xlo, 1) * (x1 - x0)

        def py(v):
            return y1 - (v - ylo) / (yhi - ylo) * (y1 - y0)

        for t in ticks(ylo, yhi, 4):
            s.line(x0, py(t), x1, py(t), GRID, 1.0)
            s.text(x0 - 6, py(t) + 4, fmt_tick(t, step), size=10, color=MUTED, anchor="end")
        s.line(x0, y1, x1, y1, AXIS, 1.0)
        d0 = dt.date.fromordinal(xlo)
        for yr in range(d0.year, dt.date.fromordinal(xhi).year + 1):
            for mo in (1, 7):
                d = dt.date(yr, mo, 1)
                if xlo <= _ordinal(d) <= xhi:
                    s.line(px(d), y1, px(d), y1 + 4, AXIS, 1.0)
                    s.text(px(d), y1 + 15, d.strftime("%b %Y"), size=10, color=MUTED, anchor="middle")
        if p.get("vline"):
            d, label = p["vline"]
            if xlo <= _ordinal(d) <= xhi:
                s.line(px(d), y0, px(d), y1, MUTED, 1.0, dash="3 3")
                s.text(px(d) + 3, y0 + 9, label, size=9, color=MUTED)
        for ser in p["series"]:
            pts = [(px(d), py(v)) for d, v in zip(ser["dates"], ser["values"]) if v is not None]
            if ser.get("points"):
                for x, y in pts:
                    s.circle(x, y, 3.0, ser["color"])
            else:
                s.polyline(pts, ser["color"], 2.0, ser.get("dash"))
        lx = x1
        for ser in reversed(p["series"]):
            label = ser["name"]
            w = 7 * len(label) + 22
            lx -= w
            s.rect(lx, y0 - 14 + (0 if ser.get("points") else 3), 12, 3 if not ser.get("points") else 8,
                   ser["color"], rx=1.5)
            s.text(lx + 16, y0 - 7, label, size=10, color=INK2)
    return s.render()


def tornado(rows: list[dict], base: float, title: str, xlabel: str, labels: dict[str, str],
            width: int = 760) -> str:
    """Horizontal bars from the base value to the outcome at each parameter's low and high input."""
    n = len(rows)
    top, row_h, left = 52, 26, 250
    height = top + n * row_h + 56
    s = Svg(width, height, title)
    s.text(8, 20, title, size=13, color=INK, weight="bold")
    vals = [base] + [r["out_low"] for r in rows] + [r["out_high"] for r in rows]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 0.1
    lo, hi = lo - pad, hi + pad
    x0, x1 = left, width - 24

    def px(v):
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    step = nice_step(hi - lo, 6)
    for t in ticks(lo, hi, 6):
        s.line(px(t), top - 6, px(t), top + n * row_h, GRID, 1.0)
        s.text(px(t), top + n * row_h + 16, fmt_tick(t, step), size=10, color=MUTED, anchor="middle")
    s.text((x0 + x1) / 2, top + n * row_h + 34, xlabel, size=11, color=INK2, anchor="middle")
    for i, r in enumerate(rows):
        y = top + i * row_h
        s.text(left - 8, y + row_h / 2 + 4, labels.get(r["parameter"], r["parameter"]), size=11,
               color=INK2, anchor="end")
        for side, color in (("out_low", SERIES[0]), ("out_high", SERIES[1])):
            v = r[side]
            s.rect(px(min(base, v)), y + 5 + (0 if side == "out_low" else 9), abs(px(v) - px(base)), 8, color,
                   rx=2.0)
    s.line(px(base), top - 10, px(base), top + n * row_h, INK, 1.5)
    s.text(px(base) + 4, top - 12, f"base {base:.3f}", size=10, color=INK, anchor="start")
    s.rect(8, 30, 12, 8, SERIES[0], rx=2.0)
    s.text(24, 38, "parameter at its low value", size=10, color=INK2)
    s.rect(188, 30, 12, 8, SERIES[1], rx=2.0)
    s.text(204, 38, "parameter at its high value", size=10, color=INK2)
    return s.render()


def range_rows(rows: list[dict], title: str, xlabel: str, width: int = 760) -> str:
    """One row per item: a P5-P95 bar, a P25-P75 bar and a P50 tick (``label``, ``p5``...``p95``)."""
    n = len(rows)
    top, row_h, left = 40, 30, 300
    height = top + n * row_h + 50
    s = Svg(width, height, title)
    s.text(8, 20, title, size=13, color=INK, weight="bold")
    vals = [r["p5"] for r in rows] + [r["p95"] for r in rows] + [0.0]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 1.0
    lo, hi = lo - pad, hi + pad
    x0, x1 = left, width - 24

    def px(v):
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    step = nice_step(hi - lo, 6)
    for t in ticks(lo, hi, 6):
        s.line(px(t), top - 4, px(t), top + n * row_h, GRID, 1.0)
        s.text(px(t), top + n * row_h + 16, fmt_tick(t, step), size=10, color=MUTED, anchor="middle")
    s.line(px(0.0), top - 4, px(0.0), top + n * row_h, AXIS, 1.0)
    s.text((x0 + x1) / 2, top + n * row_h + 34, xlabel, size=11, color=INK2, anchor="middle")
    for i, r in enumerate(rows):
        y = top + i * row_h
        s.text(left - 8, y + row_h / 2 + 4, r["label"], size=11, color=INK2, anchor="end")
        s.rect(px(r["p5"]), y + 11, px(r["p95"]) - px(r["p5"]), 8, "#b7d3f6", rx=2.0)
        s.rect(px(r["p25"]), y + 9, px(r["p75"]) - px(r["p25"]), 12, SERIES[0], rx=2.0)
        s.line(px(r["p50"]), y + 6, px(r["p50"]), y + 24, INK, 2.0)
    return s.render()
