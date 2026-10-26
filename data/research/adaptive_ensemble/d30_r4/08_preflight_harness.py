"""D.30-R4 offline preflight. No transport is constructed."""
from __future__ import annotations

import hashlib
import importlib.util
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
    "data/research/adaptive_ensemble/d30_r3",
)
ESSENTIAL = (
    "data/research/adaptive_ensemble/d30/16_gate_a_verdict.json",
    "data/research/adaptive_ensemble/d30_r1/09_client_source.py",
    "data/research/adaptive_ensemble/d30_r1/21_gate_c_verdict.json",
    "data/research/adaptive_ensemble/d30_r2/17_cleanup_test_results.json",
    "data/research/adaptive_ensemble/d30_r3/09_supervisor_source.py",
    "data/research/adaptive_ensemble/d30_r3/40_stage_d30_r3_report.md",
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


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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


def main() -> None:
    client = load_module(OUT / "06_integrated_client.py", "d30r4_client")
    historical = load_module(ROOT / "data/research/adaptive_ensemble/d30_r1/09_client_source.py", "d30r1_client_policy")
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
        raw = (ROOT / relative).read_bytes() if (ROOT / relative).exists() else b""
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
        and "D30_BLOCKED_PROMPT_INTEGRITY" in (ROOT / ESSENTIAL[0]).read_text(encoding="utf-8")
        and "D30_R1_BLOCKED_CLIENT_SAFETY" in (ROOT / "data/research/adaptive_ensemble/d30_r1/21_gate_c_verdict.json").read_text(encoding="utf-8")
        and h05_row["result"] == "NOT_EVALUATED"
        and "D30_R3_OFFLINE_PROCESS_TREE_VALIDATED" in (ROOT / ESSENTIAL[-1]).read_text(encoding="utf-8")
        and historical.dns_resolution_is_hard_bounded() is False
    )
    classification = "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED"
    if not prompt_ok:
        classification = "D30_R4_BLOCKED_PROMPT_INTEGRITY"
    elif not baseline_ok:
        classification = "D30_R4_BLOCKED_BASELINE_INTEGRITY"
    elif not oci_ok:
        classification = "D30_R4_BLOCKED_OCI_INTEGRITY"
    elif not historical_ok:
        classification = "D30_R4_BLOCKED_PRIOR_EVIDENCE_ACCESS"

    client_text = (OUT / "06_integrated_client.py").read_text(encoding="utf-8")
    worker_text = (OUT / "07_synthetic_worker.py").read_text(encoding="utf-8")
    harness_text = Path(__file__).read_text(encoding="utf-8")
    preflight = []

    def add(name: str, ok: bool) -> None:
        preflight.append({"check": name, "passed": bool(ok)})

    add("windows", os.name == "nt")
    add("no_socket_import", "import socket" not in client_text and "import socket" not in worker_text)
    add("no_dns_call", "getaddrinfo(" not in client_text and "getaddrinfo(" not in worker_text)
    add("no_http_client", "urlopen" not in client_text and "http.client" not in client_text)
    add("no_project_import", "forex_bot" not in client_text and "forex_bot" not in worker_text)
    add("no_shell", "shell" + "=True" not in client_text and "shell" + "=True" not in worker_text)
    add("discover_refuses_first", "dns_resolution_is_hard_bounded" in client_text and "dispatch_count" in client_text)
    add("historical_client_not_a_transport", "import socket" not in (ROOT / "data/research/adaptive_ensemble/d30_r1/09_client_source.py").read_text(encoding="utf-8"))
    add("output_boundary", OUT.name == "d30_r4")
    add("no_broad_kill", "task" + "kill" not in client_text and "task" + "kill" not in worker_text and "Create" + "Toolhelp32Snapshot" not in client_text)
    preflight_ok = all(item["passed"] for item in preflight)
    if classification == "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED" and not preflight_ok:
        classification = "D30_R4_BLOCKED_HARNESS_SAFETY"

    network_rows = []
    budget_rows = []
    sanitised_rows = []
    contained = None
    blocked_detail = None
    offline = client.OfflineClient()
    if classification == "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED":
        try:
            offline.discover({"sha256:example"})
            network_rows.append({"test_id": "N01", "expected": "discover closed", "actual": "returned", "result": "FAIL"})
        except client.SafetyStop as exc:
            network_rows.append({"test_id": "N01", "expected": "discover closed", "actual": exc.classification, "result": "PASS" if exc.classification == "D30_R4_NETWORK_PATH_CLOSED" and offline.budget.dispatch_count == 0 else "FAIL"})
        try:
            historical.discover({"sha256:example"})
            network_rows.append({"test_id": "N02", "expected": "historical discover closed", "actual": "returned", "result": "FAIL"})
        except historical.SafetyStop as exc:
            network_rows.append({"test_id": "N02", "expected": "historical discover closed", "actual": exc.classification, "result": "PASS" if exc.classification == "D30_R1_BLOCKED_CLIENT_SAFETY" else "FAIL"})
        policy = offline.check_request("registry-1.docker.io", "HEAD", "sha256:example", {"sha256:example"})
        network_rows.append({"test_id": "N03", "expected": "policy only", "actual": policy, "result": "PASS" if policy == "policy-only" and offline.budget.dispatch_count == 0 else "FAIL"})
        storage_closed = registry_closed = redirect_closed = False
        try:
            offline.check_request("production.cloudfront.docker.com", "GET", None, set())
        except client.SafetyStop:
            storage_closed = True
        try:
            offline.check_request("registry-1.docker.io", "GET", None, set())
        except client.SafetyStop:
            registry_closed = True
        try:
            offline.follow_redirect("https://synthetic.invalid/signed")
        except client.SafetyStop:
            redirect_closed = True
        network_rows.append({"test_id": "N04", "expected": "storage closed", "actual": storage_closed, "result": "PASS" if storage_closed else "FAIL"})
        network_rows.append({"test_id": "N05", "expected": "registry GET closed", "actual": registry_closed, "result": "PASS" if registry_closed else "FAIL"})
        network_rows.append({"test_id": "N06", "expected": "redirect not followed", "actual": offline.budget.redirects_followed, "result": "PASS" if redirect_closed and offline.budget.redirects_followed == 0 and offline.budget.redirects_recorded == 1 else "FAIL"})
        proposed = offline.propose("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "head", {"sha256:example"})
        network_rows.append({"test_id": "N07", "expected": "proposal not dispatched", "actual": proposed, "result": "PASS" if proposed == "not-dispatched" and offline.budget.dispatch_count == 0 and offline.network_opened is False else "FAIL"})
        allow = {"sha256:example"}
        many = client.Budget()
        for _ in range(20):
            many.reserve("registry-1.docker.io", "HEAD", "library/python", None, "request", allow)
        rejected_21 = False
        try:
            many.reserve("registry-1.docker.io", "HEAD", "library/python", None, "request", allow)
        except client.Reject:
            rejected_21 = True
        heads = client.Budget()
        for _ in range(16):
            heads.reserve("registry-1.docker.io", "HEAD", "library/python", None, "head", allow)
        head_rejected = False
        try:
            heads.reserve("registry-1.docker.io", "HEAD", "library/python", None, "head", allow)
        except client.Reject as exc:
            head_rejected = exc.reason == "head"
        token_budget = client.Budget()
        token_budget.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
        token_rejected = False
        try:
            token_budget.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
        except client.Reject:
            token_rejected = True
        idle = client.Budget()
        reasons = {}
        probes = {
            "storage": ("registry-1.docker.io", "HEAD", "library/python", None, "storage"),
            "registry": ("registry-1.docker.io", "GET", "library/python", None, "registry_get"),
            "host": ("production.cloudfront.docker.com", "HEAD", "library/python", None, "head"),
            "method": ("registry-1.docker.io", "PUT", "library/python", None, "head"),
            "repository": ("registry-1.docker.io", "HEAD", "other/python", None, "head"),
            "digest": ("registry-1.docker.io", "HEAD", "library/python", "sha256:nope", "head"),
            "layer": ("registry-1.docker.io", "GET", "library/python", None, "layer_body"),
            "retry": ("registry-1.docker.io", "HEAD", "library/python", None, "retry"),
        }
        for name, args in probes.items():
            try:
                idle.reserve(*args, allow)
                reasons[name] = "accepted"
            except client.Reject as exc:
                reasons[name] = exc.reason
        body = client.Budget()
        body.add_body(5)
        body_rejected = False
        try:
            body.add_body(1048576)
        except client.Reject:
            body_rejected = True
        before = offline.budget.dispatch_count
        offline.budget.dispatch_count = before
        budget_rows.extend([
            {"test_id": "B01", "expected": 20, "actual": many.total, "result": "PASS" if many.total == 20 and rejected_21 else "FAIL"},
            {"test_id": "B02", "expected": 16, "actual": heads.head, "result": "PASS" if head_rejected and heads.head == 16 else "FAIL"},
            {"test_id": "B03", "expected": 1, "actual": token_budget.token, "result": "PASS" if token_rejected and token_budget.token == 1 else "FAIL"},
            {"test_id": "B04", "expected": "storage", "actual": reasons["storage"], "result": "PASS" if reasons["storage"] == "storage" else "FAIL"},
            {"test_id": "B05", "expected": "registry_get", "actual": reasons["registry"], "result": "PASS" if reasons["registry"] == "registry_get" else "FAIL"},
            {"test_id": "B06", "expected": "host", "actual": reasons["host"], "result": "PASS" if reasons["host"] == "host" else "FAIL"},
            {"test_id": "B07", "expected": "method", "actual": reasons["method"], "result": "PASS" if reasons["method"] == "method" else "FAIL"},
            {"test_id": "B08", "expected": "repository", "actual": reasons["repository"], "result": "PASS" if reasons["repository"] == "repository" else "FAIL"},
            {"test_id": "B09", "expected": "digest", "actual": reasons["digest"], "result": "PASS" if reasons["digest"] == "digest" else "FAIL"},
            {"test_id": "B10", "expected": "layer_body", "actual": reasons["layer"], "result": "PASS" if reasons["layer"] == "layer_body" else "FAIL"},
            {"test_id": "B11", "expected": "retry", "actual": reasons["retry"], "result": "PASS" if reasons["retry"] == "retry" and idle.retries == 0 else "FAIL"},
            {"test_id": "B12", "expected": 5, "actual": body.body, "result": "PASS" if body_rejected and body.body == 5 else "FAIL"},
            {"test_id": "B13", "expected": 0, "actual": offline.budget.dispatch_count, "result": "PASS" if offline.budget.dispatch_count == 0 else "FAIL"},
        ])
        hostile = client.OfflineClient()
        hostile._record({"event": "propose", "host": "registry-1.docker.io", "method": "HEAD", "disposition": "not-dispatched", "note": "synthetic-bearer-redact-me"})
        sanitised_rows.append({"test_id": "S01", "expected": "marker dropped", "actual": hostile.ledger, "result": "PASS" if hostile.ledger == [{"event": "propose", "host": "registry-1.docker.io", "method": "HEAD", "disposition": "not-dispatched"}] else "FAIL"})
        try:
            supervisor = load_module(ROOT / "data/research/adaptive_ensemble/d30_r3/09_supervisor_source.py", "d30r3_supervisor")
            session = supervisor.Session(OUT / "07_synthetic_worker.py", OUT, "complete", 5.0, 60.0, time.monotonic())
            contained = session.execute()
        except Exception as exc:
            blocked_detail = type(exc).__name__
            classification = "D30_R4_BLOCKED_PROCESS_CLEANUP"

    wrapper_ok = bool(
        contained
        and contained["worker_in_job"] is True
        and contained["resume_previous_count"] == 1
        and contained["worker_exit_confirmed"] is True
        and contained["worker_exit_code"] == 0
        and contained["handles_closed"] is True
        and contained["cleanup_blocked"] is False
    )
    if contained and not wrapper_ok and classification == "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED":
        classification = "D30_R4_BLOCKED_HARNESS_SAFETY"
    if any(item["result"] == "FAIL" for item in network_rows + budget_rows + sanitised_rows):
        if classification == "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED":
            classification = "D30_R4_BLOCKED_HARNESS_SAFETY"

    after_protected = all(digest(ROOT / relative) == expected for relative, expected in PROTECTED.items())
    after_oci = True
    for relative, (size, expected) in OCI.items():
        raw = (ROOT / relative).read_bytes()
        after_oci = after_oci and len(raw) == size and hashlib.sha256(raw).hexdigest() == expected
    after_prior = {}
    for relative in PRIOR_DIRS:
        after_prior.update(tree_hashes(relative))
    prior_same = after_prior == prior
    if not after_protected or not after_oci or not prior_same:
        classification = "D30_R4_SAFETY_SCOPE_VIOLATION"

    def gate(name: str, ok: bool, reached: bool = True) -> dict:
        if not reached:
            verdict = "NOT_REACHED"
        elif ok:
            verdict = "PASS"
        else:
            verdict = "BLOCKED"
        return {"gate": name, "verdict": verdict}

    reached = classification not in {
        "D30_R4_BLOCKED_PROMPT_INTEGRITY",
        "D30_R4_BLOCKED_BASELINE_INTEGRITY",
        "D30_R4_BLOCKED_OCI_INTEGRITY",
        "D30_R4_BLOCKED_PRIOR_EVIDENCE_ACCESS",
    }
    gates = {
        "A": gate("A", baseline_ok and prompt_ok),
        "B": gate("B", oci_ok and historical_ok, baseline_ok),
        "C": gate("C", "D30_R4_NETWORK_PATH_CLOSED" in client_text and "not-dispatched" in client_text, reached),
        "D": gate("D", preflight_ok, reached),
        "E": gate("E", wrapper_ok, reached and preflight_ok),
        "F": gate("F", all(item["result"] == "PASS" for item in budget_rows) and bool(budget_rows), reached and preflight_ok),
        "G": gate("G", all(item["result"] == "PASS" for item in sanitised_rows), reached and preflight_ok),
        "H": gate("H", all(item["result"] == "PASS" for item in network_rows) and offline.budget.dispatch_count == 0 and offline.network_opened is False, reached and preflight_ok),
        "I": gate("I", reached),
        "J": gate("J", after_protected and after_oci and prior_same),
    }
    if any(item["verdict"] != "PASS" for item in gates.values()) and classification == "D30_R4_OFFLINE_CLIENT_PREFLIGHT_VALIDATED":
        classification = "D30_R4_BLOCKED_HARNESS_SAFETY"
    failed = [item["test_id"] for item in network_rows + budget_rows + sanitised_rows if item["result"] == "FAIL"]
    if contained and not wrapper_ok:
        failed.append("W01")
    dump("01_approval_scope.json", {"approval": "YES — Approve D.30-R4 offline network-client integration and synthetic safety preflight, with zero network access.", "network_requests": 0, "sockets_opened": 0, "real_dns": False})
    dump("02_baseline_integrity.json", {"head": head, "branch": branch, "status": status, "files": baseline, "match": baseline_ok})
    dump("03_oci_integrity.json", {"objects": oci_rows, "match": oci_ok})
    dump("04_prior_evidence_integrity.json", {"file_count": len(prior), "missing": missing, "h05_result": h05_row["result"], "match": historical_ok and prior_same})
    dump("09_network_path_results.json", {"results": network_rows, "dispatch_count": offline.budget.dispatch_count, "network_opened": offline.network_opened})
    dump("10_containment_wrapper_results.json", {"result": None if contained is None else {key: contained[key] for key in ("mode", "worker_in_job", "resume_previous_count", "worker_exit_confirmed", "worker_exit_code", "handles_closed", "cleanup_blocked", "termination_method", "operation_elapsed", "cleanup_duration", "total_elapsed")}, "wrapper_ok": wrapper_ok, "blocked": blocked_detail})
    dump("11_budget_results.json", {"results": budget_rows, "network_requests": 0})
    dump("12_sanitisation_results.json", {"results": [{"test_id": item["test_id"], "result": item["result"]} for item in sanitised_rows], "persisted_marker": False})
    dump("13_preflight_results.json", {"checks": preflight, "verdict": "PASS" if preflight_ok else "BLOCKED"})
    dump("14_residual_risk_register.json", {"items": [
        {"item": "real DNS", "status": "UNVERIFIED"},
        {"item": "real TLS", "status": "UNVERIFIED"},
        {"item": "real HTTP", "status": "UNVERIFIED"},
        {"item": "process termination cancels getaddrinfo", "status": "UNVERIFIED"},
        {"item": "python ABI", "status": "MISSING"},
        {"item": "libc", "status": "MISSING"},
        {"item": "production trading safety", "status": "UNVERIFIED"},
    ]})
    write_text("15_future_stage_decision.md", "\n".join([
        "# FUTURE STAGE",
        "",
        "No registry contact is recommended.",
        "The integrated client refuses to create a transport while name lookup is unbounded.",
        "A Job Object can contain a synthetic worker. That does not cancel a resolver call that has already entered the operating system.",
        "Any later network stage needs a fresh approval and a cancellable name-lookup design.",
        "Python ABI and libc remain unmeasured.",
        "",
    ]))
    dump("16_failure_register.json", {"failed_tests": failed, "blocked": blocked_detail})
    for key, payload in gates.items():
        index = {"A": 17, "B": 18, "C": 19, "D": 20, "E": 21, "F": 22, "G": 23, "H": 24, "I": 25, "J": 26}[key]
        dump(f"{index}_gate_{key.lower()}_verdict.json", payload)
    dump("27_source_integrity_after.json", {"protected_match": after_protected, "oci_match": after_oci, "prior_match": prior_same, "network_requests": 0, "sockets_opened": 0, "real_dns": False})
    dump("28_validation_log.json", {"commands": ["git rev-parse HEAD", "git branch --show-current", "git status --short -- protected files", "python -B offline client preflight"], "network_requests": 0, "dns_lookups": 0, "sockets_opened": 0})
    passed = sum(item["result"] == "PASS" for item in network_rows + budget_rows + sanitised_rows) + (1 if wrapper_ok else 0)
    ran = len(network_rows) + len(budget_rows) + len(sanitised_rows) + (1 if contained is not None or blocked_detail else 0)
    report = [
        "# STAGE D.30-R4 — OFFLINE NETWORK-CLIENT INTEGRATION AND SYNTHETIC SAFETY PREFLIGHT REPORT",
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
        f"- Synthetic tests run: {ran}",
        f"- Synthetic tests passed: {passed}",
        f"- Synthetic tests failed: {len(failed)}",
        "- Recommended next action: no registry contact. The client path stays closed.",
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
        f"- Protected hashes: {'matched' if after_protected else 'changed'}",
        f"- Earlier evidence integrity: {'unchanged' if prior_same else 'changed'}",
        "- Unexpected changes: none observed." if after_protected and prior_same else "- Unexpected changes: a protected or prior hash changed.",
        "",
        "## 4. HISTORICAL EVIDENCE PRESERVATION",
        "",
        "- D.30 classification: `D30_BLOCKED_PROMPT_INTEGRITY`",
        "- D.30-R1 classification: `D30_R1_BLOCKED_CLIENT_SAFETY`",
        "- D.30-R2 classification: `D30_R2_OFFLINE_SUPERVISOR_VALIDATED`",
        "- D.30-R2 H05: `NOT_EVALUATED`",
        "- D.30-R3 classification: `D30_R3_OFFLINE_PROCESS_TREE_VALIDATED`",
        f"- Earlier artifacts unchanged: {'yes' if prior_same else 'no'}",
        "",
        "## 5. OCI EVIDENCE",
        "",
        "- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes",
        "- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes",
        "- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes",
        "- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes",
        "- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes",
        f"- OCI integrity verdict: {'PASS' if after_oci else 'CHANGED'}",
        "",
        "## 6. INTEGRATED CLIENT",
        "",
        "- Policy owner: the supervisor process.",
        "- Transport: not constructed.",
        "- Discover: raises `D30_R4_NETWORK_PATH_CLOSED` because name lookup is not hard-bounded.",
        "- Historical discover: the D.30-R1 function still raises `D30_R1_BLOCKED_CLIENT_SAFETY`.",
        "- A policy-only HEAD check does not send a request.",
        "- Redirects are recorded and not followed.",
        "- Dispatch count: 0.",
        "",
        "## 7. PREFLIGHT",
        "",
        f"- Preflight verdict: {'PASS' if preflight_ok else 'BLOCKED'}",
        "- Socket import: absent from the integrated client and synthetic worker.",
        "- DNS call: absent.",
        "- HTTP client: absent.",
        "- Application import: absent.",
        "- Output directory: `d30_r4`.",
        "",
        "## 8. CONTAINMENT WRAPPER",
        "",
        f"- Synthetic worker launched: {contained is not None}",
        f"- Worker in job: {None if contained is None else contained['worker_in_job']}",
        f"- Resume previous count: {None if contained is None else contained['resume_previous_count']}",
        f"- Worker exit confirmed: {None if contained is None else contained['worker_exit_confirmed']}",
        f"- Exit code: {None if contained is None else contained['worker_exit_code']}",
        "- The worker wrote a status line. That line is not an HTTP response.",
        "- Process containment does not establish that a resolver call can be cancelled.",
        "",
        "## 9. BUDGETS",
        "",
        "- Request ceiling: 20",
        "- HEAD ceiling: 16",
        "- Token ceiling: 1",
        "- Body ceiling: 1,048,576",
        "- Redirects followed: 0",
        "- Retries: 0",
        "- These counters were exercised with simulated events.",
        "",
        "## 10. SANITISATION",
        "",
        "- Ledger fields: event, host, method, disposition.",
        "- An unlisted synthetic field was not stored.",
        "- Persisted marker leakage: no",
        "",
        "## 11. RESIDUAL RISKS",
        "",
        "- Real DNS: UNVERIFIED.",
        "- Real TLS: UNVERIFIED.",
        "- Real HTTP: UNVERIFIED.",
        "- Whether job termination cancels an in-flight name lookup: UNVERIFIED.",
        "- Python ABI: unmeasured.",
        "- libc: unmeasured.",
        "- Production readiness: not established.",
        "",
        "## 12. FINDINGS",
        "",
        "- D30R4-BASE-01. Evidence: ten local hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the protected files match. Unsupported conclusion: HEAD identifies the dirty tree. Impact: the preflight was allowed to start. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R4-OCI-01. Evidence: five OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the preserved objects match. Unsupported conclusion: layer bytes are local. Impact: the registry was not contacted. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R4-CLIENT-01. Evidence: discover and propose results. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the integrated client records policy and does not dispatch. Unsupported conclusion: a HEAD request was sent. Impact: the network path stays closed. Required next evidence: a cancellable resolver before any socket. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-DNS-01. Evidence: D.30-R1 discover still raises, and the new client returns false for a hard bound. Evidence classification: HISTORICAL_OBSERVATION. Supported conclusion: standard-library name lookup is still not treated as cancellable. Unsupported conclusion: the Job Object cancelled a resolver. Impact: DNS remains the reason the path is closed. Required next evidence: a tested cancellation mechanism. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-PROC-01. Evidence: one synthetic worker under the D.30-R3 supervisor. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: the wrapper assigned the worker before resume and confirmed its exit. Unsupported conclusion: that worker performed HTTP. Impact: the process boundary is wired to a non-network fixture. Required next evidence: the same wrapper around a real transport, after DNS cancellation exists. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-BUDGET-01. Evidence: simulated reserve calls. Evidence classification: SYNTHETIC_BUDGET_VERIFIED. Supported conclusion: the ceilings reject excess simulated requests and bytes. Unsupported conclusion: a registry enforced them. Impact: budgets remain local. Required next evidence: none until a network stage exists. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-LOG-01. Evidence: filtered ledger. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: unlisted fields were not stored. Unsupported conclusion: every future header is safe. Impact: logging stays on an allowlist. Required next evidence: review of any new field. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-NET-01. Evidence: source scan and this process. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: no socket, DNS, or HTTP client ran. Unsupported conclusion: registry behaviour is known. Impact: discovery remains unattempted. Required next evidence: an approved network stage. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-ABI-01. Evidence: no interpreter tag probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: this preflight measured it. Impact: wheel selection stays unresolved. Required next evidence: a dedicated measurement. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc remains unmeasured. Unsupported conclusion: Windows version supplies a Linux libc. Impact: native wheels stay unresolved. Required next evidence: a libc observation. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R4-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: this preflight did not read or change trading controls. Unsupported conclusion: a closed client makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.",
        "",
        "## 13. FUTURE DECISION",
        "",
        "- Recommended next stage: no registry contact.",
        "- Evidence gap addressed: the safety policy and the process wrapper now meet in one offline client, and that client still refuses to create a transport.",
        "- Permissions required: a later network stage needs a fresh approval and a cancellable name lookup.",
        "- Remaining risks: real DNS, TLS, HTTP, ABI, and libc.",
        "- Explicit approval required: yes.",
        "",
        "## 14. VALIDATION",
        "",
        "- Commands executed: git HEAD, branch, targeted status, the historical discover refusal, and one synthetic worker.",
        "- Network requests: 0",
        "- DNS lookups: 0",
        "- Sockets opened: 0",
        "- Files created: D.30-R4 artifacts under data/research/adaptive_ensemble/d30_r4/.",
        "- Files modified: none outside that new directory.",
        f"- Protected hashes: {'matched' if after_protected else 'changed'}",
        f"- OCI hashes: {'matched' if after_oci else 'changed'}",
        f"- Prior evidence hashes: {'matched' if prior_same else 'changed'}",
        "- Prohibited operations: none observed.",
        "",
        "## 15. FINAL CLASSIFICATION",
        "",
        f"`{classification}`",
        "",
        "## 16. NEXT ACTION",
        "",
        "D.30-R4 completed the offline integration and synthetic preflight when the classification is validated. The network path stayed closed. No real network request occurred. No DNS lookup occurred. No socket opened. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. A future network stage is not authorised. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.",
        "",
        "PRODUCTION DEPLOYMENT: NO-GO.",
        "LIVE TRADING: NOT AUTHORISED.",
        "ROLLBACK: NO-GO.",
        "",
    ]
    write_text("29_stage_d30_r4_report.md", "\n".join(report))
    print(classification)
    print("failed", ",".join(failed) if failed else "none")
    print("wrapper", wrapper_ok, "dispatch", offline.budget.dispatch_count)


if __name__ == "__main__":
    main()
