"""Read the provenance-labelled input tables in ``data/inputs`` and write text outputs portably.

Every hand-entered input carries one of four labels:

* ``REAL``: taken from a public source; the row gives the URL and the access date.
* ``ASSUMPTION``: chosen by the author, with the reasoning in ``note`` (and a source if one
  informed the choice).
* ``ILLUSTRATIVE``: a placeholder that shows how a mechanism works; not evidence.
* ``SYNTHETIC``: generated data (for example test fixtures or Monte Carlo noise).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT / "data" / "inputs"
LABELS = ("REAL", "ASSUMPTION", "ILLUSTRATIVE", "SYNTHETIC")


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(s: str) -> float | None:
    s = (s or "").strip()
    return None if s == "" else float(s)


def load_parameters(path: Path) -> dict[str, dict]:
    """``name -> {value, low, high, unit, label, source, url, accessed, note}`` (numbers as floats)."""
    out = {}
    for r in read_csv(path):
        out[r["name"]] = {**r, "value": float(r["value"]), "low": _num(r.get("low", "")),
                          "high": _num(r.get("high", ""))}
    return out


def provenance_problems(rows: list[dict], where: str) -> list[str]:
    """Rows without a valid label, or REAL rows without a URL and an access date."""
    bad = []
    for i, r in enumerate(rows, start=1):
        label = r.get("label", "")
        if label not in LABELS:
            bad.append(f"{where} row {i}: label {label!r} is not one of {LABELS}")
        elif label == "REAL" and not (r.get("url", "").startswith("http") and len(r.get("accessed", "")) == 10):
            bad.append(f"{where} row {i}: REAL without url and access date")
    return bad


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0]) if rows else [])
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=1, sort_keys=False, allow_nan=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)
