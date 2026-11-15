"""Causal loop diagram: Red Sea diversion -> capacity -> reliability -> Singapore -> freight market.

Every link carries a polarity and an evidence status:

* ``estimated``: quantified by the stock-and-flow calibration (``calibrate.py``);
* ``model``: follows from the equations of the voyage-economics model (``voyage.py``);
* ``cited``: a published source reports the effect; its size is not estimated here;
* ``assumed``: a hypothesis from the general literature, not verified or estimated here.

Feedback loops are found by enumerating the simple cycles of the link graph; a loop is reinforcing
(R) when the product of its polarities is positive and balancing (B) otherwise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import svg


@dataclass(frozen=True)
class Node:
    key: str
    label: str
    x: float
    y: float
    group: str          # "route", "network", "singapore", "market", "exogenous"


@dataclass(frozen=True)
class Link:
    src: str
    dst: str
    sign: int           # +1 same direction, -1 opposite
    status: str         # estimated | model | cited | assumed
    evidence: str
    bend: float = 0.12  # curvature as a share of the link length (drawing only)
    delay: bool = False


NODES = [
    Node("risk", "Red Sea security risk", 92, 70, "exogenous"),
    Node("warrisk", "War-risk premium", 92, 220, "exogenous"),
    Node("diversion", "Cape diversion share", 285, 140, "route"),
    Node("distance", "Voyage distance and time", 470, 70, "route"),
    Node("absorbed", "Capacity absorbed by|longer routes", 660, 70, "network"),
    Node("capacity", "Effective fleet capacity", 660, 250, "network"),
    Node("reliability", "Schedule reliability", 470, 330, "network"),
    Node("frontload", "Shippers' early|ordering", 92, 380, "network"),
    Node("bunching", "Bunching and berth waits|in Singapore", 300, 470, "singapore"),
    Node("port", "Port capacity response|(berths, yard)", 92, 560, "singapore"),
    Node("teu_call", "TEU per call|(Singapore)", 300, 610, "singapore"),
    Node("calls", "Container-ship calls|(Singapore)", 520, 600, "singapore"),
    Node("costs", "Carrier operating costs", 1075, 70, "market"),
    Node("blank", "Blank sailings", 880, 150, "market"),
    Node("rates", "Freight rates", 880, 330, "market"),
    Node("bunker", "Bunker price", 1075, 330, "exogenous"),
    Node("speed", "Vessel speed", 880, 510, "market"),
    Node("newbuild", "Newbuild deliveries", 660, 430, "market"),
]

UNCTAD = "UNCTAD, Review of Maritime Transport 2024, Chapter II"
UNCTAD3 = "UNCTAD, Review of Maritime Transport 2024, Chapter III"
LINKS = [
    Link("risk", "diversion", +1, "estimated",
         "Routing block: diverted share and onset fitted to PortWatch transits (outputs/maritime/sd_parameters.csv)"),
    Link("risk", "warrisk", +1, "cited",
         "Reuters via Insurance Journal, 30 Jul 2026: southern Red Sea premiums rose to 1-2% from 0.3%", -0.1),
    Link("warrisk", "diversion", +1, "model",
         "Voyage model: above the break-even premium the Cape loop is cheaper (outputs/maritime/summary.json)", -0.15),
    Link("diversion", "distance", +1, "cited",
         "searoute distances (data/inputs/voyage_legs.csv); Notteboom et al. (2024): +4,575 nm Shanghai-Rotterdam"),
    Link("distance", "absorbed", +1, "cited",
         f"{UNCTAD}, citing Clarksons: Cape diversions raise container-ship demand by 12% (June 2024)"),
    Link("absorbed", "capacity", -1, "cited",
         "Notteboom et al. (2024): at least two ships must be added to a weekly Asia-North Europe loop"),
    Link("capacity", "reliability", +1, "estimated",
         "Reliability block: beta (share of late arrivals per unit of absorbed capacity), reduced form"),
    Link("reliability", "bunching", -1, "estimated",
         "Singapore block: bunching builds over tau_q days; MPA statement of 30 May 2024 (data/events.csv)"),
    Link("bunching", "port", +1, "estimated",
         "Singapore block: adaptation stock K; MPA (4 Sep 2024) reports waits under a day after more berths and yard"),
    Link("port", "bunching", -1, "estimated",
         "Singapore block: adaptation removes the bunching pressure (adapt = 1 assumed)", 0.25),
    Link("bunching", "teu_call", +1, "estimated", "Singapore block: theta_t, MPA TEU per PortWatch call"),
    Link("bunching", "calls", -1, "estimated", "Singapore block: theta_c, PortWatch Singapore container-ship calls"),
    Link("bunching", "capacity", -1, "cited",
         f"{UNCTAD3}, citing Linerlytica: by mid-June 2024 congestion held 2.5 million TEU (8.4% of the fleet) "
         "at anchorages; not estimated here", 0.18),
    Link("reliability", "frontload", -1, "assumed", "Shippers order earlier when transit times are unreliable; not verified"),
    Link("frontload", "capacity", -1, "assumed", "Early orders add demand on the same ships; not verified", -0.22),
    Link("capacity", "rates", -1, "cited",
         f"{UNCTAD3}: diversions reduced 'the availability of shipping capacity' and rates rose; no freight-rate "
         "series in the repository, so not estimated"),
    Link("rates", "blank", -1, "assumed", "Carriers cancel sailings when rates fall; not verified here", 0.2),
    Link("blank", "capacity", -1, "assumed", "Cancelled sailings remove capacity; not verified here", 0.1),
    Link("rates", "speed", +1, "assumed",
         "Higher rates make the extra fuel of sailing faster worth paying; not verified", -0.2),
    Link("speed", "capacity", +1, "model",
         f"Round-voyage time = distance / speed (voyage model); {UNCTAD}: ships of 17,000 TEU and more sailed 5% "
         "faster in Q1 2024", -0.1),
    Link("rates", "newbuild", +1, "assumed",
         "High earnings encourage orders; deliveries follow after years; not verified", 0.15),
    Link("newbuild", "capacity", +1, "cited", f"{UNCTAD}: container-ship capacity grew by nearly 8% in 2023", 0.15,
         delay=True),
    Link("distance", "costs", +1, "model",
         "Voyage model: the Cape loop burns more fuel and needs more ship-days", -0.12),
    Link("speed", "costs", +1, "model", "Voyage model: main-engine fuel per day rises with speed^3", 0.18),
    Link("bunker", "costs", +1, "model", "Voyage model: fuel cost = fuel burnt x bunker price"),
    Link("bunker", "speed", -1, "assumed", "Dearer fuel favours slower steaming; not verified here", 0.1),
    Link("costs", "rates", +1, "cited", f"{UNCTAD}: additional costs 'translate into higher freight rates'", -0.1),
]

LOOP_NAMES = {
    ("bunching", "port"): ("B1", "Port response"),
    ("blank", "capacity", "rates"): ("B2", "Blank sailings"),
    ("capacity", "rates", "speed"): ("B3", "Speed-up"),
    ("capacity", "newbuild", "rates"): ("B4", "Fleet supply"),
    ("bunching", "capacity", "reliability"): ("R1", "Congestion spiral"),
    ("capacity", "frontload", "reliability"): ("R2", "Early ordering"),
    ("costs", "rates", "speed"): ("R3", "Cost pass-through"),
}
LOOP_LABEL_POS = {"B1": (190, 505), "B2": (812, 240), "B3": (822, 405), "B4": (748, 352), "R1": (452, 425),
                  "R2": (262, 295), "R3": (985, 220)}
STATUS_STYLE = {"estimated": ("#0b0b0b", 2.2, None), "model": ("#52514e", 1.5, "7 4"),
                "cited": ("#52514e", 1.5, None), "assumed": ("#898781", 1.5, "2 4")}
GROUP_FILL = {"exogenous": "#f0efec", "route": "#cde2fb", "network": "#e8e6f9", "singapore": "#d6f1e6",
              "market": "#fbe3d6"}


def graph(links: list[Link] | None = None) -> dict[str, list[Link]]:
    links = LINKS if links is None else links
    out: dict[str, list[Link]] = {}
    for link in links:
        out.setdefault(link.src, []).append(link)
        out.setdefault(link.dst, [])
    return out


def cycles(links: list[Link] | None = None) -> list[list[Link]]:
    """All simple cycles, each reported once, starting from its alphabetically smallest node."""
    g = graph(links)
    keys = sorted(g)
    found = []
    for start in keys:
        allowed = {k for k in keys if k >= start}
        stack = [(start, [])]
        while stack:
            node, path = stack.pop()
            for link in sorted(g[node], key=lambda lk: lk.dst, reverse=True):
                if link.dst == start:
                    found.append(path + [link])
                elif link.dst in allowed and link.dst not in {lk.src for lk in path} and link.dst != node:
                    stack.append((link.dst, path + [link]))
    return found


def loop_polarity(loop: list[Link]) -> str:
    sign = 1
    for link in loop:
        sign *= link.sign
    return "R" if sign > 0 else "B"


def loops_table() -> list[dict]:
    rows = []
    for loop in cycles():
        nodes = tuple(sorted({lk.src for lk in loop}))
        name = LOOP_NAMES.get(nodes, ("", ""))
        statuses = sorted({lk.status for lk in loop})
        rows.append({"loop": name[0], "name": name[1], "polarity": loop_polarity(loop),
                     "path": " -> ".join([loop[0].src] + [lk.dst for lk in loop]), "length": len(loop),
                     "statuses": ";".join(statuses),
                     "all_links_estimated": all(lk.status == "estimated" for lk in loop)})
    return sorted(rows, key=lambda r: (r["loop"] == "", r["loop"], r["length"], r["path"]))


# ------------------------------------------------------------------ drawing
RX, RY = 82.0, 23.0


def _edge_point(cx, cy, ux, uy):
    norm = math.sqrt(ux * ux + uy * uy)
    ux, uy = ux / norm, uy / norm
    t = 1.0 / math.sqrt((ux / RX) ** 2 + (uy / RY) ** 2)
    return cx + t * ux, cy + t * uy


def render() -> str:
    nodes = {n.key: n for n in NODES}
    s = svg.Svg(1160, 700, "Causal loop diagram: Red Sea diversion, Singapore and the freight market")
    s.add('<defs>' + "".join(
        f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
        for k, (c, _, _) in STATUS_STYLE.items()) + '</defs>')
    for link in LINKS:
        a, b = nodes[link.src], nodes[link.dst]
        mx, my = (a.x + b.x) / 2.0, (a.y + b.y) / 2.0
        dx, dy = b.x - a.x, b.y - a.y
        cx, cy = mx - dy * link.bend, my + dx * link.bend
        x0, y0 = _edge_point(a.x, a.y, cx - a.x, cy - a.y)
        x1, y1 = _edge_point(b.x, b.y, cx - b.x, cy - b.y)
        color, width, dash = STATUS_STYLE[link.status]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        s.add(f'<path d="M{svg.f(x0)},{svg.f(y0)} Q{svg.f(cx)},{svg.f(cy)} {svg.f(x1)},{svg.f(y1)}" fill="none" '
              f'stroke="{color}" stroke-width="{width}"{d} marker-end="url(#arrow-{link.status})"/>')
        t = 0.82
        px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
        py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
        tx, ty = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx), 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
        norm = math.sqrt(tx * tx + ty * ty)
        lx, ly = px - ty / norm * 11.0, py + tx / norm * 11.0
        s.text(lx, ly + 4, "+" if link.sign > 0 else "−", size=13, color=svg.INK, anchor="middle",
               weight="bold")
        if link.delay:
            qx, qy = 0.25 * x0 + 0.5 * cx + 0.25 * x1, 0.25 * y0 + 0.5 * cy + 0.25 * y1
            ox, oy = -ty / norm * 7.0, tx / norm * 7.0
            for off in (-3.0, 3.0):
                bx, by = qx + tx / norm * off, qy + ty / norm * off
                s.line(bx - ox, by - oy, bx + ox, by + oy, svg.INK, 1.5)
    for n in NODES:
        s.add(f'<rect x="{svg.f(n.x - RX)}" y="{svg.f(n.y - RY)}" width="{svg.f(2 * RX)}" height="{svg.f(2 * RY)}" '
              f'rx="12" fill="{GROUP_FILL[n.group]}" stroke="#c3c2b7" stroke-width="1"/>')
        lines = n.label.split("|")
        for i, line in enumerate(lines):
            s.text(n.x, n.y + 4 + (i - (len(lines) - 1) / 2.0) * 13.0, line, size=11, color=svg.INK, anchor="middle")
    for row in loops_table():
        if row["loop"]:
            x, y = LOOP_LABEL_POS[row["loop"]]
            s.add(f'<circle cx="{svg.f(x)}" cy="{svg.f(y)}" r="15" fill="#ffffff" stroke="#0b0b0b" stroke-width="1.2"/>')
            s.text(x, y + 4, row["loop"], size=11, color=svg.INK, anchor="middle", weight="bold")
            s.text(x, y + 27, row["name"], size=9, color=svg.INK2, anchor="middle")
    ly = 664
    s.text(560, ly - 22, "Link evidence", size=10, color=svg.INK, weight="bold")
    xs = 560
    for k, (color, width, dash) in STATUS_STYLE.items():
        label = {"estimated": "estimated (SD fit)", "model": "voyage-cost model",
                 "cited": "cited, not estimated", "assumed": "assumed"}[k]
        s.line(xs, ly - 4, xs + 28, ly - 4, color, width, dash)
        s.text(xs + 33, ly, label, size=10, color=svg.INK2)
        xs += 42 + 6 * len(label) - 4
    s.text(560, ly + 18, "+ same direction, − opposite; || delay; R reinforcing, B balancing loop",
           size=10, color=svg.INK2)
    return s.render()
