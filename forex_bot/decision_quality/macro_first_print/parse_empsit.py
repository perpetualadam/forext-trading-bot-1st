"""Extract first-print Employment Situation values from an archived BLS release."""

from __future__ import annotations

import re
from typing import Any

from forex_bot.decision_quality.macro_first_print.parse_common import (
    as_text,
    extract_embargo_local,
    extract_usdl,
    parse_payroll,
    parse_percent,
    reference_period_from_title,
    signed_change,
)

_NFP = re.compile(
    r"Total nonfarm payroll employment\s+"
    r"(increased|rose|decreased|fell|declined|was unchanged|changed little|was little changed|edged up|edged down)"
    r"(?:\s+by\s+(?P<n>[\d,]+))?"
    r"(?:[^.]{0,60}?\(\+?(?P<n2>-?[\d,]+)\))?",
    re.I,
)
_UNRATE = re.compile(
    r"unemployment rate(?!s)[^\d]{0,60}(?P<r>\d+\.\d+)\s+percent",
    re.I,
)
_PART = re.compile(
    r"labor force participation rate(?:s)?"
    r"(?:,\s+at\s+|\s+changed little at\s+|\s+\(|\s+was unchanged at\s+|"
    r"\s+decreased by [0-9.]+ percentage point to\s+|\s+increased by [0-9.]+ percentage point to\s+)"
    r"(?P<p>\d+\.\d+)\s*percent",
    re.I,
)
_AHE_MOM = re.compile(
    r"average hourly earnings for all employees on private nonfarm payrolls\s+"
    r"(?:rose|increased|fell|decreased|were unchanged).{0,80}?"
    r"(?:or\s+)?(?P<mom>\d+\.\d+)\s+percent",
    re.I | re.S,
)
_AHE_YOY = re.compile(
    r"Over the past 12 months, average hourly earnings have "
    r"(?P<yoy_verb>increased|decreased|rose|fell)\s+by\s+(?P<yoy>\d+\.\d+)\s+percent",
    re.I,
)
_REV = re.compile(
    r"The change in total nonfarm payroll employment\s+for (?P<m1>[A-Za-z]+)\s+was revised\s+"
    r"(?P<d1>up|down) by (?P<n1>[\d,]+),\s+from\s+\+?(?P<from1>-?[\d,]+)\s+to\s+\+?(?P<to1>-?[\d,]+),\s+"
    r"and the change for (?P<m2>[A-Za-z]+)\s+was revised\s+(?P<d2>up|down) by (?P<n2>[\d,]+),\s+"
    r"from\s+\+?(?P<from2>-?[\d,]+)\s+to\s+\+?(?P<to2>-?[\d,]+)",
    re.I,
)
_TWO = re.compile(
    r"combined is (?P<n>[\d,]+) (?P<dir>lower|higher) than\s+previously reported",
    re.I,
)


def parse_empsit_release(raw: str) -> dict[str, Any]:
    text = as_text(raw)
    locators: list[str] = []
    nfp = None
    nfp_m = _NFP.search(text)
    if nfp_m:
        verb = nfp_m.group(1)
        number = nfp_m.group("n") or nfp_m.group("n2")
        if verb.lower() in ("was unchanged",) and not number:
            nfp = 0
            locators.append("lead:total nonfarm unchanged")
        elif number:
            nfp = signed_change(verb, number)
            locators.append("lead:total nonfarm payroll employment")

    unrate = None
    u = _UNRATE.search(text)
    if u:
        unrate = parse_percent(u.group("r"))
        locators.append("lead:unemployment rate")

    part = None
    p = _PART.search(text)
    if p:
        part = parse_percent(p.group("p"))
        locators.append("lead:labor force participation rate")

    ahe_mom = ahe_yoy = None
    am = _AHE_MOM.search(text)
    if am:
        ahe_mom = parse_percent(am.group("mom"))
        locators.append("lead:average hourly earnings MoM")
    ay = _AHE_YOY.search(text)
    if ay:
        ahe_yoy = parse_percent(ay.group("yoy"))
        if (ay.group("yoy_verb") or "").lower() in ("decreased", "fell") and ahe_yoy is not None:
            ahe_yoy = -abs(ahe_yoy)
        locators.append("lead:average hourly earnings YoY")

    prev_as_presented = prev_rev = two_month = None
    rev = _REV.search(text)
    if rev:
        prev_as_presented = parse_payroll(rev.group("to2"))
        prev_rev = parse_payroll(rev.group("n2"), sign=-1 if rev.group("d2").lower() == "down" else 1)
        locators.append("revision paragraph: prior-month payroll as presented")
    two = _TWO.search(text)
    if two and rev:
        two_month = parse_payroll(two.group("n"), sign=-1 if two.group("dir").lower() == "lower" else 1)

    required = (nfp, unrate)
    present = sum(v is not None for v in required)
    extra = sum(v is not None for v in (ahe_mom, ahe_yoy, part))
    if present == 2 and extra >= 1:
        status = "VERIFIED_FIRST_PRINT"
    elif present:
        status = "PARTIAL"
    else:
        status = "FAILED"

    local, embargo_utc = extract_embargo_local(text)
    return {
        "event_type": "EMPLOYMENT_SITUATION",
        "release_name": "The Employment Situation",
        "reference_period": reference_period_from_title(text, kind="EMPLOYMENT"),
        "release_number": extract_usdl(text),
        "embargo_local": local.isoformat(timespec="seconds") if local else None,
        "embargo_utc": embargo_utc,
        "nfp_first_print": nfp,
        "unemployment_rate_first_print": unrate,
        "ahe_mom_first_print": ahe_mom,
        "ahe_yoy_first_print": ahe_yoy,
        "participation_rate_first_print": part,
        "previous_nfp_as_presented": prev_as_presented,
        "previous_nfp_revision": prev_rev,
        "two_month_nfp_revision": two_month,
        "validation_status": status,
        "extraction_locator": "; ".join(locators) if locators else None,
        "notes": None,
    }
