#!/usr/bin/env python3
"""Fill in your agency details.

    python3 configure.py

Writes agency.json, which every email signature, the report footer and the
landing page footer read from. Run preflight.py afterwards to confirm nothing
is left as a placeholder.

Values here appear in public marketing and in email headers, so they must be
your real, current details - the name on your license, the license number, and
a physical postal address that receives mail.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from leadmagnet import config  # noqa: E402

ORDER = [
    "agent_name", "agency_name", "license", "states_licensed",
    "phone", "mailing_address", "site_url", "calendar_url",
]


def main() -> int:
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
