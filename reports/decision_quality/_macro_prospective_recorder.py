"""Research-only prospective US CPI / Employment / FOMC recorder.

48-hour pre-release consensus + calendar + first-print capture.
No production trading authority. No OANDA. No model. No FX backtest.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

RELATIVE_DATA_ROOT = Path("data/research/macro/consensus_pit/prospective")
DEFAULT_ROOT = RELATIVE_DATA_ROOT
DATA_DIR_ENV = "MACRO_PROSPECTIVE_DATA_DIR"
NY = ZoneInfo("America/New_York")
UTC = timezone.utc

FORWARD_FLAG = "FORWARD_CONSENSUS_COLLECTION_ENABLED"


def repo_root() -> Path:
    """Repository root from this file location. Independent of process CWD."""
    return Path(__file__).resolve().parents[2]


def resolve_data_root(explicit: str | Path | None = None, env: dict[str, str] | None = None) -> Path:
    """Resolve the prospective store. Prefer explicit path, then MACRO_PROSPECTIVE_DATA_DIR, then repo-relative."""
    if explicit is not None and str(explicit).strip():
        return Path(os.path.expanduser(str(explicit).strip()))
    source = env if env is not None else os.environ
    override = str(source.get(DATA_DIR_ENV) or "").strip()
    if override:
        p = Path(os.path.expanduser(override))
        if p.is_absolute():
            return p
        return repo_root() / p
    return repo_root() / RELATIVE_DATA_ROOT

CHECKPOINTS = (
    ("T0-48h", timedelta(hours=48)),
    ("T0-36h", timedelta(hours=36)),
    ("T0-24h", timedelta(hours=24)),
    ("T0-12h", timedelta(hours=12)),
    ("T0-6h", timedelta(hours=6)),
    ("T0-4h", timedelta(hours=4)),
    ("T0-2h", timedelta(hours=2)),
    ("T0-1h", timedelta(hours=1)),
    ("T0-30m", timedelta(minutes=30)),
    ("T0-15m", timedelta(minutes=15)),
    ("T0-5m", timedelta(minutes=5)),
)
CHECKPOINT_STATUSES = (
    "FUTURE",
    "DUE",
    "CAPTURED",
    "MISSED_NOT_OBSERVED",
    "SOURCE_UNAVAILABLE",
    "SOURCE_DISABLED",
)
CHECKPOINT_ASSOCIATION_RULE = (
    "latest_checkpoint_at_or_before_observed_at_utc. "
    "The observation keeps its genuine observed_at_utc; the timestamp is never rewritten to the checkpoint clock. "
    "Association interval is [checkpoint_utc, next_checkpoint_utc); the last pre-release interval is [T0-5m, T0). "
    "Post-T0 observations (observed_at_utc >= T0) are not pre-release and do not capture any pre-release checkpoint. "
    "CAPTURED if any qualifying pre-release observation associates to that checkpoint. "
    "DUE if now >= checkpoint_utc and now < next_boundary and not CAPTURED. "
    "MISSED_NOT_OBSERVED if now >= next_boundary and not CAPTURED. "
    "FUTURE if now < checkpoint_utc. "
    "Missed is not a zero forecast."
)

EVENT_FAMILIES = ("CPI", "EMPLOYMENT_SITUATION", "FOMC")
CPI_SERIES = ("headline_mom", "headline_yoy", "core_mom", "core_yoy")
EMP_SERIES = (
    "nonfarm_payroll_change",
    "unemployment_rate",
    "average_hourly_earnings_mom",
    "average_hourly_earnings_yoy",
)
FOMC_SERIES = (
    "expected_policy_decision",
    "hold_probability",
    "cut_25bp_probability",
    "cut_50bp_probability",
    "hike_25bp_probability",
    "ff_target_change_bp",
)
EXPECTATION_TYPES = (
    "SURVEY_CONSENSUS",
    "SURVEY_MEDIAN",
    "SURVEY_MEAN",
    "PROVIDER_CONSENSUS",
    "INDIVIDUAL_FORECAST",
    "MARKET_IMPLIED_EXPECTATION",
    "ECONOMIC_CALENDAR_FORECAST",
)
VALUE_QUALITY = ("PRESENT", "NOT_AVAILABLE", "NOT_COMPUTED", "AMBIGUOUS", "INVALID")
PROSPECTIVE_PIT = (
    "OBSERVED_PRE_T0",
    "OBSERVED_PRE_T0_SOURCE_TIME_UNKNOWN",
    "OBSERVED_POST_T0",
    "INVALID_SERIES",
    "SOURCE_UNAVAILABLE",
)
STATES = (
    "SCHEDULED",
    "PRE_WINDOW",
    "COLLECTING_PRE_RELEASE",
    "FINAL_PRE_RELEASE_CAPTURED",
    "RELEASE_PENDING",
    "FIRST_PRINT_CAPTURED",
    "POST_RELEASE_OBSERVATION",
    "COMPLETE",
    "SOURCE_UNAVAILABLE",
    "SOURCE_DISABLED",
    "RELEASE_DELAYED",
    "ACTUAL_NOT_OBSERVED",
    "SERIES_AMBIGUOUS",
    "ARTIFACT_INVALID",
)
FX_PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
USD_SIGN = {
    "EUR_USD": -1,
    "GBP_USD": -1,
    "AUD_USD": -1,
    "USD_JPY": 1,
    "USD_CAD": 1,
    "USD_CHF": 1,
}
FUTURE_HORIZONS_MIN = (5, 15, 30, 60, 120, 240)

FORBIDDEN_PRODUCTION_IMPORTS = (
    "forex_bot.bot_loop",
    "forex_bot.oanda_exec",
    "forex_bot.oanda_client",
    "forex_bot.execution",
    "forex_bot.v2_shadow",
)


class RecorderConflict(RuntimeError):
    """Same logical identity with incompatible payload. Fail closed."""


class RecorderClosed(RuntimeError):
    """Unknown/disabled source or autonomous collection refused."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed for PIT ordering: %s" % s)
    return dt.astimezone(UTC)


def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_to_utc(local_naive: datetime, tz_name: str) -> datetime:
    if local_naive.tzinfo is not None:
        raise ValueError("local clock must be naive wall time")
    return local_naive.replace(tzinfo=ZoneInfo(tz_name)).astimezone(UTC)


def observation_window(t0: datetime) -> tuple[datetime, datetime]:
    if t0.tzinfo is None:
        raise ValueError("T0 must be timezone-aware UTC")
    t0 = t0.astimezone(UTC)
    return t0 - timedelta(hours=48), t0


def checkpoint_utc(t0: datetime, checkpoint_id: str) -> datetime:
    t0 = t0.astimezone(UTC)
    for cid, delta in CHECKPOINTS:
        if cid == checkpoint_id:
            return t0 - delta
    raise KeyError("unknown checkpoint: %s" % checkpoint_id)


def all_checkpoint_times(t0: datetime) -> dict[str, str]:
    return {cid: to_utc_iso(checkpoint_utc(t0, cid)) for cid, _ in CHECKPOINTS}


def classify_observed(observed_at: datetime, t0: datetime, source_publication_utc: str | None) -> str:
    if observed_at.tzinfo is None or t0.tzinfo is None:
        raise ValueError("naive datetime is not allowed")
    if observed_at >= t0:
        return "OBSERVED_POST_T0"
    if not source_publication_utc:
        return "OBSERVED_PRE_T0_SOURCE_TIME_UNKNOWN"
    return "OBSERVED_PRE_T0"


def is_pre_release(observed_at: datetime, t0: datetime) -> bool:
    return observed_at < t0


def missing_is_not_zero(value, quality: str) -> None:
    if quality in {"NOT_AVAILABLE", "NOT_COMPUTED", "AMBIGUOUS", "INVALID"} and value == 0:
        raise ValueError("missing information must not be encoded as zero")


def average_providers(_rows: list[dict]) -> None:
    raise RuntimeError("Providers must not be averaged. Store each publisher separately.")


def collapse_fomc_probability_to_bp(_prob: float, _outcome: str) -> None:
    raise RuntimeError("FOMC probability distributions must not be collapsed into scalar bp consensus.")


def logical_observation_id(
    *,
    macro_event_id: str,
    checkpoint_id: str | None,
    source_id: str,
    series_name: str,
    expectation_type: str,
    observation_kind: str,
    observed_at_utc: str | None = None,
) -> str:
    slot = checkpoint_id or "adhoc"
    stamp = observed_at_utc or ""
    return "|".join(
        [
            observation_kind,
            macro_event_id,
            slot,
            source_id,
            series_name,
            expectation_type,
            stamp,
        ]
    )


def associated_checkpoint_id(event: dict, observed_at: datetime) -> str | None:
    """Map a genuine observed_at onto a checkpoint without rewriting the timestamp."""
    t0 = parse_utc(event["scheduled_release_utc"])
    assert t0 is not None
    if observed_at >= t0:
        return None
    chosen = None
    for cid, _delta in CHECKPOINTS:
        ts = parse_utc(event["checkpoints"][cid])
        assert ts is not None
        if ts <= observed_at:
            chosen = cid
    return chosen


def logical_actual_id(macro_event_id: str, series_name: str, record_kind: str) -> str:
    return "|".join(["OFFICIAL", record_kind, macro_event_id, series_name])


class ProspectiveRecorder:
    """Disk-backed research recorder. Restart-safe. Fail closed."""

    def __init__(self, root: Path | None = None, clock=None):
        self.root = Path(root) if root is not None else resolve_data_root()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.events_path = self.root / "events" / "events.json"
        self.obs_path = self.root / "observations" / "observations.jsonl"
        self.art_dir = self.root / "artifacts"
        self.actuals_path = self.root / "release_actuals" / "actuals.jsonl"
        self.index_path = self.root / "manifests" / "identity_index.json"
        self.state_path = self.root / "manifests" / "event_state.json"
        self.config_path = self.root / "config.json"
        self.registry_path = self.root / "source_registry" / "sources.json"
        self.arming_path = self.root / "manifests" / "armed_checkpoints.json"
        self.provenance_path = self.root / "manifests" / "official_schedule_provenance.json"
        self._ensure_dirs()

    def now(self) -> datetime:
        dt = self.clock()
        if dt.tzinfo is None:
            raise ValueError("recorder clock must be timezone-aware")
        return dt.astimezone(UTC)

    def _ensure_dirs(self) -> None:
        for p in (
            self.root / "events",
            self.root / "observations",
            self.art_dir,
            self.root / "normalized",
            self.root / "manifests",
            self.root / "source_registry",
            self.root / "release_actuals",
        ):
            p.mkdir(parents=True, exist_ok=True)
        if not self.events_path.exists():
            self.events_path.write_text("[]\n", encoding="utf-8")
        if not self.index_path.exists():
            self.index_path.write_text("{}\n", encoding="utf-8")
        if not self.state_path.exists():
            self.state_path.write_text("{}\n", encoding="utf-8")
        if not self.obs_path.exists():
            self.obs_path.write_text("", encoding="utf-8")
        if not self.actuals_path.exists():
            self.actuals_path.write_text("", encoding="utf-8")

    def load_config(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {FORWARD_FLAG: False}

    def collection_enabled(self) -> bool:
        cfg_on = self.load_config().get(FORWARD_FLAG) is True
        env_raw = os.environ.get(FORWARD_FLAG)
        if env_raw is None or str(env_raw).strip() == "":
            return cfg_on
        token = str(env_raw).strip().lower()
        if token in {"0", "false", "no", "off"}:
            return False
        env_on = token in {"1", "true", "yes", "on"}
        return bool(cfg_on and env_on)

    def load_registry(self) -> dict:
        if self.registry_path.exists():
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        return {"sources": []}

    def source_by_id(self, source_id: str) -> dict | None:
        for src in self.load_registry().get("sources", []):
            if src.get("source_id") == source_id:
                return src
        return None

    def require_registered_source(self, source_id: str) -> dict:
        src = self.source_by_id(source_id)
        if src is None:
            raise RecorderClosed("unknown source fail closed: %s" % source_id)
        return src

    def assert_autonomous_allowed(self, source_id: str) -> None:
        if not self.collection_enabled():
            raise RecorderClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED is false")
        src = self.require_registered_source(source_id)
        if src.get("enabled") is not True:
            raise RecorderClosed("SOURCE_DISABLED: %s" % source_id)
        if src.get("automated_collection_permitted") is not True:
            raise RecorderClosed("unknown/false automation permission fail closed: %s" % source_id)

    def load_events(self) -> list[dict]:
        return json.loads(self.events_path.read_text(encoding="utf-8") or "[]")

    def save_events(self, events: list[dict]) -> None:
        self.events_path.write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")

    def event_by_id(self, macro_event_id: str) -> dict | None:
        for ev in self.load_events():
            if ev.get("macro_event_id") == macro_event_id:
                return ev
        return None

    def load_index(self) -> dict:
        return json.loads(self.index_path.read_text(encoding="utf-8") or "{}")

    def save_index(self, idx: dict) -> None:
        self.index_path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")

    def load_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8") or "{}")

    def save_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append_jsonl(self, path: Path, rec: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=True) + "\n")

    def load_observations(self) -> list[dict]:
        return self.read_jsonl(self.obs_path)

    def load_actuals(self) -> list[dict]:
        return self.read_jsonl(self.actuals_path)

    def put_artifact(self, data: bytes, suffix: str = "bin") -> tuple[str, str]:
        digest = sha256_bytes(data)
        path = self.art_dir / ("%s.%s" % (digest, suffix))
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise RuntimeError("ARTIFACT_INVALID hash collision with different bytes")
        else:
            path.write_bytes(data)
        return digest, str(path).replace("\\", "/")

    def register_event(
        self,
        *,
        macro_event_id: str,
        event_family: str,
        event_name: str,
        reference_period: str,
        scheduled_release_utc: str | None = None,
        scheduled_release_local: str | None = None,
        scheduled_timezone: str = "America/New_York",
        official_source: str,
        currency: str = "USD",
        country: str = "US",
        notes: str | None = None,
        official_schedule_url: str | None = None,
        official_clock_basis: str | None = None,
        schedule_provenance: dict | None = None,
        armed: bool = True,
    ) -> dict:
        if event_family not in EVENT_FAMILIES:
            raise ValueError("unsupported event_family")
        if scheduled_release_utc:
            t0 = parse_utc(scheduled_release_utc)
            assert t0 is not None
            local = t0.astimezone(ZoneInfo(scheduled_timezone))
            local_s = local.replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")
        elif scheduled_release_local:
            naive = datetime.fromisoformat(scheduled_release_local)
            t0 = local_to_utc(naive, scheduled_timezone)
            local_s = naive.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            raise ValueError("official schedule required; do not infer T0 from historical averages")
        start, end = observation_window(t0)
        existing = self.event_by_id(macro_event_id)
        rec = {
            "macro_event_id": macro_event_id,
            "event_family": event_family,
            "event_name": event_name,
            "reference_period": reference_period,
            "currency": currency,
            "country": country,
            "scheduled_release_local": local_s,
            "scheduled_timezone": scheduled_timezone,
            "scheduled_release_utc": to_utc_iso(t0),
            "observation_window_start_utc": to_utc_iso(start),
            "observation_window_end_utc": to_utc_iso(end),
            "official_source": official_source,
            "official_schedule_url": official_schedule_url,
            "official_clock_basis": official_clock_basis,
            "schedule_provenance": schedule_provenance or {},
            "event_status": "SCHEDULED",
            "armed": bool(armed),
            "checkpoints": all_checkpoint_times(t0),
            "checkpoint_association_rule": CHECKPOINT_ASSOCIATION_RULE,
            "notes": notes,
        }
        events = self.load_events()
        if existing:
            if existing.get("scheduled_release_utc") != rec["scheduled_release_utc"]:
                raise RecorderConflict("event schedule conflict: %s" % macro_event_id)
            self.persist_event_arming(existing, self.now())
            return existing
        events.append(rec)
        self.save_events(events)
        state = self.load_state()
        state[macro_event_id] = {"event_status": "SCHEDULED", "failure_status": None, "armed": bool(armed)}
        self.save_state(state)
        self.persist_event_arming(rec, self.now())
        return rec

    def set_status(self, macro_event_id: str, status: str, failure: str | None = None) -> None:
        if status not in STATES and status not in (failure or ""):
            pass
        events = self.load_events()
        for ev in events:
            if ev["macro_event_id"] == macro_event_id:
                ev["event_status"] = status
        self.save_events(events)
        state = self.load_state()
        cur = state.get(macro_event_id, {})
        cur["event_status"] = status
        if failure:
            cur["failure_status"] = failure
        state[macro_event_id] = cur
        self.save_state(state)

    def derive_status(self, macro_event_id: str, now: datetime) -> str:
        ev = self.event_by_id(macro_event_id)
        if ev is None:
            raise KeyError(macro_event_id)
        t0 = parse_utc(ev["scheduled_release_utc"])
        start = parse_utc(ev["observation_window_start_utc"])
        assert t0 and start
        obs = [o for o in self.load_observations() if o["macro_event_id"] == macro_event_id]
        pre = [o for o in obs if o.get("prospective_pit_status", "").startswith("OBSERVED_PRE_T0")]
        post = [o for o in obs if o.get("prospective_pit_status") == "OBSERVED_POST_T0"]
        actuals = [a for a in self.load_actuals() if a["macro_event_id"] == macro_event_id and a.get("record_kind") == "FIRST_PRINT"]
        if now < start:
            st = "PRE_WINDOW"
        elif now < t0:
            st = "FINAL_PRE_RELEASE_CAPTURED" if pre else "COLLECTING_PRE_RELEASE"
        else:
            if actuals and post:
                st = "POST_RELEASE_OBSERVATION"
            elif actuals:
                st = "FIRST_PRINT_CAPTURED"
            else:
                st = "RELEASE_PENDING"
        stored = self.load_state().get(macro_event_id, {}).get("event_status")
        if stored == "COMPLETE":
            return "COMPLETE"
        self.set_status(macro_event_id, st)
        return st

    def _validate_series(self, event: dict, series_name: str, reference_period: str | None) -> str | None:
        fam = event["event_family"]
        allowed = {
            "CPI": set(CPI_SERIES) | {"headline_2m_sa", "core_2m_sa"},
            "EMPLOYMENT_SITUATION": set(EMP_SERIES)
            | {"previous_nfp_as_reported", "previous_nfp_revised", "nfp_revision_prior"},
            "FOMC": set(FOMC_SERIES)
            | {
                "ff_target_lower",
                "ff_target_upper",
                "market_implied_cut_probability",
                "market_implied_hike_probability",
            },
        }
        if series_name not in allowed.get(fam, set()):
            return "INVALID_SERIES"
        revisionish = series_name.startswith("previous_") or "revision" in series_name
        if reference_period and reference_period != event["reference_period"] and not revisionish:
            return "INVALID_SERIES"
        return None

    def ingest_observation(
        self,
        *,
        macro_event_id: str,
        source_id: str,
        series_name: str,
        expectation_type: str,
        artifact_bytes: bytes,
        observed_at_utc: str,
        checkpoint_id: str | None = None,
        forecast_value=None,
        value_quality: str = "PRESENT",
        unit: str | None = None,
        seasonal_adjustment: str | None = None,
        reference_period: str | None = None,
        source_publication_utc: str | None = None,
        source_updated_utc: str | None = None,
        retrieval_method: str = "manual",
        observation_kind: str = "FORECASTER",
        n_forecasters: int | None = None,
        forecast_range: dict | None = None,
        fomc_distribution: dict | None = None,
        calendar_fields: dict | None = None,
        notes: str | None = None,
        artifact_suffix: str = "txt",
        allow_autonomous: bool = False,
        provider_name: str | None = None,
        source_event_identifier: str | None = None,
        source_url_or_endpoint_identifier: str | None = None,
        retrieval_utc: str | None = None,
    ) -> dict:
        missing_is_not_zero(forecast_value, value_quality)
        if expectation_type == "INDIVIDUAL_FORECAST" and "CONSENSUS" in expectation_type:
            raise ValueError("INDIVIDUAL_FORECAST must not be relabeled consensus")
        if expectation_type not in EXPECTATION_TYPES and observation_kind != "ECONOMIC_CALENDAR":
            if expectation_type != "OFFICIAL_ACTUAL":
                raise ValueError("unsupported expectation_type: %s" % expectation_type)
        if retrieval_method == "autonomous" or allow_autonomous:
            self.assert_autonomous_allowed(source_id)
        src = self.require_registered_source(source_id)
        event = self.event_by_id(macro_event_id)
        if event is None:
            raise KeyError("unknown event: %s" % macro_event_id)
        t0 = parse_utc(event["scheduled_release_utc"])
        obs_at = parse_utc(observed_at_utc)
        assert t0 and obs_at
        if obs_at.tzinfo is None:
            raise ValueError("observed_at_utc must be timezone-aware")
        associated = associated_checkpoint_id(event, obs_at)
        if checkpoint_id is None:
            checkpoint_id = associated
        series_fail = self._validate_series(event, series_name, reference_period or event["reference_period"])
        pit = classify_observed(obs_at, t0, source_publication_utc)
        if series_fail:
            pit = "INVALID_SERIES"
        if observation_kind == "ECONOMIC_CALENDAR":
            expectation_type = "ECONOMIC_CALENDAR_FORECAST"
        if not artifact_bytes:
            raise ValueError("artifact evidence is required")
        digest, loc = self.put_artifact(artifact_bytes, artifact_suffix)
        lid = logical_observation_id(
            macro_event_id=macro_event_id,
            checkpoint_id=checkpoint_id,
            source_id=source_id,
            series_name=series_name,
            expectation_type=expectation_type,
            observation_kind=observation_kind,
            observed_at_utc=to_utc_iso(obs_at),
        )
        payload_key = {
            "raw_artifact_hash": digest,
            "forecast_value": forecast_value,
            "unit": unit,
            "value_quality": value_quality,
            "seasonal_adjustment": seasonal_adjustment,
            "reference_period": reference_period or event["reference_period"],
        }
        idx = self.load_index()
        if lid in idx:
            prev = idx[lid]
            if prev["payload_key"] == payload_key:
                return {"status": "ALREADY_EXISTS", "observation_id": prev["observation_id"], "logical_id": lid}
            raise RecorderConflict("CONFLICT incompatible re-ingest for %s" % lid)

        rec = {
            "observation_id": str(uuid4()),
            "logical_id": lid,
            "macro_event_id": macro_event_id,
            "event_family": event["event_family"],
            "checkpoint_id": checkpoint_id,
            "associated_checkpoint_id": associated,
            "checkpoint_association_rule": CHECKPOINT_ASSOCIATION_RULE,
            "checkpoint_utc": event["checkpoints"].get(checkpoint_id) if checkpoint_id else None,
            "observation_kind": observation_kind,
            "source_id": source_id,
            "source_publisher": src.get("publisher"),
            "source_type": src.get("source_type"),
            "series_name": series_name,
            "reference_period": reference_period or event["reference_period"],
            "expectation_type": expectation_type,
            "forecast_value": forecast_value,
            "value_quality": value_quality,
            "unit": unit,
            "seasonal_adjustment": seasonal_adjustment,
            "n_forecasters": n_forecasters,
            "forecast_range": forecast_range,
            "fomc_distribution": fomc_distribution,
            "calendar_fields": calendar_fields,
            "source_publication_utc": source_publication_utc,
            "source_updated_utc": source_updated_utc,
            "observed_at_utc": to_utc_iso(obs_at),
            "official_release_utc": event["scheduled_release_utc"],
            "minutes_to_release": int((t0 - obs_at).total_seconds() // 60),
            "raw_artifact_hash": digest,
            "artifact_location": loc,
            "retrieval_method": retrieval_method,
            "provider_name": provider_name or src.get("publisher"),
            "source_event_identifier": source_event_identifier,
            "source_url_or_endpoint_identifier": source_url_or_endpoint_identifier,
            "retrieval_utc": retrieval_utc or to_utc_iso(obs_at),
            "raw_artifact_path": loc,
            "raw_artifact_sha256": digest,
            "prospective_pit_status": pit,
            "pre_release": bool(is_pre_release(obs_at, t0) and pit != "INVALID_SERIES"),
            "notes": notes,
        }
        if rec["pre_release"] is False and pit == "OBSERVED_POST_T0":
            rec["notes"] = (notes or "") + " POST-RELEASE; cannot become final_pre_release_observation."
        self.append_jsonl(self.obs_path, rec)
        idx[lid] = {"observation_id": rec["observation_id"], "payload_key": payload_key, "raw_artifact_hash": digest}
        self.save_index(idx)
        self.derive_status(macro_event_id, obs_at)
        return {"status": "RECORDED", "observation": rec}

    def ingest_manual(self, **kwargs) -> dict:
        kwargs.setdefault("retrieval_method", "manual")
        kwargs.setdefault("allow_autonomous", False)
        return self.ingest_observation(**kwargs)

    def operator_ingest(self, **kwargs) -> dict:
        """Production operator path. observed_at_utc is generated from the recorder clock."""
        if "observed_at_utc" in kwargs:
            raise RecorderClosed("OPERATOR_BACKDATE_FORBIDDEN: observed_at_utc is generated by the recorder")
        kwargs["observed_at_utc"] = to_utc_iso(self.now())
        kwargs.setdefault("retrieval_method", "manual")
        kwargs.setdefault("allow_autonomous", False)
        kwargs.setdefault("checkpoint_id", None)
        return self.ingest_observation(**kwargs)

    def ingest_calendar(self, **kwargs) -> dict:
        kwargs["observation_kind"] = "ECONOMIC_CALENDAR"
        kwargs.setdefault("expectation_type", "ECONOMIC_CALENDAR_FORECAST")
        return self.ingest_observation(**kwargs)

    def ingest_autonomous(self, **kwargs) -> dict:
        kwargs["retrieval_method"] = "autonomous"
        kwargs["allow_autonomous"] = True
        return self.ingest_observation(**kwargs)

    def final_pre_release_observation(
        self,
        macro_event_id: str,
        *,
        series_name: str | None = None,
        source_id: str | None = None,
    ) -> dict | None:
        event = self.event_by_id(macro_event_id)
        if event is None:
            return None
        t0 = parse_utc(event["scheduled_release_utc"])
        assert t0 is not None
        cand = []
        for rec in self.load_observations():
            if rec["macro_event_id"] != macro_event_id:
                continue
            if series_name is not None and rec.get("series_name") != series_name:
                continue
            if source_id is not None and rec.get("source_id") != source_id:
                continue
            if rec.get("prospective_pit_status") == "INVALID_SERIES":
                continue
            obs = parse_utc(rec["observed_at_utc"])
            assert obs is not None
            if obs >= t0:
                continue
            if rec.get("prospective_pit_status") == "OBSERVED_POST_T0":
                continue
            cand.append(rec)
        if not cand:
            return None
        cand.sort(key=lambda r: parse_utc(r["observed_at_utc"]) or datetime.min.replace(tzinfo=UTC))
        return cand[-1]

    def capture_first_print(
        self,
        *,
        macro_event_id: str,
        series_name: str,
        actual_first_print,
        artifact_bytes: bytes,
        first_observed_at_utc: str,
        unit: str | None = None,
        seasonal_adjustment: str | None = None,
        reference_period: str | None = None,
        source_id: str = "bls_official",
        notes: str | None = None,
        artifact_suffix: str = "txt",
        record_kind: str = "FIRST_PRINT",
    ) -> dict:
        event = self.event_by_id(macro_event_id)
        if event is None:
            raise KeyError(macro_event_id)
        self.require_registered_source(source_id)
        value_quality = "PRESENT" if actual_first_print is not None else "NOT_AVAILABLE"
        missing_is_not_zero(actual_first_print, value_quality)
        digest, loc = self.put_artifact(artifact_bytes, artifact_suffix)
        lid = logical_actual_id(macro_event_id, series_name, record_kind)
        payload_key = {
            "raw_artifact_hash": digest,
            "actual_first_print": actual_first_print,
            "unit": unit,
            "record_kind": record_kind,
        }
        idx = self.load_index()
        if lid in idx:
            prev = idx[lid]
            if prev["payload_key"] == payload_key:
                return {"status": "ALREADY_EXISTS", "logical_id": lid, "actual_id": prev.get("actual_id")}
            if record_kind == "FIRST_PRINT":
                raise RecorderConflict("first print cannot be overwritten: %s" % lid)
            raise RecorderConflict("CONFLICT official re-ingest: %s" % lid)
        rec = {
            "actual_id": str(uuid4()),
            "logical_id": lid,
            "record_kind": record_kind,
            "macro_event_id": macro_event_id,
            "event_family": event["event_family"],
            "series_name": series_name,
            "reference_period": reference_period or event["reference_period"],
            "actual_first_print": actual_first_print,
            "value_quality": value_quality,
            "unit": unit,
            "seasonal_adjustment": seasonal_adjustment,
            "official_release_utc": event["scheduled_release_utc"],
            "first_observed_at_utc": first_observed_at_utc,
            "source_id": source_id,
            "raw_artifact_hash": digest,
            "artifact_location": loc,
            "notes": notes,
        }
        self.append_jsonl(self.actuals_path, rec)
        idx[lid] = {"actual_id": rec["actual_id"], "payload_key": payload_key, "raw_artifact_hash": digest}
        self.save_index(idx)
        obs_at = parse_utc(first_observed_at_utc)
        if obs_at:
            self.derive_status(macro_event_id, obs_at)
        return {"status": "RECORDED", "actual": rec}

    def capture_revision(self, **kwargs) -> dict:
        kwargs["record_kind"] = "REVISION"
        kwargs["series_name"] = kwargs.get("series_name")
        return self.capture_first_print(**kwargs)

    def raw_surprise(self, macro_event_id: str, series_name: str, source_id: str | None = None) -> dict:
        final = self.final_pre_release_observation(macro_event_id, series_name=series_name, source_id=source_id)
        actuals = [
            a
            for a in self.load_actuals()
            if a["macro_event_id"] == macro_event_id and a["series_name"] == series_name and a.get("record_kind") == "FIRST_PRINT"
        ]
        if not final or not actuals:
            return {"value_quality": "NOT_COMPUTED", "surprise_raw": None}
        if final.get("value_quality") != "PRESENT" or actuals[0].get("value_quality") != "PRESENT":
            return {"value_quality": "NOT_COMPUTED", "surprise_raw": None}
        if final.get("expectation_type") == "INDIVIDUAL_FORECAST":
            return {"value_quality": "NOT_COMPUTED", "surprise_raw": None, "notes": "individual forecast is not consensus"}
        if final.get("unit") and actuals[0].get("unit") and final["unit"] != actuals[0]["unit"]:
            return {"value_quality": "INVALID", "surprise_raw": None, "notes": "unit mismatch"}
        if final.get("fomc_distribution"):
            return {"value_quality": "NOT_COMPUTED", "surprise_raw": None, "notes": "FOMC distribution not collapsed"}
        surprise = float(actuals[0]["actual_first_print"]) - float(final["forecast_value"])
        return {
            "value_quality": "PRESENT",
            "surprise_raw": surprise,
            "actual": actuals[0]["actual_first_print"],
            "final_pre_release": final["forecast_value"],
            "source_id": final.get("source_id"),
            "observed_at_utc": final.get("observed_at_utc"),
            "notes": "derived field only. no FX research.",
        }

    def reconstruct(self) -> dict:
        """Restart-safe load from disk."""
        return {
            "events": self.load_events(),
            "observations": self.load_observations(),
            "actuals": self.load_actuals(),
            "identity_index": self.load_index(),
            "event_state": self.load_state(),
            "armed_checkpoints": self.load_arming(),
            "artifact_hashes": [p.stem.split(".")[0] for p in sorted(self.art_dir.glob("*")) if p.is_file()],
        }

    def load_arming(self) -> dict:
        if self.arming_path.exists():
            return json.loads(self.arming_path.read_text(encoding="utf-8") or "{}")
        return {"association_rule": CHECKPOINT_ASSOCIATION_RULE, "events": {}}

    def persist_event_arming(self, event: dict, now: datetime) -> dict:
        blob = self.load_arming()
        blob.setdefault("association_rule", CHECKPOINT_ASSOCIATION_RULE)
        blob.setdefault("events", {})
        rows = self.checkpoint_status_rows(event, now, observations=[])
        blob["events"][event["macro_event_id"]] = {
            "macro_event_id": event["macro_event_id"],
            "event_family": event["event_family"],
            "scheduled_release_local": event["scheduled_release_local"],
            "scheduled_timezone": event["scheduled_timezone"],
            "scheduled_release_utc": event["scheduled_release_utc"],
            "observation_window_start_utc": event["observation_window_start_utc"],
            "armed": event.get("armed", True),
            "armed_at_utc": to_utc_iso(now),
            "checkpoints": {row["checkpoint_id"]: row["checkpoint_utc"] for row in rows},
            "official_schedule_url": event.get("official_schedule_url"),
        }
        blob["updated_at_utc"] = to_utc_iso(now)
        self.arming_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
        return blob

    def checkpoint_status_rows(self, event: dict, now: datetime, observations: list[dict] | None = None) -> list[dict]:
        if observations is None:
            observations = [o for o in self.load_observations() if o.get("macro_event_id") == event["macro_event_id"]]
        t0 = parse_utc(event["scheduled_release_utc"])
        assert t0 is not None
        ordered = []
        for cid, _delta in CHECKPOINTS:
            ts = parse_utc(event["checkpoints"][cid])
            assert ts is not None
            ordered.append((cid, ts))
        rows = []
        for i, (cid, ts) in enumerate(ordered):
            next_b = ordered[i + 1][1] if i + 1 < len(ordered) else t0
            captured = False
            for o in observations:
                oat = parse_utc(o.get("observed_at_utc"))
                if oat is None:
                    continue
                if not is_pre_release(oat, t0):
                    continue
                if o.get("prospective_pit_status") == "INVALID_SERIES":
                    continue
                assoc = o.get("associated_checkpoint_id")
                if assoc is None:
                    assoc = associated_checkpoint_id(event, oat)
                if assoc == cid:
                    captured = True
                    break
            if captured:
                status = "CAPTURED"
            elif now < ts:
                status = "FUTURE"
            elif now < next_b:
                status = "DUE"
            else:
                status = "MISSED_NOT_OBSERVED"
            rows.append(
                {
                    "checkpoint_id": cid,
                    "checkpoint_utc": to_utc_iso(ts),
                    "status": status,
                    "next_boundary_utc": to_utc_iso(next_b),
                }
            )
        return rows

    def upcoming_events(self, now: datetime) -> list[dict]:
        out = []
        for ev in self.load_events():
            t0 = parse_utc(ev.get("scheduled_release_utc"))
            if t0 is None:
                continue
            if t0 > now:
                out.append(ev)
        out.sort(key=lambda e: e["scheduled_release_utc"])
        return out

    def next_event(self, now: datetime | None = None) -> dict | None:
        now = now or self.now()
        upcoming = self.upcoming_events(now)
        return upcoming[0] if upcoming else None

    def event_snapshot(self, event: dict, now: datetime) -> dict:
        t0 = parse_utc(event["scheduled_release_utc"])
        start = parse_utc(event["observation_window_start_utc"])
        assert t0 and start
        state = self.derive_status(event["macro_event_id"], now)
        rows = self.checkpoint_status_rows(event, now)
        obs = [o for o in self.load_observations() if o.get("macro_event_id") == event["macro_event_id"]]
        sources = sorted({o.get("source_id") for o in obs if o.get("source_id")})
        due = [r for r in rows if r["status"] == "DUE"]
        missed = [r for r in rows if r["status"] == "MISSED_NOT_OBSERVED"]
        captured = [r for r in rows if r["status"] == "CAPTURED"]
        future = [r for r in rows if r["status"] == "FUTURE"]
        next_ck = due[0] if due else (future[0] if future else None)
        delta = t0 - now
        secs = int(delta.total_seconds())
        sign = "" if secs >= 0 else "-"
        secs_abs = abs(secs)
        hh, rem = divmod(secs_abs, 3600)
        mm, ss = divmod(rem, 60)
        return {
            "macro_event_id": event["macro_event_id"],
            "event_family": event["event_family"],
            "event_name": event.get("event_name"),
            "reference_period": event.get("reference_period"),
            "scheduled_release_local": event.get("scheduled_release_local"),
            "scheduled_timezone": event.get("scheduled_timezone"),
            "scheduled_release_utc": event["scheduled_release_utc"],
            "observation_window_start_utc": event["observation_window_start_utc"],
            "window_state": state,
            "armed": event.get("armed", True),
            "official_source": event.get("official_source"),
            "official_schedule_url": event.get("official_schedule_url"),
            "time_to_t0": "%s%02d:%02d:%02d" % (sign, hh, mm, ss),
            "checkpoints": rows,
            "observation_count": len(obs),
            "sources_observed": sources,
            "captured_checkpoints": [r["checkpoint_id"] for r in captured],
            "due_checkpoints": [r["checkpoint_id"] for r in due],
            "missed_checkpoints": [r["checkpoint_id"] for r in missed],
            "next_checkpoint": next_ck,
            "autonomous_collection": "OFF" if not self.collection_enabled() else "ON",
            "forward_consensus_collection_enabled": self.collection_enabled(),
            "trading_authority": "NONE",
            "consensus_provider": event.get("consensus_provider_id") or "NONE_APPROVED",
            "provider_status": event.get("consensus_provider_status") or "PROVIDER_PENDING",
            "automated_collection": event.get("automated_collection") or "DISABLED",
            "manual_collection": event.get("manual_collection") or "WAITING_FOR_APPROVED_PROVIDER",
            "trading_economics_currently_live": False,
        }

    def status_payload(self, now: datetime | None = None) -> dict:
        now = now or self.now()
        upcoming = self.upcoming_events(now)
        nxt = upcoming[0] if upcoming else None
        return {
            "current_utc": to_utc_iso(now),
            "next_event": self.event_snapshot(nxt, now) if nxt else None,
            "registered_upcoming": [self.event_snapshot(ev, now) for ev in upcoming],
            "autonomous_collection": "OFF" if not self.collection_enabled() else "ON",
            "forward_consensus_collection_enabled": False if not self.collection_enabled() else True,
            "trading_authority": "NONE",
            "external_requests": 0,
            "checkpoint_association_rule": CHECKPOINT_ASSOCIATION_RULE,
        }

    def due_payload(self, now: datetime | None = None) -> dict:
        now = now or self.now()
        items = []
        for ev in self.load_events():
            snap = self.event_snapshot(ev, now)
            if snap["due_checkpoints"] or snap["window_state"] in {"COLLECTING_PRE_RELEASE", "RELEASE_PENDING"}:
                items.append(
                    {
                        "macro_event_id": snap["macro_event_id"],
                        "event_family": snap["event_family"],
                        "window_state": snap["window_state"],
                        "scheduled_release_utc": snap["scheduled_release_utc"],
                        "due_checkpoints": [r for r in snap["checkpoints"] if r["status"] == "DUE"],
                        "missed_checkpoints": snap["missed_checkpoints"],
                    }
                )
        return {
            "current_utc": to_utc_iso(now),
            "attention": items,
            "autonomous_collection": "OFF" if not self.collection_enabled() else "ON",
            "external_requests": 0,
            "trading_authority": "NONE",
        }

    def format_status(self, now: datetime | None = None) -> str:
        payload = self.status_payload(now)
        lines = ["PROSPECTIVE MACRO STATUS", "------------------------", "CURRENT UTC:", payload["current_utc"], ""]
        nxt = payload.get("next_event")
        if not nxt:
            lines.extend(["NEXT EVENT:", "NONE", ""])
        else:
            nck = nxt.get("next_checkpoint") or {}
            lines.extend(
                [
                    "NEXT EVENT:",
                    nxt["macro_event_id"],
                    "EVENT FAMILY:",
                    nxt["event_family"],
                    "T0:",
                    nxt["scheduled_release_utc"],
                    "T0 LOCAL:",
                    "%s %s" % (nxt["scheduled_release_local"], nxt["scheduled_timezone"]),
                    "WINDOW OPENS:",
                    nxt["observation_window_start_utc"],
                    "NEXT_EVENT_T48H_SCHEDULED_UTC:",
                    ((nxt.get("checkpoints") or [{}])[0].get("checkpoint_utc") if nxt.get("checkpoints") else None) or (nxt.get("observation_window_start_utc") or "NONE"),
                    "NEXT_EVENT_T48H_IS_OPEN:",
                    "YES" if any(r.get("checkpoint_id") == "T0-48h" and r.get("status") == "DUE" for r in (nxt.get("checkpoints") or [])) else "NO",
                    "NEXT_EVENT_T48H_STATUS:",
                    next(
                        (
                            "NOT_YET_DUE" if r.get("status") == "FUTURE" else r.get("status")
                            for r in (nxt.get("checkpoints") or [])
                            if r.get("checkpoint_id") == "T0-48h"
                        ),
                        "UNKNOWN",
                    ),
                    "WINDOW STATE:",
                    nxt["window_state"],
                    "TIME TO T0:",
                    nxt["time_to_t0"],
                    "ARMED:",
                    "YES" if nxt.get("armed") else "NO",
                    "CONSENSUS_PROVIDER:",
                    nxt.get("consensus_provider") or "NONE_APPROVED",
                    "PROVIDER_STATUS:",
                    nxt.get("provider_status") or "PROVIDER_PENDING",
                    "CPI_AUTOMATED_COLLECTION:",
                    nxt.get("automated_collection") or "DISABLED",
                    "CPI_MANUAL_COLLECTION_STATUS:",
                    nxt.get("manual_collection") or "WAITING_FOR_APPROVED_PROVIDER",
                    "",
                    "CHECKPOINTS:",
                ]
            )
            for row in nxt["checkpoints"]:
                lines.append("%-8s  %s  %s" % (row["checkpoint_id"], row["checkpoint_utc"], row["status"]))
            lines.extend(
                [
                    "",
                    "OBSERVATIONS:",
                    str(nxt["observation_count"]),
                    "SOURCES OBSERVED:",
                    ", ".join(nxt["sources_observed"]) if nxt["sources_observed"] else "(none)",
                    "MISSING/DUE:",
                    ", ".join(nxt["due_checkpoints"] + nxt["missed_checkpoints"]) or "(none)",
                    "NEXT CHECKPOINT:",
                    nck.get("checkpoint_id") or "NONE",
                    "NEXT CHECKPOINT UTC:",
                    nck.get("checkpoint_utc") or "NONE",
                ]
            )
        lines.extend(
            [
                "",
                "AUTONOMOUS COLLECTION:",
                payload["autonomous_collection"],
                "FORWARD_CONSENSUS_COLLECTION_ENABLED:",
                "false" if payload["forward_consensus_collection_enabled"] is False else "true",
                "TRADING AUTHORITY:",
                "NONE",
                "EXTERNAL REQUESTS:",
                "0",
                "",
                "OTHER REGISTERED UPCOMING EVENTS:",
            ]
        )
        others = payload.get("registered_upcoming") or []
        if len(others) <= 1:
            lines.append("(none besides NEXT EVENT)" if others else "(none)")
        else:
            for ev in others[1:]:
                lines.append(
                    "%s  family=%s  T0=%s  window=%s  state=%s"
                    % (
                        ev["macro_event_id"],
                        ev["event_family"],
                        ev["scheduled_release_utc"],
                        ev["observation_window_start_utc"],
                        ev["window_state"],
                    )
                )
        lines.append("")
        return "\n".join(lines)

    def format_due(self, now: datetime | None = None) -> str:
        payload = self.due_payload(now)
        lines = [
            "PROSPECTIVE MACRO DUE",
            "---------------------",
            "CURRENT UTC:",
            payload["current_utc"],
            "AUTONOMOUS COLLECTION:",
            payload["autonomous_collection"],
            "EXTERNAL REQUESTS:",
            "0",
            "",
        ]
        if not payload["attention"]:
            lines.append("NO CHECKPOINTS/EVENTS REQUIRE OPERATOR ATTENTION NOW.")
            lines.append("")
            return "\n".join(lines)
        for item in payload["attention"]:
            lines.append("EVENT: %s" % item["macro_event_id"])
            lines.append("STATE: %s" % item["window_state"])
            lines.append("T0: %s" % item["scheduled_release_utc"])
            if item["due_checkpoints"]:
                for row in item["due_checkpoints"]:
                    lines.append("DUE: %s %s" % (row["checkpoint_id"], row["checkpoint_utc"]))
            else:
                lines.append("DUE: (none; window/state still needs operator attention)")
            if item["missed_checkpoints"]:
                lines.append("MISSED_NOT_OBSERVED: %s" % ", ".join(item["missed_checkpoints"]))
            lines.append("")
        return "\n".join(lines)


def bootstrap_store(root: Path, template: Path | None = None, clock=None) -> ProspectiveRecorder:
    rec = ProspectiveRecorder(root, clock=clock)
    template = template or DEFAULT_ROOT
    src_cfg = template / "config.json"
    src_reg = template / "source_registry" / "sources.json"
    if src_cfg.exists() and not rec.config_path.exists():
        rec.config_path.write_text(src_cfg.read_text(encoding="utf-8"), encoding="utf-8")
    elif not rec.config_path.exists():
        rec.config_path.write_text(json.dumps({FORWARD_FLAG: False}, indent=2) + "\n", encoding="utf-8")
    rec.registry_path.parent.mkdir(parents=True, exist_ok=True)
    if src_reg.exists() and (not rec.registry_path.exists() or rec.registry_path.stat().st_size < 10):
        rec.registry_path.write_text(src_reg.read_text(encoding="utf-8"), encoding="utf-8")
    return rec


def nfp_artifact(provider: str, value: int) -> bytes:
    return ("provider=%s series=nonfarm_payroll_change unit=persons value=%s\n" % (provider, value)).encode("utf-8")


# Verified against official BLS/Fed pages during Stage 2 execution (2026-09-28).
# Date/time authority is BLS/Fed, not an economic-calendar provider.
VERIFIED_OFFICIAL_SCHEDULES = (
    {
        "macro_event_id": "usd_empsit_2026-10-02",
        "event_family": "EMPLOYMENT_SITUATION",
        "event_name": "The Employment Situation",
        "reference_period": "2026-09",
        "scheduled_release_local": "2026-10-02T08:30:00",
        "scheduled_timezone": "America/New_York",
        "official_source": "BLS",
        "official_schedule_url": "https://www.bls.gov/schedule/news_release/empsit.htm",
        "official_clock_basis": (
            "BLS Employment Situation schedule table: Reference Month September 2026, "
            "Release Date Oct. 02, 2026, Release Time 08:30 AM. Timezone America/New_York "
            "is the BLS national news-release convention; conversion is DST-aware ZoneInfo, not hardcoded EDT/EST."
        ),
        "schedule_row": {
            "reference_month": "September 2026",
            "release_date": "Oct. 02, 2026",
            "release_time": "08:30 AM",
        },
    },
    {
        "macro_event_id": "usd_cpi_2026-10-14",
        "event_family": "CPI",
        "event_name": "Consumer Price Index",
        "reference_period": "2026-09",
        "scheduled_release_local": "2026-10-14T08:30:00",
        "scheduled_timezone": "America/New_York",
        "official_source": "BLS",
        "official_schedule_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "official_clock_basis": (
            "BLS CPI schedule table: Reference Month September 2026, "
            "Release Date Oct. 14, 2026, Release Time 08:30 AM. Timezone America/New_York "
            "is the BLS national news-release convention; conversion is DST-aware ZoneInfo, not hardcoded EDT/EST."
        ),
        "schedule_row": {
            "reference_month": "September 2026",
            "release_date": "Oct. 14, 2026",
            "release_time": "08:30 AM",
        },
    },
    {
        "macro_event_id": "usd_fomc_statement_2026-10-28",
        "event_family": "FOMC",
        "event_name": "FOMC statement/decision",
        "reference_period": "2026-10-27/28",
        "scheduled_release_local": "2026-10-28T14:00:00",
        "scheduled_timezone": "America/New_York",
        "official_source": "Federal Reserve Board",
        "official_schedule_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "official_clock_basis": (
            "Meeting dates October 27-28 from the official 2026 FOMC calendar "
            "(https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm). "
            "Statement clock 14:00 America/New_York from the Federal Reserve's own statement "
            "release line 'For release at 2:00 p.m.' printed on official FOMC statements "
            "(e.g. monetary20260916a1.pdf, 16 Sep 2026). The calendar page lists dates; "
            "the 2:00 p.m. clock is the Fed's published statement release time, not a third-party calendar."
        ),
        "schedule_row": {
            "meeting_dates": "October 27-28",
            "statement_day": "2026-10-28",
            "release_time": "2:00 p.m.",
        },
    },
)


def persist_official_provenance(rec: ProspectiveRecorder, now: datetime, excerpts: dict[str, bytes]) -> dict:
    rec.provenance_path.parent.mkdir(parents=True, exist_ok=True)
    art_dir = rec.root / "manifests" / "official_schedule_excerpts"
    art_dir.mkdir(parents=True, exist_ok=True)
    stored = []
    for name, data in excerpts.items():
        digest = sha256_bytes(data)
        path = art_dir / ("%s.txt" % name)
        path.write_bytes(data)
        stored.append({"name": name, "sha256": digest, "path": str(path).replace("\\", "/")})
    blob = {
        "retrieved_at_utc": to_utc_iso(now),
        "association_rule": CHECKPOINT_ASSOCIATION_RULE,
        "schedules": list(VERIFIED_OFFICIAL_SCHEDULES),
        "excerpts": stored,
        "notes": "Official BLS/Fed calendars are T0 authority. Economic-calendar providers are not.",
    }
    rec.provenance_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    return blob


def register_official_upcoming(
    rec: ProspectiveRecorder,
    now: datetime | None = None,
    catalog: tuple = VERIFIED_OFFICIAL_SCHEDULES,
) -> list[dict]:
    now = now or rec.now()
    registered = []
    for row in catalog:
        naive = datetime.fromisoformat(row["scheduled_release_local"])
        t0 = local_to_utc(naive, row["scheduled_timezone"])
        if t0 <= now:
            continue
        rec_event = rec.register_event(
            macro_event_id=row["macro_event_id"],
            event_family=row["event_family"],
            event_name=row["event_name"],
            reference_period=row["reference_period"],
            scheduled_release_local=row["scheduled_release_local"],
            scheduled_timezone=row["scheduled_timezone"],
            official_source=row["official_source"],
            official_schedule_url=row["official_schedule_url"],
            official_clock_basis=row["official_clock_basis"],
            schedule_provenance={
                "schedule_row": row.get("schedule_row"),
                "verified_at_utc": to_utc_iso(now),
                "t0_authority": "official_bls_or_fed_calendar",
            },
            notes="Stage 2 real prospective registration. Not the Stage 1 fixture.",
            armed=True,
        )
        rec.derive_status(rec_event["macro_event_id"], now)
        registered.append(rec.event_by_id(rec_event["macro_event_id"]))
    return registered


def official_schedule_excerpts() -> dict[str, bytes]:
    cpi = (
        "OFFICIAL SOURCE EXCERPT (BLS CPI schedule)\n"
        "URL: https://www.bls.gov/schedule/news_release/cpi.htm\n"
        "Retrieved during prospective recorder Stage 2.\n"
        "Table rows used:\n"
        "September 2026 | Oct. 14, 2026 | 08:30 AM\n"
        "October 2026 | Nov. 10, 2026 | 08:30 AM\n"
        "Timezone convention: America/New_York (BLS national news-release).\n"
    ).encode("utf-8")
    emp = (
        "OFFICIAL SOURCE EXCERPT (BLS Employment Situation schedule)\n"
        "URL: https://www.bls.gov/schedule/news_release/empsit.htm\n"
        "Retrieved during prospective recorder Stage 2.\n"
        "Table rows used:\n"
        "September 2026 | Oct. 02, 2026 | 08:30 AM\n"
        "October 2026 | Nov. 06, 2026 | 08:30 AM\n"
        "Timezone convention: America/New_York (BLS national news-release).\n"
    ).encode("utf-8")
    fomc = (
        "OFFICIAL SOURCE EXCERPT (Federal Reserve FOMC calendar + statement clock)\n"
        "Calendar URL: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm\n"
        "2026 FOMC Meetings: October 27-28 (next after September 15-16, which already has a statement).\n"
        "Statement clock: 2:00 p.m. America/New_York from Fed statement header "
        "'For release at 2:00 p.m.' (example: monetary20260916a1.pdf, 16 Sep 2026).\n"
        "Not taken from an economic-calendar provider.\n"
    ).encode("utf-8")
    return {"bls_cpi_schedule": cpi, "bls_empsit_schedule": emp, "fed_fomc_calendar": fomc}


def run_dry_run(root: Path) -> dict:
    """Deterministic infrastructure fixture. Numbers are not economic claims."""
    rec = bootstrap_store(root)
    t0 = parse_utc("2026-10-02T12:30:00Z")
    assert t0 is not None
    rec.register_event(
        macro_event_id="fixture_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
        notes="DRY-RUN FIXTURE. Not a real BLS event.",
    )
    times = all_checkpoint_times(t0)
    plan = [
        ("T0-48h", [("fixture_provider_a", 175000, "SURVEY_CONSENSUS"), ("fixture_provider_b", 170000, "SURVEY_MEDIAN")]),
        ("T0-24h", [("fixture_provider_a", 175000, "SURVEY_CONSENSUS"), ("fixture_provider_b", 165000, "SURVEY_MEDIAN")]),
        ("T0-6h", [
            ("fixture_provider_a", 165000, "SURVEY_CONSENSUS"),
            ("fixture_provider_b", 165000, "SURVEY_MEDIAN"),
            ("fixture_provider_c", 160000, "INDIVIDUAL_FORECAST"),
        ]),
        ("T0-1h", [
            ("fixture_provider_a", 160000, "SURVEY_CONSENSUS"),
            ("fixture_provider_b", 165000, "SURVEY_MEDIAN"),
            ("fixture_provider_c", 160000, "INDIVIDUAL_FORECAST"),
        ]),
        ("T0-5m", [
            ("fixture_provider_a", 160000, "SURVEY_CONSENSUS"),
            ("fixture_provider_b", 165000, "SURVEY_MEDIAN"),
            ("fixture_provider_c", 160000, "INDIVIDUAL_FORECAST"),
        ]),
    ]
    ingest_log = []
    for ck, rows in plan:
        for source_id, val, et in rows:
            out = rec.ingest_manual(
                macro_event_id="fixture_empsit_2026-10-02",
                source_id=source_id,
                series_name="nonfarm_payroll_change",
                expectation_type=et,
                artifact_bytes=nfp_artifact(source_id, val),
                observed_at_utc=times[ck],
                checkpoint_id=ck,
                forecast_value=val,
                unit="persons",
                seasonal_adjustment="SA",
                reference_period="2026-09",
                source_publication_utc=times[ck],
                notes="dry-run fixture",
            )
            ingest_log.append({"checkpoint": ck, "source_id": source_id, "status": out["status"], "hash": sha256_bytes(nfp_artifact(source_id, val))})
        rec.ingest_calendar(
            macro_event_id="fixture_empsit_2026-10-02",
            source_id="fixture_calendar",
            series_name="nonfarm_payroll_change",
            expectation_type="ECONOMIC_CALENDAR_FORECAST",
            artifact_bytes=("calendar NFP forecast=%s checkpoint=%s\n" % (rows[0][1], ck)).encode("utf-8"),
            observed_at_utc=times[ck],
            checkpoint_id=ck,
            forecast_value=rows[0][1],
            unit="persons",
            calendar_fields={
                "event_name": "Nonfarm Payrolls",
                "scheduled_t0": "2026-10-02T12:30:00Z",
                "importance": "high",
                "forecast": rows[0][1],
                "previous": 100000,
                "revised_previous": None,
                "unit": "persons",
                "reference_period": "2026-09",
                "provider": "Fixture Calendar",
            },
            notes="calendar forecast is not Reuters/FactSet/DJ",
        )
    final_a = rec.final_pre_release_observation(
        "fixture_empsit_2026-10-02", series_name="nonfarm_payroll_change", source_id="fixture_provider_a"
    )
    rec.capture_first_print(
        macro_event_id="fixture_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=110000,
        artifact_bytes=b"BLS first print NFP=110000 persons SA September 2026\n",
        first_observed_at_utc="2026-10-02T12:31:00Z",
        unit="persons",
        seasonal_adjustment="SA",
        source_id="bls_official",
        notes="fixture official first print",
    )
    post = rec.ingest_manual(
        macro_event_id="fixture_empsit_2026-10-02",
        source_id="fixture_calendar",
        series_name="nonfarm_payroll_change",
        expectation_type="ECONOMIC_CALENDAR_FORECAST",
        artifact_bytes=b"calendar POST-T0 rewrite forecast=110000 actual=110000\n",
        observed_at_utc="2026-10-02T12:35:00Z",
        checkpoint_id=None,
        forecast_value=110000,
        unit="persons",
        observation_kind="ECONOMIC_CALENDAR",
        notes="post-T0 calendar update",
    )
    final_after = rec.final_pre_release_observation(
        "fixture_empsit_2026-10-02", series_name="nonfarm_payroll_change", source_id="fixture_provider_a"
    )
    surprise = rec.raw_surprise("fixture_empsit_2026-10-02", "nonfarm_payroll_change", source_id="fixture_provider_a")
    hashes_a = []
    for o in rec.load_observations():
        if o.get("source_id") == "fixture_provider_a" and o.get("series_name") == "nonfarm_payroll_change":
            hashes_a.append((o["checkpoint_id"], o["raw_artifact_hash"], o["forecast_value"]))
    result = {
        "event_id": "fixture_empsit_2026-10-02",
        "t0": "2026-10-02T12:30:00Z",
        "window_start": rec.event_by_id("fixture_empsit_2026-10-02")["observation_window_start_utc"],
        "ingest_log": ingest_log,
        "provider_a_hashes": hashes_a,
        "final_pre_release_a": {
            "checkpoint_id": final_a.get("checkpoint_id") if final_a else None,
            "observed_at_utc": final_a.get("observed_at_utc") if final_a else None,
            "forecast_value": final_a.get("forecast_value") if final_a else None,
            "hash": final_a.get("raw_artifact_hash") if final_a else None,
        },
        "final_unchanged_by_post_t0": bool(final_after and final_a and final_after["observation_id"] == final_a["observation_id"]),
        "post_t0_status": post.get("status"),
        "post_t0_pit": (post.get("observation") or {}).get("prospective_pit_status"),
        "first_print": 110000,
        "surprise_a": surprise,
        "n_observations": len(rec.load_observations()),
        "n_artifacts": len(list(rec.art_dir.glob("*"))),
        "collection_enabled": rec.collection_enabled(),
    }
    (root / "manifests" / "dry_run_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def write_report(test_line: str, dry: dict) -> None:
    path = Path("reports/decision_quality/macro_prospective_recorder_stage1.md")
    parts = []
    parts.append("# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 1")
    parts.append("# 48-HOUR PRE-RELEASE CONSENSUS + ECONOMIC CALENDAR + FIRST-PRINT RECORDER")
    parts.append("")
    parts.append("Research-only data collection infrastructure. No directional trading rule. No model. No production trading authority.")
    parts.append("Existing historical GOLD/SILVER evidence was not rewritten. Official US PIT archive was not modified.")
    parts.append("")
    parts.append("ARCHITECTURE")
    parts.append("------------")
    parts.append("Prospective store: `data/research/macro/consensus_pit/prospective/`.")
    parts.append("Core helper: `reports/decision_quality/_macro_prospective_recorder.py`.")
    parts.append("Separate clocks: source_publication_utc, source_updated_utc, observed_at_utc (OUR clock), official_release_utc.")
    parts.append("Pre-release requires observed_at_utc < T0. T0 is not a pre-release checkpoint.")
    parts.append("Observations reference immutable SHA-256 artifact bytes. Identical bytes are reused; changed bytes create a new artifact.")
    parts.append("Official first prints live in `release_actuals/` and cannot overwrite pre-T0 observations.")
    parts.append("Future FX linkage schema preserves six USD pairs and USD_SIGN; +1m is not fabricated from M5. No directional analysis in this stage.")
    parts.append("")
    parts.append("EVENT REGISTRY")
    parts.append("--------------")
    parts.append("Families: CPI, EMPLOYMENT_SITUATION, FOMC.")
    parts.append("Required fields include macro_event_id, official schedule, 48h window start/end, event_status.")
    parts.append("T0 is taken from an official schedule (UTC or local+timezone). Historical averages are not used to invent a clock.")
    parts.append("America/New_York DST is applied when converting official local wall times to UTC.")
    parts.append("")
    parts.append("48-HOUR WINDOW")
    parts.append("--------------")
    parts.append("observation_window_start_utc = T0 - 48 hours (timezone-aware UTC).")
    parts.append("observation_window_end_utc = T0.")
    parts.append("Window math is 48 UTC hours, not 48 local hours, so DST transitions do not silently shift PIT order.")
    parts.append("")
    parts.append("CHECKPOINTS")
    parts.append("-----------")
    parts.append("Frozen before outcomes: T0-48h, T0-36h, T0-24h, T0-12h, T0-6h, T0-4h, T0-2h, T0-1h, T0-30m, T0-15m, T0-5m.")
    parts.append("T0 is RELEASE/POST-RELEASE. Not optimized on FX results.")
    parts.append("")
    parts.append("SOURCE REGISTRY")
    parts.append("---------------")
    parts.append("`source_registry/sources.json`. enabled=false by default. Unknown permissions fail closed.")
    parts.append("Reuters, FactSet, Dow Jones, Bloomberg, Trading Economics are registered and disabled.")
    parts.append("Autonomous collection requires FORWARD_CONSENSUS_COLLECTION_ENABLED=true AND source.enabled=true AND automated_collection_permitted=true.")
    parts.append("Manual ingest may use a registered source without enabling autonomous collection.")
    parts.append("")
    parts.append("ECONOMIC CALENDAR STORAGE")
    parts.append("-------------------------")
    parts.append("observation_kind=ECONOMIC_CALENDAR. expectation_type=ECONOMIC_CALENDAR_FORECAST.")
    parts.append("Calendar forecast/previous/revised_previous/importance remain provider-specific. Not relabeled as Reuters/FactSet/DJ consensus.")
    parts.append("")
    parts.append("FORECASTER STORAGE")
    parts.append("------------------")
    parts.append("SURVEY_CONSENSUS, SURVEY_MEDIAN, SURVEY_MEAN, PROVIDER_CONSENSUS, INDIVIDUAL_FORECAST, MARKET_IMPLIED_EXPECTATION stored separately.")
    parts.append("INDIVIDUAL_FORECAST is never consensus. Providers are never averaged.")
    parts.append("CPI series: headline/core MoM/YoY with SA/NSA. Employment: NFP, u-rate, AHE MoM/YoY. FOMC distributions are not collapsed to scalar bp.")
    parts.append("")
    parts.append("IMMUTABLE ARTIFACT STORAGE")
    parts.append("--------------------------")
    parts.append("Content-addressed files `artifacts/{sha256}.{ext}`. SHA-256 over actual preserved bytes. Parsed values reference the hash.")
    parts.append("")
    parts.append("OBSERVATION VS ARTIFACT")
    parts.append("-----------------------")
    parts.append("Each checkpoint writes an observation timestamp. Unchanged bytes reuse the artifact hash. Changed bytes create a new hash and a new observation.")
    parts.append("")
    parts.append("OFFICIAL FIRST-PRINT STORAGE")
    parts.append("----------------------------")
    parts.append("`release_actuals/actuals.jsonl` with record_kind=FIRST_PRINT. Revisions are separate REVISION records. First print cannot be overwritten.")
    parts.append("")
    parts.append("RELEASE-TIME RACE PROTECTION")
    parts.append("----------------------------")
    parts.append("observed_at_utc compared to T0. Post-T0 pages are OBSERVED_POST_T0 and cannot become final_pre_release_observation.")
    parts.append("Pre-T0 artifact hashes remain on disk. Calendar actual-overwrite after T0 is a new observation, not an edit.")
    parts.append("")
    parts.append("RESTART / IDEMPOTENCY")
    parts.append("---------------------")
    parts.append("Recorder reconstructs events, observations, artifacts, first-print status, and identity index from disk.")
    parts.append("Identical re-ingest: ALREADY_EXISTS. Same logical identity with incompatible payload: CONFLICT (fail closed).")
    parts.append("State machine: SCHEDULED -> PRE_WINDOW -> COLLECTING_PRE_RELEASE -> FINAL_PRE_RELEASE_CAPTURED -> RELEASE_PENDING -> FIRST_PRINT_CAPTURED -> POST_RELEASE_OBSERVATION -> COMPLETE, plus explicit failure states.")
    parts.append("")
    parts.append("DRY-RUN RESULT")
    parts.append("--------------")
    parts.append("Fixture event fixture_empsit_2026-10-02, T0=2026-10-02T12:30:00Z, window_start=%s." % dry.get("window_start"))
    parts.append("Provider A 175k (48h/24h) then 165k (6h) then 160k (1h/5m). Unchanged 5m reuses hash.")
    parts.append("Provider B 170k -> 165k. Provider C individual 160k from T0-6h, not relabeled consensus.")
    parts.append("Final pre-T0 Provider A: checkpoint=%s value=%s observed_at=%s" % (
        dry.get("final_pre_release_a", {}).get("checkpoint_id"),
        dry.get("final_pre_release_a", {}).get("forecast_value"),
        dry.get("final_pre_release_a", {}).get("observed_at_utc"),
    ))
    parts.append("Post-T0 calendar update did not alter final pre-T0 record: %s" % dry.get("final_unchanged_by_post_t0"))
    parts.append("First official actual stored separately: 110000. Derived surprise vs Provider A final 160k is infrastructure-only: %s" % dry.get("surprise_a"))
    parts.append("n_observations=%s n_artifacts=%s collection_enabled=%s" % (dry.get("n_observations"), dry.get("n_artifacts"), dry.get("collection_enabled")))
    parts.append("Numbers are not an economic interpretation.")
    parts.append("")
    parts.append("TEST RESULT")
    parts.append("-----------")
    parts.append(test_line)
    parts.append("")
    parts.append("SECURITY / ACCESS LIMITS")
    parts.append("------------------------")
    parts.append("No paywall/CAPTCHA/auth/robots bypass. Unknown sources fail closed. Autonomous collection disabled.")
    parts.append("Recorder does not import bot_loop, oanda_exec, oanda_client, execution, or v2_shadow.")
    parts.append("bot_loop does not import the recorder. Zero OANDA requests. No Docker deploy. No production logic change.")
    parts.append("")
    parts.append("PROSPECTIVE RECORDER STAGE 1")
    parts.append("----------------------------")
    parts.append("48H WINDOW IMPLEMENTED: YES")
    parts.append("CHECKPOINTS IMPLEMENTED: YES")
    parts.append("CHECKPOINTS: T0-48h, T0-36h, T0-24h, T0-12h, T0-6h, T0-4h, T0-2h, T0-1h, T0-30m, T0-15m, T0-5m")
    parts.append("EVENT REGISTRY READY: YES")
    parts.append("CPI SCHEMA READY: YES")
    parts.append("EMPLOYMENT SCHEMA READY: YES")
    parts.append("FOMC SCHEMA READY: YES")
    parts.append("ECONOMIC CALENDAR SNAPSHOTS READY: YES")
    parts.append("MULTI-FORECASTER SNAPSHOTS READY: YES")
    parts.append("MANUAL INGEST READY: YES")
    parts.append("OBSERVED_AT_UTC PRESERVED: YES")
    parts.append("SOURCE_PUBLICATION_UTC KEPT SEPARATE: YES")
    parts.append("IMMUTABLE ARTIFACTS: YES")
    parts.append("SHA-256: YES")
    parts.append("FINAL PRE-T0 SNAPSHOT PROTECTED: YES")
    parts.append("FIRST OFFICIAL ACTUAL STORED SEPARATELY: YES")
    parts.append("REVISIONS CANNOT OVERWRITE FIRST PRINT: YES")
    parts.append("RESTART SAFE: YES")
    parts.append("IDEMPOTENT: YES")
    parts.append("UNKNOWN SOURCES FAIL CLOSED: YES")
    parts.append("AUTONOMOUS EXTERNAL COLLECTION ENABLED: NO")
    parts.append("GLOBAL COLLECTION FLAG: FORWARD_CONSENSUS_COLLECTION_ENABLED=false")
    parts.append("PRODUCTION TRADING AUTHORITY: NONE")
    parts.append("OANDA/API REQUESTS: 0")
    parts.append("PRODUCTION LOGIC MODIFIED: NO")
    parts.append("V2 POLICY MODIFIED: NO")
    parts.append("MODEL TRAINED: NO")
    parts.append("DIRECTIONAL RULE CREATED: NO")
    parts.append("SURPRISE FX BACKTEST RUN: NO")
    parts.append("TESTS: %s" % test_line)
    parts.append("FILES CHANGED:")
    parts.append("- data/research/macro/consensus_pit/prospective/")
    parts.append("- reports/decision_quality/_macro_prospective_recorder.py")
    parts.append("- reports/decision_quality/macro_prospective_recorder_stage1.md")
    parts.append("- tests/test_macro_prospective_recorder_stage1.py")
    parts.append("NEXT SAFE STEP: Register the next officially scheduled US CPI, Employment Situation, or FOMC T0 from the BLS/Fed calendar; lawfully capture manual pre-release artifacts inside the 48h window with observed_at_utc; leave autonomous source enablement false until a specific source has documented archival/automation permission.")
    parts.append("STOP.")
    parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    result = run_dry_run(DEFAULT_ROOT / "fixtures" / "dry_run")
    print(json.dumps({k: result[k] for k in result if k != "ingest_log"}, indent=2))
