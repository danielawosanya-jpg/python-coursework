"""SQLite lead store. Stdlib only - no ORM, no external service.

The whole point of an organic lead magnet is that it costs nothing to run.
Leads live in a single file (leads.db) you can back up, export to CSV, and
import into any CRM later.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# LEADS_DB lets a container mount the database on a volume, so a redeploy
# doesn't take the lead list with it. Defaults to a file beside the code.
DB_PATH = Path(os.environ.get("LEADS_DB")
               or Path(__file__).resolve().parent.parent / "leads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    token             TEXT UNIQUE NOT NULL,
    email             TEXT NOT NULL,
    first_name        TEXT NOT NULL DEFAULT '',
    zip_code          TEXT NOT NULL DEFAULT '',
    consent           INTEGER NOT NULL DEFAULT 0,
    source            TEXT NOT NULL DEFAULT 'direct',
    score             INTEGER,
    band              TEXT,
    total_dollar_gap  REAL,
    answers_json      TEXT NOT NULL DEFAULT '{}',
    result_json       TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    unsubscribed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);

CREATE TABLE IF NOT EXISTS email_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES leads(id),
    step        INTEGER NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    send_after  TEXT NOT NULL,
    sent_at     TEXT,
    UNIQUE(lead_id, step)
);
CREATE INDEX IF NOT EXISTS idx_queue_pending ON email_queue(sent_at, send_after);
"""

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")


class DuplicateLead(Exception):
    """Raised when an email already exists - we return the old token instead."""

    def __init__(self, token: str):
        super().__init__("lead already exists")
        self.token = token


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip())) and len(value.strip()) <= 254


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_lead(
    *,
    email: str,
    first_name: str = "",
    zip_code: str = "",
    consent: bool = False,
    source: str = "direct",
    answers: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    db_path: Path | str = DB_PATH,
) -> str:
    """Insert a lead and return its report token.

    Re-submitting a known email refreshes the stored quiz answers rather than
    creating a duplicate, and reuses the original token so old report links
    keep working.
    """
    email = email.strip().lower()
    if not valid_email(email):
        raise ValueError("invalid email address")

    answers = answers or {}
    result = result or {}
    token = secrets.token_urlsafe(16)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT token FROM leads WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE leads SET score=?, band=?, total_dollar_gap=?,
                       answers_json=?, result_json=?, unsubscribed_at=NULL
                   WHERE email=?""",
                (
                    result.get("score"),
                    result.get("band"),
                    result.get("total_dollar_gap"),
                    json.dumps(answers),
                    json.dumps(result),
                    email,
                ),
            )
            return existing["token"]

        conn.execute(
            """INSERT INTO leads (token, email, first_name, zip_code, consent,
                                  source, score, band, total_dollar_gap,
                                  answers_json, result_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                token,
                email,
                first_name.strip()[:80],
                zip_code.strip()[:10],
                int(bool(consent)),
                source.strip()[:60] or "direct",
                result.get("score"),
                result.get("band"),
                result.get("total_dollar_gap"),
                json.dumps(answers),
                json.dumps(result),
                _now(),
            ),
        )
    return token


def get_lead(token: str, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE token = ?", (token,)
        ).fetchone()
    if row is None:
        return None
    lead = dict(row)
    lead["answers"] = json.loads(lead.pop("answers_json") or "{}")
    lead["result"] = json.loads(lead.pop("result_json") or "{}")
    return lead


def list_leads(limit: int = 200, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT id, token, email, first_name, zip_code, consent, source,
                      score, band, total_dollar_gap, created_at, unsubscribed_at
               FROM leads ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def unsubscribe(token: str, db_path: Path | str = DB_PATH) -> bool:
    """CAN-SPAM requires a working opt-out. This is it."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE leads SET unsubscribed_at=? WHERE token=? AND unsubscribed_at IS NULL",
            (_now(), token),
        )
        conn.execute(
            """DELETE FROM email_queue WHERE sent_at IS NULL AND lead_id IN
               (SELECT id FROM leads WHERE token=?)""",
            (token,),
        )
        return cur.rowcount > 0


def stats(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    with connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
        avg = conn.execute(
            "SELECT AVG(score) a FROM leads WHERE score IS NOT NULL"
        ).fetchone()["a"]
        by_source = conn.execute(
            """SELECT source, COUNT(*) c FROM leads
               GROUP BY source ORDER BY c DESC"""
        ).fetchall()
        hot = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE score IS NOT NULL AND score < 50"
        ).fetchone()["c"]
        opted_out = conn.execute(
            "SELECT COUNT(*) c FROM leads WHERE unsubscribed_at IS NOT NULL"
        ).fetchone()["c"]
    return {
        "total_leads": total,
        "average_score": round(avg, 1) if avg is not None else None,
        "hot_leads": hot,
        "unsubscribed": opted_out,
        "by_source": [dict(r) for r in by_source],
    }


CSV_COLUMNS = [
    "id", "created_at", "first_name", "email", "zip_code", "source",
    "score", "band", "total_dollar_gap", "consent", "unsubscribed_at",
]


def export_csv(db_path: Path | str = DB_PATH) -> str:
    """CRM-ready export. Import straight into HubSpot/Zoho/AgencyBloc."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for lead in list_leads(limit=100_000, db_path=db_path):
        writer.writerow(lead)
    return buf.getvalue()


# --- email queue ---------------------------------------------------------

def enqueue(
    lead_id: int,
    messages: Iterable[tuple[int, str, str, str]],
    db_path: Path | str = DB_PATH,
) -> int:
    """messages: (step, subject, body, send_after_iso). Idempotent per step."""
    count = 0
    with connect(db_path) as conn:
        for step, subject, body, send_after in messages:
            try:
                conn.execute(
                    """INSERT INTO email_queue (lead_id, step, subject, body, send_after)
                       VALUES (?,?,?,?,?)""",
                    (lead_id, step, subject, body, send_after),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass  # already queued for this lead+step
    return count


def due_emails(now: str | None = None, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    now = now or _now()
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT q.*, l.email, l.first_name, l.token
               FROM email_queue q JOIN leads l ON l.id = q.lead_id
               WHERE q.sent_at IS NULL AND q.send_after <= ?
                 AND l.unsubscribed_at IS NULL
               ORDER BY q.send_after""",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


def pending_steps(lead_id: int, db_path: Path | str = DB_PATH) -> list[int]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT step FROM email_queue WHERE lead_id=? AND sent_at IS NULL "
            "ORDER BY step", (lead_id,)
        ).fetchall()
    return [r["step"] for r in rows]


def reschedule_step(lead_id: int, step: int, send_after: str,
                    db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE email_queue SET send_after=? "
            "WHERE lead_id=? AND step=? AND sent_at IS NULL",
            (send_after, lead_id, step),
        )


def mark_sent(queue_id: int, db_path: Path | str = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE email_queue SET sent_at=? WHERE id=?", (_now(), queue_id)
        )


def lead_id_for_token(token: str, db_path: Path | str = DB_PATH) -> int | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT id FROM leads WHERE token=?", (token,)).fetchone()
    return row["id"] if row else None
