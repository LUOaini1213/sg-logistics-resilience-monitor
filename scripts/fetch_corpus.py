"""Download the public texts of the extraction corpus and cut out the passages (network; not in CI).

Run: ``python scripts/fetch_corpus.py`` (needs ``pip install -r requirements-extra.txt`` for PDFs).

The texts are saved under ``data/corpus/cache/`` (git-ignored). Only metadata is committed:
``data/corpus/sources.csv`` (where each text comes from and its terms) and ``data/corpus/passages.csv``
(two short anchor phrases that locate each passage, its word count and a SHA-256 of its normalised
text). The MPA and MOT terms of use do not allow republishing their pages, so the repository holds
no passage text; re-running this script re-creates the passages and checks the hashes.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
CACHE = CORPUS / "cache"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36", "Accept": "*/*"}

# passage id, source id, start anchor, end anchor (the passage runs from the start anchor to the first
# end anchor after it, inclusive, in whitespace-normalised text)
PASSAGES = [
    ("u2-01", "unctad_rmt2024_ch2", "However, increased geopolitical instability", "low water levels."),
    ("u2-02", "unctad_rmt2024_ch2", "Rerouting vessels around Africa adds distance", "has overwhelmed many ports."),
    ("u2-03", "unctad_rmt2024_ch2", "Off-schedule arrivals, for example,", "freight rates and shipping expenses"),
    ("u2-04", "unctad_rmt2024_ch2", "Rerouting has increased ship sailing speeds", "compared to 2023"),
    ("u2-05", "unctad_rmt2024_ch2", "In 2023, the global fleet and container ship capacity grew faster",
     "overcapacity issues are likely to return."),
    ("u3-01", "unctad_rmt2024_ch3", "At the end of 2023 and into 2024, disruptions", "including record highs."),
    ("u3-02", "unctad_rmt2024_ch3", "Since December 2023, disruptions in the Red Sea", "to meet delivery schedules.",
     "first"),
    ("u3-03", "unctad_rmt2024_ch3", "Disruptions in the Red Sea and the Suez Canal exacerbated",
     "contributed to the increase in freight rates."),
    ("u3-04", "unctad_rmt2024_ch3", "Charter rates initially responded slowly", "cascading effects of the disruption."),
    ("u3-05", "unctad_rmt2024_ch3", "The disruptions to the Suez Canal, the Red Sea and the Panama Canal significantly",
     "SIDS and LDCs."),
    ("m1-01", "mpa_2024_05_30", "The diversion of vessels around the Cape", "increase in vessel arrivals."),
    ("m1-02", "mpa_2024_05_30", "Container volumes handled in Singapore in the first four months",
     "about two to three days."),
    ("m1-03", "mpa_2024_05_30", "The increased demand on container handling", "subsequent port calls."),
    ("m1-04", "mpa_2024_05_30", "have been working with PSA and the industry since late 2023", "820,000 TEUs currently."),
    ("m2-01", "mpa_2024_09_04", "The total number of containers handled by the Port of Singapore",
     "scheduling for operations."),
    ("t1-01", "mot_2024_07_02", "The Red Sea crisis has led to vessels being diverted", "effect."),
    ("t1-02", "mot_2024_07_02", "To allow vessels to return to Europe more quickly", "congestion at our container berths."),
    ("t1-03", "mot_2024_07_02", "are working closely together with our tripartite partners", "anticipated demand."),
    ("t1-04", "mot_2024_07_02", "While our efforts have improved average waiting times", "second half of the year."),
]


def sources() -> dict[str, dict]:
    with open(CORPUS / "sources.csv", newline="", encoding="utf-8") as f:
        return {r["source_id"]: r for r in csv.DictReader(f)}


def download(url: str, path: Path) -> None:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                path.write_bytes(r.read())
            return
        except Exception:  # pragma: no cover - network
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def normalise(text: str) -> str:
    text = text.replace("­", "")
    return re.sub(r"\s+", " ", text).strip()


def html_text(raw: str) -> str:
    raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)
    raw = raw.replace('\\"', '"').replace("\\n", "\n")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return normalise(html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw)))


def pdf_text(path: Path) -> str:
    import pymupdf  # requirements-extra.txt
    with pymupdf.open(path) as doc:
        return normalise(" ".join(page.get_text() for page in doc))


def passage(text: str, start: str, end: str, occurrence: int = 1) -> str:
    """Text from the ``occurrence``-th start anchor to the first end anchor after it. Anchors must
    occur exactly once unless an occurrence is given (a pull quote can repeat a sentence)."""
    i, n = -1, 0
    for _ in range(occurrence):
        i = text.find(start, i + 1)
        if i < 0:
            raise ValueError(f"start anchor not found {occurrence} time(s): {start!r}")
    n = text.count(start)
    if occurrence == 1 and n != 1:
        raise ValueError(f"start anchor found {n} times; give the occurrence: {start!r}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise ValueError(f"end anchor not found after the start: {end!r}")
    return text[i:j + len(end)]


def first_occurrence(text: str, start: str, end: str) -> str:
    """For an anchor that a pull quote repeats: the body text comes first."""
    i = text.find(start)
    j = text.find(end, i + len(start))
    if i < 0 or j < 0:
        raise ValueError(f"anchors not found: {start!r} / {end!r}")
    return text[i:j + len(end)]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(write: bool = False) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    src = sources()
    texts = {}
    for sid, s in src.items():
        path = CACHE / f"{sid}.{s['format']}"
        if not path.exists():
            download(s["url"], path)
        texts[sid] = pdf_text(path) if s["format"] == "pdf" else html_text(path.read_text(encoding="utf-8",
                                                                                           errors="replace"))
    rows, out = [], []
    for pid, sid, start, end, *occ in PASSAGES:
        text = passage(texts[sid], start, end, 1) if not occ else first_occurrence(texts[sid], start, end)
        rows.append({"passage_id": pid, "source_id": sid, "start_anchor": start, "end_anchor": end,
                     "n_words": len(text.split()), "sha256": sha256(text)})
        out.append({"passage_id": pid, "text": text})
    with open(CACHE / "passages.jsonl", "w", newline="\n", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    committed = CORPUS / "passages.csv"
    if write or not committed.exists():
        with open(committed, "w", newline="\n", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {committed}")
    else:
        with open(committed, newline="", encoding="utf-8") as f:
            old = {r["passage_id"]: r["sha256"] for r in csv.DictReader(f)}
        changed = [r["passage_id"] for r in rows if old.get(r["passage_id"]) != r["sha256"]]
        print("hash check:", "all passages match" if not changed else f"CHANGED: {changed}")
    print(f"{len(rows)} passages, {sum(r['n_words'] for r in rows)} words; texts in {CACHE}")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
