"""One source of truth for the agency's details.

Every legally-significant string in this system - the producer name, the
license number, the physical address CAN-SPAM requires in each email - lives
in `agency.json` and is loaded here. Nothing else should hard-code them.

The shipped `agency.json` is all placeholders on purpose. `preflight.py`
refuses to declare the system launch-ready while any of them remain, because
publishing a made-up license number or mailing address is a regulatory
problem, not a cosmetic one.

    python3 configure.py     # fill it in interactively
    python3 preflight.py     # verify nothing is left as a placeholder
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "agency.json"

# Every field is required. The values here are the shipped placeholders, and
# they are what preflight.py looks for.
DEFAULTS: dict[str, str] = {
    "agent_name": "[Your Name]",
    "agency_name": "[Your Agency]",
    "license": "[State] license #[0000000]",
    "phone": "[555-555-5555]",
    "calendar_url": "https://[your-calendar-link]",
    "site_url": "https://[yourdomain.com]",
    "mailing_address": "[Street, City, ST ZIP]",
    "states_licensed": "[ST, ST]",
}

# What each field is for, shown by configure.py and used in error messages.
FIELD_HELP: dict[str, str] = {
    "agent_name": "Your name exactly as it appears on your license",
    "agency_name": "Agency legal name (a DBA usually needs separate registration)",
    "license": "License number with state, e.g. 'GA license #1234567'",
    "phone": "Business phone shown in the report footer",
    "calendar_url": ("Booking link for the review. A 'mailto:you@example.com' "
                     "address works as a fallback if you have no scheduler yet"),
    "site_url": "Public https URL where this is hosted (no trailing slash)",
    "mailing_address": "Physical postal address - CAN-SPAM requires it in every email",
    "states_licensed": "States you are licensed to solicit in, e.g. 'GA, FL'",
}


def load(path: Path | str = CONFIG_PATH) -> dict[str, str]:
    """Load agency.json, falling back to placeholders for anything missing."""
    config = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as handle:
            stored = json.load(handle)
    except FileNotFoundError:
        return config
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"{path} is not readable JSON: {exc}") from exc

    for key in DEFAULTS:
        value = stored.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = value.strip()
    config["site_url"] = config["site_url"].rstrip("/")
    return config


def save(values: dict[str, str], path: Path | str = CONFIG_PATH) -> None:
    config = {key: str(values.get(key, DEFAULTS[key])).strip() for key in DEFAULTS}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def placeholders_remaining(config: dict[str, str] | None = None) -> list[str]:
    """Field names still holding a shipped placeholder value."""
    config = config if config is not None else load()
    return [key for key, default in DEFAULTS.items() if config.get(key) == default]


def is_configured(config: dict[str, str] | None = None) -> bool:
    return not placeholders_remaining(config)


def as_template_vars(config: dict[str, str] | None = None) -> dict[str, Any]:
    """`{{agent_name}}`-style keys for substitution into the static HTML."""
    config = config if config is not None else load()
    return {"{{" + key + "}}": value for key, value in config.items()}


def cta(config: dict[str, str] | None = None) -> dict[str, str]:
    """How to present the call to action.

    A real scheduler gets a "book a time" button. A `mailto:` fallback has to
    say something honest instead - nobody books a slot by sending an email -
    and in plain-text email it must render as a bare address, because
    "mailto:you@example.com" pasted into a sentence looks broken.
    """
    config = config if config is not None else load()
    href = config["calendar_url"].strip()

    if href.lower().startswith("mailto:"):
        address = href[len("mailto:"):].split("?", 1)[0]
        if "?" not in href:
            href = f"{href}?subject=Policy%20review%20request"
        return {
            "href": href,
            "button": "Email me for a policy review",
            "inline": address,
            # One action, so no "or" branch - a scheduler is what makes the
            # second option distinct, and there isn't one here.
            "offer": f"send your dec pages to {address}",
            "kind": "mailto",
        }

    return {
        "href": href,
        "button": "Book a 20-minute review",
        "inline": href,
        "offer": f"send me your dec pages, or grab 20 minutes here - {href} -",
        "kind": "url",
    }


def render(markup: str, config: dict[str, str] | None = None) -> str:
    """Substitute {{field}} tokens in a page. Unknown tokens are left alone."""
    for token, value in as_template_vars(config).items():
        markup = markup.replace(token, value)
    return markup
