"""Stage 14: retire Trading Economics from active prospective operations.

Operational status change only. Historical TE evidence, adapters, tests, and
provenance are preserved. No replacement provider is selected. Zero network.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

_REC_PATH = Path(__file__).with_name("_macro_prospective_recorder.py")
_REC_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_stage14", _REC_PATH)
R = importlib.util.module_from_spec(_REC_SPEC)
assert _REC_SPEC is not None and _REC_SPEC.loader is not None
_REC_SPEC.loader.exec_module(R)

_AD_PATH = Path(__file__).with_name("_macro_prospective_adapters.py")
_AD_SPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_stage14", _AD_PATH)
A = importlib.util.module_from_spec(_AD_SPEC)
assert _AD_SPEC is not None and _AD_SPEC.loader is not None
_AD_SPEC.loader.exec_module(A)

TE_SOURCE_ID = "trading_economics"
CPI_EVENT_ID = "usd_cpi_2026-10-14"
EMP_EVENT_ID = "usd_empsit_2026-10-02"
FOMC_EVENT_ID = "usd_fomc_statement_2026-10-28"
TE_LIVE_FLAG = "TRADING_ECONOMICS_ADAPTER_CURRENTLY_LIVE"
PROVIDER_PENDING = "PROVIDER_PENDING"
NONE_APPROVED = "NONE_APPROVED"
WAITING_FOR_APPROVED_PROVIDER = "WAITING_FOR_APPROVED_PROVIDER"
ROLE_CONSENSUS = "CONSENSUS_PROVIDER"
ROLE_OFFICIAL_ACTUAL = "OFFICIAL_ACTUAL_PROVIDER"
ROLE_MANUAL_METHOD = "MANUAL_COLLECTION_METHOD"
ROLE_NOT_REGISTERED = "NOT_IN_LIVE_REGISTRY"
APPROVED_CONSENSUS_PROVIDER_IDS: tuple[str, ...] = ()
FIXTURE_PREFIX = "fixture_"
PRODUCTION_ROOT = R.resolve_data_root()

PROVIDER_ACCEPTANCE_REQUIREMENTS = (
    "A. Genuine externally published market/economist consensus for the relevant release.",
    "B. Distinguishes Consensus from proprietary Forecast, Previous, and Actual where applicable.",
    "C. Clear component semantics. CPI requires headline_mom, headline_yoy, core_mom, core_yoy.",
    "D. Point-in-time observation: a dated/timed published vintage, not a reconstructed later view.",
    "E. Evidence that can be preserved with provenance (artifact + SHA-256 + observed_at_utc).",
    "F. Permitted access method. No paywall, CAPTCHA, auth, or robots bypass.",
    "G. No requirement to bypass access restrictions.",
    "H. No automatic averaging across providers.",
    "I. Provider-specific vintages remain separate.",
    "J. observed_at_utc < T0 for consensus use.",
)

CONSENSUS_VS_FORECAST_RULES = (
    "A proprietary provider forecast is NOT automatically a consensus.",
    "A model forecast is NOT a consensus.",
    "A nowcast is NOT a consensus.",
    "A single economist forecast is NOT automatically a market consensus.",
    "The source must characterize the value as a survey, poll, median/mean consensus, "
    "or equivalent aggregated expectation with sufficiently clear semantics.",
    "Do not infer consensus merely because a number appears before release.",
    "Never substitute Forecast for a blank Consensus.",
    "Never copy forward an earlier value.",
    "Never manufacture Consensus=null merely to mark a checkpoint collected.",
)


class ProviderClosed(RuntimeError):
    pass


def te_currently_live() -> bool:
    return False


def approved_consensus_provider_ids() -> tuple[str, ...]:
    return APPROVED_CONSENSUS_PROVIDER_IDS


def approved_consensus_provider_available() -> bool:
    return bool(approved_consensus_provider_ids())


def is_production_root(rec: R.ProspectiveRecorder) -> bool:
    try:
        return Path(rec.root).resolve() == Path(PRODUCTION_ROOT).resolve()
    except OSError:
        return False


def known_provider_status() -> list[dict[str, Any]]:
    return [
        {
            "source_id": TE_SOURCE_ID,
            "display_name": "Trading Economics",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "OPERATIONAL_RETIRED_SUBSCRIPTION_CANCELLED",
            "automation_class": "API_AVAILABLE_CREDENTIALS_MISSING",
            "notes": "Historical TE observations remain valid. Adapter preserved. Not used for future CPI.",
        },
        {
            "source_id": "forex_factory",
            "display_name": "Forex Factory",
            "role": ROLE_CONSENSUS,
            "registered": False,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "PROBED_NOT_REGISTERED",
            "automation_class": "NOT_IN_LIVE_REGISTRY",
            "notes": "Stage 7A probe only. Never added to the live source registry. Not promoted.",
        },
        {
            "source_id": "bls_official",
            "display_name": "BLS official",
            "role": ROLE_OFFICIAL_ACTUAL,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "OFFICIAL_ACTUAL_ONLY",
            "automation_class": "UNSUPPORTED",
            "notes": "Official first-print/actual source. Not a market-consensus provider.",
        },
        {
            "source_id": "frb_official",
            "display_name": "Federal Reserve Board official",
            "role": ROLE_OFFICIAL_ACTUAL,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "OFFICIAL_ACTUAL_ONLY",
            "automation_class": "UNSUPPORTED",
            "notes": "Official FOMC statement/decision. Not a market-consensus provider.",
        },
        {
            "source_id": "manual_operator",
            "display_name": "manual/unknown operator ingest",
            "role": ROLE_MANUAL_METHOD,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "METHOD_NOT_PROVIDER",
            "automation_class": "MANUAL_ONLY",
            "notes": "Ingest method, not a survey/consensus publisher. Cannot be assumed as TE.",
        },
        {
            "source_id": "econoday",
            "display_name": "Econoday",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "REGISTERED_NOT_APPROVED",
            "automation_class": "MANUAL_ONLY",
            "notes": "Not promoted to replace TE.",
        },
        {
            "source_id": "reuters",
            "display_name": "Reuters",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "REGISTERED_NOT_APPROVED",
            "automation_class": "MANUAL_ONLY",
            "notes": "Not promoted to replace TE.",
        },
        {
            "source_id": "factset_insight",
            "display_name": "FactSet",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "REGISTERED_NOT_APPROVED",
            "automation_class": "MANUAL_ONLY",
            "notes": "Not promoted to replace TE.",
        },
        {
            "source_id": "dow_jones",
            "display_name": "Dow Jones",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "REGISTERED_NOT_APPROVED",
            "automation_class": "MANUAL_ONLY",
            "notes": "Not promoted to replace TE.",
        },
        {
            "source_id": "bloomberg",
            "display_name": "Bloomberg",
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "REGISTERED_NOT_APPROVED",
            "automation_class": "MANUAL_ONLY",
            "notes": "Not promoted to replace TE.",
        },
    ]


def classify_provider(source_id: str | None) -> dict[str, Any]:
    sid = (source_id or "").strip()
    for row in known_provider_status():
        if row["source_id"] == sid:
            return dict(row)
    if sid.startswith(FIXTURE_PREFIX):
        return {
            "source_id": sid,
            "display_name": sid,
            "role": ROLE_CONSENSUS,
            "registered": True,
            "enabled": False,
            "currently_live": False,
            "approved_consensus_provider": False,
            "operational_status": "FIXTURE_ONLY",
            "automation_class": "MANUAL_ONLY",
            "notes": "Infrastructure fixture. Not an approved live consensus provider.",
        }
    return {
        "source_id": sid or None,
        "display_name": sid or None,
        "role": ROLE_NOT_REGISTERED,
        "registered": False,
        "enabled": False,
        "currently_live": False,
        "approved_consensus_provider": False,
        "operational_status": "UNKNOWN",
        "automation_class": "UNKNOWN",
        "notes": "Unknown source. Fail closed.",
    }


def event_provider_status(event: dict | None) -> dict[str, Any]:
    stored_id = None if event is None else event.get("consensus_provider_id")
    stored_status = None if event is None else event.get("consensus_provider_status")
    approved = approved_consensus_provider_available()
    provider_id = stored_id if stored_id not in (None, "", NONE_APPROVED) else None
    if provider_id and provider_id not in approved_consensus_provider_ids():
        provider_id = None
    status = stored_status or (PROVIDER_PENDING if not approved else "APPROVED")
    if not approved:
        status = PROVIDER_PENDING
        provider_id = None
    return {
        "registration": "ACTIVE" if event is not None else "UNREGISTERED",
        "checkpoint_schedule": "ACTIVE" if event and event.get("checkpoints") else "NONE",
        "consensus_provider_id": provider_id,
        "consensus_provider": NONE_APPROVED if provider_id is None else provider_id,
        "provider_status": status,
        "automated_collection": "DISABLED",
        "manual_collection": WAITING_FOR_APPROVED_PROVIDER if not approved else "APPROVED_PROVIDER_REQUIRED",
        "approved_consensus_provider_available": approved,
        "trading_economics_currently_live": te_currently_live(),
        "cpi_components": list(R.CPI_SERIES),
    }


def resolve_manual_provider(
    rec: R.ProspectiveRecorder,
    provider_id: str | None,
    *,
    allow_fixture: bool | None = None,
) -> dict[str, Any]:
    sid = (provider_id or "").strip()
    if not sid:
        raise ProviderClosed("PROVIDER_ID_REQUIRED: future manual evidence cannot assume Trading Economics")
    if sid == TE_SOURCE_ID:
        raise ProviderClosed(
            "TRADING_ECONOMICS_OPERATIONAL_RETIRED: subscription cancelled; not an active future consensus provider"
        )
    classified = classify_provider(sid)
    if classified.get("role") == ROLE_OFFICIAL_ACTUAL:
        raise ProviderClosed("BLS/official actual is not a consensus provider: %s" % sid)
    if classified.get("role") == ROLE_MANUAL_METHOD:
        raise ProviderClosed("manual_operator is a method, not an approved consensus publisher")
    if allow_fixture is None:
        allow_fixture = not is_production_root(rec)
    if sid in approved_consensus_provider_ids():
        src = rec.source_by_id(sid)
        if src is None:
            raise ProviderClosed("unknown source fail closed: %s" % sid)
        return {"provider_id": sid, "source": src, "classified": classified, "mode": "APPROVED"}
    if allow_fixture and sid.startswith(FIXTURE_PREFIX):
        src = rec.source_by_id(sid)
        if src is None:
            raise ProviderClosed("unknown source fail closed: %s" % sid)
        return {"provider_id": sid, "source": src, "classified": classified, "mode": "FIXTURE_ONLY"}
    raise ProviderClosed(
        "NO_APPROVED_CONSENSUS_PROVIDER: %s is not approved; CPI remains %s" % (sid, PROVIDER_PENDING)
    )


def refuse_fake_observation() -> None:
    raise ProviderClosed("NO_ENABLED_SOURCE: do not manufacture a Consensus=null observation")


def cpi_overlay_fields() -> dict[str, Any]:
    return {
        "consensus_provider_id": None,
        "consensus_provider_status": PROVIDER_PENDING,
        "automated_collection": "DISABLED",
        "manual_collection": WAITING_FOR_APPROVED_PROVIDER,
    }


def apply_operational_overlay(rec: R.ProspectiveRecorder) -> dict[str, Any]:
    """Write CPI provider-pending + TE retired flags. Never rewrite observations."""
    events = rec.load_events()
    changed_events = False
    cpi = None
    for ev in events:
        if ev.get("macro_event_id") == CPI_EVENT_ID:
            for key, value in cpi_overlay_fields().items():
                if ev.get(key) != value:
                    ev[key] = value
                    changed_events = True
            cpi = ev
    if changed_events:
        rec.save_events(events)
    blob = rec.load_registry()
    changed_reg = False
    for src in blob.get("sources", []):
        if src.get("source_id") == TE_SOURCE_ID:
            desired = {
                "enabled": False,
                "operational_status": "OPERATIONAL_RETIRED_SUBSCRIPTION_CANCELLED",
                "currently_live": False,
                "approved_consensus_provider": False,
                "role": ROLE_CONSENSUS,
            }
            for key, value in desired.items():
                if src.get(key) != value:
                    src[key] = value
                    changed_reg = True
            if src.get("automation_class") == "APPROVED_AUTOMATION_READY":
                src["automation_class"] = "API_AVAILABLE_CREDENTIALS_MISSING"
                changed_reg = True
    if changed_reg:
        rec.registry_path.parent.mkdir(parents=True, exist_ok=True)
        rec.registry_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    cfg = rec.load_config()
    changed_cfg = False
    if cfg.get(TE_LIVE_FLAG) is not False:
        cfg[TE_LIVE_FLAG] = False
        changed_cfg = True
    if cfg.get(R.FORWARD_FLAG) is True:
        raise ProviderClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED must remain false")
    if changed_cfg:
        rec.config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {
        "cpi_event": None if cpi is None else event_provider_status(cpi),
        "events_written": changed_events,
        "registry_written": changed_reg,
        "config_written": changed_cfg,
        "http_requests": 0,
    }


def trading_economics_adapter_live(rec: R.ProspectiveRecorder | None = None) -> bool:
    if te_currently_live():
        return True
    if rec is None:
        return False
    src = rec.source_by_id(TE_SOURCE_ID)
    if src is None:
        return False
    if src.get("currently_live") is True or src.get("enabled") is True:
        return True
    if rec.load_config().get(TE_LIVE_FLAG) is True:
        return True
    ad = A.TradingEconomicsAdapter(env={})
    ok, _reason = ad.is_enabled(rec)
    return bool(ok)


def readiness_check(rec: R.ProspectiveRecorder | None = None, event_id: str = CPI_EVENT_ID) -> dict[str, Any]:
    rec = rec or R.ProspectiveRecorder(PRODUCTION_ROOT)
    event = rec.event_by_id(event_id)
    now = rec.now()
    t48 = {"scheduled_utc": None, "is_open": False, "status": "UNREGISTERED"}
    if event is not None:
        from datetime import timezone as _tz

        _ = _tz
        rows = rec.checkpoint_status_rows(event, now)
        t48_row = next((r for r in rows if r["checkpoint_id"] == "T0-48h"), None)
        status = (t48_row or {}).get("status") or "UNKNOWN"
        t48 = {
            "scheduled_utc": (t48_row or {}).get("checkpoint_utc") or (event.get("checkpoints") or {}).get("T0-48h"),
            "is_open": status == "DUE",
            "status": "NOT_YET_DUE" if status == "FUTURE" else status,
        }
    provider = event_provider_status(event)
    te = rec.source_by_id(TE_SOURCE_ID) or {}
    return {
        "event_registered": event is not None,
        "event_id": event_id,
        "t0_utc": None if event is None else event.get("scheduled_release_utc"),
        "t48h_scheduled_utc": t48.get("scheduled_utc"),
        "t48h_is_open": t48.get("is_open"),
        "t48h_status": t48.get("status"),
        "provider": provider,
        "trading_economics_currently_live": False,
        "trading_economics_enabled": te.get("enabled") is True,
        "trading_economics_code_preserved": Path("forex_bot/decision_quality/trading_economics/client.py").exists(),
        "forward_enabled": rec.collection_enabled(),
        "cpi_components": list(R.CPI_SERIES),
        "http_requests": 0,
    }
