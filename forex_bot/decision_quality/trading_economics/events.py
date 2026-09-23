"""Documented US target families and request plans. No invented REST paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

# Official REST host documented at docs.tradingeconomics.com.
API_HOST = "https://api.tradingeconomics.com"

# Docs checked 2026-09-23. Indicator/group slugs are those shown in official
# calendar pages / MCP tool examples — not scraped live event names.
#
# inflation rate  — docs.tradingeconomics.com/economic_calendar/country/
#                   and docs.tradingeconomics.com/mcp/tools/ (get_calendar_by_indicator)
# non farm payrolls — schema example URL /united-states/non-farm-payrolls
#                     (space form matches documented "initial jobless claims")
# interest rate   — documented calendar group
FAMILY_CPI = "cpi"
FAMILY_NFP = "nfp"
FAMILY_FOMC = "fomc"

# Local post-filters applied AFTER a documented range response. They do not
# invent endpoints; they only classify rows we already retrieved.
CPI_NAME_HINTS = ("cpi", "consumer price", "inflation rate")
NFP_NAME_HINTS = ("non farm payroll", "nonfarm payroll", "employment situation")
FOMC_NAME_HINTS = ("fed interest rate", "federal funds", "fomc", "fed rate decision")


@dataclass(frozen=True)
class TargetFamily:
    family_id: str
    label: str
    country: str
    path_kind: str  # "indicator" | "group"
    slug: str
    local_name_hints: tuple[str, ...]


TARGETS: tuple[TargetFamily, ...] = (
    TargetFamily(
        FAMILY_CPI,
        "US CPI / inflation-rate calendar family",
        "united states",
        "indicator",
        "inflation rate",
        CPI_NAME_HINTS,
    ),
    TargetFamily(
        FAMILY_NFP,
        "US Non-Farm Payrolls / Employment Situation family",
        "united states",
        "indicator",
        "non farm payrolls",
        NFP_NAME_HINTS,
    ),
    TargetFamily(
        FAMILY_FOMC,
        "US FOMC / Fed interest-rate family",
        "united states",
        "group",
        "interest rate",
        FOMC_NAME_HINTS,
    ),
)


@dataclass(frozen=True)
class PlannedRequest:
    family_id: str
    method: str
    path: str
    query: dict[str, str]
    country: str
    start: str
    end: str
    slug: str
    path_kind: str
    destination_raw_glob: str
    notes: str


def _enc_segment(text: str) -> str:
    return str(text).strip().replace(" ", "%20")


def calendar_path(family: TargetFamily, start: str, end: str) -> str:
    country = _enc_segment(family.country)
    slug = _enc_segment(family.slug)
    if family.path_kind == "group":
        return f"/calendar/country/{country}/group/{slug}/{start}/{end}"
    return f"/calendar/country/{country}/indicator/{slug}/{start}/{end}"


def calendarid_path(calendar_id: str) -> str:
    return f"/calendar/calendarid/{_enc_segment(calendar_id)}"


def snapshot_path() -> str:
    return "/calendar"


def public_url(req: PlannedRequest) -> str:
    from urllib.parse import urlencode

    query = urlencode(req.query)
    return f"{API_HOST}{req.path}" + (f"?{query}" if query else "")


def plan_requests(
    *,
    start: str,
    end: str,
    families: tuple[TargetFamily, ...] = TARGETS,
    values: bool = True,
    dest_root: str = "data/research/trading_economics/raw",
) -> list[PlannedRequest]:
    out: list[PlannedRequest] = []
    for fam in families:
        path = calendar_path(fam, start, end)
        query = {"f": "json"}
        if values:
            query["values"] = "true"
        out.append(
            PlannedRequest(
                family_id=fam.family_id,
                method="GET",
                path=path,
                query=query,
                country=fam.country,
                start=start,
                end=end,
                slug=fam.slug,
                path_kind=fam.path_kind,
                destination_raw_glob=f"{dest_root}/{fam.family_id}_*.json",
                notes=(
                    "Documented country+date-range calendar. "
                    "Official PIT page uses this same URL shape. "
                    "Local name hints applied after download."
                ),
            )
        )
    return out


HORIZON_MONTHS = {
    "sample": 18,
    "3m": 3,
    "1y": 12,
    "3y": 36,
    "5y": 60,
}


def horizon_window(profile: str, *, now_utc: datetime | None = None) -> tuple[str, str]:
    """Closed UTC date window ending yesterday. Months are calendar-month counts."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    months = HORIZON_MONTHS[profile]
    end = now.date()
    y, m = end.year, end.month - months
    while m <= 0:
        y -= 1
        m += 12
    start = datetime(y, m, 1, tzinfo=timezone.utc).date()
    return start.isoformat(), end.isoformat()


def request_count_note(n_requests: int) -> dict[str, Any]:
    return {
        "planned_requests": n_requests,
        "lower_bound": n_requests,
        "upper_bound": None,
        "upper_bound_reason": (
            "Official changelog states calendar responses are limited to "
            "'top limit rows by calendar role' but does not publish the number "
            "or a pagination cursor. If a live response is truncated, the "
            "range must be split. Until that is observed, only the lower bound "
            "is known."
        ),
        "trial_request_cap_documented": 100,
        "trial_datapoint_cap_documented": 100000,
        "trial_cap_source": "https://tradingeconomics.com/api/pricing.aspx",
    }


def plan_as_dict(req: PlannedRequest) -> dict[str, Any]:
    return asdict(req)
