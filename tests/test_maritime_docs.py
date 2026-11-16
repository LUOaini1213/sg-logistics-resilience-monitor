"""Provenance labels, and the numbers in the README, the working paper and the workshop pack against
the results files."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lsr.maritime import paper  # noqa: E402
from lsr.maritime.inputs import LABELS, provenance_problems, read_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "maritime"


def summary() -> dict:
    return json.loads((OUT / "summary.json").read_text(encoding="utf-8"))


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_every_hand_entered_input_is_labelled():
    files = sorted((ROOT / "data" / "inputs").glob("*.csv")) + [ROOT / "data" / "corpus" / "sources.csv"]
    assert len(files) >= 9
    for path in files:
        rows = read_csv(path)
        assert rows and "label" in rows[0], path.name
        assert provenance_problems(rows, path.name) == []
    counts = {r["file"]: r for r in read_csv(OUT / "provenance_summary.csv")}
    assert len(counts) == len(files)
    for r in counts.values():
        assert int(r["rows"]) == sum(int(r[lab]) for lab in LABELS)


def test_paper_markdown_is_rendered_from_the_results():
    main = json.loads((ROOT / "outputs" / "summary.json").read_text(encoding="utf-8"))
    template = (ROOT / "paper" / "working_paper.template.md").read_text(encoding="utf-8")
    want = paper.render(template, summary(), main)
    assert (ROOT / "paper" / "working_paper.md").read_text(encoding="utf-8") == want


def test_pdf_was_built_from_the_committed_markdown():
    side = (ROOT / "paper" / "working_paper.pdf.source-sha256").read_text(encoding="utf-8").split()[0]
    assert side == lf_sha256(ROOT / "paper" / "working_paper.md")
    assert (ROOT / "paper" / "working_paper.pdf").read_bytes()[:5] == b"%PDF-"


def test_llm_runs_used_the_committed_codebook_and_passages():
    book = lf_sha256(ROOT / "data" / "corpus" / "codebook.md")
    runs = sorted((ROOT / "data" / "corpus" / "llm_runs").glob("*.json"))
    assert runs
    for path in runs:
        meta = json.loads(path.read_text(encoding="utf-8"))
        assert meta["codebook_sha256"] == book, path.name
        assert meta["passages"] == len(read_csv(ROOT / "data" / "corpus" / "passages.csv"))
        assert meta["options"]["temperature"] == 0
        # a failed passage (both attempts unusable) must be visible in the scores, never silently dropped
        failed = {e["passage_id"] for e in meta["errors"] if e["attempt"] == 1}
        scores = {r["model"]: r for r in read_csv(OUT / "extraction_scores.csv")}
        assert int(scores[meta["model"]]["failed_passages"]) == len(failed), path.name


def test_workshop_pack_numbers_match_the_results():
    s = summary()
    guide = (ROOT / "workshop" / "interview_guide.md").read_text(encoding="utf-8")
    words = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
    c = s["cld"]["links_by_status"]
    assert f"The diagram has {s['cld']['links']} links" in guide
    assert (f"{words[c['estimated']].capitalize()} are estimated from public data, {words[c['model']]} follow from "
            f"the voyage-cost\nmodel, {words[c['cited']]} are reported") in guide
    assert f"and {words[c['assumed']]} are assumed" in guide
    assert f"break-even near {s['voyage']['breakeven_war_risk_pct']:.1f}%" in guide
    assert f"about {s['sd']['params']['tau_q']:.0f} days" in guide
    agenda = (ROOT / "workshop" / "workshop_agenda.md").read_text(encoding="utf-8")
    assert f"Turn the {words[c['assumed']]} links marked *assumed*" in agenda


def _date(iso: str, year: bool = True) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')}" + (f" {d.year}" if year else "")


def test_readme_maritime_numbers_match_the_results():
    s = summary()
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())

    def has(text):
        assert " ".join(text.split()) in readme, f"README does not contain {text!r}"

    c, sd, v, sc = s["cld"], s["sd"], s["voyage"], s["scenarios"]
    st = c["links_by_status"]
    has(f"{c['links']} signed links between {c['nodes']} variables")
    has(f"{st['estimated']} estimated by the stock-and-flow fit, {st['model']} implied by the voyage-cost model, "
        f"{st['cited']} cited from published sources but not estimated here, and {st['assumed']} assumed")
    r2 = sd["r2"]
    has(f"Bab el-Mandeb {r2['bab']:.2f}, Cape {r2['cape']:.2f}, schedule reliability {r2['glp']:.2f}, "
        f"Singapore calls {r2['calls']:.2f}, TEU per call {r2['tpc']:.2f}")
    has(f"The profiled onset is {_date(sd['onset'])} (95% range {_date(sd['onset_ci95'][0], False)} to "
        f"{_date(sd['onset_ci95'][1], False)})")
    has(f"{sd['params']['d_max']:.0%} of the pre-crisis Bab el-Mandeb container traffic diverted")
    has(f"reached the Cape about {sd['params']['tau_c']:.0f} days later")
    has(f"rejects more than {sd['tau_a_profile_max_days']:.0f} days")
    has(f"time constant of {sd['params']['tau_q']:.0f} days (95% interval {sd['ci95']['tau_q'][0]:.0f} to "
        f"{sd['ci95']['tau_q'][1]:.0f})")
    has(f"reaches a {sd['peak_calls_drop_pct']}% fall in calls where the data show {sd['obs_calls_drop_pct']}%")
    has(f"the Cape round voyage takes {v['cape_days']:.2f} days against {v['suez_days']:.2f} via Suez, needs "
        f"{v['extra_ships_weekly']:.2f} more ships for a weekly service and burns {v['extra_fuel_t']:,} t more fuel")
    has(f"**{v['breakeven_war_risk_pct']:.3f}% of hull value per transit**")
    has(f"Cape is cheaper by {-v['cape_minus_suez_usd_per_teu']:.2f} USD per TEU")
    lad = sc["ladder"]
    has(f"an Alert caused by the incident in {lad['strait']['p_level2_attributable']:.0%} of draws, a median "
        f"{lad['strait']['days_to_level2_p50']:.0f} days after it")
    has(f"waiting ships cost a median {sc['strait_waiting_cost_usd_m'][1]:.0f} million USD")
    g = sc["gulf_cape_cost_change_usd_per_teu"]
    has(f"a median {g[1]:.0f} USD per TEU more on the Cape loop (5-95%: {g[0]:.0f} to {g[2]:.0f})")
    has(f"an Alert caused by it in only {lad['gulf']['p_level2_attributable']:.1%} of draws")
    has(f"Suez is cheaper than the Cape in {sc['reopen_p_suez_cheaper']:.0%} of draws")
    has(f"Noise alone reaches Alert in {lad['control']['p_level2']:.0%} of draws")
    ex = s["extraction"]
    has(f"{ex['passages']} passages from UNCTAD's")
    has(f"{ex['reference_links']} reference links")
    q = ex["models"]["qwen3_5_4b"]
    has(f"`qwen3.5:4b` reached precision {q['precision']:.2f} (95% interval {q['precision_ci95']}) and recall "
        f"{q['recall']:.2f} ({q['recall_ci95']})")
    for slug, name in (("llama3_2_3b", "llama3.2:3b"), ("gemma3_4b", "gemma3:4b")):
        m = ex["models"][slug]
        has(f"`{name}` {m['precision']:.2f} and {m['recall']:.2f}")
    p = s["provenance"]
    has(f"{p['REAL']} REAL and {p['ASSUMPTION']} ASSUMPTION rows across {p['files']} files")
    rep = ex["repeat"]["qwen3_5_4b"]
    has(f"shared {rep['shared']} of {rep['union']} distinct links")


def test_provenance_check_rejects_bad_rows():
    good = {"label": "REAL", "url": "https://example.org/x", "accessed": "2026-11-15"}
    assert provenance_problems([good, {"label": "ASSUMPTION", "url": "", "accessed": ""}], "f") == []
    bad = [{"label": "REAL", "url": "", "accessed": "2026-11-15"},          # no URL
           {"label": "REAL", "url": "https://example.org/x", "accessed": ""},  # no access date
           {"label": "real", "url": "https://example.org/x", "accessed": "2026-11-15"},  # not a label
           {"label": "", "url": "", "accessed": ""}]
    problems = provenance_problems(bad, "f")
    assert len(problems) == 4 and "row 1" in problems[0] and "row 4" in problems[3]


def test_paper_renderer_formats_and_refuses_leftovers():
    import pytest
    data = {"a": {"b": [0.25, 3]}, "n": 1234}
    main = {"k": 2.5}
    assert paper.render("x {{a.b.0|.0%}} y {{a.b.1}} z {{n|,}} k {{main.k}}", data, main) == "x 25% y 3 z 1,234 k 2.5"
    assert paper.sig3("165.9978") == "166" and paper.sig3("2023-12-14") == "2023-12-14"
    assert paper.md_table(["A", "B"], [["x", 1]]) == "| A | B |\n| --- | ---: |\n| x | 1 |"
    with pytest.raises(KeyError):
        paper.render("{{missing.key}}", data, main)
    with pytest.raises(ValueError):
        paper.render("{{a.b.1}} }}", data, main)
