#!/usr/bin/env python3
"""Generate the static (no-server) build from the same source as the server one.

    python3 build_static.py

Reads web/index.html and agency.json and writes static/index.html with the
config baked in, so the landing page has exactly one source of truth. Run it
again after editing web/index.html or agency.json.

The static build differs from the server build in three ways, all applied
here rather than maintained as a second copy of the page:

  * scoring runs in the browser (static/scoring.js), so there is no API
  * the report renders in place instead of at /report?t=TOKEN
  * leads post to Netlify Forms, which needs the fields declared in markup

What it cannot do is send the follow-up sequence. That needs a real server,
a domain and an authenticated sender - see content/NO-SERVER.md.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from leadmagnet import config  # noqa: E402

SOURCE = ROOT / "web" / "index.html"
TARGET_DIR = ROOT / "static"

NETLIFY_FORM = """
<!-- Netlify reads the lead fields from this form at deploy time. The quiz
     posts to it with fetch; a visitor never sees it. -->
<form name="coverage-gap-lead" data-netlify="true" netlify-honeypot="company" hidden>
  <input type="text" name="first_name">
  <input type="email" name="email">
  <input type="text" name="zip_code">
  <input type="text" name="score">
  <input type="text" name="band">
  <input type="text" name="total_gap">
  <input type="text" name="top_gap">
  <input type="text" name="source">
  <input type="text" name="company">
  <textarea name="answers"></textarea>
</form>

</main>"""


def build() -> int:
    markup = SOURCE.read_text(encoding="utf-8")
    values = config.load()

    # Bake the agency details in - a static host has no templating layer.
    markup = config.render(markup, values)

    markup = markup.replace('<link rel="stylesheet" href="/styles.css">',
                            '<link rel="stylesheet" href="styles.css">')
    markup = markup.replace('<script src="/app.js"></script>',
                            '<script src="scoring.js"></script>\n'
                            '<script src="app.js"></script>')
    markup = markup.replace("</main>", NETLIFY_FORM)

    markup = markup.replace(
        '<a class="btn btn-primary btn-lg" id="reportLink" href="#">'
        'Open my Coverage Gap Report →</a>',
        '<a class="btn btn-primary btn-lg" id="reportLink" href="#report">'
        'See my Coverage Gap Report →</a>')
    markup = markup.replace(
        '<p id="doneNote">Your report is ready below.</p>',
        '<p id="doneNote">Scroll down for the full breakdown — or print it '
        'to PDF to keep.</p>')
    markup = markup.replace(
        '<!-- ================= WHY TRUST ================= -->',
        '<!-- ============ REPORT (rendered in place) ============ -->\n'
        '<section id="report" class="report-section" hidden aria-live="polite">'
        '</section>\n\n'
        '<!-- ================= WHY TRUST ================= -->')

    TARGET_DIR.mkdir(exist_ok=True)
    (TARGET_DIR / "index.html").write_text(markup, encoding="utf-8")
    shutil.copy2(ROOT / "web" / "styles.css", TARGET_DIR / "styles.css")

    leftover = markup.count("{{")
    print(f"Wrote {TARGET_DIR / 'index.html'}")
    print(f"Copied styles.css")
    if leftover:
        print(f"  WARNING: {leftover} unreplaced {{{{token}}}} left in the page",
              file=sys.stderr)
        return 1

    unset = config.placeholders_remaining(values)
    public = [f for f in unset if f not in {"site_url", "mailing_address"}]
    if public:
        print(f"  WARNING: still placeholder on the public page: "
              f"{', '.join(public)}", file=sys.stderr)
        return 1
    print("\nStatic build ready. Deploy the static/ folder to Netlify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
