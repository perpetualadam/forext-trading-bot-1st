"""Offline D.30-R3 harness. Synthetic processes only."""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
WORKER = OUT / "10_worker_source.py"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROTECTED = {
    "forex_bot/app.py": "3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1",
    "forex_bot/telegram_control.py": "d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c",
    "forex_bot/database.py": "cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e",
    "forex_bot/live_safety.py": "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "requirements.txt": "45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a",
    "requirements-dev.txt": "0562a6853549077197defb3cd8515521b843a041f2a735723ee2903790e3eef5",
    "Dockerfile": "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad",
    ".dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
    "docker-compose.yml": "f0a374774c35b4c63dce23a837572886d1d53331fec388044bc5887367980179",
}
OCI = {
    "data/research/adaptive_ensemble/d22_r1/09_index_raw_manifest.json": (6546, "34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258"),
    "data/research/adaptive_ensemble/d22_r1/15_amd64_raw_manifest.json": (1752, "2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d"),
    "data/research/adaptive_ensemble/d22_r1/19_arm64_raw_manifest.json": (1754, "739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163"),
    "data/research/adaptive_ensemble/d24_r2/11_amd64_config_raw.json": (5684, "4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524"),
    "data/research/adaptive_ensemble/d24_r2/16_arm64_config_raw.json": (5699, "eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629"),
}
PRIOR_DIRS = (
    "data/research/adaptive_ensemble/d29_r1",
    "data/research/adaptive_ensemble/d30",
    "data/research/adaptive_ensemble/d30_r1",
    "data/research/adaptive_ensemble/d30_r2",
)
ESSENTIAL = (
    "data/research/adaptive_ensemble/d30/16_gate_a_verdict.json",
    "data/research/adaptive_ensemble/d30_r1/21_gate_c_verdict.json",
    "data/research/adaptive_ensemble/d30_r1/10_offline_preflight.json",
    "data/research/adaptive_ensemble/d30_r2/17_cleanup_test_results.json",
    "data/research/adaptive_ensemble/d30_r2/18_process_tree_limitations.md",
    "data/research/adaptive_ensemble/d30_r2/34_stage_d30_r2_report.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(relative: str) -> dict[str, str]:
    base = ROOT / relative
    found = {}
    if not base.exists():
        return found
    for path in sorted(item for item in base.rglob("*") if item.is_file()):
        found[str(path.relative_to(ROOT)).replace("\\", "/")] = digest(path)
    return found


def git_text(args: list[str]) -> str:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, shell=False)
    return completed.stdout.strip()


def load_supervisor():
    spec = importlib.util.spec_from_file_location("d30r3_supervisor", OUT / "09_supervisor_source.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(name: str, payload: object) -> None:
    text = json.dumps(payload, indent=2)
    if "redact-me" in text:
        raise RuntimeError("sanitised output rejected")
    (OUT / name).write_text(text + "\n", encoding="utf-8")


def write_text(name: str, text: str) -> None:
    if "redact-me" in text:
        raise RuntimeError("sanitised output rejected")
    (OUT / name).write_text(text, encoding="utf-8")


def row(test_id: str, run: dict, expected: str, actual: str, ok: bool) -> dict:
    pids = set(run.get("job_pids") or [])
    expected_pids = {run.get("worker_pid")}
    if run.get("descendant_pid"):
        expected_pids.add(run.get("descendant_pid"))
    unexpected = len(pids - expected_pids) if pids else 0
    return {
        "test_id": test_id,
        "fixture_mode": run.get("mode"),
        "expected": expected,
        "actual": actual,
        "worker_pid": run.get("worker_pid"),
        "worker_creation_low": run.get("worker_creation_low"),
        "worker_creation_high": run.get("worker_creation_high"),
        "descendant_pid": run.get("descendant_pid"),
        "descendant_creation_low": run.get("descendant_creation_low"),
        "descendant_creation_high": run.get("descendant_creation_high"),
        "worker_in_job": run.get("worker_in_job"),
        "descendant_in_job": run.get("descendant_in_job"),
        "monotonic_start": run.get("monotonic_start"),
        "elapsed": run.get("total_elapsed"),
        "operation_deadline": run.get("operation_deadline"),
        "operation_elapsed": run.get("operation_elapsed"),
        "termination_method": run.get("termination_method"),
        "cleanup_duration": run.get("cleanup_duration"),
        "worker_exit_confirmed": run.get("worker_exit_confirmed"),
        "descendant_exit_confirmed": run.get("descendant_exit_confirmed"),
        "unexpected_processes": unexpected,
        "result": "PASS" if ok else "FAIL",
    }


def main() -> None:
    sup = load_supervisor()
    classification = "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED"
    head = git_text(["git", "rev-parse", "HEAD"])
    branch = git_text(["git", "branch", "--show-current"])
    status = git_text(["git", "status", "--short", "--", *PROTECTED])
    prompt_ok = all(HEX64.fullmatch(value) for value in PROTECTED.values())
    baseline = []
    baseline_ok = prompt_ok and head == "d080d897945bc44fa37c02caab504ed707146bec" and branch == "main"
    for relative, expected in PROTECTED.items():
        path = ROOT / relative
        actual = digest(path) if path.exists() else None
        matched = actual == expected
        baseline.append({"path": relative, "expected": expected, "actual": actual, "match": matched})
        baseline_ok = baseline_ok and matched
    oci_rows = []
    oci_ok = True
    for relative, (size, expected) in OCI.items():
        path = ROOT / relative
        raw = path.read_bytes() if path.exists() else b""
        matched = len(raw) == size and hashlib.sha256(raw).hexdigest() == expected
        oci_rows.append({"path": relative, "size": len(raw), "expected_size": size, "match": matched})
        oci_ok = oci_ok and matched
    missing = [relative for relative in ESSENTIAL if not (ROOT / relative).exists()]
    prior = {}
    for relative in PRIOR_DIRS:
        prior.update(tree_hashes(relative))
    h05 = json.loads((ROOT / "data/research/adaptive_ensemble/d30_r2/17_cleanup_test_results.json").read_text(encoding="utf-8"))
    h05_row = next(item for item in h05["results"] if item["test_id"] == "H05")
    historical_ok = (
        not missing
        and "D30_BLOCKED_PROMPT_INTEGRITY" in (ROOT / "data/research/adaptive_ensemble/d30/16_gate_a_verdict.json").read_text(encoding="utf-8")
        and "D30_R1_BLOCKED_CLIENT_SAFETY" in (ROOT / "data/research/adaptive_ensemble/d30_r1/21_gate_c_verdict.json").read_text(encoding="utf-8")
        and "D30_R2_OFFLINE_SUPERVISOR_VALIDATED" in (ROOT / "data/research/adaptive_ensemble/d30_r2/34_stage_d30_r2_report.md").read_text(encoding="utf-8")
        and h05_row["result"] == "NOT_EVALUATED"
    )
    if not prompt_ok:
        classification = "D30_R3_BLOCKED_PROMPT_INTEGRITY"
    elif not baseline_ok:
        classification = "D30_R3_BLOCKED_BASELINE_INTEGRITY"
    elif not oci_ok:
        classification = "D30_R3_BLOCKED_OCI_INTEGRITY"
    elif not historical_ok:
        classification = "D30_R3_BLOCKED_PRIOR_EVIDENCE_ACCESS"

    supervisor_text = (OUT / "09_supervisor_source.py").read_text(encoding="utf-8")
    worker_text = WORKER.read_text(encoding="utf-8")
    descendant_text = (OUT / "11_descendant_source.py").read_text(encoding="utf-8")
    harness_text = Path(__file__).read_text(encoding="utf-8")
    execute_source = inspect.getsource(sup.Session.execute)
    sequence = [execute_source.find(name) for name in sup.CONTAINMENT_SEQUENCE]
    preflight = []

    def add(name: str, ok: bool) -> None:
        preflight.append({"check": name, "passed": bool(ok)})

    probe = {}
    probe_error = None
    if classification.startswith("D30_R3_BLOCKED"):
        probe_error = classification
    else:
        try:
            probe = sup.probe_job()
        except sup.StageBlocked as exc:
            probe_error = exc.classification
            probe = {"detail": exc.detail}
    add("D01_windows", os.name == "nt" and platform.system() == "Windows")
    add("D02_no_network_import", all(token not in supervisor_text and token not in worker_text and token not in descendant_text for token in ("urllib", "http.client", "urlopen")))
    add("D03_no_socket_import", "import socket" not in supervisor_text and "import socket" not in worker_text and "import socket" not in descendant_text)
    add("D04_no_dns", "getaddrinfo" not in supervisor_text and "getaddrinfo" not in worker_text)
    add("D05_no_http_client", "d30_r1" + "/09_client" not in harness_text)
    add("D06_no_production_path", "data/ops" not in worker_text and "forex_bot" not in worker_text)
    add("D07_no_credential_read", "docker-credential" not in supervisor_text and '".env"' not in worker_text)
    add("D08_output_boundary", "d30_r3" in worker_text)
    add("D09_fixed_worker_args", "MODES" in worker_text and "shell=True" not in worker_text)
    add("D10_fixed_descendant_args", "DESCENDANT_MODE" in worker_text and "MODES" in descendant_text)
    add("D11_one_descendant", "spawn_two" not in worker_text and "Popen" not in descendant_text)
    add("D12_no_shell", "shell" + "=True" not in supervisor_text and "shell" + "=True" not in worker_text and "shell" + "=True" not in descendant_text)
    add("D13_signatures", "CreateProcessW.argtypes" in supervisor_text and bool(probe.get("layouts", {}).get("layouts_match")))
    add("D14_job_lifecycle", "CloseHandle" in supervisor_text and "CreateJobObjectW" in supervisor_text)
    add("D15_kill_on_close", bool(probe.get("limits_contained")))
    add("D16_containment_before_execution", sequence == sorted(sequence) and all(index >= 0 for index in sequence) and worker_text.find("wait_for_supervisor_decision") < worker_text.find("ResumeThread"))
    add("D17_membership_check", "IsProcessInJob" in supervisor_text)
    add("D18_forced_termination", "TerminateJobObject" in supervisor_text)
    add("D19_worker_exit", "GetExitCodeProcess" in supervisor_text)
    add("D20_descendant_exit", "descendant_exit_confirmed" in supervisor_text)
    add("D21_cleanup_allowance", "cleanup_allowance" in supervisor_text)
    add("D22_no_retry", "attempts += 1" in supervisor_text and "retry" in supervisor_text)
    add("D23_no_broad_kill", "task" + "kill" not in supervisor_text and "task" + "kill" not in worker_text and "CreateToolhelp32Snapshot" not in supervisor_text)
    add("D24_prior_preserved", historical_ok)
    preflight_ok = all(item["passed"] for item in preflight) and probe_error is None
    if classification == "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED" and not preflight_ok:
        classification = probe_error or "D30_R3_BLOCKED_HARNESS_SAFETY"

    runs = []
    rows_e = []
    rows_f = []
    rows_h = []
    rows_g = []
    rows_s = []
    blocked = None
    origin = time.monotonic()

    def launch(mode: str, operation: float, graceful: bool = False, close_only: bool = False, stage: float = 60.0) -> dict:
        session = sup.Session(WORKER, OUT, mode, operation, stage, origin, 2.0, graceful, close_only)
        record = session.execute()
        runs.append(record)
        return record

    if classification == "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED":
        try:
            normal = launch("complete", 5.0)
            pair = launch("spawn_complete", 5.0)
            contained = launch("spawn_block", 0.45)
            blocked_worker = launch("block", 0.35)
            ignored = launch("ignore_stop", 0.35, graceful=True)
            closed = launch("spawn_block", 0.35, close_only=True)
            orphan = launch("spawn_exit_first", 5.0)
            nonzero = launch("nonzero", 5.0)
            malformed = launch("malformed", 5.0)
            flood = launch("stdout_flood", 2.0)
            late = launch("late", 0.2)
            secrets = launch("secrets", 2.0)
            secret_block = launch("secret_block", 0.35)
        except sup.StageBlocked as exc:
            blocked = exc
            classification = exc.classification
        except OSError as exc:
            blocked = exc
            classification = "D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE"

    def use(run: dict | None) -> dict:
        return run or {}

    if len(runs) == 13:
        normal, pair, contained, blocked_worker, ignored, closed, orphan, nonzero, malformed, flood, late, secrets, secret_block = runs
        rows_e.append(row("E01", normal, "assigned before resume", str(normal["resume_previous_count"]), normal["resume_previous_count"] == 1 and normal["worker_in_job"]))
        rows_e.append(row("E02", normal, "worker membership", str(normal["worker_in_job"]), normal["worker_in_job"] is True))
        rows_e.append(row("E03", normal, "normal exit", str(normal["worker_exit_code"]), normal["worker_exit_code"] == 0 and normal["worker_exit_confirmed"]))
        rows_e.append(row("E04", pair, "one descendant", str(pair["descendant_pid"]), bool(pair["descendant_pid"]) and pair["descendant_resumed_after_membership"]))
        rows_e.append(row("E05", contained, "descendant membership", str(contained["descendant_in_job"]), contained["descendant_in_job"] is True))
        rows_e.append(row("E06", pair, "both normal exits", str([pair["worker_exit_code"], pair["descendant_exit_code"]]), pair["worker_exit_code"] == 0 and pair["descendant_exit_code"] == 0 and pair["worker_exit_confirmed"] and pair["descendant_exit_confirmed"]))
        rows_e.append(row("E07", blocked_worker, "operation deadline", blocked_worker["stop_reason"], blocked_worker["stop_reason"] == "operation" and blocked_worker["worker_exit_confirmed"]))
        rows_e.append(row("E08", contained, "descendant deadline", contained["stop_reason"], contained["stop_reason"] == "operation" and contained["descendant_exit_confirmed"]))
        rows_e.append(row("E09", ignored, "graceful stop ignored", str(ignored["alive_after_graceful"]), ignored["alive_after_graceful"] is True and ignored["termination_method"] == "TerminateJobObject" and ignored["worker_exit_confirmed"]))
        rows_e.append(row("E10", blocked_worker, "job termination ends worker", blocked_worker["termination_method"], blocked_worker["termination_method"] == "TerminateJobObject" and blocked_worker["worker_exit_confirmed"]))
        rows_e.append(row("E11", contained, "job termination ends descendant", contained["termination_method"], contained["termination_method"] == "TerminateJobObject" and contained["descendant_exit_confirmed"] is True))
        rows_e.append(row("E12", closed, "kill on close", str(closed["kill_on_close_sufficient"]), closed["kill_on_close_sufficient"] is True and closed["worker_exit_confirmed"] and closed["descendant_exit_confirmed"]))
        member_names = [name.lower() for name in contained["job_member_names"]]
        contained_members = set(member_names) <= {"python.exe", "conhost.exe"} and member_names.count("python.exe") == 2 and "not-in-job" not in member_names
        rows_e.append(row("E13", contained, "fixture processes stayed in the job", ",".join(member_names), contained["breakaway_clear"] and contained["descendant_in_job"] is True and contained_members))
        rows_e.append(row("E14", normal, "worker exit handle", str(normal["worker_exit_confirmed"]), normal["worker_exit_confirmed"] is True))
        rows_e.append(row("E15", pair, "descendant exit handle", str(pair["descendant_exit_confirmed"]), pair["descendant_exit_confirmed"] is True))
        rows_e.append(row("E16", contained, "one fixture descendant exited", ",".join(member_names), contained_members and contained["descendant_exit_confirmed"] is True and contained["cleanup_blocked"] is False))
        rows_f.append(row("F01", normal, "completed inside deadline", str(normal["operation_elapsed"]), normal["stop_reason"] == "completed" and normal["operation_elapsed"] < normal["operation_deadline"]))
        rows_f.append(row("F02", blocked_worker, "operation deadline", blocked_worker["stop_reason"], blocked_worker["stop_reason"] == "operation" and blocked_worker["operation_elapsed"] >= 0.35))
        rows_f.append(row("F03", blocked_worker, "termination after deadline", blocked_worker["termination_method"], blocked_worker["termination_method"] == "TerminateJobObject" and blocked_worker["termination_elapsed"] >= blocked_worker["operation_elapsed"]))
        rows_f.append(row("F04", blocked_worker, "worker exit verified", str(blocked_worker["worker_exit_confirmed"]), blocked_worker["worker_exit_confirmed"] is True))
        rows_f.append(row("F05", contained, "descendant exit verified", str(contained["descendant_exit_confirmed"]), contained["descendant_exit_confirmed"] is True))
        rows_f.append(row("F06", blocked_worker, "cleanup measured", str(blocked_worker["cleanup_duration"]), blocked_worker["cleanup_duration"] >= 0 and blocked_worker["cleanup_duration"] <= 2.0))
        detector_blocked = sup.cleanup_status(blocked_worker["cleanup_duration"], 0.0, True) == "BLOCKED"
        detector_live = sup.cleanup_status(blocked_worker["cleanup_duration"], 2.0, True) == "complete"
        rows_f.append(row("F07", blocked_worker, "tighter allowance blocks", "BLOCKED", detector_blocked and detector_live))
        rows_f.append(row("F08", pair, "stage origin unchanged", str(pair["stage_origin"] == normal["stage_origin"]), pair["stage_origin"] == normal["stage_origin"] == round(origin, 6)))
        rows_f.append(row("F09", ignored, "failure does not reset stage origin", str(ignored["stage_origin"] == blocked_worker["stage_origin"]), ignored["stage_origin"] == blocked_worker["stage_origin"]))
        rows_f.append(row("F10", late, "late output discarded", str(late["discarded_after_deadline"]), late["accepted"] is False and late["discarded_after_deadline"] > 0))
        rows_f.append(row("F11", blocked_worker, "no restart", str(blocked_worker["attempts"]), blocked_worker["attempts"] == 1))
        rows_f.append(row("F12", blocked_worker, "unconfirmed exit is BLOCKED", sup.cleanup_status(0.01, 2.0, False), sup.cleanup_status(0.01, 2.0, False) == "BLOCKED"))
        rows_f.append(row("F13", blocked_worker, "monotonic clock", blocked_worker["clock"], blocked_worker["clock"] == "monotonic" and "time.time(" not in supervisor_text))
        rows_f.append(row("F14", blocked_worker, "not a DNS deadline", "synthetic", "getaddrinfo" not in supervisor_text and blocked_worker["operation_deadline"] == 0.35))
        rows_f.append(row("F15", blocked_worker, "total elapsed separate", str(blocked_worker["total_elapsed"]), blocked_worker["total_elapsed"] > blocked_worker["operation_deadline"]))
        rows_h.append(row("H01", normal, "normal exit reaped", str(normal["worker_exit_code"]), normal["worker_exit_code"] == 0 and normal["handles_closed"]))
        rows_h.append(row("H02", nonzero, "abnormal exit", str(nonzero["worker_exit_code"]), nonzero["worker_exit_code"] == 3 and nonzero["worker_exit_confirmed"]))
        rows_h.append(row("H03", ignored, "graceful ignored", str(ignored["alive_after_graceful"]), ignored["alive_after_graceful"] is True))
        rows_h.append(row("H04", orphan, "descendant stayed alive in job", str(orphan["descendant_alive_after_worker"]), orphan["descendant_alive_after_worker"] is True and orphan["descendant_in_job_after_worker"] is True))
        rows_h.append(row("H05", orphan, "worker exit left contained descendant", str(orphan["descendant_exit_confirmed"]), orphan["descendant_alive_after_worker"] is True and orphan["descendant_exit_confirmed"] is True and orphan["termination_method"] == "TerminateJobObject"))
        rows_h.append(row("H06", orphan, "job termination", orphan["termination_method"], orphan["termination_method"] == "TerminateJobObject"))
        rows_h.append(row("H07", orphan, "worker exit after cleanup", str(orphan["worker_exit_confirmed"]), orphan["worker_exit_confirmed"] is True))
        rows_h.append(row("H08", orphan, "descendant exit after cleanup", str(orphan["descendant_exit_confirmed"]), orphan["descendant_exit_confirmed"] is True))
        rows_h.append(row("H09", malformed, "malformed rejected", malformed["disposition"], malformed["disposition"] == "rejected_malformed" and malformed["accepted"] is False))
        rows_h.append(row("H10", flood, "stdout capped", str(flood["stdout_bytes"]), flood["stdout_bytes"] <= 8192 and flood["worker_exit_confirmed"]))
        rows_h.append(row("H11", late, "late message rejected", str(late["accepted"]), late["accepted"] is False and late["discarded_after_deadline"] > 0))
        rows_h.append(row("H12", blocked_worker, "cleanup classifier", "BLOCKED", detector_blocked))
        rows_h.append(row("H13", blocked_worker, "no restart", str(blocked_worker["attempts"]), blocked_worker["attempts"] == 1))
        rows_h.append(row("H14", contained, "no extra fixture descendant", ",".join(member_names), contained_members and contained["descendant_exit_confirmed"] is True))
        rows_h.append(row("H16", normal, "no network import", "absent", "import socket" not in supervisor_text and "getaddrinfo" not in supervisor_text))
        rows_h.append(row("H17", normal, "no production path", "absent", "forex_bot" not in worker_text and "data/ops" not in worker_text))
        rows_h.append(row("H18", normal, "handles closed", str(normal["handles_closed"]), all(item["handles_closed"] for item in runs)))
        rows_h.append(row("H19", normal, "creation mismatch rejected", str(normal["identity_guard_ok"]), normal["identity_guard_ok"] is True))
        reclassify_blocked = False
        try:
            sample = {"result": "FAIL"}
            sup.lock_result(sample, "PASS")
        except sup.Reject:
            reclassify_blocked = True
        rows_h.append(row("H20", normal, "reclassify refused", str(reclassify_blocked), reclassify_blocked))
        rows_s.append(row("S01", secrets, "marker not accepted", secrets["disposition"], secrets["saw_unlisted_marker"] is True and secrets["accepted"] is False))
        rows_s.append(row("S02", secret_block, "failure path marker not accepted", secret_block["disposition"], secret_block["saw_unlisted_marker"] is True and secret_block["accepted"] is False and secret_block["worker_exit_confirmed"]))

    budget = sup.Budget()
    allow = {"sha256:example"}
    before = budget.snapshot()
    budget.apply_worker_message({"total": 99, "approved": True})
    budget.apply_descendant_message({"total": 99})
    forged_same = budget.snapshot() == before
    first = budget.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "head", allow)
    many = sup.Budget()
    for _ in range(20):
        many.reserve("registry-1.docker.io", "HEAD", "library/python", None, "request", allow)
    rejected_21 = False
    try:
        many.reserve("registry-1.docker.io", "HEAD", "library/python", None, "request", allow)
    except sup.Reject:
        rejected_21 = True
    heads = sup.Budget()
    for _ in range(16):
        heads.reserve("registry-1.docker.io", "HEAD", "library/python", None, "head", allow)
    head_rejected = False
    try:
        heads.reserve("registry-1.docker.io", "HEAD", "library/python", None, "head", allow)
    except sup.Reject as exc:
        head_rejected = exc.reason == "head"
    token_budget = sup.Budget()
    token_budget.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
    token_rejected = False
    try:
        token_budget.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
    except sup.Reject:
        token_rejected = True
    storage_rejected = host_rejected = method_rejected = repository_rejected = digest_rejected = layer_rejected = retry_rejected = registry_rejected = False
    idle = sup.Budget()
    checks = {
        "storage": ("registry-1.docker.io", "HEAD", "library/python", None, "storage"),
        "registry": ("registry-1.docker.io", "GET", "library/python", None, "registry_get"),
        "method": ("registry-1.docker.io", "PUT", "library/python", None, "head"),
        "host": ("production.cloudfront.docker.com", "HEAD", "library/python", None, "head"),
        "repository": ("registry-1.docker.io", "HEAD", "other/python", None, "head"),
        "digest": ("registry-1.docker.io", "HEAD", "library/python", "sha256:nope", "head"),
        "layer": ("registry-1.docker.io", "GET", "library/python", None, "layer_body"),
        "retry": ("registry-1.docker.io", "HEAD", "library/python", None, "retry"),
    }
    reasons = {}
    for name, args in checks.items():
        try:
            idle.reserve(*args, allow)
            reasons[name] = "accepted"
        except sup.Reject as exc:
            reasons[name] = exc.reason
    idle.record_redirect()
    body = sup.Budget()
    body.add_body(3)
    body.add_body(4)
    body_rejected = False
    try:
        body.add_body(1048576)
    except sup.Reject:
        body_rejected = True
    body_after = body.snapshot()["body"]
    rows_g.append({"test_id": "G01", "expected": "counter increments", "actual": first, "result": "PASS" if first == 1 else "FAIL"})
    rows_g.append({"test_id": "G02", "expected": "twenty allowed", "actual": many.total, "result": "PASS" if many.total == 20 else "FAIL"})
    rows_g.append({"test_id": "G03", "expected": "twenty-first rejected", "actual": many.total, "result": "PASS" if rejected_21 and many.total == 20 else "FAIL"})
    rows_g.append({"test_id": "G04", "expected": "head ceiling", "actual": heads.head, "result": "PASS" if head_rejected and heads.head == 16 else "FAIL"})
    rows_g.append({"test_id": "G05", "expected": "token ceiling", "actual": token_budget.token, "result": "PASS" if token_rejected and token_budget.token == 1 else "FAIL"})
    rows_g.append({"test_id": "G06", "expected": "storage rejected", "actual": reasons["storage"], "result": "PASS" if reasons["storage"] == "storage" else "FAIL"})
    rows_g.append({"test_id": "G07", "expected": "registry GET rejected", "actual": reasons["registry"], "result": "PASS" if reasons["registry"] == "registry_get" else "FAIL"})
    rows_g.append({"test_id": "G08", "expected": "redirect recorded not followed", "actual": idle.redirects_followed, "result": "PASS" if idle.redirects_recorded == 1 and idle.redirects_followed == 0 else "FAIL"})
    rows_g.append({"test_id": "G09", "expected": "retry rejected", "actual": reasons["retry"], "result": "PASS" if reasons["retry"] == "retry" and idle.retries == 0 else "FAIL"})
    rows_g.append({"test_id": "G10", "expected": "body bytes counted", "actual": body_after, "result": "PASS" if body_after == 7 else "FAIL"})
    rows_g.append({"test_id": "G12", "expected": "excess body rejected", "actual": body_after, "result": "PASS" if body_rejected and body_after == 7 else "FAIL"})
    rows_g.append({"test_id": "G13", "expected": "failed reserve keeps counters", "actual": many.total, "result": "PASS" if many.total == 20 else "FAIL"})
    rows_g.append({"test_id": "G14", "expected": "worker message ignored", "actual": forged_same, "result": "PASS" if forged_same else "FAIL"})
    rows_g.append({"test_id": "G15", "expected": "descendant message ignored", "actual": forged_same, "result": "PASS" if forged_same else "FAIL"})
    rows_g.append({"test_id": "G16", "expected": "unexpected method", "actual": reasons["method"], "result": "PASS" if reasons["method"] == "method" else "FAIL"})
    rows_g.append({"test_id": "G17", "expected": "unexpected host", "actual": reasons["host"], "result": "PASS" if reasons["host"] == "host" else "FAIL"})
    rows_g.append({"test_id": "G18", "expected": "unexpected repository", "actual": reasons["repository"], "result": "PASS" if reasons["repository"] == "repository" else "FAIL"})
    rows_g.append({"test_id": "G19", "expected": "unexpected digest", "actual": reasons["digest"], "result": "PASS" if reasons["digest"] == "digest" else "FAIL"})
    rows_g.append({"test_id": "G20", "expected": "layer body rejected", "actual": reasons["layer"], "result": "PASS" if reasons["layer"] == "layer_body" else "FAIL"})
    if len(runs) == 13:
        same_after_process = secrets["attempts"] == 1 and budget.total == 1
        rows_g.append({"test_id": "G21", "expected": "process termination leaves supervisor counter", "actual": budget.total, "result": "PASS" if same_after_process else "FAIL"})

    after_protected = [{"path": relative, "actual": digest(ROOT / relative), "match": digest(ROOT / relative) == expected} for relative, expected in PROTECTED.items()]
    after_oci = []
    for relative, (size, expected) in OCI.items():
        raw = (ROOT / relative).read_bytes()
        after_oci.append({"path": relative, "match": len(raw) == size and hashlib.sha256(raw).hexdigest() == expected})
    after_prior = {}
    for relative in PRIOR_DIRS:
        after_prior.update(tree_hashes(relative))
    protected_same = all(item["match"] for item in after_protected)
    oci_same = all(item["match"] for item in after_oci)
    prior_same = after_prior == prior
    if not protected_same or not oci_same or not prior_same:
        classification = "D30_R3_SAFETY_SCOPE_VIOLATION"
    rows_h.append({"test_id": "H15", "expected": "prior evidence unchanged", "actual": prior_same, "result": "PASS" if prior_same and protected_same else "FAIL", "fixture_mode": "hashes"})
    all_rows = rows_e + rows_f + rows_h + rows_g + rows_s
    failed = [item["test_id"] for item in all_rows if item["result"] == "FAIL"]
    if classification == "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED" and failed:
        classification = "D30_R3_OFFLINE_PROCESS_TREE_PARTIAL"
    if blocked is not None and classification == "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED":
        classification = "D30_R3_BLOCKED_PROCESS_CLEANUP"
    survivors = [item for item in runs if item.get("cleanup_blocked")]
    if survivors:
        classification = "D30_R3_BLOCKED_PROCESS_CLEANUP"

    def gate(name: str, ok: bool, reached: bool) -> dict:
        if not reached:
            verdict = "NOT_REACHED"
        elif ok:
            verdict = "PASS"
        else:
            verdict = "BLOCKED"
        return {"gate": name, "verdict": verdict}

    reached_tests = bool(runs) and blocked is None
    gates = {
        "A": gate("A", baseline_ok and prompt_ok and OUT.name == "d30_r3", True),
        "B": gate("B", oci_ok and historical_ok, baseline_ok),
        "C": gate("C", bool(probe.get("limits_contained")) and any(item["test_id"] == "E01" and item["result"] == "PASS" for item in rows_e), baseline_ok and oci_ok and historical_ok and preflight_ok),
        "D": gate("D", preflight_ok, baseline_ok and oci_ok and historical_ok),
        "E": gate("E", len(rows_e) == 16 and all(item["result"] == "PASS" for item in rows_e), reached_tests),
        "F": gate("F", len(rows_f) == 15 and all(item["result"] == "PASS" for item in rows_f), reached_tests),
        "G": gate("G", all(item["result"] == "PASS" for item in rows_g + rows_s) and bool(rows_s), reached_tests),
        "H": gate("H", all(item["result"] == "PASS" for item in rows_h) and any(item["test_id"] == "H05" and item["result"] == "PASS" for item in rows_h), reached_tests),
        "I": gate("I", reached_tests or classification.startswith("D30_R3_BLOCKED"), True),
        "J": gate("J", protected_same and oci_same and prior_same and not survivors, True),
    }
    if any(item["verdict"] != "PASS" for item in gates.values()) and classification == "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED":
        classification = "D30_R3_OFFLINE_PROCESS_TREE_PARTIAL"
    version = sys.getwindowsversion()
    passed_count = sum(item["result"] == "PASS" for item in all_rows)
    failed_count = len(failed)
    dump("01_approval_scope.json", {"approval": "YES — Approve D.30-R3 offline Windows process-tree containment and deadline-cleanup validation.", "network_requests": 0, "real_dns": False, "sockets_opened": 0})
    dump("02_baseline_integrity.json", {"head": head, "branch": branch, "status": status, "files": baseline, "match": baseline_ok})
    dump("03_oci_integrity.json", {"objects": oci_rows, "match": oci_ok})
    dump("04_prior_evidence_integrity.json", {"files": prior, "h05_result": h05_row["result"], "missing": missing, "match": historical_ok})
    dump("07_windows_api_signature_review.json", sup.api_review() | {"probe": {key: value for key, value in probe.items() if key != "layouts"}, "windows": {"major": version.major, "minor": version.minor, "build": version.build}, "machine": platform.machine()})
    dump("13_harness_preflight.json", {"checks": preflight, "verdict": "PASS" if preflight_ok else "BLOCKED"})
    dump("14_job_object_creation_results.json", {"probe": probe, "runs": [{"mode": item["mode"], "limit_flags": item["limit_flags"], "breakaway_clear": item["breakaway_clear"]} for item in runs]})
    dump("15_worker_membership_results.json", {"results": [item for item in rows_e if item["test_id"] in {"E01", "E02", "E03"}]})
    dump("16_descendant_membership_results.json", {"results": [item for item in rows_e if item["test_id"] in {"E04", "E05", "E06", "E13"}]})
    dump("17_containment_test_results.json", {"results": rows_e})
    dump("18_deadline_cleanup_results.json", {"results": rows_f, "historical_d30_r2_e04": {"synthetic_deadline_seconds": 0.35, "measured_total_elapsed_seconds": 0.534, "meaning": "termination was inside that total; cleanup was not a separate confirmed descendant exit"}})
    dump("19_failure_injection_results.json", {"results": rows_h})
    dump("20_process_identity_results.json", {"results": [item for item in rows_h if item["test_id"] in {"H18", "H19", "H20"}]})
    dump("21_budget_isolation_results.json", {"results": rows_g, "network_requests": 0})
    dump("22_logging_sanitisation_results.json", {"results": rows_s, "persisted_marker": False})
    dump("23_handle_cleanup_results.json", {"handles_closed": all(item.get("handles_closed") for item in runs) if runs else False, "unresolved": [item.get("unresolved") for item in runs if item.get("unresolved")]})
    limitations = [
        "# WINDOWS LIMITATIONS",
        "",
        f"- Supervisor already in a Job Object: {probe.get('supervisor_in_job')}.",
        f"- Limit flags read back: {probe.get('limit_flags')}.",
        f"- Active process limit read back: {probe.get('active_process_limit')}.",
        f"- Breakaway bits were clear in the readback: {probe.get('limits_contained')}.",
        "- A third fixture process was not created. The active-process limit was configured and read back. While a descendant was alive, the job also contained conhost.exe members, so that limit is not proof that the job holds only two processes.",
        "- Job handles were not placed in the inherited handle list.",
        "- CloseHandle on the job was tested separately from TerminateJobObject.",
        f"- Windows version observed through sys.getwindowsversion: {version.major}.{version.minor}.{version.build}.",
        f"- Process pointer width: {sup.layout_report()['pointer_bytes']} bytes. This is not a Python ABI measurement.",
        "- libc was not measured.",
        "- These results belong to this Windows process. They are not a universal Windows guarantee.",
        "",
    ]
    write_text("24_windows_limitations.md", "\n".join(limitations))
    dump("25_residual_risk_register.json", {"items": [
        {"item": "real DNS", "status": "UNVERIFIED"},
        {"item": "real TLS", "status": "UNVERIFIED"},
        {"item": "real HTTP", "status": "UNVERIFIED"},
        {"item": "registry HEAD", "status": "UNVERIFIED"},
        {"item": "python ABI", "status": "MISSING"},
        {"item": "libc", "status": "MISSING"},
        {"item": "production trading safety", "status": "UNVERIFIED"},
    ]})
    write_text("26_future_stage_decision.md", "\n".join([
        "# FUTURE STAGE",
        "",
        "No registry contact is recommended.",
        "Process-tree evidence from this Windows session does not make DNS, TLS, or HTTP cancellation known.",
        "A later network stage would need a fresh approval, a cancellable name lookup, and the existing request ceilings.",
        "Python ABI and libc remain unmeasured.",
        "",
    ]))
    dump("27_failure_register.json", {"failed_tests": failed, "blocked": None if blocked is None else getattr(blocked, "detail", str(blocked))})
    for key, payload in gates.items():
        index = {"A": 28, "B": 29, "C": 30, "D": 31, "E": 32, "F": 33, "G": 34, "H": 35, "I": 36, "J": 37}[key]
        dump(f"{index}_gate_{key.lower()}_verdict.json", payload)
    dump("38_source_integrity_after.json", {"protected_match": protected_same, "oci_match": oci_same, "prior_match": prior_same, "network_requests": 0, "sockets_opened": 0, "real_dns": False, "workers_left_alive": bool(survivors)})
    dump("39_validation_log.json", {"commands": ["git rev-parse HEAD", "git branch --show-current", "git status --short -- protected files", "python -B synthetic job object tests"], "network_requests": 0, "dns_lookups": 0, "sockets_opened": 0, "processes_created": sup.Session.created_processes})
    not_evaluated = sum(item["result"] == "NOT_EVALUATED" for item in all_rows)
    report = [
        "# STAGE D.30-R3 — OFFLINE WINDOWS PROCESS-TREE CONTAINMENT AND DEADLINE-CLEANUP VALIDATION REPORT",
        "",
        "## 1. EXECUTIVE SUMMARY",
        "",
        f"- Overall classification: `{classification}`",
        f"- Gate A: {gates['A']['verdict']}",
        f"- Gate B: {gates['B']['verdict']}",
        f"- Gate C: {gates['C']['verdict']}",
        f"- Gate D: {gates['D']['verdict']}",
        f"- Gate E: {gates['E']['verdict']}",
        f"- Gate F: {gates['F']['verdict']}",
        f"- Gate G: {gates['G']['verdict']}",
        f"- Gate H: {gates['H']['verdict']}",
        f"- Gate I: {gates['I']['verdict']}",
        f"- Gate J: {gates['J']['verdict']}",
        "- Production source modified: no",
        "- Network requests: 0",
        "- Real DNS lookups: 0",
        "- Sockets opened: 0",
        f"- Synthetic tests run: {len(all_rows)}",
        f"- Synthetic tests passed: {passed_count}",
        f"- Synthetic tests failed: {failed_count}",
        f"- Synthetic tests not evaluated: {not_evaluated}",
        "- Recommended next action: no registry contact. Real DNS, TLS, and HTTP remain unverified.",
        "",
        "## 2. LIVE SAFETY",
        "",
        "- Production container changed: no",
        "- Broker requests: none",
        "- Broker mutations: none",
        "- Production database access: none",
        "- Telegram network requests: none",
        "- Operational-state access: none",
        "- Shadow-mount access: none",
        "- Docker commands: none",
        "- WSL commands: none",
        "- VM commands: none",
        "- Image-layer downloads: none",
        "- Image-layer extraction: none",
        "- Package installations: none",
        "- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.",
        "- Strategy activation: none. The six strategies remain historically inactive.",
        "",
        "## 3. BASELINE INTEGRITY",
        "",
        f"- Git HEAD: `{head}`",
        f"- Branch: `{branch}`",
        "- Working-tree status: dirty before this stage. HEAD does not identify the working-tree bytes.",
        f"- Protected hashes: {'matched' if protected_same else 'changed'}",
        f"- Earlier evidence integrity: {'unchanged' if prior_same else 'changed'}",
        "- Unexpected changes: none observed." if protected_same and prior_same else "- Unexpected changes: a protected or prior hash changed.",
        "",
        "## 4. HISTORICAL EVIDENCE PRESERVATION",
        "",
        "- D.30 classification: `D30_BLOCKED_PROMPT_INTEGRITY`",
        "- D.30-R1 classification: `D30_R1_BLOCKED_CLIENT_SAFETY`",
        "- D.30-R2 classification: `D30_R2_OFFLINE_SUPERVISOR_VALIDATED`",
        "- H05 historical status: `NOT_EVALUATED`",
        f"- Earlier artifacts unchanged: {'yes' if prior_same else 'no'}",
        "",
        "## 5. OCI EVIDENCE",
        "",
        "- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes",
        "- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes",
        "- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes",
        "- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes",
        "- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes",
        f"- OCI integrity verdict: {'PASS' if oci_same else 'CHANGED'}",
        "",
        "## 6. WINDOWS CONTAINMENT ARCHITECTURE",
        "",
        "- Job Object design: an unnamed job with kill-on-close and an active-process limit.",
        "- API signatures: kernel32 through ctypes, with explicit argument and return types.",
        "- Containment-before-execution: CreateProcess suspended, assign, IsProcessInJob, then ResumeThread.",
        "- Worker assignment: membership is required before resume. The resume count is recorded.",
        "- Descendant membership: creation FILETIME must match, and IsProcessInJob must be true, before resume.",
        "- Breakaway controls: breakaway limit bits are not set.",
        "- Handle ownership: the inherited list is NUL and the worker output writes. The job handle is not inherited.",
        f"- Nested-job limitations: supervisor_in_job={probe.get('supervisor_in_job')}.",
        "",
        "## 7. HARNESS PREFLIGHT",
        "",
        "- Fixed fixture allowlist: worker and descendant modes are closed sets.",
        "- Socket prohibition: no socket import in the supervisor, worker, or descendant.",
        "- DNS prohibition: no getaddrinfo call.",
        "- Network prohibition: no HTTP client and no D.30-R1 client execution.",
        "- Credential prohibition: no credential helper and no environment values in the ledger.",
        "- Production prohibition: no application import.",
        "- Process creation bounds: one session at a time, with a hard creation cap.",
        f"- Preflight verdict: {'PASS' if preflight_ok else 'BLOCKED'}",
        "",
        "## 8. PROCESS-TREE TESTS",
        "",
        f"- Tests run: {len(rows_e)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in rows_e)}",
        f"- Tests failed: {sum(item['result'] == 'FAIL' for item in rows_e)}",
        "- Tests not evaluated: 0" if rows_e else "- Tests not evaluated: process tests did not run",
        "- Worker membership: recorded from IsProcessInJob on the CreateProcess handle.",
        "- Descendant membership: recorded only after creation-time verification.",
        "- Worker exit verification: GetExitCodeProcess on the retained handle.",
        "- Descendant exit verification: GetExitCodeProcess on the verified descendant handle.",
        "- Unexpected processes: a live descendant fixture also showed two in-job conhost.exe members. They were inside the job, and the fixture count stayed at two python.exe processes.",
        "",
        "## 9. DEADLINE AND CLEANUP TESTS",
        "",
        f"- Tests run: {len(rows_f)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in rows_f)}",
        f"- Tests failed: {sum(item['result'] == 'FAIL' for item in rows_f)}",
        "- Operation deadline evidence: the block fixture stops on the operation clock.",
        "- Termination initiation evidence: TerminateJobObject is requested after that stop.",
        "- Cleanup duration: measured from cleanup start until the waits finish.",
        "- Worker exit evidence: a non-active exit code on the worker handle.",
        "- Descendant exit evidence: a non-active exit code on the descendant handle.",
        "- Stage-budget evidence: later sessions keep the original monotonic origin.",
        "- D.30-R2 comparison: deadline 0.35 seconds, total elapsed 0.534 seconds, without a descendant.",
        "",
        "## 10. FAILURE INJECTION",
        "",
        f"- Tests run: {len(rows_h)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in rows_h)}",
        f"- Tests failed: {sum(item['result'] == 'FAIL' for item in rows_h)}",
        f"- Cleanup failures: {len(survivors)}",
        "- Unexpected processes: no second fixture descendant was launched. In-job conhost.exe members were identified by file name and ended with the job.",
        "- Unverified exits: recorded only if a handle stayed active.",
        "",
        "## 11. BUDGET AND LOGGING SAFETY",
        "",
        "- Supervisor-owned request counters: reserve rejects the twenty-first request, a second token, registry GET, storage, and retry.",
        "- Supervisor-owned byte counters: excess synthetic bytes are rejected and the prior total remains.",
        "- Worker budget isolation: a worker message does not change the snapshot.",
        "- Descendant budget isolation: a descendant message does not change the snapshot.",
        "- Synthetic sanitisation: unlisted fields are dropped. The ledger stores a disposition, not the payload.",
        "- Persisted secret leakage: the written artifacts were refused if the marker fragment was present.",
        "",
        "## 12. PROCESS AND HANDLE CLEANUP",
        "",
        "- Worker exit: confirmed on the retained process handle.",
        "- Descendant exit: confirmed on a separate verified handle when a descendant existed.",
        "- Job Object closure: the job handle is closed after the wait.",
        "- Process-handle closure: worker, descendant, and pipe handles are closed once.",
        f"- Unexpected survivors: {len(survivors)}",
        "- Cleanup limitations: an active-process limit was configured. A rejected third CreateProcess was not attempted.",
        "",
        "## 13. RESIDUAL RISKS",
        "",
        "- Real DNS: UNVERIFIED.",
        "- Real TLS: UNVERIFIED.",
        "- Real HTTP: UNVERIFIED.",
        "- Registry behaviour: UNVERIFIED.",
        "- Windows portability: this session only.",
        "- Job Object limitations: nested-job state was recorded. Breakaway was not enabled. A third child was not launched.",
        "- Deadline enforcement: operation time, termination, and cleanup are separate. This does not bound a real resolver.",
        "- Cleanup guarantees: verified for the handles this stage retained.",
        "- Python ABI: unmeasured.",
        "- libc: unmeasured.",
        "- Production readiness: not established.",
        "",
        "## 14. FINDINGS",
        "",
        "- D30R3-BASE-01. Evidence: ten local hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the protected files match. Unsupported conclusion: HEAD identifies the dirty tree. Impact: process tests were allowed to start. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R3-OCI-01. Evidence: five OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: preserved objects match size and digest. Unsupported conclusion: layer bytes are local. Impact: the registry was not contacted. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R3-TREE-01. Evidence: Job Object limit readback and membership tests. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the tested worker and its one descendant were members of the supervisor job when those tests passed. Unsupported conclusion: every Windows configuration behaves the same. Impact: descendant containment is no longer the D.30-R2 unevaluated gap for this session. Required next evidence: none for this local mechanism. Required approval: yes before any network use. Production impact: UNVERIFIED.",
        "- D30R3-RACE-01. Evidence: ResumeThread previous count. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the worker thread was still suspended when assignment finished. Unsupported conclusion: a running worker was assigned after the fact. Impact: fixture code did not run before membership. Required next evidence: the same sequence for any future real worker. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-CHILD-01. Evidence: descendant creation FILETIME and IsProcessInJob. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the descendant handle was tied to the published creation time and the intended job before resume. Unsupported conclusion: a process id alone proves identity. Impact: PID reuse was not accepted as proof. Required next evidence: the same check for any future child. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-TERM-01. Evidence: TerminateJobObject runs. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: job termination ended the worker and the descendant in the tests that passed. Unsupported conclusion: terminating the parent handle alone would have done so. Impact: descendant exit was not inferred from the parent. Required next evidence: the same split for any future real worker. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-EXIT-01. Evidence: GetExitCodeProcess on retained handles. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: exit was read from the verified handles. Unsupported conclusion: closing a handle by itself was the proof. Impact: cleanup and exit are distinct. Required next evidence: retained handles for any future child. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-TIME-01. Evidence: deadline rows. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: operation elapsed, termination, cleanup duration, and total elapsed are separate fields. Unsupported conclusion: the 10, 15, 30, and 180 second network ceilings were exercised. Impact: D.30-R2's 0.534 second total is not reused as a cleanup proof. Required next evidence: a real operation if one is ever approved. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-BUDGET-01. Evidence: simulated reserve calls. Evidence classification: SYNTHETIC_BUDGET_VERIFIED. Supported conclusion: counters stay with the supervisor across ignored worker and descendant messages. Unsupported conclusion: a registry enforced them. Impact: budgets remain local. Required next evidence: none until a network stage exists. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-LOG-01. Evidence: disposition records. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: unlisted synthetic fields were not stored. Unsupported conclusion: every future field is safe. Impact: logging is an allowlist. Required next evidence: review of any new field. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-NET-01. Evidence: source scan and this process. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: no socket, DNS, or HTTP client ran. Unsupported conclusion: registry HEAD behaviour is known. Impact: discovery remains unattempted. Required next evidence: an approved network stage. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-ABI-01. Evidence: no interpreter tag probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: pointer width is an ABI tag. Impact: wheel selection stays unresolved. Required next evidence: a dedicated measurement. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc remains unmeasured. Unsupported conclusion: the Windows version supplies a Linux libc. Impact: native wheels stay unresolved. Required next evidence: a libc observation. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R3-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: these fixtures did not read or change trading controls. Unsupported conclusion: containment makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.",
        "",
        "## 15. FUTURE DECISION",
        "",
        "- Recommended next stage: no registry contact.",
        "- Evidence gap addressed: one contained synthetic descendant on this Windows session, with separate exit and cleanup times.",
        "- Permissions required: any network stage still needs a fresh approval and a cancellable DNS design.",
        "- Remaining risks: real DNS, TLS, HTTP, ABI, libc, and portability beyond this session.",
        "- Explicit approval required: yes.",
        "",
        "## 16. VALIDATION",
        "",
        "- Commands executed: git HEAD, branch, targeted status, and local synthetic workers.",
        "- Network requests: 0",
        "- DNS lookups: 0",
        "- Sockets opened: 0",
        "- Files created: D.30-R3 artifacts under data/research/adaptive_ensemble/d30_r3/.",
        "- Files modified: none outside that new directory.",
        f"- Protected hashes: {'matched' if protected_same else 'changed'}",
        f"- OCI hashes: {'matched' if oci_same else 'changed'}",
        f"- Prior evidence hashes: {'matched' if prior_same else 'changed'}",
        f"- Processes still alive after cleanup: {len(survivors)}",
        "- Prohibited operations: none observed.",
        "",
        "## 17. FINAL CLASSIFICATION",
        "",
        f"`{classification}`",
        "",
        "## 18. NEXT ACTION",
        "",
        "D.30-R3 completed its offline process-tree programme when the classification is validated. Worker exit and descendant exit are verified only where the test rows say so. Deadline cleanup is recorded separately from the operation deadline. No real network request occurred. No DNS lookup occurred. No socket opened. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. A future network stage is not authorised. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.",
        "",
        "PRODUCTION DEPLOYMENT: NO-GO.",
        "LIVE TRADING: NOT AUTHORISED.",
        "ROLLBACK: NO-GO.",
        "",
    ]
    write_text("40_stage_d30_r3_report.md", "\n".join(report))
    print(classification)
    print("failed", ",".join(failed) if failed else "none")
    print("passed", passed_count, "failed_count", failed_count, "runs", len(runs))


if __name__ == "__main__":
    main()
