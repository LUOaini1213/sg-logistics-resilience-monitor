"""Compute the sea distances of the representative Asia-North Europe loop with ``searoute``.

Not part of the offline build: the build reads the committed ``data/inputs/voyage_legs.csv``.
``searoute`` bundles its own marine network, so this runs offline too, but it is an extra
dependency (``pip install -r requirements-extra.txt``). Run: ``python scripts/compute_distances.py``.

Routing rules:
* ``suez``: searoute's default restrictions (Northwest Passage closed), which route Asia-Europe
  legs through Malacca, Bab el-Mandeb, Suez and Gibraltar.
* ``cape``: Suez, Bab el-Mandeb and Panama closed as well, which routes the same legs round the
  Cape of Good Hope.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import searoute as sr

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"
LOOP = ["Shanghai", "Ningbo", "Yantian", "Singapore", "Rotterdam", "Hamburg", "Antwerp", "Singapore", "Shanghai"]
RESTRICTIONS = {"suez": ["northwest"], "cape": ["northwest", "suez", "babalmandab", "panama"]}
# Published distances to compare with (see data/inputs/distance_checks.csv for the citations).
CHECKS = [("Shanghai", "Rotterdam"), ("Yantian", "Rotterdam"), ("Singapore", "Rotterdam")]


def ports() -> dict[str, tuple[float, float]]:
    with open(INPUTS / "ports.csv", newline="", encoding="utf-8") as f:
        return {r["port"]: (float(r["lon"]), float(r["lat"])) for r in csv.DictReader(f)}


def leg(p: dict, a: str, b: str, routing: str) -> tuple[float, str]:
    feat = sr.searoute(list(p[a]), list(p[b]), units="naut", restrictions=RESTRICTIONS[routing],
                       return_passages=True)
    passages = feat["properties"].get("traversed_passages") or []
    return round(float(feat["properties"]["length"]), 1), ";".join(sorted(passages))


def main() -> None:
    p = ports()
    version = getattr(sr, "__version__", "unknown")
    rows = []
    for routing in ("suez", "cape"):
        for seq, (a, b) in enumerate(zip(LOOP, LOOP[1:]), start=1):
            nm, passages = leg(p, a, b, routing)
            rows.append({"routing": routing, "seq": seq, "from_port": a, "to_port": b, "distance_nm": nm,
                         "passages": passages, "label": "REAL",
                         "source": f"searoute {version} (Python package, bundled marine network); "
                                   "computed from the port positions in ports.csv (ASSUMPTION)",
                         "url": f"https://pypi.org/project/searoute/{version}/",
                         "accessed": dt.date.today().isoformat()})
    with open(INPUTS / "voyage_legs.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    checks = []
    for a, b in CHECKS:
        s, _ = leg(p, a, b, "suez")
        c, _ = leg(p, a, b, "cape")
        checks.append({"from_port": a, "to_port": b, "suez_nm": s, "cape_nm": c, "extra_nm": round(c - s, 1),
                       "label": "REAL", "source": f"searoute {version}; port positions in ports.csv (ASSUMPTION)",
                       "url": f"https://pypi.org/project/searoute/{version}/", "accessed": dt.date.today().isoformat()})
    with open(INPUTS / "distance_checks_searoute.csv", "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(checks)
    for r in checks:
        print(r)


if __name__ == "__main__":
    main()
