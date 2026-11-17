"""Score LLM-extracted cause-effect links against the codebook reference set (offline).

Inputs (all committed): ``data/corpus/codebook.md`` (variables), ``data/corpus/reference_links.csv``
(the reference labels, made with the codebook by the author's tooling, one labeller) and
``data/corpus/llm_runs/<model>.csv`` (written by ``scripts/run_llm_extraction.py``). The passages
themselves are not committed; quote checks were done when the model ran.

A prediction is a true positive when the same directed (cause, effect) pair appears in the reference
set for the same passage. Polarity agreement is measured over the true positives. Confidence
intervals come from a seeded bootstrap over passages.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import numpy as np

from .inputs import ROOT

CORPUS = ROOT / "data" / "corpus"
RUNS = CORPUS / "llm_runs"
REPEAT = CORPUS / "llm_repeat"      # an earlier run of the same model and settings, kept to measure repeatability


def codebook_variables(path: Path = CORPUS / "codebook.md") -> list[str]:
    return re.findall(r"^\| `([a-z_]+)` \|", path.read_text(encoding="utf-8"), flags=re.M)


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def link_sets(rows: list[dict]) -> dict[str, dict[tuple[str, str], str]]:
    """passage -> {(cause, effect): polarity}; the first polarity wins for a repeated pair."""
    out: dict[str, dict[tuple[str, str], str]] = {}
    for r in rows:
        out.setdefault(r["passage_id"], {}).setdefault((r["cause"], r["effect"]), r["polarity"])
    return out


def counts(ref: dict, pred: dict, passages: list[str]) -> dict:
    tp = fp = fn = pol = 0
    for p in passages:
        r, q = ref.get(p, {}), pred.get(p, {})
        hit = set(r) & set(q)
        tp += len(hit)
        fp += len(set(q) - set(r))
        fn += len(set(r) - set(q))
        pol += sum(r[k] == q[k] for k in hit)
    return {"tp": tp, "fp": fp, "fn": fn, "polarity_agree": pol}


def rates(c: dict) -> dict:
    pr = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    rc = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    pa = c["polarity_agree"] / c["tp"] if c["tp"] else 0.0
    return {"precision": pr, "recall": rc, "f1": f1, "polarity_agreement": pa}


def bootstrap(ref: dict, pred: dict, passages: list[str], draws: int = 2000, seed: int = 20261115) -> dict:
    """Percentile intervals (2.5, 97.5) for precision, recall and F1, resampling whole passages."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(passages), size=(draws, len(passages)))
    out = {"precision": [], "recall": [], "f1": []}
    for row in idx:
        r = rates(counts(ref, pred, [passages[i] for i in row]))
        for k in out:
            out[k].append(r[k])
    return {k: [float(v) for v in np.percentile(np.array(vals), [2.5, 97.5])] for k, vals in out.items()}


def score_model(path: Path, ref_rows: list[dict], passages: list[str], names: list[str]) -> dict:
    rows = read(path)
    in_book = [r for r in rows if r["cause"] in names and r["effect"] in names]
    ref = link_sets(ref_rows)
    pred = link_sets(rows)                      # out-of-codebook links stay in and count as false positives
    c = counts(ref, pred, passages)
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    verbatim = sum(r["quote_verbatim"] == "True" for r in rows)
    attempts: dict[str, int] = {}
    for e in meta.get("errors", []):
        attempts[e["passage_id"]] = attempts.get(e["passage_id"], 0) + 1
    failed = sorted(pid for pid, k in attempts.items() if k >= 2)      # both attempts gave unusable output
    return {"model": meta.get("model", path.stem), "digest": (meta.get("digest") or "")[:12],
            "passages": len(passages), "reference_links": sum(len(v) for v in ref.values()),
            "predicted_links": sum(len(v) for v in pred.values()), **c, **rates(c),
            "ci95": bootstrap(ref, pred, passages),
            "out_of_codebook": len(rows) - len(in_book), "failed_passages": len(failed),
            "quote_verbatim_share": verbatim / len(rows) if rows else 0.0,
            "median_seconds_per_passage": (float(np.median(meta["seconds_per_passage"]))
                                           if meta.get("seconds_per_passage") else None)}


def errors(path: Path, ref_rows: list[dict]) -> list[dict]:
    ref, pred = link_sets(ref_rows), link_sets(read(path))
    out = []
    for p in sorted(set(ref) | set(pred)):
        r, q = ref.get(p, {}), pred.get(p, {})
        for k in sorted(set(q) - set(r)):
            out.append({"passage_id": p, "kind": "false_positive", "cause": k[0], "effect": k[1], "polarity": q[k]})
        for k in sorted(set(r) - set(q)):
            out.append({"passage_id": p, "kind": "false_negative", "cause": k[0], "effect": k[1], "polarity": r[k]})
        for k in sorted(set(r) & set(q)):
            if r[k] != q[k]:
                out.append({"passage_id": p, "kind": "polarity_mismatch", "cause": k[0], "effect": k[1],
                            "polarity": q[k]})
    return out


def repeat_agreement(a: Path, b: Path) -> dict:
    """Directed (passage, cause, effect) links shared by two runs of one model, over their union."""
    x = {(r["passage_id"], r["cause"], r["effect"]) for r in read(a)}
    y = {(r["passage_id"], r["cause"], r["effect"]) for r in read(b)}
    return {"links_a": len(x), "links_b": len(y), "shared": len(x & y), "union": len(x | y),
            "jaccard": len(x & y) / len(x | y) if x | y else 1.0}


def run() -> dict:
    names = codebook_variables()
    ref_rows = read(CORPUS / "reference_links.csv")
    passages = [r["passage_id"] for r in read(CORPUS / "passages.csv")]
    models = {}
    for path in sorted(RUNS.glob("*.csv")):
        models[path.stem] = {"score": score_model(path, ref_rows, passages, names),
                             "errors": errors(path, ref_rows)}
    repeats = {path.stem: repeat_agreement(path, RUNS / path.name)
               for path in sorted(REPEAT.glob("*.csv")) if (RUNS / path.name).exists()}
    return {"variables": names, "passages": passages, "reference": ref_rows, "models": models, "repeats": repeats}


def quote_words(text: str) -> int:
    return len([w for w in text.split() if w not in ("...", "…")])


def mean(xs) -> float:
    xs = list(xs)
    return math.fsum(xs) / len(xs) if xs else 0.0
