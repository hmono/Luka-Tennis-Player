"""
md2pdf.py
Renders a Markdown document to a print-ready A4 PDF.

Built for the reference documents in docs/data-sources/ — the ones meant to be
carried to a consultation or printed. Handles the constructs those documents
actually use: tables, blockquotes, `- [ ]` checkboxes (rendered as tickable
boxes), and the `**Field:** value` metadata header block.

Usage:
    python scripts/md2pdf.py docs/data-sources/consulta_dr_abud_2026-08-19.md
    python scripts/md2pdf.py input.md -o output.pdf

Requires:
    pip install markdown
    A Chromium/Chrome binary. Searched in this order:
      $CHROME_BIN, then common Linux/macOS install paths, then the Playwright
      bundle at /opt/pw-browsers/ (present in the Claude Code web sandbox).
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ─── Chromium discovery ───────────────────────────────────────────────────────

CHROME_CANDIDATES = [
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

CHROME_GLOBS = [
    "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
]


def find_chrome():
    """Return a usable Chromium/Chrome executable path, or None."""
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]

    for name in CHROME_CANDIDATES:
        found = shutil.which(name) if "/" not in name else (name if os.path.exists(name) else None)
        if found:
            return found

    for pattern in CHROME_GLOBS:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]  # highest build number

    return None


# ─── Stylesheet ───────────────────────────────────────────────────────────────

CSS = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", "Helvetica Neue", Arial, sans-serif;
  font-size: 9.6pt; line-height: 1.45; color: #16181d; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 {
  font-size: 19pt; line-height: 1.15; margin: 0 0 4mm; padding-bottom: 3mm;
  border-bottom: 2.5px solid #1b4a8f; color: #10233f; letter-spacing: -0.2px;
}
h2 {
  font-size: 13pt; margin: 8mm 0 2.5mm; padding: 2mm 0 1.5mm;
  border-bottom: 1px solid #c8d2e0; color: #1b4a8f;
  break-after: avoid; page-break-after: avoid;
}
h3 {
  font-size: 10.6pt; margin: 5mm 0 1.5mm; color: #24344d;
  break-after: avoid; page-break-after: avoid;
}
p { margin: 0 0 2.2mm; }
ul, ol { margin: 0 0 2.5mm; padding-left: 5.5mm; }
li { margin: 0 0 1.1mm; }
strong { color: #0d1a2b; }
code {
  font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt;
  background: #eef1f6; padding: 0.4mm 1.1mm; border-radius: 2px; color: #234;
}
hr { border: 0; border-top: 1px solid #d8dee8; margin: 6mm 0; }

table {
  border-collapse: collapse; width: 100%; margin: 2mm 0 4mm;
  font-size: 8.9pt; break-inside: avoid; page-break-inside: avoid;
}
th {
  background: #1b4a8f; color: #fff; text-align: left; font-weight: 600;
  padding: 1.8mm 2.2mm; border: 1px solid #1b4a8f; font-size: 8.7pt;
}
td { padding: 1.6mm 2.2mm; border: 1px solid #ccd5e2; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f5f7fb; }

blockquote {
  margin: 2.5mm 0 3.5mm; padding: 2.2mm 3mm; background: #eef4fd;
  border-left: 3.5px solid #1b4a8f; break-inside: avoid; page-break-inside: avoid;
}
blockquote p { margin: 0; }

.box {
  display: inline-block; width: 3.3mm; height: 3.3mm; border: 1px solid #5a6b82;
  border-radius: 1px; margin-right: 1.4mm; vertical-align: -0.4mm; background: #fff;
}
.box.checked { background: #1b4a8f; border-color: #1b4a8f; }
li:has(> .box) { list-style: none; margin-left: -4mm; margin-bottom: 1.7mm; }

h2, h3, table, blockquote { orphans: 3; widows: 3; }
"""

HTML_SHELL = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{title}</title>
<style>{css}</style></head><body>
{body}
</body></html>"""


# ─── Conversion ───────────────────────────────────────────────────────────────

def markdown_to_html(src: str, title: str) -> str:
    """Convert Markdown to a self-contained, print-styled HTML document."""
    try:
        import markdown
    except ImportError:
        sys.exit("error: the 'markdown' package is required — pip install markdown")

    # `- [ ]` / `- [x]` -> printable boxes. The task-list extension is not a
    # dependency here, and its default output is a disabled <input> that some
    # print engines drop entirely.
    src = re.sub(r'^(\s*)- \[ \] ', r'\1- <span class="box"></span> ', src, flags=re.M)
    src = re.sub(r'^(\s*)- \[x\] ', r'\1- <span class="box checked"></span> ', src, flags=re.M | re.I)

    # Metadata header lines ("**Atleta:** ...") are consecutive single lines that
    # Markdown would otherwise collapse into one paragraph. Force a hard break.
    src = re.sub(r'^(\*\*[^*\n]+:\*\* .*)$', r'\1  ', src, flags=re.M)

    body = markdown.markdown(src, extensions=["tables", "attr_list", "sane_lists"])
    return HTML_SHELL.format(title=title, css=CSS, body=body)


def html_to_pdf(html: str, out_pdf: Path) -> None:
    """Print an HTML string to PDF using headless Chromium."""
    chrome = find_chrome()
    if not chrome:
        sys.exit(
            "error: no Chromium/Chrome binary found.\n"
            "       Set CHROME_BIN, or install chromium."
        )

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "doc.html"
        html_path.write_text(html, encoding="utf-8")

        result = subprocess.run(
            [
                chrome, "--headless", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out_pdf}",
                html_path.as_uri(),
            ],
            capture_output=True, text=True,
        )

    if not out_pdf.exists():
        sys.exit(f"error: Chromium produced no PDF.\n{result.stderr.strip()}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Render a Markdown file to a print-ready A4 PDF.")
    parser.add_argument("input", type=Path, help="path to the .md file")
    parser.add_argument("-o", "--output", type=Path, help="output .pdf (default: alongside the input)")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"error: {args.input} not found")

    out_pdf = (args.output or args.input.with_suffix(".pdf")).resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    src = args.input.read_text(encoding="utf-8")

    # Title for the PDF metadata / browser tab: the first H1, else the filename.
    match = re.search(r'^#\s+(.+)$', src, flags=re.M)
    title = match.group(1).strip() if match else args.input.stem

    html_to_pdf(markdown_to_html(src, title), out_pdf)
    print(f"{out_pdf}  ({out_pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
