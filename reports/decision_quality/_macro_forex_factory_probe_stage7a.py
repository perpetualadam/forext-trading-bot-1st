"""Stage 7A: Forex Factory official weekly Calendar export capability probe.

Research-only. Isolated from live collection. Never writes real observations.
Does not scrape HTML. Does not enable autonomous collection or the Windows task.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

UTC = timezone.utc
SCHEME = "https"
HOST = "nfs.faireconomy.media"
PATH = "/ff_calendar_thisweek.json"
EXPORT_URL = "%s://%s%s" % (SCHEME, HOST, PATH)
TIMEOUT_SEC = 30
TARGET_DATE = "2026-10-02"
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective/probes")
CONFIG_PATH = Path("data/research/macro/consensus_pit/prospective/config.json")
REGISTRY_PATH = Path("data/research/macro/consensus_pit/prospective/source_registry/sources.json")
FORWARD_FLAG = "FORWARD_CONSENSUS_COLLECTION_ENABLED"
SANITIZED_NAME = "forex_factory_stage7a.sanitized.json"
META_NAME = "forex_factory_stage7a.meta.json"

# Official Weekly Export links are published on Forex Factory's own calendar UI
# as ICS/CSV/JSON/XML. Hosted by Fair Economy, Inc. (same FEI as Forex Factory).
# This is an export download, not an HTML scrape and not an undocumented AJAX path.
OFFICIAL_EXPORT = {
    "identified": True,
    "type": "weekly_calendar_json_export",
    "host": HOST,
    "path": PATH,
    "url": EXPORT_URL,
    "credential_required": False,
    "html_scraping": False,
}

# Field-name candidates are inspected, never assumed to exist.
LABEL_KEYS = ("title", "Title", "name", "Name", "event", "Event")
COUNTRY_KEYS = ("country", "Country", "currency", "Currency")
DATE_KEYS = ("date", "Date")
TIME_KEYS = ("time", "Time")
IMPACT_KEYS = ("impact", "Impact")
FORECAST_KEYS = ("forecast", "Forecast")
PREVIOUS_KEYS = ("previous", "Previous")
ACTUAL_KEYS = ("actual", "Actual")
TZ_KEYS = ("timezone", "Timezone", "timeZone", "tz", "TZ", "utcOffset", "UTCOffset")
FORBIDDEN_SUBSTITUTES = (
    "adp",
    "jobless claims",
    "initial claims",
    "private payroll",
    "participation rate",
    "jolts",
)
SERIES_ORDER = (
    "nonfarm_payroll_change",
    "unemployment_rate",
    "average_hourly_earnings_mom",
    "average_hourly_earnings_yoy",
)
SERIES_LABEL = {
    "nonfarm_payroll_change": "NFP",
    "unemployment_rate": "UNEMPLOYMENT",
    "average_hourly_earnings_mom": "AHE_MOM",
    "average_hourly_earnings_yoy": "AHE_YOY",
}

# Notices: FEED copying/republication/redistribution is prohibited. Export existence
# is not a license. Automation is not explicitly granted.
PERMISSIONS = {
    "automated_retrieval": "NOT_CONFIRMED",
    "local_private_retention": "NOT_CONFIRMED",
    "redistribution": "RESTRICTED",
}


class RequestGuard:
    """Hard cap. A second call fails closed without opening a socket."""

    def __init__(self, maximum: int = 1):
        self.maximum = maximum
        self.count = 0

    def authorize(self) -> None:
        if self.count >= self.maximum:
            raise RuntimeError("FF_REQUEST_GUARD: request #%s rejected" % (self.count + 1))
        self.count += 1


class ProbeClosed(RuntimeError):
    pass


def public_request_spec() -> dict[str, Any]:
    return {
        "scheme": SCHEME,
        "host": HOST,
        "path": PATH,
        "query_parameter_names": [],
        "credential_required": False,
        "html_scraping": False,
        "fallback_html": False,
    }


def first_present(row: dict, names: tuple[str, ...]) -> tuple[str | None, Any]:
    keys = {str(k).lower(): k for k in row.keys()}
    for name in names:
        actual = keys.get(name.lower())
        if actual is not None:
            return actual, row.get(actual)
    return None, None


def display_value(value: Any) -> str:
    if value in (None, ""):
        return "BLANK"
    return str(value)


def returned_field_names(rows: list[dict]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            names.update(str(k) for k in row.keys())
    return sorted(names)


def classify_timezone(rows: list[dict]) -> str:
    for row in rows:
        if not isinstance(row, dict):
            continue
        tz_key, tz_val = first_present(row, TZ_KEYS)
        if tz_key and tz_val not in (None, ""):
            return "TIMEZONE_FIELD_PRESENT:%s" % tz_key
        for key in TIME_KEYS + DATE_KEYS:
            raw = str(row.get(key) or "")
            if raw.endswith("Z") or "+" in raw[1:] or "UTC" in raw.upper():
                return "OFFSET_OR_UTC_TOKEN_IN_TIMESTAMP"
    return "UNSPECIFIED_OR_USER_LOCALIZED"


def refuse_silent_utc_conversion(semantics: str, raw_time: Any) -> None:
    if semantics.startswith("UNSPECIFIED") or semantics.startswith("AMBIGUOUS"):
        raise ProbeClosed("TIMEZONE_AMBIGUOUS: refusing silent UTC conversion of %r" % (raw_time,))


def is_united_states(row: dict) -> bool:
    _, value = first_present(row, COUNTRY_KEYS)
    text = str(value or "").strip().lower()
    return text in {"united states", "us", "usa", "usd"}


def date_matches_target(row: dict) -> bool:
    _, value = first_present(row, DATE_KEYS)
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "2026-10-02",
            "10-02-2026",
            "10/02/2026",
            "oct 2, 2026",
            "oct 02, 2026",
            "october 2, 2026",
            "october 02, 2026",
            "2 oct 2026",
            "02 oct 2026",
        )
    )


def map_employment_title(title: str) -> str | None:
    n = (title or "").strip().lower()
    if not n:
        return None
    if any(tok in n for tok in FORBIDDEN_SUBSTITUTES):
        return None
    if "unemployment" in n and "rate" in n:
        return "unemployment_rate"
    if "average hourly" in n and ("y/y" in n or "yoy" in n or "year" in n):
        return "average_hourly_earnings_yoy"
    if "average hourly" in n and ("m/m" in n or "mom" in n or "month" in n):
        return "average_hourly_earnings_mom"
    compact = n.replace(" ", "").replace("-", "")
    if "nonfarm" in compact and ("payroll" in compact or "employment" in compact):
        return "nonfarm_payroll_change"
    return None


def inspect_employment_rows(rows: list[dict]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not is_united_states(row) or not date_matches_target(row):
            continue
        label_key, label = first_present(row, LABEL_KEYS)
        series = map_employment_title(str(label or ""))
        if series is None or series in found:
            continue
        f_key, forecast = first_present(row, FORECAST_KEYS)
        p_key, previous = first_present(row, PREVIOUS_KEYS)
        a_key, actual = first_present(row, ACTUAL_KEYS)
        _, impact = first_present(row, IMPACT_KEYS)
        _, date = first_present(row, DATE_KEYS)
        _, time_val = first_present(row, TIME_KEYS)
        _, country = first_present(row, COUNTRY_KEYS)
        found[series] = {
            "returned_event_name": label,
            "label_field": label_key,
            "country_currency": country,
            "date": date,
            "time": time_val,
            "impact": impact,
            "forecast": forecast,
            "forecast_field": f_key,
            "forecast_display": display_value(forecast),
            "previous": previous,
            "previous_field": p_key,
            "previous_display": display_value(previous),
            "actual": actual,
            "actual_field": a_key,
            "forecast_replaced_with_previous": False,
            "forecast_fabricated": False,
        }
    return found


def parse_export_body(body: bytes) -> list[dict]:
    text = body.decode("utf-8", errors="replace").lstrip()
    if text.lower().startswith("<!doctype") or text.lower().startswith("<html"):
        raise ProbeClosed("PARSE_FAILED: HTML body received; HTML scraping fallback is forbidden")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeClosed("PARSE_FAILED: malformed json") from exc
    if isinstance(payload, dict):
        for key in ("events", "data", "calendar", "rows"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ProbeClosed("PARSE_FAILED: calendar payload is not a list")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            raise ProbeClosed("PARSE_FAILED: row is not an object")
        rows.append(item)
    return rows


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _urllib_transport(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    if url.rstrip("/") != EXPORT_URL:
        raise ProbeClosed("REFUSED: only the official weekly JSON export URL is permitted")
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            return int(resp.status), resp.read() or b"", {k: str(v) for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read() or b""
        return int(exc.code), body, {k: str(v) for k, v in (exc.headers.items() if exc.headers else [])}


def run_probe(
    *,
    dest: Path,
    transport: Callable | None = None,
    live: bool = False,
    guard: RequestGuard | None = None,
    clock: Callable | None = None,
) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    guard = guard or RequestGuard(1)
    now = (clock or datetime.now)(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    observed_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec = public_request_spec()
    report = {
        "kind": "FF_CALENDAR_STAGE7A_PROBE",
        "stage": "7A",
        "live": live,
        "provider": "forex_factory",
        "official_export_identified": True,
        "official_export_type": OFFICIAL_EXPORT["type"],
        "official_export_host": HOST,
        "official_export_path": PATH,
        "html_scraping_used": False,
        "credential_required": False,
        "query_parameter_names": spec["query_parameter_names"],
        "request_count": 0,
        "entered_observations": False,
        "real_checkpoint_created": False,
        "http_status": None,
        "result": "NOT_ATTEMPTED",
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "forecast_semantics": "CONSENSUS_LIKE_NOT_CONFIRMED",
        "event_timezone_semantics": "UNSPECIFIED_OR_USER_LOCALIZED",
        "permissions": PERMISSIONS,
        "archival_permission": "NOT_CONFIRMED",
    }
    if not live:
        report["result"] = "DRY_RUN_NO_NETWORK"
        _write_outputs(dest, report, None)
        return report

    guard.authorize()
    headers = {"Accept": "application/json"}
    send = transport or _urllib_transport
    try:
        status, body, resp_headers = send(EXPORT_URL, headers)
    except TimeoutError:
        report["request_count"] = guard.count
        report["result"] = "TIMEOUT"
        _write_outputs(dest, report, None)
        return report
    except OSError as exc:
        report["request_count"] = guard.count
        report["result"] = "NETWORK_ERROR"
        report["error"] = str(exc)
        _write_outputs(dest, report, None)
        return report

    report["request_count"] = guard.count
    report["http_status"] = status
    header_names = sorted({k.lower() for k in resp_headers})
    if status >= 400:
        report["result"] = "ACCESS_DENIED" if status in (401, 403) else "HTTP_%s" % status
        report["records_returned"] = 0
        report["returned_field_names"] = []
        report["forecast_field_present"] = False
        report["previous_field_present"] = False
        report["actual_field_present"] = False
        fail = _failure_artifact(status, observed_at, header_names)
        digest = _persist_artifact(dest, fail, report)
        _write_outputs(dest, report, digest)
        return report
    try:
        rows = parse_export_body(body)
    except ProbeClosed as exc:
        report["result"] = str(exc)
        fail = _failure_artifact(status, observed_at, header_names)
        fail["result"] = str(exc)
        digest = _persist_artifact(dest, fail, report)
        _write_outputs(dest, report, digest)
        return report

    fields = returned_field_names(rows)
    tz_semantics = classify_timezone(rows)
    employment = inspect_employment_rows(rows)
    artifact = {
        "kind": "FF_CALENDAR_SANITIZED_RESPONSE",
        "stage": "7A",
        "provider": "forex_factory",
        "official_export_host": HOST,
        "official_export_path": PATH,
        "probe_started_at_utc": observed_at,
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "http_status": status,
        "credential_required": False,
        "official_export_status": "IDENTIFIED_WEEKLY_JSON",
        "returned_field_names": fields,
        "records_returned": len(rows),
        "forecast_field_present": any(k.lower() == "forecast" for k in fields),
        "previous_field_present": any(k.lower() == "previous" for k in fields),
        "actual_field_present": any(k.lower() == "actual" for k in fields),
        "forecast_semantics": "CONSENSUS_LIKE_NOT_CONFIRMED",
        "event_timezone_semantics": tz_semantics,
        "identified_targets": [{**employment[s], "series": s} for s in SERIES_ORDER if s in employment],
        "rows": rows,
        "real_checkpoint_created": False,
        "response_header_names": header_names,
        "permissions": PERMISSIONS,
    }
    digest = _persist_artifact(dest, artifact, report)
    report.update(
        {
            "result": "SUCCESS",
            "records_returned": len(rows),
            "returned_field_names": fields,
            "forecast_field_present": artifact["forecast_field_present"],
            "previous_field_present": artifact["previous_field_present"],
            "actual_field_present": artifact["actual_field_present"],
            "event_timezone_semantics": tz_semantics,
            "employment": employment,
        }
    )
    _write_outputs(dest, report, digest)
    return report


def _failure_artifact(status: int, observed_at: str, header_names: list[str]) -> dict:
    return {
        "kind": "FF_CALENDAR_SANITIZED_RESPONSE",
        "stage": "7A",
        "provider": "forex_factory",
        "official_export_host": HOST,
        "official_export_path": PATH,
        "probe_started_at_utc": observed_at,
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "http_status": status,
        "credential_required": False,
        "official_export_status": "IDENTIFIED_WEEKLY_JSON",
        "returned_field_names": [],
        "records_returned": 0,
        "identified_targets": [],
        "rows": [],
        "real_checkpoint_created": False,
        "response_header_names": header_names,
        "permissions": PERMISSIONS,
    }


def _persist_artifact(dest: Path, artifact: dict, report: dict) -> str:
    raw = json.dumps(artifact, indent=2, ensure_ascii=True) + "\n"
    digest = sha256_bytes(raw.encode("utf-8"))
    path = dest / SANITIZED_NAME
    path.write_bytes(raw.encode("utf-8"))
    report["artifact_path"] = str(path).replace("\\", "/")
    report["artifact_sha256"] = digest
    return digest


def _write_outputs(dest: Path, report: dict, digest: str | None) -> None:
    meta = dict(report)
    meta.pop("error", None)
    meta.pop("employment", None)
    path = dest / META_NAME
    path.write_bytes((json.dumps(meta, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))


def assert_scheduler_and_sources_unchanged() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if cfg.get(FORWARD_FLAG) is True:
        raise ProbeClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED must remain false")
    blob = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    ids = [s.get("source_id") for s in blob.get("sources", [])]
    if "forex_factory" in ids:
        raise ProbeClosed("forex_factory must not be added to the live source registry in Stage 7A")
    for src in blob.get("sources", []):
        if src.get("source_id") == "trading_economics":
            if src.get("enabled") is True:
                raise ProbeClosed("trading_economics must remain disabled")
            if src.get("automation_class") == "APPROVED_AUTOMATION_READY":
                raise ProbeClosed("trading_economics must not be APPROVED_AUTOMATION_READY")


def _safe_print(report: dict) -> None:
    keys = (
        "result",
        "http_status",
        "official_export_identified",
        "official_export_host",
        "official_export_path",
        "html_scraping_used",
        "request_count",
        "records_returned",
        "returned_field_names",
        "forecast_field_present",
        "previous_field_present",
        "actual_field_present",
        "event_timezone_semantics",
        "observed_at_utc",
        "artifact_path",
        "artifact_sha256",
        "real_checkpoint_created",
    )
    for key in keys:
        print("%s=%s" % (key, report.get(key)))
    employment = report.get("employment") or {}
    for series in SERIES_ORDER:
        item = employment.get(series)
        label = SERIES_LABEL[series]
        if not item:
            print("%s_FOUND=NO" % label)
            continue
        print("%s_FOUND=YES" % label)
        print("%s_RETURNED_NAME=%s" % (label, item.get("returned_event_name")))
        print("%s_FORECAST=%s" % (label, item.get("forecast_display")))
        print("%s_PREVIOUS=%s" % (label, item.get("previous_display")))


if __name__ == "__main__":
    import sys

    dest = Path(sys.argv[sys.argv.index("--dest") + 1]) if "--dest" in sys.argv else PROBE_DIR
    live = "--live" in sys.argv
    out = run_probe(dest=dest, live=live)
    _safe_print(out)
