"""Causal loop diagram: link bookkeeping, loop detection and polarity, and the drawing."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr.maritime import cld  # noqa: E402

L = cld.Link


def test_cycle_enumeration_on_a_small_graph():
    links = [L("a", "b", +1, "assumed", "x"), L("b", "a", -1, "assumed", "x"), L("b", "c", +1, "assumed", "x"),
             L("c", "a", +1, "assumed", "x"), L("c", "c2", -1, "assumed", "x"), L("c2", "b", -1, "assumed", "x")]
    found = sorted(" ".join([c[0].src] + [lk.dst for lk in c]) for c in cld.cycles(links))
    assert found == ["a b a", "a b c a", "b c c2 b"]
    pol = {" ".join([c[0].src] + [lk.dst for lk in c]): cld.loop_polarity(c) for c in cld.cycles(links)}
    assert pol == {"a b a": "B", "a b c a": "R", "b c c2 b": "R"}


def test_named_loops_and_their_polarity():
    loops = {r["loop"]: r for r in cld.loops_table() if r["loop"]}
    assert {k: v["polarity"] for k, v in loops.items()} == {
        "B1": "B", "B2": "B", "B3": "B", "B4": "B", "R1": "R", "R2": "R", "R3": "R"}
    assert loops["B1"]["all_links_estimated"]                     # the port-response loop is fitted
    assert loops["R1"]["statuses"] == "cited;estimated"          # the congestion spiral is only partly fitted
    assert "assumed" in loops["R2"]["statuses"] and "assumed" in loops["B2"]["statuses"]
    for name in ("B2", "B3", "B4", "R2", "R3"):
        assert not loops[name]["all_links_estimated"]


def test_links_are_complete_and_unique():
    keys = {n.key for n in cld.NODES}
    pairs = [(lk.src, lk.dst) for lk in cld.LINKS]
    assert len(pairs) == len(set(pairs))
    for lk in cld.LINKS:
        assert lk.src in keys and lk.dst in keys and lk.src != lk.dst
        assert lk.sign in (1, -1) and lk.status in cld.STATUS_STYLE and len(lk.evidence) > 20
        if lk.status == "assumed":
            assert "not" in lk.evidence                            # says it is not verified/estimated
    est = {(lk.src, lk.dst) for lk in cld.LINKS if lk.status == "estimated"}
    assert ("risk", "diversion") in est and ("capacity", "reliability") in est
    assert ("capacity", "rates") not in est                       # no freight-rate data in the repository
    assert sum(lk.delay for lk in cld.LINKS) == 1


def test_drawing_is_valid_svg_with_every_node():
    text = cld.render()
    root = ET.fromstring(text)
    assert root.tag.endswith("svg")
    for n in cld.NODES:
        for part in n.label.split("|"):
            assert part.replace("'", "&#x27;") in text or part in text
    assert text.count("marker-end=") == len(cld.LINKS)
