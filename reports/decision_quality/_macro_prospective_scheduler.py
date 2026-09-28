"""Research-only prospective checkpoint scheduler/orchestrator.

Short-lived collect-due process. No production trading. No OANDA. No Telegram.
Autonomous external collection remains gated by the source registry and
FORWARD_CONSENSUS_COLLECTION_ENABLED. The scheduler may run while collection is off.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_REC_PATH = Path(__file__).with_name("_macro_prospective_recorder.py")
_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_for_sched", _REC_PATH)
R = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(R)

UTC = timezone.utc
TASK_NAME = "ForexMacroProspectiveCollectDue"
TASK_INTERVAL_MINUTES = 5
LOCK_STALE_SECONDS = 180
CHECKPOINT_IDS = tuple(cid for cid, _ in R.CHECKPOINTS)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKDIR = str(REPO_ROOT)
CANONICAL_MODULE = "reports.decision_quality.macro_prospective_cli"
CANONICAL_ARGS = "-m %s collect-due" % CANONICAL_MODULE
FORBIDDEN_PRODUCTION_IMPORTS = R.FORBIDDEN_PRODUCTION_IMPORTS + (
    "forex_bot.app",
    "forex_bot.telegram_bot",
)

ADAPTER_STATUSES = (
    "SUCCESS",
    "NO_DATA",
    "SOURCE_DISABLED",
    "SOURCE_UNAVAILABLE",
    "RATE_LIMITED",
    "ACCESS_DENIED",
    "PARSE_FAILED",
    "INVALID_SERIES",
    "PERMISSION_UNKNOWN_OR_FALSE",
    "GLOBAL_FLAG_FALSE",
    "UNKNOWN_SOURCE",
    "WOULD_COLLECT",
)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / ("%s.%s.tmp" % (path.name, os.getpid()))
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: dict) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=True) + "\n")


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return json.loads(json.dumps(default))
    return json.loads(path.read_text(encoding="utf-8-sig") or "{}")


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def pid_alive(pid: int) -> bool:
    """Best-effort liveness. Heartbeat is the stale-lock authority.

    POSIX uses signal 0 /proc. Windows os.kill is not a liveness probe
    (it can terminate). Unknown platforms treat the PID as possibly alive
    so a live owner is never stolen before the heartbeat expires.
    """
    if pid <= 0:
        return False
    if os.name != "nt":
        proc = Path("/proc") / str(pid)
        try:
            if proc.exists():
                return True
        except OSError:
            pass
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    return True


class ProcessLock:
    """Filesystem process lock. Same-host only. Not a distributed lock.

    Exclusive create (O_CREAT|O_EXCL) plus heartbeat stale recovery.
    Coordinates processes that share this lock file. Does not coordinate
    independent Windows PC + VPS copies.
    """

    def __init__(self, path: Path, now_fn: Callable[[], datetime], stale_seconds: int = LOCK_STALE_SECONDS):
        self.path = path
        self.now_fn = now_fn
        self.stale_seconds = stale_seconds
        self._owned = False

    def _payload(self) -> dict:
        now = self.now_fn()
        return {
            "pid": os.getpid(),
            "started_utc": R.to_utc_iso(now),
            "heartbeat_utc": R.to_utc_iso(now),
            "lock_scope": "shared_filesystem",
        }

    def _is_stale(self, blob: dict, now: datetime) -> bool:
        hb = R.parse_utc(blob.get("heartbeat_utc"))
        if hb is None:
            return True
        if (now - hb).total_seconds() > self.stale_seconds:
            return True
        pid = int(blob.get("pid") or 0)
        if pid and not pid_alive(pid):
            return True
        return False

    def acquire(self) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = self.now_fn()
        if self.path.exists():
            try:
                blob = json.loads(self.path.read_text(encoding="utf-8-sig") or "{}")
            except json.JSONDecodeError:
                blob = {}
            if not self._is_stale(blob, now):
                return "BUSY"
            try:
                self.path.unlink()
            except OSError:
                return "BUSY"
            recovered = True
        else:
            recovered = False
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            return "BUSY"
        try:
            os.write(fd, json.dumps(self._payload(), indent=2).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        self._owned = True
        return "STALE_RECOVERED" if recovered else "OWNED"

    def release(self) -> None:
        if not self._owned:
            return
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass
        self._owned = False


class CollectionResult:
    def __init__(
        self,
        status: str,
        source_id: str,
        external_request: bool = False,
        artifact_bytes: bytes | None = None,
        series_name: str | None = None,
        expectation_type: str | None = None,
        forecast_value=None,
        unit: str | None = None,
        reference_period: str | None = None,
        source_publication_utc: str | None = None,
        source_updated_utc: str | None = None,
        observation_kind: str = "FORECASTER",
        notes: str | None = None,
        reason: str | None = None,
    ):
        self.status = status
        self.source_id = source_id
        self.external_request = external_request
        self.artifact_bytes = artifact_bytes
        self.series_name = series_name
        self.expectation_type = expectation_type
        self.forecast_value = forecast_value
        self.unit = unit
        self.reference_period = reference_period
        self.source_publication_utc = source_publication_utc
        self.source_updated_utc = source_updated_utc
        self.observation_kind = observation_kind
        self.notes = notes
        self.reason = reason
        self.calendar_fields = None
        self.fomc_distribution = None
        self.payloads = []
        self.provider_name = None
        self.source_event_identifier = None
        self.source_url_or_endpoint_identifier = None
        self.retrieval_utc = None


class CollectionAdapter:
    source_id = "unknown"

    def is_enabled(self, rec: R.ProspectiveRecorder) -> tuple[bool, str]:
        return autonomous_gate(rec, self.source_id)

    def supports(self, event: dict) -> bool:
        return True

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> CollectionResult:
        raise R.RecorderClosed("unapproved adapter must never fetch")


class NeverFetchAdapter(CollectionAdapter):
    """Registered production sources. Gate only. Never issues an HTTP/API request."""

    def __init__(self, source_id: str):
        self.source_id = source_id

    def collect(self, event: dict, checkpoint: dict, now: datetime) -> CollectionResult:
        raise R.RecorderClosed("NO REQUEST: adapter %s is not approved for autonomous fetch" % self.source_id)


def autonomous_gate(rec: R.ProspectiveRecorder, source_id: str) -> tuple[bool, str]:
    src = rec.source_by_id(source_id)
    if src is None:
        return False, "UNKNOWN_SOURCE"
    if rec.collection_enabled() is not True:
        return False, "GLOBAL_FLAG_FALSE"
    if src.get("enabled") is not True:
        return False, "SOURCE_DISABLED"
    if src.get("automated_collection_permitted") is not True:
        return False, "PERMISSION_UNKNOWN_OR_FALSE"
    return True, "OK"


def default_adapters(rec: R.ProspectiveRecorder) -> list[CollectionAdapter]:
    ad_path = Path(__file__).with_name("_macro_prospective_adapters.py")
    spec = importlib.util.spec_from_file_location("macro_prospective_adapters", ad_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.build_production_adapters(rec)


def enabled_autonomous_sources(rec: R.ProspectiveRecorder) -> list[str]:
    out = []
    for src in rec.load_registry().get("sources", []):
        sid = src.get("source_id")
        if not sid:
            continue
        ok, _reason = autonomous_gate(rec, sid)
        if ok:
            out.append(sid)
    return out


def processed_key(event_id: str, checkpoint_id: str) -> str:
    return "%s|%s" % (event_id, checkpoint_id)


def windows_task_status(marker_path: Path) -> str:
    if marker_path.exists():
        return "INSTALLED"
    return "NOT_INSTALLED"


def installer_spec(python_executable: str | None = None, workdir: str | None = None) -> dict:
    py = python_executable or sys.executable
    wd = str(Path(workdir or DEFAULT_WORKDIR).resolve())
    args = CANONICAL_ARGS
    return {
        "task_name": TASK_NAME,
        "interval_minutes": TASK_INTERVAL_MINUTES,
        "python_executable": py,
        "working_directory": wd,
        "arguments": args,
        "command": '%s %s' % (py, args),
        "start_when_available": True,
        "multiple_instances": "IgnoreNew",
        "installs_during_tests": False,
    }


class ProspectiveScheduler:
    def __init__(self, rec: R.ProspectiveRecorder, adapters: list[CollectionAdapter] | None = None):
        self.rec = rec
        self.adapters = adapters if adapters is not None else default_adapters(rec)
        self.sched_dir = rec.root / "scheduler"
        self.state_path = self.sched_dir / "state.json"
        self.lock_path = self.sched_dir / "collect.lock"
        self.audit_path = self.sched_dir / "audit.jsonl"
        self.attention_path = self.sched_dir / "operator_attention.jsonl"
        self.task_marker_path = self.sched_dir / "windows_task_installed.json"
        self.external_requests = 0
        # Do not create scheduler dirs until a persisting collect-due run.

    def now(self) -> datetime:
        return self.rec.now()

    def load_state(self) -> dict:
        return load_json(
            self.state_path,
            {
                "last_run_utc": None,
                "last_success_utc": None,
                "processed": {},
                "first_print_required": {},
            },
        )

    def save_state(self, state: dict) -> None:
        atomic_write_json(self.state_path, state)

    def audit(self, event_type: str, **fields) -> None:
        rec = {
            "event": event_type,
            "utc": R.to_utc_iso(self.now()),
            **fields,
        }
        rec.pop("artifact_bytes", None)
        rec.pop("token", None)
        rec.pop("password", None)
        rec.pop("secret", None)
        append_jsonl(self.audit_path, rec)

    def notify(self, kind: str, **fields) -> None:
        append_jsonl(
            self.attention_path,
            {"kind": kind, "utc": R.to_utc_iso(self.now()), **fields},
        )

    def reconstruct(self) -> dict:
        return {
            "state": self.load_state(),
            "audit_exists": self.audit_path.exists(),
            "lock_exists": self.lock_path.exists(),
        }

    def _consider_adapters(self, event: dict) -> list[dict]:
        rows = []
        for ad in self.adapters:
            if not ad.supports(event):
                rows.append({"source_id": ad.source_id, "considered": False, "reason": "UNSUPPORTED_EVENT"})
                continue
            ok, reason = ad.is_enabled(self.rec)
            rows.append({"source_id": ad.source_id, "considered": True, "allowed": ok, "reason": reason})
        return rows

    def collect_due(self, *, dry_run: bool = False) -> dict:
        now = self.now()
        summary = {
            "ok": True,
            "dry_run": dry_run,
            "current_utc": R.to_utc_iso(now),
            "external_requests": 0,
            "actions": [],
            "lock": None,
            "exit_code": 0,
        }
        if dry_run:
            return self._run_pass(now, summary, persist=False, dry_run=True)

        lock = ProcessLock(self.lock_path, self.now)
        acquired = lock.acquire()
        summary["lock"] = acquired
        if acquired == "BUSY":
            self.audit("LOCK_BUSY")
            summary["actions"].append({"status": "LOCK_BUSY"})
            return summary
        try:
            if acquired == "STALE_RECOVERED":
                self.audit("STALE_LOCK_RECOVERED")
            return self._run_pass(now, summary, persist=True, dry_run=False)
        except Exception as exc:
            self.audit("ERROR", error=type(exc).__name__, message=str(exc)[:200])
            summary["ok"] = False
            summary["exit_code"] = 1
            summary["error"] = str(exc)
            return summary
        finally:
            lock.release()

    def _run_pass(self, now: datetime, summary: dict, *, persist: bool, dry_run: bool) -> dict:
        if persist:
            self.audit("SCHEDULER_STARTED", dry_run=False)
        state = self.load_state() if persist else self.load_state()
        before = json.dumps(state, sort_keys=True)
        events = self.rec.load_events()
        any_window = False
        for ev in events:
            t0 = R.parse_utc(ev.get("scheduled_release_utc"))
            start = R.parse_utc(ev.get("observation_window_start_utc"))
            if t0 is None or start is None:
                continue
            in_window = start <= now < t0
            at_or_after_t0 = now >= t0
            if in_window or at_or_after_t0:
                any_window = True
            rows = self.rec.checkpoint_status_rows(ev, now)
            unknown = [r for r in rows if r["checkpoint_id"] not in CHECKPOINT_IDS]
            if unknown:
                raise RuntimeError("non-predefined checkpoint")
            for row in rows:
                self._handle_checkpoint(ev, row, now, state, summary, persist=persist, dry_run=dry_run)
            if at_or_after_t0:
                self._handle_release(ev, now, state, summary, persist=persist, dry_run=dry_run)
        if not any_window:
            summary["actions"].append({"status": "NO_EVENT_ACTIVE"})
            if persist:
                self.audit("NO_EVENT_ACTIVE")
        summary["external_requests"] = self.external_requests
        if persist:
            state["last_run_utc"] = R.to_utc_iso(now)
            if summary["ok"]:
                state["last_success_utc"] = R.to_utc_iso(now)
            self.save_state(state)
        else:
            after = json.dumps(self.load_state(), sort_keys=True)
            if after != before and dry_run:
                summary["ok"] = False
                summary["exit_code"] = 1
                summary["error"] = "dry-run mutated state"
        return summary

    def _handle_checkpoint(
        self,
        ev: dict,
        row: dict,
        now: datetime,
        state: dict,
        summary: dict,
        *,
        persist: bool,
        dry_run: bool,
    ) -> None:
        eid = ev["macro_event_id"]
        cid = row["checkpoint_id"]
        key = processed_key(eid, cid)
        processed = state.get("processed", {})
        if row["status"] == "FUTURE":
            return
        if key in processed:
            summary["actions"].append(
                {
                    "status": "ALREADY_PROCESSED",
                    "macro_event_id": eid,
                    "checkpoint_id": cid,
                    "prior": processed[key].get("status"),
                }
            )
            return
        if row["status"] == "MISSED_NOT_OBSERVED":
            action = {
                "status": "CHECKPOINT_MISSED",
                "macro_event_id": eid,
                "checkpoint_id": cid,
                "checkpoint_utc": row["checkpoint_utc"],
                "processing_started_utc": R.to_utc_iso(now),
                "observed_at_utc": None,
                "result": "MISSED_NOT_OBSERVED",
            }
            summary["actions"].append(action)
            if persist:
                processed[key] = action
                state["processed"] = processed
                self.audit("CHECKPOINT_MISSED", macro_event_id=eid, checkpoint_id=cid)
            return
        if row["status"] != "DUE":
            if row["status"] == "CAPTURED":
                action = {
                    "status": "ALREADY_PROCESSED",
                    "macro_event_id": eid,
                    "checkpoint_id": cid,
                    "prior": "CAPTURED",
                }
                summary["actions"].append(action)
                if persist:
                    processed[key] = {
                        "status": "CAPTURED_PREEXISTING",
                        "macro_event_id": eid,
                        "checkpoint_id": cid,
                        "checkpoint_utc": row["checkpoint_utc"],
                        "processing_started_utc": R.to_utc_iso(now),
                    }
                    state["processed"] = processed
            return

        considered = self._consider_adapters(ev)
        allowed = [c for c in considered if c.get("allowed")]
        action = {
            "status": "CHECKPOINT_DUE",
            "macro_event_id": eid,
            "checkpoint_id": cid,
            "checkpoint_utc": row["checkpoint_utc"],
            "processing_started_utc": R.to_utc_iso(now),
            "observed_at_utc": None,
            "adapters": considered,
        }
        if persist:
            self.audit("CHECKPOINT_DUE", macro_event_id=eid, checkpoint_id=cid, checkpoint_utc=row["checkpoint_utc"])
        if dry_run:
            action["result"] = "DRY_RUN"
            action["would_collect"] = [c["source_id"] for c in allowed]
            summary["actions"].append(action)
            return
        if not allowed:
            action["result"] = "NO_ENABLED_SOURCE"
            action["observation"] = "NO_OBSERVATION_RECORDED"
            summary["actions"].append(action)
            processed[key] = action
            state["processed"] = processed
            if persist:
                self.audit("NO_ENABLED_SOURCE", macro_event_id=eid, checkpoint_id=cid)
                self.audit("CHECKPOINT_PROCESSED", macro_event_id=eid, checkpoint_id=cid, result="NO_ENABLED_SOURCE")
                self.notify(
                    "MANUAL_FORECAST_CAPTURE_REQUIRED",
                    macro_event_id=eid,
                    checkpoint_id=cid,
                    checkpoint_utc=row["checkpoint_utc"],
                )
            return

        captured_any = False
        for ad in self.adapters:
            ok, reason = ad.is_enabled(self.rec)
            if not ok or not ad.supports(ev):
                continue
            result = ad.collect(ev, row, now)
            if result.external_request:
                self.external_requests += 1
                summary["external_requests"] = self.external_requests
            items = [result] + list(getattr(result, "payloads", None) or [])
            t0 = R.parse_utc(ev.get("scheduled_release_utc"))
            for item in items:
                if item.status != "SUCCESS" or not item.artifact_bytes:
                    action.setdefault("adapter_results", []).append(
                        {"source_id": ad.source_id, "status": item.status, "reason": getattr(item, "reason", None)}
                    )
                    continue
                if t0 is not None and now >= t0:
                    action.setdefault("adapter_results", []).append(
                        {"source_id": ad.source_id, "status": "POST_T0_REJECTED", "reason": "forecast not pre-release"}
                    )
                    continue
                observed_at = R.to_utc_iso(now)
                out = self.rec.ingest_observation(
                    macro_event_id=eid,
                    source_id=ad.source_id,
                    series_name=item.series_name or "nonfarm_payroll_change",
                    expectation_type=item.expectation_type or "SURVEY_CONSENSUS",
                    artifact_bytes=item.artifact_bytes,
                    observed_at_utc=observed_at,
                    checkpoint_id=cid,
                    forecast_value=item.forecast_value,
                    unit=item.unit,
                    reference_period=item.reference_period or ev.get("reference_period"),
                    source_publication_utc=item.source_publication_utc,
                    source_updated_utc=item.source_updated_utc,
                    observation_kind=item.observation_kind,
                    retrieval_method="autonomous",
                    allow_autonomous=True,
                    notes=item.notes,
                    calendar_fields=getattr(item, "calendar_fields", None),
                    fomc_distribution=getattr(item, "fomc_distribution", None),
                    provider_name=getattr(item, "provider_name", None),
                    source_event_identifier=getattr(item, "source_event_identifier", None),
                    source_url_or_endpoint_identifier=getattr(item, "source_url_or_endpoint_identifier", None),
                    retrieval_utc=getattr(item, "retrieval_utc", None) or observed_at,
                )
                captured_any = True
                action["result"] = "OBSERVATION_CAPTURED"
                action["observed_at_utc"] = observed_at
                action["ingest"] = out.get("status")
                if persist:
                    self.audit(
                        "OBSERVATION_CAPTURED",
                        macro_event_id=eid,
                        checkpoint_id=cid,
                        source_id=ad.source_id,
                        series_name=item.series_name,
                        observed_at_utc=observed_at,
                        checkpoint_utc=row["checkpoint_utc"],
                        artifact_hash=R.sha256_bytes(item.artifact_bytes),
                    )
        if not captured_any:
            action["result"] = action.get("result") or "NO_DATA"
            action["observation"] = "NO_OBSERVATION_RECORDED"
        processed[key] = action
        state["processed"] = processed
        summary["actions"].append(action)
        if persist:
            self.audit("CHECKPOINT_PROCESSED", macro_event_id=eid, checkpoint_id=cid, result=action.get("result"))

    def _handle_release(self, ev: dict, now: datetime, state: dict, summary: dict, *, persist: bool, dry_run: bool) -> None:
        eid = ev["macro_event_id"]
        st = self.rec.derive_status(eid, now)
        if st != "RELEASE_PENDING":
            return
        req = {
            "macro_event_id": eid,
            "status": "FIRST_PRINT_REQUIRED",
            "scheduled_release_utc": ev["scheduled_release_utc"],
            "utc": R.to_utc_iso(now),
            "auto_fetch": "OFF",
        }
        summary["actions"].append(req)
        if dry_run:
            return
        fp = state.setdefault("first_print_required", {})
        if eid not in fp and persist:
            fp[eid] = req
            self.audit("FIRST_PRINT_REQUIRED", macro_event_id=eid)
            self.notify("FIRST_PRINT_REQUIRED", macro_event_id=eid)

    def format_status(self) -> str:
        rec_text = self.rec.format_status()
        now = self.now()
        state = self.load_state()
        enabled = enabled_autonomous_sources(self.rec)
        nxt = self.rec.next_event(now)
        window = "NONE"
        manual = "NO"
        if nxt:
            snap = self.rec.event_snapshot(nxt, now)
            window = snap["window_state"]
            if snap["window_state"] in {"COLLECTING_PRE_RELEASE", "FINAL_PRE_RELEASE_CAPTURED", "RELEASE_PENDING"} and not enabled:
                manual = "YES"
            if snap["due_checkpoints"] and not enabled:
                manual = "YES"
        extra = [
            "SCHEDULER:",
            windows_task_status(self.task_marker_path),
            "LAST SCHEDULER RUN:",
            state.get("last_run_utc") or "(none)",
            "LAST SUCCESS:",
            state.get("last_success_utc") or "(none)",
            "NEXT REGISTERED EVENT:",
            nxt["macro_event_id"] if nxt else "NONE",
            "CURRENT WINDOW:",
            window,
            "NEXT CHECKPOINT:",
            ((self.rec.event_snapshot(nxt, now).get("next_checkpoint") or {}).get("checkpoint_id") if nxt else "NONE"),
            "AUTONOMOUS COLLECTION:",
            "OFF" if not self.rec.collection_enabled() else "ON",
            "ENABLED SOURCES:",
            str(len(enabled)) if enabled else "0",
            "MANUAL ACTION REQUIRED:",
            manual,
            "",
        ]
        # Insert scheduler block after the header/current UTC section.
        lines = rec_text.splitlines()
        out = []
        inserted = False
        i = 0
        while i < len(lines):
            out.append(lines[i])
            if not inserted and lines[i] == "CURRENT UTC:" and i + 1 < len(lines):
                out.append(lines[i + 1])
                out.append("")
                out.extend(extra)
                inserted = True
                i += 2
                continue
            i += 1
        if not inserted:
            out = extra + lines
        return "\n".join(out) if out[-1:] == [""] else "\n".join(out) + "\n"


def format_collect_result(summary: dict) -> str:
    lines = [
        "PROSPECTIVE COLLECT-DUE",
        "----------------------",
        "DRY RUN:" + (" YES" if summary.get("dry_run") else " NO"),
        "CURRENT UTC:",
        summary.get("current_utc") or "",
        "LOCK:",
        str(summary.get("lock") or "N/A"),
        "EXTERNAL REQUESTS:",
        str(summary.get("external_requests") or 0),
        "",
    ]
    if not summary.get("actions"):
        lines.append("NO ACTION")
        lines.append("")
        return "\n".join(lines)
    for act in summary["actions"]:
        lines.append(
            "%s  event=%s  checkpoint=%s  result=%s"
            % (
                act.get("status"),
                act.get("macro_event_id") or "-",
                act.get("checkpoint_id") or "-",
                act.get("result") or act.get("prior") or "-",
            )
        )
    lines.append("")
    return "\n".join(lines)
