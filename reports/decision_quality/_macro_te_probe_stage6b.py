"""Stage 6B: documented Calendar authentication + one-request validation.

Research-only. Never prints credentials. Never writes real observations.
Does not enable autonomous collection or the Windows task.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_AD_PATH = Path(__file__).with_name("_macro_prospective_adapters.py")
_AD_SPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_for_te_probe_6b", _AD_PATH)
A = importlib.util.module_from_spec(_AD_SPEC)
assert _AD_SPEC is not None and _AD_SPEC.loader is not None
_AD_SPEC.loader.exec_module(A)

UTC = timezone.utc
TE_KEY_ENV = A.TE_KEY_ENV
SCHEME = "https"
HOST = "api.tradingeconomics.com"
PATH = "/calendar/country/All/2026-10-02/2026-10-02"
QUERY_PARAM_NAMES = ("c", "f")
TARGET_COUNTRY = "United States"
TARGET_DATE = "2026-10-02"
TIMEOUT_SEC = 30
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective/probes")
REAL_OBS = Path("data/research/macro/consensus_pit/prospective/observations/observations.jsonl")
CONFIG_PATH = Path("data/research/macro/consensus_pit/prospective/config.json")
REGISTRY_PATH = Path("data/research/macro/consensus_pit/prospective/source_registry/sources.json")
FORWARD_FLAG = "FORWARD_CONSENSUS_COLLECTION_ENABLED"
SANITIZED_NAME = "te_calendar_2026-10-02_stage6b.sanitized.json"
META_NAME = "te_calendar_2026-10-02_stage6b.meta.json"

CAPTURE_FIELDS = (
    "CalendarId",
    "Date",
    "Country",
    "Category",
    "Event",
    "Reference",
    "ReferenceDate",
    "Source",
    "Actual",
    "Previous",
    "Forecast",
    "TEForecast",
    "Importance",
    "LastUpdate",
    "Revised",
    "Currency",
    "Unit",
    "Ticker",
    "Symbol",
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

# Offline audit of the Stage 6A request (no network). Host and f=json matched;
# authentication placement and country path did not match the supplied Calendar docs.
STAGE_6A_AUDIT = {
    "scheme": "https",
    "host": "api.tradingeconomics.com",
    "path": "/calendar/country/united%20states/2026-10-02/2026-10-02",
    "query_parameter_names": ["f", "values"],
    "authentication_placement": "Authorization header",
    "output_format_parameter": "f=json",
    "documented_pattern_match": "NO",
    "discrepancy": (
        "Authorization header instead of documented c query parameter; "
        "path /calendar/country/united%20states/{date}/{date} instead of "
        "documented /calendar/country/All/{date}/{date}; extra values=true "
        "query parameter"
    ),
}


class RequestGuard:
    """Hard cap. A second call fails closed without opening a socket."""

    def __init__(self, maximum: int = 1):
        self.maximum = maximum
        self.count = 0

    def authorize(self) -> None:
        if self.count >= self.maximum:
            raise RuntimeError("TE_REQUEST_GUARD: request #%s rejected" % (self.count + 1))
        self.count += 1


class ProbeClosed(RuntimeError):
    def __str__(self) -> str:
        return A.redact(super().__str__())


def read_key(*, env: dict[str, str] | None = None, dotenv_path: Path | None = None) -> str | None:
    if env is not None:
        raw = (env.get(TE_KEY_ENV) or "").strip()
        if raw:
            return raw
        if dotenv_path is None:
            return None
    else:
        raw = (os.environ.get(TE_KEY_ENV) or "").strip()
        if raw:
            return raw
    path = dotenv_path or Path(".env")
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, val = text.partition("=")
        if key.strip() != TE_KEY_ENV:
            continue
        val = val.strip().strip('"').strip("'")
        return val or None
    return None


def credential_configured(*, env: dict[str, str] | None = None, dotenv_path: Path | None = None) -> bool:
    return bool(read_key(env=env, dotenv_path=dotenv_path))


def public_request_spec() -> dict[str, Any]:
    return {
        "scheme": SCHEME,
        "host": HOST,
        "path": PATH,
        "query_parameter_names": list(QUERY_PARAM_NAMES),
        "authentication_placement": "c query parameter",
        "output_format_parameter": "f=json",
        "authorization_header": False,
        "bearer": False,
        "basic": False,
    }


def build_authenticated_url(key: str) -> str:
    """Return the live URL. Caller must not print, log, or persist this value."""
    if not key:
        raise ProbeClosed("CREDENTIAL_REQUIRED")
    query = urllib.parse.urlencode({"c": key, "f": "json"})
    return "%s://%s%s?%s" % (SCHEME, HOST, PATH, query)


def sanitize_obj(obj: Any, secret: str | None) -> Any:
    if secret and isinstance(obj, str):
        return A.redact(obj, secret)
    if isinstance(obj, list):
        return [sanitize_obj(x, secret) for x in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_obj(v, secret) for k, v in obj.items()}
    return obj


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_united_states(row: dict) -> bool:
    return str(row.get("Country") or "").strip().lower() == "united states"


def is_target_date(row: dict) -> bool:
    date = str(row.get("Date") or "")
    ref = str(row.get("ReferenceDate") or "")
    return date.startswith(TARGET_DATE) or ref.startswith(TARGET_DATE)


def capture_row(row: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in CAPTURE_FIELDS:
        if field in row:
            out[field] = row.get(field)
        elif field == "CalendarId" and "CalendarID" in row:
            out["CalendarId"] = row.get("CalendarID")
    return out


def forecast_display(value: Any) -> str:
    if value in (None, ""):
        return "BLANK"
    return str(value)


def map_te_semantics(row: dict, observed_at_utc: str) -> dict[str, Any]:
    forecast = row.get("Forecast")
    te = row.get("TEForecast")
    last_update = row.get("LastUpdate")
    return {
        "SURVEY_CONSENSUS": "SURVEY_CONSENSUS_CURRENTLY_BLANK" if forecast in (None, "") else forecast,
        "PROVIDER_FORECAST": te if te not in (None, "") else "BLANK",
        "PREVIOUS": row.get("Previous"),
        "REVISED_PREVIOUS": row.get("Revised"),
        "ACTUAL": row.get("Actual"),
        "PROVIDER_EVENT_ID": row.get("CalendarId") or row.get("CalendarID"),
        "SOURCE_UPDATED_UTC": last_update,
        "OBSERVED_AT_UTC": observed_at_utc,
        "forecast_blank": forecast in (None, ""),
        "teforecast_substituted_for_forecast": False,
        "last_update_is_not_observed_at": str(last_update or "") != observed_at_utc,
    }


def inspect_employment_rows(rows: list[dict], observed_at_utc: str | None = None) -> dict[str, dict]:
    observed = observed_at_utc or ""
    found: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Event") or "")
        series = A.map_employment_series(name)
        if series is None or series in found:
            continue
        captured = capture_row(row)
        semantics = map_te_semantics(captured, observed)
        found[series] = {
            "event_name": name,
            "calendar_id": semantics["PROVIDER_EVENT_ID"],
            "forecast": captured.get("Forecast"),
            "forecast_present": captured.get("Forecast") not in (None, ""),
            "te_forecast": captured.get("TEForecast"),
            "te_forecast_present": captured.get("TEForecast") not in (None, ""),
            "consensus_display": forecast_display(captured.get("Forecast")),
            "te_forecast_display": forecast_display(captured.get("TEForecast")),
            "fields": captured,
            "semantics": semantics,
        }
    return found


def consensus_and_te_distinct(row: dict) -> bool:
    return "Forecast" in row and "TEForecast" in row


def parse_calendar_body(body: bytes) -> list[dict]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeClosed("PARSE_FAILED: malformed json") from exc
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload = payload["data"]
    if not isinstance(payload, list):
        raise ProbeClosed("PARSE_FAILED: calendar payload is not a list")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            raise ProbeClosed("PARSE_FAILED: row is not an object")
        rows.append(item)
    return rows


def filter_us_target_date(rows: list[dict]) -> list[dict]:
    return [row for row in rows if is_united_states(row) and is_target_date(row)]


def _urllib_transport(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            return int(resp.status), resp.read() or b"", {k: str(v) for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read() or b""
        return int(exc.code), body, {k: str(v) for k, v in (exc.headers.items() if exc.headers else [])}


def credential_leak_scan(paths: list[Path], secret: str | None) -> list[str]:
    leaked: list[str] = []
    if not secret:
        return leaked
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if secret in text:
            leaked.append(str(path).replace("\\", "/"))
    return leaked


def run_probe(
    *,
    dest: Path,
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
    transport: Callable | None = None,
    live: bool = False,
    guard: RequestGuard | None = None,
    clock: Callable | None = None,
) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    guard = guard or RequestGuard(1)
    key = read_key(env=env, dotenv_path=dotenv_path)
    now = (clock or datetime.now)(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    observed_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec = public_request_spec()
    report = {
        "kind": "TE_CALENDAR_STAGE6B_PROBE",
        "stage": "6B",
        "live": live,
        "target_country": TARGET_COUNTRY,
        "target_date": TARGET_DATE,
        "request_host": spec["host"],
        "request_path": spec["path"],
        "query_parameter_names": spec["query_parameter_names"],
        "authentication_method": "c query parameter",
        "stage_6a_audit": STAGE_6A_AUDIT,
        "credential_configured": bool(key),
        "request_count": 0,
        "entered_observations": False,
        "real_checkpoint_created": False,
        "http_status": None,
        "authentication": "NOT_ATTEMPTED",
        "calendar_access": "NOT_CONFIRMED",
        "result": "NOT_ATTEMPTED",
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "forecast_field_semantics": "SURVEY_CONSENSUS",
        "teforecast_field_semantics": "PROVIDER_FORECAST",
        "lastupdate_semantics": "SOURCE_UPDATED_UTC",
        "archival_permission": "NOT_CONFIRMED",
    }
    if not key:
        report["result"] = "CREDENTIAL_REQUIRED"
        _write_outputs(dest, report, None, key)
        return report
    if not live:
        report["result"] = "DRY_RUN_NO_NETWORK"
        _write_outputs(dest, report, None, key)
        return report

    guard.authorize()
    url = build_authenticated_url(key)
    headers = {"Accept": "application/json"}
    send = transport or _urllib_transport
    try:
        status, body, resp_headers = send(url, headers)
    except TimeoutError:
        report["request_count"] = guard.count
        report["result"] = "TIMEOUT"
        report["authentication"] = "FAILED"
        _write_outputs(dest, report, None, key)
        return report
    except OSError as exc:
        report["request_count"] = guard.count
        report["result"] = "NETWORK_ERROR"
        report["authentication"] = "FAILED"
        report["error"] = A.redact(str(exc), key)
        _write_outputs(dest, report, None, key)
        return report

    report["request_count"] = guard.count
    report["http_status"] = status
    if status in (401, 403):
        report["result"] = "ACCESS_DENIED"
        report["authentication"] = "FAILED"
        report["calendar_access"] = "NOT_CONFIRMED"
        report["us_events_returned"] = 0
        fail = _failure_artifact(status, observed_at)
        digest = _persist_artifact(dest, fail, key, report)
        _write_outputs(dest, report, digest, key)
        return report
    if status == 429:
        report["result"] = "RATE_LIMITED"
        report["authentication"] = "FAILED"
        _write_outputs(dest, report, None, key)
        return report
    if status >= 400:
        report["result"] = "HTTP_%s" % status
        report["authentication"] = "FAILED"
        _write_outputs(dest, report, None, key)
        return report
    if status != 200:
        report["result"] = "HTTP_%s" % status
        report["authentication"] = "FAILED"
        _write_outputs(dest, report, None, key)
        return report

    try:
        rows = parse_calendar_body(body)
    except ProbeClosed as exc:
        report["result"] = str(exc)
        report["authentication"] = "SUCCESS"
        report["calendar_access"] = "NOT_CONFIRMED"
        _write_outputs(dest, report, None, key)
        return report

    us_rows = filter_us_target_date(rows)
    sanitized_us = [capture_row(sanitize_obj(row, key)) for row in us_rows]
    employment = inspect_employment_rows(sanitized_us, observed_at)
    identified = []
    for series in SERIES_ORDER:
        if series not in employment:
            continue
        item = dict(employment[series])
        item["series"] = series
        identified.append(item)
    artifact = {
        "kind": "TE_CALENDAR_SANITIZED_RESPONSE",
        "stage": "6B",
        "source_id": "trading_economics",
        "product": "ECONOMIC_CALENDAR",
        "request_host": HOST,
        "request_path": PATH,
        "query_parameter_names": list(QUERY_PARAM_NAMES),
        "authentication_method": "c query parameter",
        "probe_timestamp_utc": observed_at,
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "http_status": status,
        "raw_row_count": len(rows),
        "us_events_returned": len(sanitized_us),
        "us_event_summaries": [
            {
                "CalendarId": row.get("CalendarId"),
                "Country": row.get("Country"),
                "Category": row.get("Category"),
                "Event": row.get("Event"),
                "Date": row.get("Date"),
                "Ticker": row.get("Ticker"),
                "Symbol": row.get("Symbol"),
            }
            for row in sanitized_us
        ],
        "identified_targets": identified,
        "us_rows": sanitized_us,
        "forecast_field_semantics": "SURVEY_CONSENSUS",
        "teforecast_field_semantics": "PROVIDER_FORECAST",
        "lastupdate_semantics": "SOURCE_UPDATED_UTC",
        "real_checkpoint_created": False,
        "credential_redacted": True,
        "response_header_names": sorted({k.lower() for k in resp_headers}),
    }
    digest = _persist_artifact(dest, artifact, key, report)
    report.update(
        {
            "result": "SUCCESS",
            "authentication": "SUCCESS",
            "calendar_access": "CONFIRMED",
            "us_events_returned": len(sanitized_us),
            "raw_row_count": len(rows),
            "employment": employment,
            "consensus_te_distinct_in_any_row": any(
                consensus_and_te_distinct(r) for r in sanitized_us if isinstance(r, dict)
            ),
        }
    )
    _write_outputs(dest, report, digest, key)
    return report


def _failure_artifact(status: int, observed_at: str) -> dict:
    return {
        "kind": "TE_CALENDAR_SANITIZED_RESPONSE",
        "stage": "6B",
        "source_id": "trading_economics",
        "product": "ECONOMIC_CALENDAR",
        "request_host": HOST,
        "request_path": PATH,
        "query_parameter_names": list(QUERY_PARAM_NAMES),
        "authentication_method": "c query parameter",
        "probe_timestamp_utc": observed_at,
        "observed_at_utc": observed_at,
        "observed_at_clock_role": "LOCAL_COLLECTION_TIME_ONLY",
        "http_status": status,
        "result": "ACCESS_DENIED",
        "raw_row_count": 0,
        "us_events_returned": 0,
        "us_event_summaries": [],
        "identified_targets": [],
        "us_rows": [],
        "real_checkpoint_created": False,
        "credential_redacted": True,
    }


def _persist_artifact(dest: Path, artifact: dict, key: str | None, report: dict) -> str:
    raw = json.dumps(sanitize_obj(artifact, key), indent=2, ensure_ascii=True) + "\n"
    if key and key in raw:
        raise ProbeClosed("credential leaked into sanitized artifact")
    digest = sha256_bytes(raw.encode("utf-8"))
    artifact_path = dest / SANITIZED_NAME
    artifact_path.write_bytes(raw.encode("utf-8"))
    report["artifact_path"] = str(artifact_path).replace("\\", "/")
    report["artifact_sha256"] = digest
    report["credential_in_artifact"] = False
    return digest


def _write_outputs(dest: Path, report: dict, digest: str | None, key: str | None) -> None:
    meta = dict(report)
    meta.pop("error", None)
    meta.pop("employment", None)
    path = dest / META_NAME
    text = json.dumps(meta, indent=2, ensure_ascii=True) + "\n"
    if key and key in text:
        raise ProbeClosed("credential leaked into meta artifact")
    path.write_bytes(text.encode("utf-8"))


def assert_scheduler_still_disabled() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if cfg.get(FORWARD_FLAG) is True:
        raise ProbeClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED must remain false")
    blob = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    for src in blob.get("sources", []):
        if src.get("source_id") == "trading_economics":
            if src.get("enabled") is True:
                raise ProbeClosed("trading_economics must remain disabled")
            if src.get("automation_class") == "APPROVED_AUTOMATION_READY":
                raise ProbeClosed("trading_economics must not be APPROVED_AUTOMATION_READY")
            if src.get("automated_collection_permitted") is True:
                raise ProbeClosed("trading_economics automation must remain off")


def _safe_print(report: dict) -> None:
    keys = (
        "result",
        "authentication",
        "calendar_access",
        "http_status",
        "request_host",
        "request_path",
        "query_parameter_names",
        "authentication_method",
        "request_count",
        "us_events_returned",
        "observed_at_utc",
        "artifact_path",
        "artifact_sha256",
        "credential_in_artifact",
        "real_checkpoint_created",
        "credential_configured",
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
        print("%s_CALENDAR_ID=%s" % (label, item.get("calendar_id")))
        print("%s_EVENT_NAME=%s" % (label, item.get("event_name")))
        print("%s_CONSENSUS=%s" % (label, item.get("consensus_display")))
        print("%s_TE_FORECAST=%s" % (label, item.get("te_forecast_display")))


if __name__ == "__main__":
    import sys

    dest = Path(sys.argv[sys.argv.index("--dest") + 1]) if "--dest" in sys.argv else PROBE_DIR
    live = "--live" in sys.argv
    out = run_probe(dest=dest, live=live)
    _safe_print(out)
