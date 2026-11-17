"""Extract cause-effect links from the corpus passages with a local model through Ollama (not in CI).

Run ``python scripts/fetch_corpus.py`` first (it re-creates the passages in data/corpus/cache), then
``python scripts/run_llm_extraction.py [model ...]`` with Ollama serving on localhost:11434. Default
model: qwen3.5:4b. Results go to ``data/corpus/llm_runs/<model>.csv`` and ``<model>.json``; they are
committed, and the offline build only scores them, so CI never calls a model.

Settings: temperature 0, fixed seed, JSON-schema constrained output, thinking switched off where the
model supports it. The prompt is the codebook (data/corpus/codebook.md) verbatim plus the passage.
Quotes are checked against the passage here (the passages are not committed) and stored cut to at
most 14 words.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
OLLAMA = "http://127.0.0.1:11434"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 1024}  # cap runaway lists
MAX_QUOTE_WORDS = 14


def variables() -> list[str]:
    text = (CORPUS / "codebook.md").read_text(encoding="utf-8")
    return re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.M)


def system_prompt() -> str:
    codebook = (CORPUS / "codebook.md").read_text(encoding="utf-8")
    body = codebook.split("## Variables", 1)[1].split("## Scoring", 1)[0]
    return ("You extract cause-effect links from one passage about maritime shipping. Apply this codebook "
            "exactly.\n\n## Variables" + body.rstrip() +
            "\n\nAnswer with JSON only: {\"links\": [{\"cause\": variable, \"effect\": variable, "
            "\"polarity\": \"+\" or \"-\", \"quote\": evidence}]}. If the passage has no link, answer "
            "{\"links\": []}.")


def schema(names: list[str]) -> dict:
    link = {"type": "object", "properties": {
        "cause": {"type": "string", "enum": names}, "effect": {"type": "string", "enum": names},
        "polarity": {"type": "string", "enum": ["+", "-"]}, "quote": {"type": "string"}},
        "required": ["cause", "effect", "polarity", "quote"]}
    return {"type": "object", "properties": {"links": {"type": "array", "items": link}}, "required": ["links"]}


def call(path: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("“", '"').replace("”", '"').replace("’", "'")).strip()


def quote_is_verbatim(quote: str, passage: str) -> bool:
    frags = [f.strip(" .,;:") for f in re.split(r"\.\.\.|…", quote) if f.strip(" .,;:")]
    p = norm(passage).lower()
    return bool(frags) and all(norm(f).lower() in p for f in frags)


def main(models: list[str]) -> None:
    names = variables()
    sysmsg = system_prompt()
    passages = [json.loads(line) for line in (CORPUS / "cache" / "passages.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    with open(CORPUS / "passages.csv", newline="", encoding="utf-8") as f:
        want = {r["passage_id"]: r["sha256"] for r in csv.DictReader(f)}
    for p in passages:
        if hashlib.sha256(p["text"].encode("utf-8")).hexdigest() != want[p["passage_id"]]:
            raise SystemExit(f"passage {p['passage_id']} differs from data/corpus/passages.csv; re-run fetch_corpus")
    version = call("/api/version")["version"]
    tags = {m["name"]: m for m in call("/api/tags")["models"]}
    out_dir = CORPUS / "llm_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for model in models:
        caps = call("/api/show", {"model": model}).get("capabilities", [])
        rows, timing, errors, stops = [], [], [], []
        for p in passages:
            payload = {"model": model, "stream": False, "format": schema(names), "options": OPTIONS,
                       "keep_alive": "5m",
                       "messages": [{"role": "system", "content": sysmsg},
                                    {"role": "user", "content": "Passage:\n" + p["text"]}]}
            if "thinking" in caps:
                payload["think"] = False
            t0 = time.time()
            links = None
            for attempt in range(2):
                try:
                    resp = call("/api/chat", payload)
                    stops.append(resp.get("done_reason"))
                    links = json.loads(resp["message"]["content"])["links"]
                    break
                except Exception as exc:  # pragma: no cover - model or network failure
                    errors.append({"passage_id": p["passage_id"], "attempt": attempt, "error": repr(exc)[:200]})
            timing.append(round(time.time() - t0, 1))
            seen = set()
            for lk in links or []:
                key = (lk.get("cause"), lk.get("effect"))
                if key in seen:
                    continue
                seen.add(key)
                words = str(lk.get("quote", "")).split()
                rows.append({"passage_id": p["passage_id"], "cause": lk.get("cause"), "effect": lk.get("effect"),
                             "polarity": lk.get("polarity"),
                             "in_codebook": lk.get("cause") in names and lk.get("effect") in names,
                             "quote_verbatim": quote_is_verbatim(str(lk.get("quote", "")), p["text"]),
                             "quote_words": len(words), "quote_truncated": len(words) > MAX_QUOTE_WORDS,
                             "quote_stored": " ".join(words[:MAX_QUOTE_WORDS])})
            print(model, p["passage_id"], len(links or []), "links", timing[-1], "s", flush=True)
        slug = model.replace(":", "-").replace("/", "-")
        with open(out_dir / f"{slug}.csv", "w", newline="\n", encoding="utf-8") as f:
            fields = ["passage_id", "cause", "effect", "polarity", "in_codebook", "quote_verbatim", "quote_words",
                      "quote_truncated", "quote_stored"]
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        meta = {"model": model, "digest": tags.get(model, {}).get("digest"), "ollama_version": version,
                "options": OPTIONS, "think": False if "thinking" in caps else None,
                "prompt_sha256": hashlib.sha256(sysmsg.encode("utf-8")).hexdigest(),
                "codebook_sha256": hashlib.sha256((CORPUS / "codebook.md").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "passages": len(passages), "links": len(rows), "seconds_per_passage": timing,
                "outputs_cut_at_num_predict": sum(s == "length" for s in stops),
                "errors": errors, "run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        with open(out_dir / f"{slug}.json", "w", newline="\n", encoding="utf-8") as f:
            f.write(json.dumps(meta, indent=1) + "\n")
        # unload the model so it does not keep memory after the run
        call("/api/generate", {"model": model, "keep_alive": 0})
        print("wrote", out_dir / f"{slug}.csv", len(rows), "links")


if __name__ == "__main__":
    main(sys.argv[1:] or ["qwen3.5:4b"])
