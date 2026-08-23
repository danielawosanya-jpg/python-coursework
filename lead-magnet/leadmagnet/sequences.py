"""The follow-up sequence.

The report is the magnet; this is the machine that turns a download into a
conversation. Six emails over 16 days, each personalized with the prospect's
own numbers - which is the entire reason for scoring the quiz server-side.

Nothing here sends mail on its own. `render_sequence` produces the messages
and `storage.enqueue` schedules them; `send_worker.py` hands them to whatever
SMTP or ESP you use. That keeps the deliverability decision (and the cost)
in your hands.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import config

# Loaded from agency.json - edit that file, or run `python3 configure.py`.
# Every email signature and the report footer read from here.
AGENCY = config.load()

# step -> days after opt-in
SCHEDULE = {1: 0, 2: 1, 3: 3, 4: 6, 5: 10, 6: 16}


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _signature(token: str) -> str:
    """The only place the postal address appears.

    CAN-SPAM requires a valid physical postal address in every commercial
    email. It is deliberately NOT on the landing page or the report, which
    have no such requirement - that keeps it out of search results and off
    the open web, reaching only people who asked for the report. A PO Box or
    a registered private mailbox satisfies the statute just as well as a
    street address. Check with your compliance contact before adding it back
    to public pages; some state advertising rules ask for it.
    """
    return (
        f"\n\n--\n{AGENCY['agent_name']}\n{AGENCY['agency_name']}\n"
        f"{AGENCY['license']} | Licensed in {AGENCY['states_licensed']}\n"
        f"{AGENCY['phone']} | {AGENCY['site_url']}\n"
        f"{AGENCY['mailing_address']}\n\n"
        f"You are receiving this because you requested a Coverage Gap Report at "
        f"{AGENCY['site_url']}.\n"
        f"Unsubscribe: {AGENCY['site_url']}/unsubscribe?t={token}\n"
        f"This email is general education, not insurance advice, and is not an "
        f"offer of coverage. Policy terms govern."
    )


def render_sequence(lead: dict[str, Any]) -> list[dict[str, str]]:
    """Return six ready-to-send emails personalized to this lead."""
    name = (lead.get("first_name") or "").strip() or "there"
    token = lead["token"]
    result = lead.get("result") or {}
    gaps = result.get("gaps") or []
    score = result.get("score", 0)
    band = result.get("band", "")
    total_gap = result.get("total_dollar_gap", 0) or 0
    life_gap = result.get("life_gap", 0) or 0
    report_url = f"{AGENCY['site_url']}/report?t={token}"

    top = gaps[0] if gaps else None
    second = gaps[1] if len(gaps) > 1 else None
    top_title = top["title"].lower() if top else "your coverage mix"
    top_fix = top["fix"] if top else "Keep your limits current as your income grows."

    emails: list[dict[str, str]] = []

    # 1 - deliver instantly. Nothing else. Delivery emails get opened.
    emails.append({
        "step": "1",
        "subject": f"Your Coverage Gap Report ({score}/100)",
        "body": (
            f"{name},\n\n"
            f"Here is your report: {report_url}\n\n"
            f"Your protection score came out to {score} out of 100 - "
            f"\"{band}\". The report breaks down every gap we found, what it "
            f"would cost you at claim time, and the specific fix for each one.\n\n"
            f"Bookmark that link. It stays live, so you can pull it up next "
            f"time you review a policy.\n\n"
            f"- {AGENCY['agent_name']}"
            + _signature(token)
        ),
    })

    # 2 - the single biggest gap, explained. Teach, do not pitch.
    if top:
        body2 = (
            f"{name},\n\n"
            f"Of everything in your report, one line matters more than the "
            f"rest: {top_title}.\n\n"
            f"{top['finding']}\n\n"
            f"Here is what I would do about it:\n{top_fix}\n\n"
            f"That is the whole email. No pitch. If you want to talk it "
            f"through, reply and tell me what your current policy says - I "
            f"read every reply myself.\n\n"
            f"- {AGENCY['agent_name']}"
        )
    else:
        body2 = (
            f"{name},\n\n"
            f"Your report came back clean, which is rare. The risk for you is "
            f"not a missing policy - it is limits that quietly fall behind your "
            f"income and your assets.\n\n"
            f"Put a 20-minute review on the calendar every January. Compare "
            f"your liability limits to your net worth and your life coverage to "
            f"your mortgage balance. If both still line up, you are done.\n\n"
            f"- {AGENCY['agent_name']}"
        )
    emails.append({
        "step": "2",
        "subject": f"The one line in your report I'd fix first",
        "body": body2 + _signature(token),
    })

    # 3 - story / proof. Social proof without naming clients.
    emails.append({
        "step": "3",
        "subject": "The $9 mistake that costs families the house",
        "body": (
            f"{name},\n\n"
            f"The most expensive insurance mistake I see is not a missing "
            f"policy. It is a limit nobody looked at.\n\n"
            f"A family carries state-minimum auto liability to save about $9 a "
            f"month. They cause a three-car accident. The medical bills clear "
            f"their limit in an afternoon, and the balance follows them - wage "
            f"garnishment, liens, years of it.\n\n"
            f"Nothing about that is exotic. It is the default setting on a "
            f"policy nobody re-read after they bought it.\n\n"
            f"Your report flagged "
            f"{_money(total_gap)} in total exposure across "
            f"{len(gaps)} area{'s' if len(gaps) != 1 else ''}. "
            f"Pull it back up here: {report_url}\n\n"
            f"- {AGENCY['agent_name']}"
            + _signature(token)
        ),
    })

    # 4 - objection handling: cost.
    emails.append({
        "step": "4",
        "subject": "\"I can't afford more coverage right now\"",
        "body": (
            f"{name},\n\n"
            f"I hear that constantly, and usually the person is right about "
            f"their budget and wrong about the math.\n\n"
            f"Three moves that add coverage without adding cost:\n\n"
            f"1. Raise deductibles you can actually cover. Going from $500 to "
            f"$1,000 on auto and home often frees $15-40/month. Only do this "
            f"once your emergency fund can absorb it.\n\n"
            f"2. Bundle and re-shop together, not separately. Carriers price "
            f"the household, not the policy.\n\n"
            f"3. Buy term where you were quoted permanent. If your gap is "
            f"{_money(life_gap) if life_gap else 'six figures'} and temporary - "
            f"until the mortgage is paid or the kids are grown - term is the "
            f"honest product for it.\n\n"
            f"Most people close their biggest gap for less than what they "
            f"already spend on streaming.\n\n"
            f"- {AGENCY['agent_name']}"
            + _signature(token)
        ),
    })

    # 5 - the soft ask. First explicit call to action in the sequence.
    second_line = (
        f" and {second['title'].lower()}" if second else ""
    )
    emails.append({
        "step": "5",
        "subject": f"Want me to look at your actual policy?",
        "body": (
            f"{name},\n\n"
            f"Your report is built from ten answers. Your declarations page has "
            f"about forty numbers on it, and that is where the real gaps hide - "
            f"exclusions, coinsurance clauses, riders that lapsed.\n\n"
            f"If it is useful: {config.cta(AGENCY)['offer']} "
            f"and I will read them with you "
            f"and tell you plainly which of your current policies I would "
            f"leave alone. Most reviews end with me telling someone to change "
            f"nothing.\n\n"
            f"For you I would want to look at {top_title}{second_line}.\n\n"
            f"No cost, no obligation, and I am not going to chase you.\n\n"
            f"- {AGENCY['agent_name']}"
            + _signature(token)
        ),
    })

    # 6 - permission to leave. Cleans the list and converts fence-sitters.
    emails.append({
        "step": "6",
        "subject": "Last one from me (unless you want more)",
        "body": (
            f"{name},\n\n"
            f"That is the end of the sequence you signed up for. From here I "
            f"send one short email a month - a claim I saw, a coverage rule "
            f"that surprised someone, a rate change worth knowing about. No "
            f"pitches.\n\n"
            f"If that is not useful, unsubscribe below and we are square. No "
            f"hard feelings and no re-adds.\n\n"
            f"If it is, do one thing this week: open your auto declarations "
            f"page and read the liability line. It takes ninety seconds and it "
            f"is the number most likely to matter.\n\n"
            f"Your report stays live here: {report_url}\n\n"
            f"- {AGENCY['agent_name']}"
            + _signature(token)
        ),
    })

    return emails


def schedule_for(
    lead: dict[str, Any], start: datetime | None = None
) -> list[tuple[int, str, str, str]]:
    """Produce (step, subject, body, send_after_iso) tuples for storage.enqueue."""
    start = start or datetime.now(timezone.utc)
    out = []
    for email in render_sequence(lead):
        step = int(email["step"])
        send_after = start + timedelta(days=SCHEDULE.get(step, 0))
        out.append((step, email["subject"], email["body"],
                    send_after.isoformat(timespec="seconds")))
    return out
