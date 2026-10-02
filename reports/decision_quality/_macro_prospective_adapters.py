"""Prospective source adapters. Research-only. Fail closed. No trading imports.

No source is APPROVED_AUTOMATION_READY in the live registry. Adapters exist so
an operator can activate a source later without weakening PIT gates.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import URLError

UTC = timezone.utc
TE_KEY_ENV = "TRADING_ECONOMICS_API_KEY"
TE_HOST = "https://api.tradingeconomics.com"
BLS_EMPSIT_HTML = "https://www.bls.gov/news.release/empsit.htm"
BLS_CPI_HTML = "https://www.bls.gov/news.release/cpi.htm"
PROBE_DIR_NAME = "probes"

EMP_SERIES = (
    "nonfarm_payroll_change",
    "unemployment_rate",
    "average_hourly_earnings_mom",
    "average_hourly_earnings_yoy",
)
CPI_SERIES = ("headline_mom", "headline_yoy", "core_mom", "core_yoy")
FOMC_SERIES = (
    "expected_policy_decision",
    "hold_probability",
    "cut_25bp_probability",
    "cut_50bp_probability",
    "hike_25bp_probability",
    "ff_target_change_bp",
)
FORBIDDEN_SUBSTITUTES = (
    "adp",
    "jobless claims",
    "initial claims",
    "private payroll",
    "participation rate",
    "jolts",
)
SECRET_PATTERNS = re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)[^\s'\"]+")
SECRET_QUERY = re.compile(r"(?i)([?&](?:c|client|apikey|api_key|token|key)=)[^&\s]+")

SOURCE_AUDIT = (
    {
        "source_id": "trading_economics",
        "classification": "API_AVAILABLE_CREDENTIALS_MISSING",
        "access_method": "documented REST calendar API (header Authorization)",
        "authentication_required": True,
        "credentials_present": False,
        "forecast_fields_available": "Forecast / ForecastValue / TEForecast (provider-owned, not Reuters)",
        "publication_update_timestamps_available": "Date UTC; LastUpdate (insertion/update, not proven pre-T0 vintage)",
        "individual_forecasts_available": False,
        "consensus_available": True,
        "previous_revised_available": True,
        "programmatic_retrieval_supported": True,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "currently_live": False,
        "operational_status": "OPERATIONAL_RETIRED_SUBSCRIPTION_CANCELLED",
        "approved_consensus_provider": False,
        "role": "CONSENSUS_PROVIDER",
        "reason": "API exists in prior research harness. Subscription cancelled. Adapter preserved for historical reproducibility. Not an active future consensus provider. Calendar consensus is TE-specific, not Reuters/FactSet.",
    },
    {
        "source_id": "econoday",
        "classification": "MANUAL_ONLY",
        "access_method": "licensed XML feed (sample ZIP audited historically); no live feed URL/credentials in this repo",
        "authentication_required": True,
        "credentials_present": False,
        "forecast_fields_available": "CONSENSUS / CONSENSUSRANGEFROM / CONSENSUSRANGETO in licensed XML",
        "publication_update_timestamps_available": "RELEASED_ON_GMT; DATA@date/seq file vintage",
        "individual_forecasts_available": False,
        "consensus_available": True,
        "previous_revised_available": True,
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "No Econoday live-feed credentials or endpoint configured. HTML calendar is not an approved scrape target. Sample extract is not a live adapter.",
    },
    {
        "source_id": "reuters",
        "classification": "MANUAL_ONLY",
        "access_method": "licensed newswire / paywalled pages",
        "authentication_required": "desk_dependent",
        "credentials_present": False,
        "forecast_fields_available": "survey/range when printed",
        "publication_update_timestamps_available": "HIGH when original clock present",
        "individual_forecasts_available": True,
        "consensus_available": True,
        "previous_revised_available": "sometimes",
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "No Reuters API/feed credentials. Do not scrape paywalled pages. Manual ingest of lawfully obtained text remains allowed.",
    },
    {
        "source_id": "factset_insight",
        "classification": "MANUAL_ONLY",
        "access_method": "public insight pages / licensed FactSet",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": "labeled medians on some posts",
        "publication_update_timestamps_available": "date-only / Tomorrow; no UTC clock",
        "individual_forecasts_available": False,
        "consensus_available": True,
        "previous_revised_available": False,
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "No automation permission. Live pages can be edited. Fail closed.",
    },
    {
        "source_id": "dow_jones",
        "classification": "MANUAL_ONLY",
        "access_method": "licensed Dow Jones / Newswires",
        "authentication_required": True,
        "credentials_present": False,
        "forecast_fields_available": "survey consensus when licensed",
        "publication_update_timestamps_available": "HIGH when clocked relay exists",
        "individual_forecasts_available": True,
        "consensus_available": True,
        "previous_revised_available": "unknown",
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "Primary feed not licensed here. Do not scrape paywalled DJ.",
    },
    {
        "source_id": "bloomberg",
        "classification": "MANUAL_ONLY",
        "access_method": "licensed terminal/API",
        "authentication_required": True,
        "credentials_present": False,
        "forecast_fields_available": "survey/BN when licensed",
        "publication_update_timestamps_available": "HIGH when accessible",
        "individual_forecasts_available": True,
        "consensus_available": True,
        "previous_revised_available": "unknown",
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "No Bloomberg credentials. Paywall. No bypass.",
    },
    {
        "source_id": "bls_official",
        "classification": "UNSUPPORTED",
        "access_method": "official HTML news release (not a forecast source)",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": False,
        "publication_update_timestamps_available": "embargo clock",
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": "revisions exist; first print must stay immutable",
        "programmatic_retrieval_supported": "PARTIAL (direct GET historically 403)",
        "local_artifact_retention_permitted": "UNKNOWN for bulk scrape; official public releases are citable",
        "autonomous_status": "disabled",
        "currently_live": False,
        "approved_consensus_provider": False,
        "role": "OFFICIAL_ACTUAL_PROVIDER",
        "reason": "Official actuals only. Not consensus. Adapter implemented DISABLED. Never fetch before T0. Do not classify BLS as a market-consensus provider.",
    },
    {
        "source_id": "frb_official",
        "classification": "UNSUPPORTED",
        "access_method": "federalreserve.gov statement HTML/PDF",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": False,
        "publication_update_timestamps_available": "For release at 2:00 p.m.",
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": False,
        "programmatic_retrieval_supported": True,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "Official decision/statement, not a pre-release consensus source.",
    },
    {
        "source_id": "fred_alfred",
        "classification": "REJECTED",
        "access_method": "FRED/ALFRED vintage APIs",
        "authentication_required": "API key for FRED",
        "credentials_present": False,
        "forecast_fields_available": False,
        "publication_update_timestamps_available": "vintage dates for official series",
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": True,
        "programmatic_retrieval_supported": True,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "Official statistical vintages, not economist pre-release forecasts. Already rejected as first-print substitute.",
    },
    {
        "source_id": "search_engine_snippets",
        "classification": "REJECTED",
        "access_method": "Google/Bing/AI summaries",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": "unreliable snippets",
        "publication_update_timestamps_available": False,
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": False,
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "n/a",
        "autonomous_status": "disabled",
        "reason": "Search/AI summaries are not prospective evidence.",
    },
    {
        "source_id": "cme_fedwatch",
        "classification": "MANUAL_ONLY",
        "access_method": "contemporaneous citation of CME FedWatch; live tool is not a vintage archive",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": "implied rate probabilities when cited",
        "publication_update_timestamps_available": "only as good as the citing article clock",
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": False,
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "Do not reconstruct historical probabilities from today's live tool. Manual citation ingest only.",
    },
    {
        "source_id": "fxstreet",
        "classification": "MANUAL_ONLY",
        "access_method": "public analysis pages used historically as FOMC preview citations",
        "authentication_required": False,
        "credentials_present": False,
        "forecast_fields_available": "sometimes cites futures/survey figures",
        "publication_update_timestamps_available": "page byline when present",
        "individual_forecasts_available": False,
        "consensus_available": False,
        "previous_revised_available": False,
        "programmatic_retrieval_supported": False,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "No automation permission. Historical excerpts were manual. Do not scrape.",
    },
    {
        "source_id": "fxmacrodata",
        "classification": "API_AVAILABLE_CREDENTIALS_MISSING",
        "access_method": "documented REST predictions API (prior coverage probe only)",
        "authentication_required": True,
        "credentials_present": False,
        "forecast_fields_available": "survey/compiled consensus when a paid plan is active",
        "publication_update_timestamps_available": "unknown vintage clock",
        "individual_forecasts_available": "unknown",
        "consensus_available": True,
        "previous_revised_available": "unknown",
        "programmatic_retrieval_supported": True,
        "local_artifact_retention_permitted": "UNKNOWN",
        "autonomous_status": "disabled",
        "reason": "Prior coverage probe showed forecast values require a plan. No key in this repo. Archival permission not established. No new live request in Stage 4.",
    },
)


def redact(text: str, secret: str | None = None) -> str:
    out = str(text or "")
    if secret:
        out = out.replace(secret, "<redacted>")
    out = SECRET_QUERY.sub(r"\1<redacted>", out)
    out = SECRET_PATTERNS.sub(r"\1<redacted>", out)
    return out


def credential_present(name: str, env: dict[str, str] | None = None, dotenv_path: Path | None = None) -> bool:
    if env is not None:
        return bool((env.get(name) or "").strip())
    if (os.environ.get(name) or "").strip():
        return True
    path = dotenv_path or Path(".env")
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, val = raw.partition("=")
        if key.strip() == name and val.strip().strip('"').strip("'"):
            return True
    return False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AdapterError(RuntimeError):
    def __str__(self) -> str:
        return redact(super().__str__())


def normalize_jobs_value(raw) -> int:
    if raw is None:
        raise ValueError("ambiguous unit")
    if isinstance(raw, bool):
        raise ValueError("ambiguous unit")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw != int(raw):
            raise ValueError("ambiguous unit")
        return int(raw)
    text = str(raw).strip().lower().replace(",", "").replace(" ", "")
    if not text or any(tok in text for tok in ("-", "to", "about", "around", "approx")):
        raise ValueError("ambiguous unit")
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(k|m)?", text)
    if not m:
        raise ValueError("ambiguous unit")
    num = float(m.group(1))
    suf = m.group(2)
    if suf == "k":
        num *= 1000
    elif suf == "m":
        num *= 1000000
    if num != int(num):
        raise ValueError("ambiguous unit")
    return int(num)


def normalize_percent_value(raw) -> float:
    if raw is None:
        raise ValueError("ambiguous unit")
    if isinstance(raw, bool):
        raise ValueError("ambiguous unit")
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().lower().replace("%", "").replace("percent", "").strip()
    if not text or any(tok in text for tok in ("-", "to", "about", "around")):
        raise ValueError("ambiguous unit")
    return float(text)


def map_employment_series(event_name: str) -> str | None:
    n = (event_name or "").strip().lower()
    if any(tok in n for tok in FORBIDDEN_SUBSTITUTES):
        return None
    if "unemployment" in n and "rate" in n:
        return "unemployment_rate"
    if "average hourly" in n and ("yoy" in n or "year" in n):
        return "average_hourly_earnings_yoy"
    if "average hourly" in n and ("mom" in n or "month" in n):
        return "average_hourly_earnings_mom"
    if "nonfarm" in n.replace(" ", "") or "non farm payroll" in n or n == "nonfarm_payroll_change":
        return "nonfarm_payroll_change"
    return None


def map_cpi_series(event_name: str) -> str | None:
    n = (event_name or "").strip().lower()
    core = "core" in n or "excluding food" in n
    yoy = "yoy" in n or "year" in n
    mom = "mom" in n or "month" in n
    if "cpi" not in n and "consumer price" not in n and n not in CPI_SERIES:
        return None
    if n in CPI_SERIES:
        return n
    if core and yoy:
        return "core_yoy"
    if core and mom:
        return "core_mom"
    if yoy:
        return "headline_yoy"
    if mom:
        return "headline_mom"
    return None


def refuse_fomc_collapse(prob: float, outcome: str) -> None:
    raise RuntimeError("FOMC probability distributions must not be collapsed into scalar bp consensus.")


class AdapterResult:
    def __init__(self, **kwargs):
        self.status = kwargs.get("status")
        self.source_id = kwargs.get("source_id")
        self.external_request = bool(kwargs.get("external_request"))
        self.artifact_bytes = kwargs.get("artifact_bytes")
        self.series_name = kwargs.get("series_name")
        self.expectation_type = kwargs.get("expectation_type")
        self.forecast_value = kwargs.get("forecast_value")
        self.unit = kwargs.get("unit")
        self.reference_period = kwargs.get("reference_period")
        self.source_publication_utc = kwargs.get("source_publication_utc")
        self.source_updated_utc = kwargs.get("source_updated_utc")
        self.observation_kind = kwargs.get("observation_kind", "FORECASTER")
        self.notes = kwargs.get("notes")
        self.reason = kwargs.get("reason")
        self.calendar_fields = kwargs.get("calendar_fields")
        self.fomc_distribution = kwargs.get("fomc_distribution")
        self.payloads = kwargs.get("payloads") or []
        self.provider_name = kwargs.get("provider_name")
        self.source_event_identifier = kwargs.get("source_event_identifier")
        self.source_url_or_endpoint_identifier = kwargs.get("source_url_or_endpoint_identifier")
        self.retrieval_utc = kwargs.get("retrieval_utc")


class BaseAdapter:
    source_id = "unknown"
    requires_credential_env: str | None = None

    def __init__(self, env: dict[str, str] | None = None, transport: Callable | None = None):
        self.env = env
        self.transport = transport
        self.network_calls = 0

    def is_enabled(self, rec) -> tuple[bool, str]:
        src = rec.source_by_id(self.source_id)
        if src is None:
            return False, "UNKNOWN_SOURCE"
        if rec.collection_enabled() is not True:
            return False, "GLOBAL_FLAG_FALSE"
        if src.get("enabled") is not True:
            return False, "SOURCE_DISABLED"
        if src.get("automated_collection_permitted") is not True:
            return False, "PERMISSION_UNKNOWN_OR_FALSE"
        if src.get("archival_permitted") is not True:
            return False, "ARCHIVAL_PERMISSION_UNCLEAR"
        if src.get("automation_class") != "APPROVED_AUTOMATION_READY":
            return False, "NOT_APPROVED"
        if self.requires_credential_env and not credential_present(self.requires_credential_env, self.env):
            return False, "MISSING_CREDENTIALS"
        return True, "OK"

    def supports(self, event: dict) -> bool:
        return True

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> AdapterResult:
        raise AdapterError("unapproved adapter must never fetch")


class TradingEconomicsAdapter(BaseAdapter):
    source_id = "trading_economics"
    requires_credential_env = TE_KEY_ENV

    def currently_live(self) -> bool:
        return False

    def supports(self, event: dict) -> bool:
        return event.get("event_family") in {"CPI", "EMPLOYMENT_SITUATION", "FOMC"}

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> AdapterResult:
        return AdapterResult(
            status="SOURCE_DISABLED",
            source_id=self.source_id,
            reason="NOT_APPROVED",
            external_request=False,
        )


class _ApprovedTeTestAdapter(TradingEconomicsAdapter):
    """Test-only path: mock transport, never used in production default_adapters."""

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> AdapterResult:
        if self.transport is None:
            return AdapterResult(status="SOURCE_UNAVAILABLE", source_id=self.source_id, reason="no transport", external_request=False)
        if not credential_present(TE_KEY_ENV, self.env):
            return AdapterResult(status="ACCESS_DENIED", source_id=self.source_id, reason="MISSING_CREDENTIALS", external_request=False)
        key = (self.env or os.environ).get(TE_KEY_ENV, "")
        url = "%s/calendar/country/united states/indicator/non farm payrolls" % TE_HOST
        self.network_calls += 1
        try:
            resp = self.transport(url, {"Authorization": key, "Accept": "application/json"})
        except TimeoutError:
            return AdapterResult(status="SOURCE_UNAVAILABLE", source_id=self.source_id, reason="timeout", external_request=True)
        except URLError as exc:
            return AdapterResult(status="SOURCE_UNAVAILABLE", source_id=self.source_id, reason=redact(str(exc), key), external_request=True)
        status = getattr(resp, "status", None)
        body = getattr(resp, "body", b"")
        if status == 429:
            return AdapterResult(status="RATE_LIMITED", source_id=self.source_id, external_request=True, reason="HTTP 429")
        if status in (401, 403):
            return AdapterResult(status="ACCESS_DENIED", source_id=self.source_id, external_request=True, reason="HTTP %s" % status)
        if status is not None and status >= 400:
            return AdapterResult(status="SOURCE_UNAVAILABLE", source_id=self.source_id, external_request=True, reason="HTTP %s" % status)
        try:
            rows = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="malformed json")
        if not isinstance(rows, list):
            return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="not a list")
        payloads = []
        artifact = json.dumps(rows, ensure_ascii=True).encode("utf-8")
        for row in rows:
            if not isinstance(row, dict):
                return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="row not object")
            series = map_employment_series(str(row.get("Event") or row.get("series") or ""))
            if event.get("event_family") == "CPI":
                series = map_cpi_series(str(row.get("Event") or row.get("series") or ""))
            if event.get("event_family") == "FOMC":
                if row.get("fomc_distribution"):
                    payloads.append(
                        AdapterResult(
                            status="SUCCESS",
                            source_id=self.source_id,
                            external_request=True,
                            artifact_bytes=artifact,
                            series_name="hold_probability",
                            expectation_type="MARKET_IMPLIED_EXPECTATION",
                            forecast_value=row["fomc_distribution"].get("hold"),
                            unit="probability",
                            fomc_distribution=row["fomc_distribution"],
                            observation_kind="FORECASTER",
                            calendar_fields={"provider": "Trading Economics", "fomc_distribution": row["fomc_distribution"]},
                        )
                    )
                    continue
                return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="FOMC scalar collapse refused")
            if not series:
                return AdapterResult(status="INVALID_SERIES", source_id=self.source_id, external_request=True, reason="unmapped or substituted series")
            try:
                if series == "nonfarm_payroll_change":
                    value = normalize_jobs_value(row.get("Forecast") if "Forecast" in row else row.get("forecast_value"))
                    unit = "persons"
                else:
                    value = normalize_percent_value(row.get("Forecast") if "Forecast" in row else row.get("forecast_value"))
                    unit = "percent"
            except (ValueError, TypeError):
                return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="ambiguous unit")
            payloads.append(
                AdapterResult(
                    status="SUCCESS",
                    source_id=self.source_id,
                    external_request=True,
                    artifact_bytes=artifact,
                    series_name=series,
                    expectation_type="ECONOMIC_CALENDAR_FORECAST",
                    forecast_value=value,
                    unit=unit,
                    reference_period=row.get("reference_period") or event.get("reference_period"),
                    source_publication_utc=row.get("source_publication_utc"),
                    source_updated_utc=row.get("LastUpdate") or row.get("source_updated_utc"),
                    observation_kind="ECONOMIC_CALENDAR",
                    provider_name="Trading Economics",
                    source_event_identifier=str(row.get("CalendarId") or row.get("CalendarID") or ""),
                    source_url_or_endpoint_identifier=redact(url, key),
                    retrieval_utc=now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    calendar_fields={
                        "provider": "Trading Economics",
                        "event_name": row.get("Event"),
                        "forecast": value,
                        "previous": row.get("Previous"),
                        "revised_previous": row.get("Revised"),
                        "importance": row.get("Importance"),
                        "unit": unit,
                        "reference_period": row.get("reference_period") or event.get("reference_period"),
                        "source_event_identifier": str(row.get("CalendarId") or ""),
                        "source_url_or_endpoint_identifier": redact(url, key),
                        "retrieval_utc": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    notes="TE calendar forecast is provider-specific; not Reuters/FactSet/DJ.",
                )
            )
        if not payloads:
            return AdapterResult(status="NO_DATA", source_id=self.source_id, external_request=True, artifact_bytes=artifact)
        first = payloads[0]
        first.payloads = payloads[1:]
        first.artifact_bytes = artifact
        first.external_request = True
        return first


BLS_FLAG = "OFFICIAL_BLS_FIRST_PRINT_ENABLED"


class OfficialBlsFirstPrintAdapter(BaseAdapter):
    source_id = "bls_official"
    enabled_by_default = False

    def is_enabled(self, rec) -> tuple[bool, str]:
        src = rec.source_by_id(self.source_id)
        if src is None:
            return False, "UNKNOWN_SOURCE"
        if rec.load_config().get(BLS_FLAG) is not True:
            return False, "SOURCE_DISABLED"
        if src.get("enabled") is not True:
            return False, "SOURCE_DISABLED"
        if rec.collection_enabled() is not True:
            return False, "GLOBAL_FLAG_FALSE"
        if src.get("automated_collection_permitted") is not True:
            return False, "PERMISSION_UNKNOWN_OR_FALSE"
        return True, "OK"

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> AdapterResult:
        t0 = event.get("scheduled_release_utc")
        if t0:
            t0dt = datetime.fromisoformat(t0.replace("Z", "+00:00"))
            if now.astimezone(UTC) < t0dt.astimezone(UTC):
                return AdapterResult(
                    status="ACCESS_DENIED",
                    source_id=self.source_id,
                    reason="NEVER_BEFORE_T0",
                    external_request=False,
                )
        if self.transport is None:
            return AdapterResult(status="SOURCE_DISABLED", source_id=self.source_id, reason="disabled_no_transport", external_request=False)
        url = BLS_EMPSIT_HTML if event.get("event_family") == "EMPLOYMENT_SITUATION" else BLS_CPI_HTML
        self.network_calls += 1
        resp = self.transport(url, {"Accept": "text/html"})
        status = getattr(resp, "status", 0)
        body = getattr(resp, "body", b"")
        if status in (401, 403):
            return AdapterResult(status="ACCESS_DENIED", source_id=self.source_id, external_request=True, reason="HTTP %s" % status)
        if status == 429:
            return AdapterResult(status="RATE_LIMITED", source_id=self.source_id, external_request=True)
        if status >= 400:
            return AdapterResult(status="SOURCE_UNAVAILABLE", source_id=self.source_id, external_request=True, reason="HTTP %s" % status)
        parsed = parse_bls_first_print(body, event.get("event_family"), event.get("series_hint") or "nonfarm_payroll_change")
        if parsed is None:
            return AdapterResult(status="PARSE_FAILED", source_id=self.source_id, external_request=True, reason="ambiguous official print")
        return AdapterResult(
            status="SUCCESS",
            source_id=self.source_id,
            external_request=True,
            artifact_bytes=body,
            series_name=parsed["series_name"],
            expectation_type="OFFICIAL_ACTUAL",
            forecast_value=parsed["actual"],
            unit=parsed["unit"],
            observation_kind="OFFICIAL",
            notes="Official first print. Not a forecast.",
        )


def parse_bls_first_print(body: bytes, family: str | None, series: str) -> dict | None:
    text = body.decode("utf-8", errors="replace")
    if family == "EMPLOYMENT_SITUATION" and series == "nonfarm_payroll_change":
        m = re.search(r"nonfarm payroll[s]?\s+(?:increased|rose|changed by)?\s*([+-]?\d[\d,]*)", text, re.I)
        if not m:
            m = re.search(r"FIRST_PRINT_NFP=([+-]?\d+)", text)
        if not m:
            return None
        return {"series_name": "nonfarm_payroll_change", "actual": int(m.group(1).replace(",", "")), "unit": "persons"}
    if family == "CPI":
        m = re.search(r"FIRST_PRINT_%s=([+-]?\d+(?:\.\d+)?)" % re.escape(series), text)
        if not m:
            return None
        return {"series_name": series, "actual": float(m.group(1)), "unit": "percent"}
    return None


class NeverFetchAdapter(BaseAdapter):
    def __init__(self, source_id: str):
        super().__init__()
        self.source_id = source_id

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> AdapterResult:
        return AdapterResult(status="SOURCE_DISABLED", source_id=self.source_id, reason="NOT_APPROVED", external_request=False)


def build_production_adapters(rec, env: dict[str, str] | None = None) -> list:
    """Live collect-due adapters. None are approved; none fetch."""
    adapters: list[BaseAdapter] = [
        TradingEconomicsAdapter(env=env),
        OfficialBlsFirstPrintAdapter(env=env),
    ]
    seen = {a.source_id for a in adapters}
    for src in rec.load_registry().get("sources", []):
        sid = src.get("source_id")
        if sid and sid not in seen:
            adapters.append(NeverFetchAdapter(sid))
            seen.add(sid)
    return adapters


def run_capability_probes(*, dest: Path, env: dict[str, str] | None = None, live: bool = False) -> dict:
    """Audit probes only. Never writes observations.jsonl."""
    dest.mkdir(parents=True, exist_ok=True)
    te_present = credential_present(TE_KEY_ENV, env)
    report = {
        "kind": "SOURCE_AUDIT_PROBE",
        "live": live,
        "trading_economics_credentials_present": te_present,
        "requests": [],
        "total_external_requests": 0,
        "entered_observations": False,
    }
    # No live request unless credentials exist AND live=True. Stage 4 default: live=False
    # because TE is not archival-approved even if a key appears later.
    if live and te_present:
        report["requests"].append({"source_id": "trading_economics", "result": "SKIPPED_NOT_ARCHIVAL_APPROVED", "count": 0})
    else:
        report["requests"].append(
            {
                "source_id": "trading_economics",
                "result": "NO_PROBE_CREDENTIALS_MISSING" if not te_present else "NO_PROBE_NOT_APPROVED",
                "count": 0,
            }
        )
    report["requests"].append({"source_id": "bls_official", "result": "NO_PROBE_DISABLED_FORECAST_SOURCE", "count": 0})
    path = dest / "capability_probe.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
