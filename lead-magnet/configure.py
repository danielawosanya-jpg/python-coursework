#!/usr/bin/env python3
"""Fill in your agency details.

    python3 configure.py                              # interactive, all fields
    python3 configure.py --set calendar_url=https://calendar.app.google/abc
    python3 configure.py --show                       # print current values

Writes agency.json, which every email signature, the report footer and the
landing page footer read from. Run preflight.py afterwards to confirm nothing
is left as a placeholder.

Values here appear in public marketing and in email headers, so they must be
your real, current details - the name on your license, the license number, and
a physical postal address that receives mail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from leadmagnet import config  # noqa: E402

ORDER = [
    "agent_name", "agency_name", "license", "states_licensed",
    "phone", "mailing_address", "site_url", "calendar_url",
]


def show(current: dict[str, str]) -> int:
    width = max(len(k) for k in ORDER)
    for key in ORDER:
        mark = "  " if current[key] != config.DEFAULTS[key] else "! "
        print(f"  {mark}{key:<{width}}  {current[key]}")
    remaining = config.placeholders_remaining(current)
    print(f"\n  {len(remaining)} field(s) still unset."
          if remaining else "\n  All fields set.")
    return 0


def set_fields(assignments: list[str], current: dict[str, str]) -> int:
    """Non-interactive updates: --set key=value, repeatable."""
    updated = dict(current)
    for assignment in assignments:
        key, sep, value = assignment.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not value:
            print(f"  Expected key=value, got {assignment!r}", file=sys.stderr)
            return 1
        if key not in config.DEFAULTS:
            print(f"  Unknown field {key!r}. Valid fields: "
                  f"{', '.join(ORDER)}", file=sys.stderr)
            return 1
        updated[key] = value
        print(f"  {key} -> {value}")

    config.save(updated)
    print(f"\n  Written to {config.CONFIG_PATH}")
    remaining = config.placeholders_remaining(config.load())
    if remaining:
        print(f"  Still unset: {', '.join(remaining)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="assignments", action="append", default=[],
                        metavar="KEY=VALUE",
                        help="set one field without the prompts; repeatable")
    parser.add_argument("--show", action="store_true",
                        help="print current values and exit")
    args = parser.parse_args()

    if args.show:
        return show(config.load())
    if args.assignments:
        return set_fields(args.assignments, config.load())

    current = config.load()
    configured = config.is_configured(current)

    print("\nCoverage Gap Finder - agency details")
    print("=" * 52)
    if configured:
        print("agency.json is already filled in. Press Enter to keep a value.\n")
    else:
        print("These appear in public marketing and in every email you send.")
        print("Use your real, current details.\n")

    values: dict[str, str] = {}
    for key in ORDER:
        existing = current[key]
        is_placeholder = existing == config.DEFAULTS[key]
        print(f"  {config.FIELD_HELP[key]}")
        prompt = f"  {key}"
        prompt += " []: " if is_placeholder else f" [{existing}]: "
        try:
            entered = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled. Nothing written.")
            return 1
        if not entered and is_placeholder:
            print("  (left unset - preflight will flag it)\n")
            values[key] = existing
            continue
        values[key] = entered or existing
        print()

    config.save(values)
    print(f"Written to {config.CONFIG_PATH}\n")

    remaining = config.placeholders_remaining(config.load())
    if remaining:
        print(f"Still unset: {', '.join(remaining)}")
        print("Run configure.py again, or edit agency.json directly.")
        return 1

    print("All fields set. Next: python3 preflight.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
