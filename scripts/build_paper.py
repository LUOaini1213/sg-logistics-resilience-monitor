"""Build paper/working_paper.pdf from paper/working_paper.md (not part of the offline build or CI).

Needs pandoc on PATH (or PANDOC=/path/to/pandoc) and Playwright with Chromium
(``pip install -r requirements-extra.txt`` and ``python -m playwright install chromium``).
``python run_all.py`` regenerates the Markdown from the results; this script turns it into HTML with
pandoc (figures and CSS embedded) and prints that to A4 with headless Chromium. It writes the SHA-256
of the Markdown it used to ``paper/working_paper.pdf.source-sha256``; a test checks that the committed
PDF was built from the committed Markdown.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def md_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> None:
    pandoc = os.environ.get("PANDOC") or shutil.which("pandoc")
    if not pandoc:
        raise SystemExit("pandoc not found: set PANDOC or put it on PATH")
    md = PAPER / "working_paper.md"
    build = PAPER / "build"
    build.mkdir(exist_ok=True)
    html = build / "working_paper.html"
    subprocess.run([pandoc, str(md), "--standalone", "--embed-resources", "--css", str(PAPER / "paper.css"),
                    "--resource-path", str(PAPER), "--metadata", "lang=en", "-o", str(html)], check=True, cwd=PAPER)
    from playwright.sync_api import sync_playwright
    pdf = PAPER / "working_paper.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu"])
        page = browser.new_page()
        page.goto(html.resolve().as_uri(), wait_until="load")
        page.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True,
                 display_header_footer=True, header_template="<span></span>",
                 footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#666">'
                                 '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        browser.close()
    (PAPER / "working_paper.pdf.source-sha256").write_text(md_hash(md) + "  working_paper.md\n", encoding="utf-8",
                                                           newline="\n")
    try:
        import pymupdf
        with pymupdf.open(pdf) as doc:
            print(f"{pdf}: {doc.page_count} pages")
    except ImportError:  # pragma: no cover
        print(f"wrote {pdf}")


if __name__ == "__main__":
    sys.exit(main())
