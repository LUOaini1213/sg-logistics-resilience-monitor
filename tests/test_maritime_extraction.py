"""Extraction scoring on hand-made sets, and the integrity of the committed corpus files."""
import csv
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr.maritime import extraction as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"


def rows(*links):
    return [{"passage_id": p, "cause": c, "effect": e, "polarity": s} for p, c, e, s in links]


def test_counts_rates_and_errors_by_hand():
    ref = E.link_sets(rows(("p1", "a", "b", "+"), ("p1", "b", "c", "-"), ("p2", "c", "d", "+")))
    pred = E.link_sets(rows(("p1", "a", "b", "+"), ("p1", "a", "b", "-"),     # repeated pair: first wins
                            ("p1", "c", "d", "+"), ("p2", "c", "d", "-"), ("p3", "x", "y", "+")))
    c = E.counts(ref, pred, ["p1", "p2", "p3"])
    assert c == {"tp": 2, "fp": 2, "fn": 1, "polarity_agree": 1}
    r = E.rates(c)
    assert r["precision"] == pytest.approx(0.5) and r["recall"] == pytest.approx(2 / 3)
    assert r["f1"] == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))
    assert r["polarity_agreement"] == pytest.approx(0.5)
    # direction matters: b -> a is not a -> b
    assert E.counts(E.link_sets(rows(("p", "a", "b", "+"))), E.link_sets(rows(("p", "b", "a", "+"))), ["p"])["tp"] == 0
    assert E.rates({"tp": 0, "fp": 0, "fn": 0, "polarity_agree": 0})["f1"] == 0.0


def test_error_listing_and_bootstrap(tmp_path):
    path = tmp_path / "m.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["passage_id", "cause", "effect", "polarity", "quote_verbatim"])
        w.writeheader()
        w.writerows([{**r, "quote_verbatim": "True"} for r in rows(("p1", "a", "b", "-"), ("p1", "q", "r", "+"))])
    ref = rows(("p1", "a", "b", "+"), ("p2", "c", "d", "+"))
    kinds = sorted((e["kind"], e["cause"]) for e in E.errors(path, ref))
    assert kinds == [("false_negative", "c"), ("false_positive", "q"), ("polarity_mismatch", "a")]
    s = E.score_model(path, ref, ["p1", "p2"], ["a", "b", "c", "d"])
    assert s["tp"] == 1 and s["fp"] == 1 and s["fn"] == 1 and s["out_of_codebook"] == 1
    assert s["polarity_agreement"] == 0.0
    other = tmp_path / "n.csv"
    with open(other, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["passage_id", "cause", "effect", "polarity"])
        w.writeheader()
        w.writerows(rows(("p1", "a", "b", "+"), ("p2", "c", "d", "+")))
    rep = E.repeat_agreement(path, other)
    assert (rep["shared"], rep["union"]) == (1, 3) and rep["jaccard"] == pytest.approx(1 / 3)
    b1, b2 = E.bootstrap(E.link_sets(ref), E.link_sets(E.read(path)), ["p1", "p2"]), \
        E.bootstrap(E.link_sets(ref), E.link_sets(E.read(path)), ["p1", "p2"])
    assert b1 == b2 and 0.0 <= b1["precision"][0] <= b1["precision"][1] <= 1.0


def test_reference_set_follows_the_codebook():
    names = set(E.codebook_variables())
    assert len(names) == 17
    passages = {r["passage_id"] for r in E.read(CORPUS / "passages.csv")}
    seen = set()
    for r in E.read(CORPUS / "reference_links.csv"):
        assert r["cause"] in names and r["effect"] in names and r["cause"] != r["effect"]
        assert r["polarity"] in ("+", "-") and r["passage_id"] in passages
        assert 0 < E.quote_words(r["evidence"]) <= 14, r["evidence"]
        key = (r["passage_id"], r["cause"], r["effect"])
        assert key not in seen
        seen.add(key)


def test_corpus_holds_no_passage_text():
    cols = set(E.read(CORPUS / "passages.csv")[0])
    assert cols == {"passage_id", "source_id", "start_anchor", "end_anchor", "n_words", "sha256"}
    for r in E.read(CORPUS / "passages.csv"):
        assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"])
        assert len(r["start_anchor"].split()) <= 14 and len(r["end_anchor"].split()) <= 14
    for path in sorted((CORPUS / "llm_runs").glob("*.csv")) + sorted((CORPUS / "llm_repeat").glob("*.csv")):
        for r in E.read(path):
            assert len(r["quote_stored"].split()) <= 14
    assert not (CORPUS / "cache").exists() or "data/corpus/cache/" in (ROOT / ".gitignore").read_text()


def test_committed_scores_match_a_rescore():
    out = {r["model"]: r for r in E.read(ROOT / "outputs" / "maritime" / "extraction_scores.csv")}
    res = E.run()
    assert res["models"], "no LLM run committed"
    for slug, m in res["models"].items():
        s = m["score"]
        row = out[s["model"]]
        assert int(row["tp"]) == s["tp"] and int(row["fp"]) == s["fp"] and int(row["fn"]) == s["fn"]
        assert float(row["precision"]) == pytest.approx(s["precision"], abs=6e-4)
        assert float(row["recall"]) == pytest.approx(s["recall"], abs=6e-4)
