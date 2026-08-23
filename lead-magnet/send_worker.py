#!/usr/bin/env python3
"""Sends whatever is due in the email queue.

    python3 send_worker.py --dry-run     # print what would go out
    python3 send_worker.py               # actually send via SMTP

Configure SMTP with environment variables (works with Gmail app passwords,
Fastmail, Zoho, Amazon SES, Postmark - anything that speaks SMTP):

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@youragency.com
    SMTP_PASS=your-app-password
    SMTP_FROM="Your Name <you@youragency.com>"

Then run it on a schedule - cron every 15 minutes is plenty:

    */15 * * * * cd /path/to/lead-magnet && /usr/bin/python3 send_worker.py >> worker.log 2>&1
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from leadmagnet import sequences, storage


def one_per_lead(due: list[dict]) -> list[dict]:
    """Collapse a backlog to the earliest unsent step per lead.

    If leads were captured before SMTP was configured, every step of every
    sequence comes due the moment sending is switched on. Delivering six
    emails at once is a spam complaint, not a nurture sequence - so send the
    oldest step now and let the rest be re-spaced.
    """
    first: dict[int, dict] = {}
    for item in due:
        current = first.get(item["lead_id"])
        if current is None or item["step"] < current["step"]:
            first[item["lead_id"]] = item
    return sorted(first.values(), key=lambda i: i["send_after"])


def respace_remaining(lead_id: int, sent_step: int,
                      now: datetime | None = None) -> int:
    """Re-space a lead's remaining steps relative to the one just sent."""
    now = now or datetime.now(timezone.utc)
    base = sequences.SCHEDULE.get(sent_step, 0)
    moved = 0
    for step in storage.pending_steps(lead_id):
        offset = sequences.SCHEDULE.get(step)
        if offset is None or offset <= base:
            continue
        when = now + timedelta(days=offset - base)
        storage.reschedule_step(lead_id, step,
                                when.isoformat(timespec="seconds"))
        moved += 1
    return moved


def build_message(item: dict, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = item["email"]
    msg["Subject"] = item["subject"]
    # One-click unsubscribe headers materially help inbox placement.
    msg["List-Unsubscribe"] = f"<{_unsub_url(item['token'])}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(item["body"])
    return msg


def _unsub_url(token: str) -> str:
    from leadmagnet.sequences import AGENCY
    return f"{AGENCY['site_url']}/unsubscribe?t={token}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the queue without sending or marking sent")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    storage.init_db()
    backlog = storage.due_emails()
    due = one_per_lead(backlog)[: args.limit]

    if not due:
        print("Nothing due.")
        return 0

    held = len(backlog) - len(due)
    if held:
        print(f"{held} message(s) held back so no one gets a burst; "
              f"they will be re-spaced after this run.")

    if args.dry_run:
        for item in due:
            print(f"\n{'=' * 68}\nTo: {item['email']}  (step {item['step']})\n"
                  f"Subject: {item['subject']}\n{'-' * 68}\n{item['body']}")
        print(f"\n{len(due)} message(s) would be sent.")
        return 0

    host = os.environ.get("SMTP_HOST")
    if not host:
        print("SMTP_HOST is not set. Run with --dry-run, or configure SMTP "
              "(see the docstring at the top of this file).", file=sys.stderr)
        return 1

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("SMTP_FROM") or user

    sent = failed = 0
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, password)
        for item in due:
            try:
                smtp.send_message(build_message(item, sender))
                storage.mark_sent(item["id"])
                respace_remaining(item["lead_id"], item["step"])
                sent += 1
                print(f"sent step {item['step']} -> {item['email']}")
            except smtplib.SMTPException as exc:
                failed += 1
                print(f"FAILED {item['email']}: {exc}", file=sys.stderr)

    print(f"{sent} sent, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
