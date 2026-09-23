"""Extract first-print CPI values from an archived BLS news release."""

from __future__ import annotations

import re
from typing import Any

from forex_bot.decision_quality.macro_first_print.parse_common import (
    as_text,
    extract_embargo_local,
    extract_usdl,
    last_two_floats,
    parse_percent,
    reference_period_from_title,
)

_TWO_MONTH = re.compile(
    r"on a seasonally adjusted basis over the\s+2\s+months",
    re.I,
)
_LEAD_MOM = re.compile(
    r"CPI-U\)?\s+(increased|decreased|rose|fell|was unchanged)\s+"
    r"(?:(?P<mom>\d+\.\d+)\s+percent\s+)?"
    r"on a seasonally adjusted basis\s+in\s+(?P<month>[A-Za-z]+)"
    r"(?:, after (?:rising|increasing|falling|decreasing|a decrease of)\s+(?P<prev_mom>\d+\.\d+)\s+percent)?",
    re.I,
)
_LEAD_YOY = re.compile(
    r"Over the\s+last\s+12\s+months,\s+the all items index\s+(increased|decreased|rose|fell)\s+"
    r"(?P<yoy>\d+\.\d+)\s+percent",
    re.I,
)
_PREV_YOY = re.compile(
    r"after (?:rising|increasing|falling|decreasing)\s+(?P<prev_yoy>\d+\.\d+)\s+percent\s+"
    r"over the 12\s+months ending",
    re.I,
)
_CORE_MOM = re.compile(
    r"(?:The index for )?all items less food and energy\s+"
    r"(increased|decreased|rose|fell|was unchanged)\s+"
    r"(?:(?P<core_mom>\d+\.\d+)\s+percent\s+)?in\s+(?P<month>[A-Za-z]+)",
    re.I,
)
_CORE_YOY = re.compile(
    r"(?:The )?(?:all items less food and energy index|index for all items less food and energy)\s+"
    r"(increased|decreased|rose|fell)\s+(?P<core_yoy>\d+\.\d+)\s+percent "
    r"over the (?:last 12 months|past 12 months)",
    re.I,
)


def _signed_pct(verb: str, number: str | None) -> float | None:
    if verb.lower() == "was unchanged":
        return 0.0
    parsed = parse_percent(number)
    if parsed is None:
        return None
    if verb.lower() in ("decreased", "fell"):
        return -abs(parsed)
    return parsed


def _table_a_row(text: str, label: str) -> tuple[float | None, float | None]:
    want = label.lower()
    idx = text.lower().find("table a")
    block = text[idx : idx + 3000] if idx >= 0 else text[:3000]
    for line in block.splitlines():
        compact = re.sub(r"\s+", " ", line).strip().lstrip("| ").strip()
        low = compact.lower()
        nums = re.findall(r"-?\d+\.\d+", compact)
        if len(nums) < 6:
            continue
        if want == "all items":
            if re.match(r"^all items(?! less)\b", low):
                return last_two_floats(compact)
        elif low.startswith(want):
            return last_two_floats(compact)
    return None, None


def parse_cpi_release(raw: str) -> dict[str, Any]:
    text = as_text(raw)
    locators: list[str] = []
    headline_mom = headline_yoy = core_mom = core_yoy = None
    prev_mom = prev_yoy = None

    two_month = bool(_TWO_MONTH.search(text[:2500]))
    lead = _LEAD_MOM.search(text)
    if lead and not two_month:
        headline_mom = _signed_pct(lead.group(1), lead.group("mom"))
        prev_mom = parse_percent(lead.group("prev_mom"))
        locators.append("lead:CPI-U seasonally adjusted monthly change")
    elif two_month:
        locators.append("lead:two-month change stated; MoM first-print not established")
    yoy = _LEAD_YOY.search(text)
    if yoy:
        headline_yoy = _signed_pct(yoy.group(1), yoy.group("yoy"))
        locators.append("lead:all items 12-month")
    py = _PREV_YOY.search(text)
    if py:
        prev_yoy = parse_percent(py.group("prev_yoy"))
    core_m = _CORE_MOM.search(text)
    if core_m:
        core_mom = _signed_pct(core_m.group(1), core_m.group("core_mom"))
        locators.append("lead:all items less food and energy monthly")
    core_y = _CORE_YOY.search(text)
    if core_y:
        core_yoy = _signed_pct(core_y.group(1), core_y.group("core_yoy"))
        locators.append("lead:all items less food and energy 12-month")

    t_mom, t_yoy = _table_a_row(text, "All items")
    c_mom, c_yoy = _table_a_row(text, "All items less food and energy")
    ambiguous = False
    if t_mom is not None and headline_mom is not None and abs(t_mom - headline_mom) > 1e-9:
        ambiguous = True
    if t_yoy is not None and headline_yoy is not None and abs(t_yoy - headline_yoy) > 1e-9:
        ambiguous = True
    if not two_month:
        if headline_mom is None and t_mom is not None:
            headline_mom = t_mom
            locators.append("Table A: All items last monthly column")
        if core_mom is None and c_mom is not None:
            core_mom = c_mom
            locators.append("Table A: All items less food and energy monthly")
    if headline_yoy is None and t_yoy is not None:
        headline_yoy = t_yoy
        locators.append("Table A: All items 12-month column")
    if core_yoy is None and c_yoy is not None:
        core_yoy = c_yoy
        locators.append("Table A: All items less food and energy 12-month")
    if c_mom is not None and core_mom is not None and abs(c_mom - core_mom) > 1e-9:
        ambiguous = True

    local, embargo_utc = extract_embargo_local(text)
    required = (headline_mom, headline_yoy, core_mom, core_yoy)
    present = sum(v is not None for v in required)
    if two_month:
        status = "AMBIGUOUS"
        notes_extra = "two_month_change_not_standard_mom"
    elif ambiguous:
        status = "AMBIGUOUS"
        notes_extra = "table_vs_lead_mismatch"
    elif present == 4:
        status = "VERIFIED_FIRST_PRINT"
        notes_extra = None
    elif present:
        status = "PARTIAL"
        notes_extra = None
    else:
        status = "FAILED"
        notes_extra = None

    return {
        "event_type": "CPI",
        "release_name": "Consumer Price Index",
        "reference_period": reference_period_from_title(text, kind="CPI"),
        "release_number": extract_usdl(text),
        "embargo_local": local.isoformat(timespec="seconds") if local else None,
        "embargo_utc": embargo_utc,
        "headline_mom_first_print": headline_mom,
        "headline_yoy_first_print": headline_yoy,
        "core_mom_first_print": core_mom,
        "core_yoy_first_print": core_yoy,
        "previous_headline_mom_as_known": prev_mom,
        "previous_headline_yoy_as_known": prev_yoy,
        "validation_status": status,
        "extraction_locator": "; ".join(locators) if locators else None,
        "notes": notes_extra,
    }
