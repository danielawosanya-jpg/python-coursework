#!/usr/bin/env python3
"""Coverage Gap Finder - the whole lead magnet in one stdlib server.

    python3 server.py            # http://localhost:8000
    python3 server.py --port 9000

Routes
------
GET  /                      landing page + quiz
POST /api/score             score answers, return partial result (no email yet)
POST /api/lead              capture email, store lead, queue follow-ups
GET  /report?t=TOKEN        the personalized report
GET  /unsubscribe?t=TOKEN   CAN-SPAM opt-out
GET  /admin?key=KEY         lead dashboard  (ADMIN_KEY env var, default 'changeme')
GET  /admin/export.csv?key= CRM export

No third-party packages. Runs on any Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from leadmagnet import report, scoring, sequences, storage

WEB_DIR = Path(__file__).resolve().parent / "web"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "changeme")
MAX_BODY = 16 * 1024

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "CoverageGapFinder/1.0"

    # --- helpers ---------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str,
              extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _html(self, status: int, markup: str) -> None:
        self._send(status, markup.encode(), "text/html; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _query(self) -> dict[str, str]:
        parsed = urllib.parse.urlparse(self.path)
        return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    def _authorized(self) -> bool:
        return self._query().get("key") == ADMIN_KEY

    def log_message(self, fmt, *args):  # quieter default logging
        print(f"{self.log_date_time_string()}  {fmt % args}")

    # --- routing ---------------------------------------------------------

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            return self._serve_file("index.html")
        if path == "/report":
            return self._route_report()
        if path == "/unsubscribe":
            return self._route_unsubscribe()
        if path == "/admin":
            return self._route_admin()
        if path == "/admin/export.csv":
            return self._route_export()
        if path == "/api/stats":
            if not self._authorized():
                return self._json(403, {"error": "forbidden"})
            return self._json(200, storage.stats())
        if path == "/healthz":
            return self._json(200, {"ok": True})

        return self._serve_file(path.lstrip("/"))

    do_HEAD = do_GET

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/score":
            return self._route_score()
        if path == "/api/lead":
            return self._route_lead()
        return self._json(404, {"error": "not found"})

    # --- static ----------------------------------------------------------

    def _serve_file(self, relative: str):
        candidate = (WEB_DIR / relative).resolve()
        if not str(candidate).startswith(str(WEB_DIR)) or not candidate.is_file():
            return self._html(404, "<h1>404</h1><p><a href='/'>Back to the quiz</a></p>")
        ctype = CONTENT_TYPES.get(candidate.suffix, "application/octet-stream")
        self._send(200, candidate.read_bytes(), ctype)

    # --- api -------------------------------------------------------------

    def _route_score(self):
        """Score without capturing anything. Powers the live preview."""
        payload = self._read_json()
        result = scoring.score_payload(payload.get("answers") or payload)
        data = result.to_dict()
        # Teaser only: count and score, never the gap detail. The detail is
        # what the email buys.
        self._json(200, {
            "score": data["score"],
            "band": data["band"],
            "gap_count": len(data["gaps"]),
            "critical_count": sum(1 for g in data["gaps"] if g["severity"] == "critical"),
            "total_dollar_gap": data["total_dollar_gap"],
            "headline": data["headline"],
        })

    def _route_lead(self):
        payload = self._read_json()
        email = str(payload.get("email", "")).strip()
        if not storage.valid_email(email):
            return self._json(400, {"error": "Please enter a valid email address."})
        if not payload.get("consent"):
            return self._json(400, {
                "error": "Please check the consent box so we can send your report."
            })

        answers = payload.get("answers") or {}
        result = scoring.score_payload(answers).to_dict()

        token = storage.save_lead(
            email=email,
            first_name=str(payload.get("first_name", ""))[:80],
            zip_code=str(payload.get("zip_code", ""))[:10],
            consent=True,
            source=str(payload.get("source", "direct"))[:60],
            answers=answers,
            result=result,
        )

        lead = storage.get_lead(token)
        lead_id = lead["id"] if lead else None
        if lead_id:
            storage.enqueue(
                lead_id,
                sequences.schedule_for(lead, start=datetime.now(timezone.utc)),
            )

        self._json(200, {"ok": True, "token": token, "report_url": f"/report?t={token}"})

    # --- pages -----------------------------------------------------------

    def _route_report(self):
        token = self._query().get("t", "")
        lead = storage.get_lead(token) if token else None
        if lead is None:
            return self._html(404, (
                "<h1>Report not found</h1><p>That link has expired or was "
                "mistyped. <a href='/'>Run the quiz again</a> and we will "
                "rebuild it.</p>"
            ))
        self._html(200, report.render_report(lead))

    def _route_unsubscribe(self):
        token = self._query().get("t", "")
        done = storage.unsubscribe(token) if token else False
        message = ("You're unsubscribed. No further emails will go out, and "
                   "your report link still works."
                   if done else
                   "You were already unsubscribed, or that link is not valid.")
        self._html(200, (
            "<!doctype html><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Unsubscribed</title>"
            "<body style=\"font:16px/1.6 system-ui,sans-serif;max-width:38rem;"
            "margin:15vh auto;padding:0 1.25rem;color:#16202e\">"
            f"<h1 style='font-size:1.6rem'>{message}</h1>"
            "<p><a href='/'>Back to the Coverage Gap Finder</a></p></body>"
        ))

    def _route_admin(self):
        if not self._authorized():
            return self._html(403, (
                "<h1>403</h1><p>Add <code>?key=YOUR_ADMIN_KEY</code> to the URL. "
                "Set it with the <code>ADMIN_KEY</code> environment variable.</p>"
            ))
        leads = storage.list_leads()
        s = storage.stats()
        rows = "".join(
            f"<tr><td>{l['created_at'][:10]}</td><td>{l['first_name'] or '-'}</td>"
            f"<td>{l['email']}</td><td>{l['zip_code'] or '-'}</td>"
            f"<td>{l['source']}</td>"
            f"<td class='{'hot' if (l['score'] or 100) < 50 else ''}'>{l['score'] if l['score'] is not None else '-'}</td>"
            f"<td>{l['band'] or '-'}</td>"
            f"<td>${(l['total_dollar_gap'] or 0):,.0f}</td>"
            f"<td><a href='/report?t={l['token']}'>report</a></td>"
            f"<td>{'opted out' if l['unsubscribed_at'] else ''}</td></tr>"
            for l in leads
        ) or "<tr><td colspan='10'>No leads yet.</td></tr>"
        sources = "".join(
            f"<li>{r['source']}: <strong>{r['c']}</strong></li>" for r in s["by_source"]
        ) or "<li>No traffic yet.</li>"
        self._html(200, f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leads</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:28px;color:#16202e;background:#f7f8fa}}
 h1{{margin:0 0 4px}} .sub{{color:#5b6878;margin:0 0 20px}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
 .card{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:14px 18px;flex:1 1 160px}}
 .card b{{display:block;font-size:26px}} .card span{{color:#5b6878;font-size:13px}}
 table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3e8ef;border-radius:10px;overflow:hidden}}
 th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #eef1f5;font-size:14px}}
 th{{background:#f0f3f7;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#5b6878}}
 .hot{{color:#b4342b;font-weight:700}}
 ul{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:12px 12px 12px 32px;list-style:disc}}
 a.btn{{display:inline-block;background:#0f5c4a;color:#fff;padding:9px 16px;border-radius:7px;text-decoration:none;margin-bottom:18px}}
</style>
<h1>Coverage Gap Finder &mdash; leads</h1>
<p class="sub">Scores under 50 are your call-first list.</p>
<div class="cards">
  <div class="card"><b>{s['total_leads']}</b><span>Total leads</span></div>
  <div class="card"><b>{s['hot_leads']}</b><span>Hot (score &lt; 50)</span></div>
  <div class="card"><b>{s['average_score'] if s['average_score'] is not None else '-'}</b><span>Average score</span></div>
  <div class="card"><b>{s['unsubscribed']}</b><span>Opted out</span></div>
</div>
<a class="btn" href="/admin/export.csv?key={urllib.parse.quote(ADMIN_KEY)}">Export CSV for your CRM</a>
<h2 style="font-size:17px">Where they came from</h2>
<ul>{sources}</ul>
<h2 style="font-size:17px">Leads</h2>
<table><tr><th>Date</th><th>Name</th><th>Email</th><th>ZIP</th><th>Source</th>
<th>Score</th><th>Band</th><th>Exposure</th><th></th><th></th></tr>{rows}</table>""")

    def _route_export(self):
        if not self._authorized():
            return self._json(403, {"error": "forbidden"})
        self._send(
            200, storage.export_csv().encode(), "text/csv; charset=utf-8",
            {"Content-Disposition": "attachment; filename=leads.csv"},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    storage.init_db()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Coverage Gap Finder running at http://{args.host}:{args.port}")
    print(f"Admin dashboard: http://{args.host}:{args.port}/admin?key={ADMIN_KEY}")
    if ADMIN_KEY == "changeme":
        print("  (set ADMIN_KEY in your environment before putting this online)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
