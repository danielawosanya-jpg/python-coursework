#!/usr/bin/env python3
"""Launch gate. Run this before the site is reachable from the internet.

    python3 preflight.py

Checks the things that are expensive to get wrong: an unfilled license number,
a missing CAN-SPAM address, a default admin key, an unset send domain. Exits
non-zero if the system is not safe to put online, so it can gate a deploy.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from leadmagnet import config, storage  # noqa: E402

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def check_agency() -> tuple[str, str]:
    remaining = config.placeholders_remaining()
    if not remaining:
        return PASS, "All agency fields are filled in."
    return FAIL, (
        f"{len(remaining)} field(s) still placeholder: {', '.join(remaining)}. "
        "Run: python3 configure.py"
    )


def check_calendar() -> tuple[str, str]:
    values = config.load()
    link = values["calendar_url"]
    if link == config.DEFAULTS["calendar_url"]:
        return FAIL, "calendar_url is unset; the report has no call to action."
    if config.cta(values)["kind"] == "mailto":
        return WARN, ("Call to action is a mailto: fallback. It works, but a "
                      "scheduler converts better - people book a slot more "
                      "readily than they compose an email.")
    if not link.startswith("https://"):
        return FAIL, f"calendar_url is {link!r} - use an https link or a mailto:."
    if config.looks_like_scheduler(link):
        return PASS, f"Call to action books at {link}"
    return WARN, (f"Call to action points at {link}, which is not a recognised "
                  f"scheduler. Fine if it is your own booking page - just "
                  f"confirm it loads for someone who is not signed in as you.")


def check_site_url() -> tuple[str, str]:
    url = config.load()["site_url"]
    if url == config.DEFAULTS["site_url"]:
        return FAIL, "site_url is unset. Report links in emails will not work."
    if not url.startswith("https://"):
        return FAIL, f"site_url is {url!r} - must be https for a public site."
    return PASS, f"site_url is {url}"


def check_admin_key() -> tuple[str, str]:
    key = os.environ.get("ADMIN_KEY", "changeme")
    if key == "changeme":
        return FAIL, ("ADMIN_KEY is the default. Anyone could read your lead "
                      "list. Set it to a random value.")
    if len(key) < 16:
        return WARN, f"ADMIN_KEY is only {len(key)} characters. Use 24+."
    return PASS, "ADMIN_KEY is set to a non-default value."


# Free mailbox providers publish a strict DMARC policy on their own domains.
# Sending bulk mail as one of these through any other provider fails DMARC
# alignment and is quarantined - it is not a style preference, it is broken.
CONSUMER_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com",
    "proton.me", "protonmail.com", "gmx.com", "mail.com", "zoho.com",
}


def _sender_domain(address: str) -> str:
    """Pull the domain out of either 'a@b.com' or 'Name <a@b.com>'."""
    if "<" in address and ">" in address:
        address = address[address.rfind("<") + 1:address.rfind(">")]
    _, _, domain = address.strip().rpartition("@")
    return domain.strip().lower()


def check_smtp() -> tuple[str, str]:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return WARN, ("SMTP_HOST is not set. The site will capture leads but "
                      "no email will go out until send_worker.py can send.")
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    if not sender:
        return FAIL, "SMTP_HOST is set but neither SMTP_FROM nor SMTP_USER is."

    domain = _sender_domain(sender)
    if domain in CONSUMER_MAIL_DOMAINS:
        return FAIL, (
            f"SMTP_FROM is on {domain}, a consumer mailbox domain. You cannot "
            f"authenticate mail for it, so the sequence will fail DMARC and be "
            f"quarantined. Send as an address on your own domain instead - see "
            f"content/EMAIL-SETUP.md."
        )
    return PASS, f"SMTP configured via {host} as {sender}"


def check_sender_alignment() -> tuple[str, str]:
    """The From domain should match the site domain, or DMARC gets unhappy."""
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    if not sender:
        return WARN, "No sender configured yet; alignment not checked."

    site = config.load()["site_url"]
    if site == config.DEFAULTS["site_url"]:
        return WARN, "site_url is unset; cannot check sender alignment."

    site_domain = site.split("//", 1)[-1].split("/", 1)[0].lower()
    site_domain = site_domain.removeprefix("www.")
    from_domain = _sender_domain(sender)

    if from_domain == site_domain or from_domain.endswith("." + site_domain):
        return PASS, f"Sender {from_domain} aligns with the site domain."
    return WARN, (
        f"You send as {from_domain} but the site is {site_domain}. That works "
        f"if {from_domain} is authenticated, but readers trust a From address "
        f"that matches the link they clicked."
    )


def check_database() -> tuple[str, str]:
    try:
        storage.init_db()
    except Exception as exc:  # noqa: BLE001 - report any failure to the operator
        return FAIL, f"Cannot initialise {storage.DB_PATH}: {exc}"
    if storage.DB_PATH.parent == ROOT / "web":
        return FAIL, "leads.db sits in the web directory and would be servable."
    return PASS, f"Lead database writable at {storage.DB_PATH}"


def check_tests() -> tuple[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode == 0:
        line = result.stderr.strip().splitlines()[0] if result.stderr else "ok"
        return PASS, f"Test suite passes ({line})."
    return FAIL, "Test suite is failing. Fix that before deploying."


def check_compliance_ack() -> tuple[str, str]:
    return WARN, ("Compliance review is a human step. Confirm content/"
                  "COMPLIANCE.md is signed off by your carrier or counsel.")


CHECKS = [
    ("Agency details", check_agency),
    ("Site URL", check_site_url),
    ("Call to action", check_calendar),
    ("Admin key", check_admin_key),
    ("Email sending", check_smtp),
    ("Sender alignment", check_sender_alignment),
    ("Lead database", check_database),
    ("Tests", check_tests),
    ("Compliance sign-off", check_compliance_ack),
]

SYMBOL = {PASS: "  ok  ", WARN: " warn ", FAIL: " FAIL "}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true",
                        help="skip the test suite (used on service start, "
                             "where the config checks are what matter)")
    args = parser.parse_args()

    checks = [c for c in CHECKS if not (args.skip_tests and c[0] == "Tests")]

    print("\nCoverage Gap Finder - preflight")
    print("=" * 68)

    failures = warnings = 0
    for name, check in checks:
        status, detail = check()
        if status == FAIL:
            failures += 1
        elif status == WARN:
            warnings += 1
        print(f"[{SYMBOL[status]}] {name}")
        print(f"          {detail}")

    print("=" * 68)
    if failures:
        print(f"\n{failures} blocking issue(s). Do not put this online yet.\n")
        return 1
    if warnings:
        print(f"\nReady to deploy, with {warnings} thing(s) to confirm above.\n")
        return 0
    print("\nAll checks passed. Ready to deploy.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
