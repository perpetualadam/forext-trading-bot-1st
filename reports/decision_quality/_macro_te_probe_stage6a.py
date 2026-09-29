"""Stage 6A: one-request Trading Economics Calendar capability probe.

Research-only. Never prints credentials. Never writes real observations.
Does not enable autonomous collection or the Windows task.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_AD_PATH = Path(__file__).with_name("_macro_prospective_adapters.py")
_AD_SPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_for_te_probe", _AD_PATH)
A = importlib.util.module_from_spec(_AD_SPEC)
assert _AD_SPEC is not None and _AD_SPEC.loader is not None
_AD_SPEC.loader.exec_module(A)

UTC = timezone.utc
TE_KEY_ENV = A.TE_KEY_ENV
TE_HOST = A.TE_HOST
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective/probes")
REAL_OBS = Path("data/research/macro/consensus_pit/prospective/observations/observations.jsonl")
CONFIG_PATH = Path("data/research/macro/consensus_pit/prospective/config.json")
REGISTRY_PATH = Path("data/research/macro/consensus_pit/prospective/source_registry/sources.json")
FORWARD_FLAG = "FORWARD_CONSENSUS_COLLECTION_ENABLED"

# Documented country + closed date-range calendar (pretrial readiness 2026-09-23).
# One US release day. values=true is a query flag on the same GET, not a second request.
DOCUMENTED_PATH = "/calendar/country/united%20states/2026-10-02/2026-10-02"
DOCUMENTED_QUERY = "f=json&values=true"
DOCUMENTED_URL = "%s%s?%s" % (TE_HOST, DOCUMENTED_PATH, DOCUMENTED_QUERY)
TIMEOUT_SEC = 30


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
        return raw or None
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


def classify_field_presence(row: dict) -> dict[str, bool]:
    keys = {str(k).lower(): k for k in row.keys()}
    def has(*names: str) -> bool:
        return any(n.lower() in keys and row.get(keys[n.lower()]) not in (None, "") for n in names)

    return {
        "calendar_id": has("CalendarId", "CalendarID"),
        "country": has("Country"),
        "category": has("Category"),
        "event": has("Event"),
        "date": has("Date"),
        "reference": has("Reference", "reference_period"),
        "actual": has("Actual", "ActualValue"),
        "previous": has("Previous", "PreviousValue"),
        "revised": has("Revised", "RevisedPrevious"),
        "forecast": has("Forecast", "ForecastValue"),
        "teforecast": has("TEForecast", "TEForecastValue"),
        "importance": has("Importance"),
        "source": has("Source"),
        "source_url": has("SourceURL"),
        "last_update": has("LastUpdate"),
        "unit": has("Unit"),
        "ticker": has("Ticker", "Symbol"),
    }


def inspect_employment_rows(rows: list[dict]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Event") or "")
        series = A.map_employment_series(name)
        if series is None:
            continue
        if series in found:
            continue
        forecast = row.get("Forecast") if "Forecast" in row else row.get("ForecastValue")
        te = row.get("TEForecast") if "TEForecast" in row else row.get("TEForecastValue")
        found[series] = {
            "event_name": name,
            "forecast": forecast,
            "forecast_present": forecast not in (None, ""),
            "te_forecast": te,
            "te_forecast_present": te not in (None, ""),
            "fields": classify_field_presence(row),
            "calendar_id": row.get("CalendarId") or row.get("CalendarID"),
            "category": row.get("Category"),
            "date": row.get("Date"),
            "reference": row.get("Reference") or row.get("reference_period"),
            "unit": row.get("Unit"),
            "previous": row.get("Previous") if "Previous" in row else row.get("PreviousValue"),
            "revised": row.get("Revised"),
            "actual": row.get("Actual") if "Actual" in row else row.get("ActualValue"),
            "importance": row.get("Importance"),
            "source": row.get("Source"),
            "last_update": row.get("LastUpdate"),
        }
    return found


def consensus_and_te_distinct(row: dict) -> bool:
    return ("Forecast" in row or "ForecastValue" in row) and ("TEForecast" in row or "TEForecastValue" in row)


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


def _urllib_transport(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
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
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
    transport: Callable | None = None,
    live: bool = False,
    guard: RequestGuard | None = None,
) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    guard = guard or RequestGuard(1)
    key = read_key(env=env, dotenv_path=dotenv_path)
    report = {
        "kind": "TE_CALENDAR_CAPABILITY_PROBE",
        "stage": "6A",
        "live": live,
        "target_country": "united states",
        "target_date": "2026-10-02",
        "documented_url": DOCUMENTED_URL,
        "auth": "Authorization header",
        "credential_configured": bool(key),
        "request_count": 0,
        "entered_observations": False,
        "http_status": None,
        "result": "NOT_ATTEMPTED",
    }
    if not key:
        report["result"] = "CREDENTIAL_REQUIRED"
        _write_report(dest, report, None)
        return report
    if not live:
        report["result"] = "DRY_RUN_NO_NETWORK"
        _write_report(dest, report, None)
        return report

    guard.authorize()
    headers = {"Authorization": key, "Accept": "application/json"}
    send = transport or _urllib_transport
    try:
        status, body, resp_headers = send(DOCUMENTED_URL, headers)
    except TimeoutError:
        report["request_count"] = guard.count
        report["result"] = "TIMEOUT"
        _write_report(dest, report, None)
        return report
    except OSError as exc:
        report["request_count"] = guard.count
        report["result"] = "NETWORK_ERROR"
        report["error"] = A.redact(str(exc), key)
        _write_report(dest, report, None)
        return report

    report["request_count"] = guard.count
    report["http_status"] = status
    if status in (401, 403):
        report["result"] = "ACCESS_DENIED"
        fail = {
            "kind": "TE_CALENDAR_SANITIZED_RESPONSE",
            "source_id": "trading_economics",
            "product": "ECONOMIC_CALENDAR",
            "documented_url": DOCUMENTED_URL,
            "http_status": status,
            "result": "ACCESS_DENIED",
            "row_count": 0,
            "rows": [],
            "credential_redacted": True,
        }
        raw = json.dumps(sanitize_obj(fail, key), indent=2, ensure_ascii=True) + "\n"
        digest = sha256_bytes(raw.encode("utf-8"))
        artifact_path = dest / "te_calendar_2026-10-02.sanitized.json"
        if not artifact_path.exists():
            artifact_path.write_text(raw, encoding="utf-8")
        report["artifact_path"] = str(artifact_path).replace("\\", "/")
        report["artifact_sha256"] = digest
        report["credential_in_artifact"] = bool(key and key in raw)
        _write_report(dest, report, digest)
        return report
    if status == 429:
        report["result"] = "RATE_LIMITED"
        _write_report(dest, report, None)
        return report
    if status >= 400:
        report["result"] = "HTTP_%s" % status
        _write_report(dest, report, None)
        return report
    try:
        rows = parse_calendar_body(body)
    except ProbeClosed as exc:
        report["result"] = str(exc)
        _write_report(dest, report, None)
        return report

    sanitized_rows = sanitize_obj(rows, key)
    artifact = {
        "kind": "TE_CALENDAR_SANITIZED_RESPONSE",
        "source_id": "trading_economics",
        "product": "ECONOMIC_CALENDAR",
        "documented_url": DOCUMENTED_URL,
        "retrieved_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": status,
        "row_count": len(sanitized_rows),
        "rows": sanitized_rows,
        "response_header_names": sorted({k.lower() for k in resp_headers}),
    }
    raw = json.dumps(artifact, indent=2, ensure_ascii=True) + "\n"
    raw_bytes = raw.encode("utf-8")
    digest = sha256_bytes(raw_bytes)
    artifact_path = dest / "te_calendar_2026-10-02.sanitized.json"
    artifact_path.write_text(raw, encoding="utf-8")
    if key and key in raw:
        raise ProbeClosed("credential leaked into sanitized artifact")
    employment = inspect_employment_rows(sanitized_rows)
    field_union = sorted({k for row in sanitized_rows if isinstance(row, dict) for k in row.keys()})
    report.update(
        {
            "result": "SUCCESS",
            "us_events_returned": len(sanitized_rows),
            "field_names": field_union,
            "employment": employment,
            "artifact_path": str(artifact_path).replace("\\", "/"),
            "artifact_sha256": digest,
            "credential_in_artifact": False,
            "consensus_te_distinct_in_any_row": any(
                consensus_and_te_distinct(r) for r in sanitized_rows if isinstance(r, dict)
            ),
        }
    )
    _write_report(dest, report, digest)
    return report


def _write_report(dest: Path, report: dict, digest: str | None) -> None:
    meta = dict(report)
    meta.pop("error", None)
    path = dest / "te_calendar_2026-10-02.meta.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


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
