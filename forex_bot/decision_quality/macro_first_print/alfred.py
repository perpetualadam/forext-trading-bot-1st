"""ALFRED / FRED is SECONDARY validation only.

Stage 1 does not call ALFRED or FRED. Current FRED observations are revised
series and are never written into first-print fields.

What ALFRED can independently validate later (vintage date, not clock):
- UNRATE first-release vintages vs unemployment_rate_first_print
- CPIAUCSL / CPILFESL first-release *index levels* (not the news-release MoM/YoY percents)
- CES earnings series first-release levels

What ALFRED cannot validate as a substitute for the BLS news release:
- The headline NFP *change* printed in The Employment Situation (PAYEMS is a level)
- Intra-day 08:30 ET publication clocks (ALFRED realtime_start is a date)
- A missing archived BLS HTML/TXT/PDF release

Do not replace a missing historical release with today's FRED value.
"""

from __future__ import annotations

ALFRED_SECONDARY_SERIES = {
    "UNRATE": "unemployment rate level; first-release vintage may match news-release rate",
    "CPIAUCSL": "CPI-U SA index level; not the printed MoM/YoY percent",
    "CPILFESL": "core CPI SA index level; not the printed MoM/YoY percent",
    "PAYEMS": "total nonfarm employment LEVEL; not the printed monthly change",
    "CES0500000003": "average hourly earnings level; YoY/MoM still need the release text",
}

ALFRED_USED_AS_FIRST_PRINT = False
FRED_CURRENT_USED_AS_FIRST_PRINT = False
