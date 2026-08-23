# Coverage Gap Finder

A complete, working lead-magnet system for an insurance agency — built to be
distributed **organically, with no ad spend**.

Prospects answer 10 questions, get a protection score out of 100, and trade an
email address for a personalized Coverage Gap Report that names every gap in
their coverage, sizes it in dollars, and tells them how to fix it. The system
then stores the lead, queues a six-email follow-up sequence personalized with
their own numbers, and shows you which organic channel produced them.

**Zero dependencies.** Python 3.10+ standard library only — no Flask, no npm,
no SaaS subscription. It runs on a $5 VPS, a free-tier host, or a laptop.

---

## Run it

```bash
cd lead-magnet
python3 server.py
```

Open <http://localhost:8000>. That's the whole install.

```bash
python3 -m unittest discover -s tests -v   # 36 tests
python3 send_worker.py --dry-run           # preview queued emails
ADMIN_KEY=yourkey python3 server.py        # then /admin?key=yourkey
```

---

## What's in the box

| | |
|---|---|
| **Landing page + quiz** | `web/` — 5-step quiz, live score preview, email gate |
| **Scoring engine** | `leadmagnet/scoring.py` — DIME, income multiples, replacement-cost and liability checks |
| **Personalized report** | `leadmagnet/report.py` — standalone HTML, prints to PDF from the browser |
| **Lead database** | `leadmagnet/storage.py` — SQLite, CSV export for any CRM |
| **Email sequence** | `leadmagnet/sequences.py` — 6 emails over 16 days, personalized with their numbers |
| **Send worker** | `send_worker.py` — SMTP, run from cron |
| **Admin dashboard** | `/admin?key=…` — leads, scores, source attribution, CSV export |
| **Organic playbook** | `content/ORGANIC-PLAYBOOK.md` — the 90-day no-ads distribution plan |
| **Content bank** | `content/SOCIAL-CONTENT-BANK.md` — 30 ready-to-post pieces |
| **Compliance** | `content/COMPLIANCE.md` — read before launch |

---

## How it works

```
  Organic channel (?src=reddit)
            │
            ▼
   Landing page + 10-question quiz
            │
            ├── POST /api/score ──► teaser: score + gap COUNT only
            │                       (the detail is what the email buys)
            ▼
     Email gate + consent checkbox
            │
            ├── POST /api/lead ───► SQLite: answers, result, source
            │                    └► queue 6 personalized emails
            ▼
   /report?t=TOKEN — the full report
            │
            ▼
   send_worker.py (cron) ──► SMTP ──► inbox
            │
            ▼
   /admin?key= — leads by source, hot list, CSV to your CRM
```

### The two design decisions that matter

**The teaser withholds detail, not value.** `/api/score` returns the score and
how many gaps were found — never the gaps themselves. That's the trade the
email address buys. But once they've paid it, the report is complete: gaps,
dollar amounts, and the fix for each, including the times the right answer is
"change nothing." A report that's genuinely useful without you is the only kind
that gets shared, and sharing is the whole organic engine.

**Every link is source-tagged.** Add `?src=anything` to any URL you post and it
lands in the admin dashboard's source column. That's your entire analytics
stack, and it's what tells you which of the six organic channels to keep doing.

---

## Setup for real use

### 1. Replace the placeholders

Everything you must fill in is in one dict — `AGENCY` at the top of
`leadmagnet/sequences.py`:

```python
AGENCY = {
    "agent_name": "Your Name",
    "agency_name": "Your Agency",
    "license": "GA license #1234567",
    "phone": "555-555-5555",
    "calendar_url": "https://cal.com/you/review",
    "site_url": "https://yourdomain.com",
    "mailing_address": "12 Main St, Atlanta, GA 30301",  # CAN-SPAM requires this
    "states_licensed": "GA, FL",
}
```

Then replace the matching `[Your Agency]` / `[Your Name]` / `[State]`
placeholders in `web/index.html` (topbar and footer).

### 2. Tune the assumptions

The top of `leadmagnet/scoring.py` holds every number the engine uses —
income-replacement years, college cost per child, the auto-liability floor, the
umbrella trigger. Adjust them to your state and your book, then re-run the
tests.

### 3. Configure email

```bash
export SMTP_HOST=smtp.yourprovider.com
export SMTP_PORT=587
export SMTP_USER=you@youragency.com
export SMTP_PASS=your-app-password
export SMTP_FROM="Your Name <you@youragency.com>"

python3 send_worker.py --dry-run   # confirm the copy reads right
python3 send_worker.py             # send for real
```

Then schedule it — every 15 minutes is plenty:

```cron
*/15 * * * * cd /path/to/lead-magnet && /usr/bin/python3 send_worker.py >> worker.log 2>&1
```

Set up SPF and DKIM on your sending domain before you send to anyone. Without
them the sequence lands in spam and none of the rest matters.

### 4. Deploy

```bash
export ADMIN_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
python3 server.py --host 127.0.0.1 --port 8000
```

Put nginx or Caddy in front for HTTPS and proxy to port 8000. The server binds
to localhost by default on purpose — don't expose it directly.

The stdlib `ThreadingHTTPServer` comfortably handles organic-scale traffic
(thousands of visits a day). If you ever outgrow it, `Handler` maps cleanly
onto any WSGI framework — the logic all lives in `leadmagnet/`.

### 5. Read the compliance checklist

`content/COMPLIANCE.md`. Licensing disclosure, CAN-SPAM, TCPA, state
advertising rules, and a pre-launch sign-off sheet. Have your carrier's
compliance contact review the page and the emails before launch.

---

## Getting traffic without ads

The tool is half the system. `content/ORGANIC-PLAYBOOK.md` is the other half —
six channels, a 90-day plan, and realistic benchmarks:

1. **Search** — one hub page, twelve spoke articles, local SEO. Slowest, largest.
2. **Communities** — answer two questions a day in r/Insurance and r/personalfinance, thoroughly, without links. Fastest.
3. **Short-form video** — 30 scripts in `SOCIAL-CONTENT-BANK.md`, one a day.
4. **Referral partners** — realtors, mortgage brokers, CPAs, each with a tagged link.
5. **Your existing book** — the warmest, most neglected audience you have.
6. **Local offline** — lunch-and-learns, chamber, QR codes.

Expect 5–15 leads in month one, 30–60 by month three, and search overtaking
everything around month six. The single biggest failure mode is quitting at
week six, which is exactly where the curve looks worst.

---

## API

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/` | Landing page + quiz |
| `POST` | `/api/score` | Score answers → teaser only (no gap detail) |
| `POST` | `/api/lead` | Capture lead, store, queue the sequence |
| `GET` | `/report?t=TOKEN` | The personalized report |
| `GET` | `/unsubscribe?t=TOKEN` | CAN-SPAM opt-out (also clears queued mail) |
| `GET` | `/admin?key=KEY` | Lead dashboard |
| `GET` | `/admin/export.csv?key=KEY` | CRM export |
| `GET` | `/healthz` | Health check |

---

## Notes on what this is and isn't

The scoring uses standard industry rules of thumb — DIME for life needs, income
multiples for disability, replacement-cost ratios for property. Those are the
same methods behind a paid needs analysis, and they produce a defensible
educational estimate. They are not advice, not a quote, and not a substitute
for reading an actual policy. The report says so in its footer, every email
says so in its signature, and `COMPLIANCE.md` explains why that language needs
to stay.
