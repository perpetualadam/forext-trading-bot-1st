"""Shared first-print parsers for official BLS news-release text."""

from __future__ import annotations

import re
from datetime import datetime

from forex_bot.decision_quality.macro_first_print.htmlutil import html_to_text
from forex_bot.decision_quality.schedule import local_clock_to_utc

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def as_text(raw: str) -> str:
    if "<html" in raw.lower() or "<table" in raw.lower() or "<p>" in raw.lower():
        return html_to_text(raw)
    return raw


def parse_percent(token: str | None) -> float | None:
    if token is None:
        return None
    text = str(token).strip().replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if abs(value) > 100:
        return None
    return value


def parse_payroll(token: str | None, *, sign: int = 1) -> int | None:
    if token is None:
        return None
    text = str(token).strip().replace(",", "").replace("+", "")
    if text == "":
        return None
    neg = text.startswith("-") or sign < 0
    text = text.lstrip("-")
    if not text.isdigit():
        return None
    value = int(text)
    if value > 5_000_000:
        return None
    return -value if neg else value


def signed_change(verb: str, number: str | None) -> int | None:
    down = verb.lower() in ("decreased", "fell", "declined", "down", "edged down")
    parsed = parse_payroll(number, sign=-1 if down else 1)
    return parsed


def extract_usdl(text: str) -> str | None:
    m = re.search(r"USDL-\d{2}-\d{3,5}", text, re.I)
    return m.group(0).upper() if m else None


def extract_embargo_local(text: str) -> tuple[datetime | None, str | None]:
    """Parse '8:30 a.m. (ET) Wednesday, January 15, 2025' from the embargo line."""
    m = re.search(
        r"8:30\s*a\.m\.\s*\(ET\)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s+(20\d{2})",
        text,
        re.I,
    )
    if not m:
        return None, None
    local = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} 08:30", "%B %d %Y %H:%M")
    utc = local_clock_to_utc(local, "America/New_York")
    return local, utc.isoformat(timespec="seconds") + "Z"


def reference_period_from_title(text: str, *, kind: str) -> str | None:
    if kind == "CPI":
        m = re.search(r"CONSUMER PRICE INDEX\s*[-\u2013]\s*([A-Z]+)\s+(20\d{2})", text, re.I)
    else:
        m = re.search(r"EMPLOYMENT SITUATION\s*[-\u2013]+\s*([A-Z]+)\s+(20\d{2})", text, re.I)
    if not m:
        return None
    name = m.group(1).title()
    year = m.group(2)
    try:
        month = MONTHS.index(name) + 1
    except ValueError:
        return None
    return f"{year}-{month:02d}"


def last_two_floats(line: str) -> tuple[float | None, float | None]:
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", line)]
    if len(nums) < 2:
        return None, None
    return nums[-2], nums[-1]
