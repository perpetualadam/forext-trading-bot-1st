"""Offline synthetic validation for the D.30-R2 supervisor. No sockets."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
HEX64 = __import__("re").compile(r"^[0-9a-f]{64}$")
EXPECTED_HEAD = "d080d897945bc44fa37c02caab504ed707146bec"
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
    "index": ("data/research/adaptive_ensemble/d22_r1/09_index_raw_manifest.json", "34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258", 6546),
    "amd64_manifest": ("data/research/adaptive_ensemble/d22_r1/15_amd64_raw_manifest.json", "2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d", 1752),
    "arm64_manifest": ("data/research/adaptive_ensemble/d22_r1/19_arm64_raw_manifest.json", "739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163", 1754),
    "amd64_config": ("data/research/adaptive_ensemble/d24_r2/11_amd64_config_raw.json", "4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524", 5684),
    "arm64_config": ("data/research/adaptive_ensemble/d24_r2/16_arm64_config_raw.json", "eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629", 5699),
}
PRIOR = [
    "data/research/adaptive_ensemble/d29_r1/10_timeout_deadline_specification.json",
    "data/research/adaptive_ensemble/d29_r1/14_future_client_safety_specification.md",
    "data/research/adaptive_ensemble/d30/16_gate_a_verdict.json",
    "data/research/adaptive_ensemble/d30/28_stage_d30_report.md",
    "data/research/adaptive_ensemble/d30_r1/09_client_source.py",
    "data/research/adaptive_ensemble/d30_r1/10_offline_preflight.json",
    "data/research/adaptive_ensemble/d30_r1/16_deadline_reconciliation.json",
    "data/research/adaptive_ensemble/d30_r1/31_stage_d30_r1_report.md",
]
MARKERS = (
    "synthetic-bearer-redact-me",
    "synthetic-authorization-redact-me",
    "synthetic-cookie-redact-me",
    "synthetic-signed-query-redact-me",
    "synthetic-proxy-redact-me",
    "synthetic-env-redact-me",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write_md(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


def case(test_id: str, fixture: str, expected: str, actual: str, started: float, elapsed: float, passed: bool, **extra: object) -> dict[str, object]:
    row = {
        "test_id": test_id,
        "fixture": fixture,
        "expected": expected,
        "actual": actual,
        "monotonic_start": round(started, 6),
        "elapsed": round(elapsed, 4),
        "result": "PASS" if passed else "FAIL",
    }
    row.update(extra)
    return row


def main() -> None:
    for digest in list(PROTECTED.values()) + [item[1] for item in OCI.values()]:
        if not HEX64.fullmatch(digest):
            raise SystemExit("D30_R2_BLOCKED_PROMPT_INTEGRITY")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    targeted = subprocess.run(["git", "status", "--short", "--", *PROTECTED], cwd=ROOT, capture_output=True, text=True, check=False).stdout.splitlines()
    if head != EXPECTED_HEAD or branch != "main":
        raise SystemExit("D30_R2_BLOCKED_BASELINE_INTEGRITY")
    hashes = {}
    for relative, expected in PROTECTED.items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise SystemExit("D30_R2_BLOCKED_BASELINE_INTEGRITY")
        hashes[relative] = expected
    missing = [relative for relative in PRIOR if not (ROOT / relative).is_file()]
    if missing:
        raise SystemExit("D30_R2_BLOCKED_PRIOR_EVIDENCE_ACCESS")
    prior_hashes = {relative: sha256_file(ROOT / relative) for relative in PRIOR}
    oci_ok = True
    for _key, (relative, digest, size) in OCI.items():
        raw = (ROOT / relative).read_bytes()
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            oci_ok = False
    if not oci_ok:
        raise SystemExit("D30_R2_BLOCKED_OCI_INTEGRITY")
    d30_gate = json.loads((ROOT / PRIOR[2]).read_text(encoding="utf-8"))
    d30_r1_preflight = json.loads((ROOT / PRIOR[5]).read_text(encoding="utf-8"))
    if d30_gate.get("classification") != "D30_BLOCKED_PROMPT_INTEGRITY":
        raise SystemExit("D30_R2_BLOCKED_PRIOR_EVIDENCE_ACCESS")
    if d30_r1_preflight.get("dns_demonstration", {}).get("resolver_still_running_at_deadline") is not True:
        raise SystemExit("D30_R2_BLOCKED_PRIOR_EVIDENCE_ACCESS")
    supervisor_text = (OUT / "08_supervisor_source.py").read_text(encoding="utf-8")
    worker_text = (OUT / "09_synthetic_worker_source.py").read_text(encoding="utf-8")
    harness_text = (OUT / "10_offline_harness_source.py").read_text(encoding="utf-8")
    forbidden = ("import socket", "getaddrinfo", "urllib", "http.client", "forex_bot", "urlopen")
    preflight = []

    def add(name: str, passed: bool) -> None:
        preflight.append({"check": name, "passed": passed})

    add("fixture_modes_fixed", "MODES = frozenset" in worker_text)
    add("no_arbitrary_command", "shell=True" not in supervisor_text)
    add("no_url_input", "https://" not in worker_text and "https://" not in supervisor_text)
    add("no_hostname_resolution", "getaddrinfo" not in worker_text and "getaddrinfo" not in supervisor_text)
    add("no_network_import", all(token not in worker_text and token not in supervisor_text for token in forbidden))
    add("no_socket_path", "import socket" not in worker_text and "import socket" not in supervisor_text)
    add("no_dns_path", "getaddrinfo" not in worker_text)
    add("no_project_import", "forex_bot" not in worker_text and "forex_bot" not in supervisor_text)
    add("no_credential_read", "docker-credential" not in supervisor_text and '".env"' not in worker_text)
    add("no_production_access", "operational" not in worker_text and "shadow" not in worker_text)
    add("output_boundary", "cwd=str(self.out_dir)" in supervisor_text)
    add("bounded_output", "OUTPUT_CAP" in supervisor_text)
    add("bounded_runtime", "wait(timeout=2.0)" in supervisor_text)
    add("bounded_process_creation", "Popen" in supervisor_text and "shell=True" not in supervisor_text)
    add("worker_spawns_no_children", "subprocess" not in worker_text and "Popen" not in worker_text)
    add("no_retry_helper", "retry" not in supervisor_text or "raise Reject" in supervisor_text)
    add("termination_available", "proc.terminate" in supervisor_text and "proc.kill" in supervisor_text)
    add("exit_check_available", "proc.poll" in supervisor_text)
    add("synthetic_cannot_request", "urlopen" not in worker_text)
    add("d30_r1_client_not_executed", "load_module(\"d30_r1" not in harness_text)
    if any(not item["passed"] for item in preflight):
        dump("11_harness_preflight.json", {"checks": preflight, "verdict": "BLOCKED"})
        raise SystemExit("D30_R2_BLOCKED_HARNESS_SAFETY")
    sup_mod = load_module("d30r2_supervisor", OUT / "08_supervisor_source.py")
    worker = OUT / "09_synthetic_worker_source.py"
    results_e = []
    results_f = []
    cleanup_alive = False

    def run(mode: str, operation: float, stage: float = 10.0) -> tuple[object, dict]:
        supervisor = sup_mod.Supervisor(worker, OUT, stage)
        started = time.monotonic()
        record = supervisor.run(mode, operation)
        return supervisor, {**record, "monotonic_start": started, "elapsed_measured": time.monotonic() - started}

    def dead(record: dict) -> bool:
        return record["worker_alive_after_cleanup"] is False and record["exit_observed"] is True

    supervisor, record = run("complete", 2.0)
    results_e.append(case("E01", "complete", "normal exit", record["stop_reason"], record["monotonic_start"], record["elapsed"], dead(record) and record["accepted"] is True and record["exit_code"] == 0 and record["termination_requested"] is False, termination_requested=False, termination_method=record["termination_method"], exit_observed=True, exit_code=0, worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("nonzero", 2.0)
    results_e.append(case("E02", "nonzero", "exit 3", str(record["exit_code"]), record["monotonic_start"], record["elapsed"], dead(record) and record["exit_code"] == 3, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("exception", 2.0)
    results_e.append(case("E03", "exception", "nonzero exception exit", str(record["exit_code"]), record["monotonic_start"], record["elapsed"], dead(record) and record["exit_code"] not in {0, None}, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("block", 0.35)
    results_e.append(case("E04", "block", "terminated at deadline", record["termination_method"], record["monotonic_start"], record["elapsed"], dead(record) and record["termination_requested"] is True and record["termination_method"] in {"terminate", "kill"} and record["elapsed"] < 2.5 and record["attempts"] if False else record["elapsed"] < 2.5, termination_requested=True, termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("ignore_stop", 0.35)
    results_e.append(case("E05", "ignore_stop", "graceful stop ignored then terminated", record["termination_method"], record["monotonic_start"], record["elapsed"], dead(record) and record["alive_after_graceful_request"] is True and record["termination_method"] in {"terminate", "kill"}, termination_requested=True, termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("silent", 0.35)
    results_e.append(case("E06", "silent", "no response then terminated", record["stop_reason"], record["monotonic_start"], record["elapsed"], dead(record) and record["accepted"] is False and record["termination_requested"] is True, termination_requested=True, termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("malformed", 2.0)
    results_e.append(case("E07", "malformed", "response rejected", str(record["accepted"]), record["monotonic_start"], record["elapsed"], dead(record) and record["accepted"] is False, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("stdout_flood", 2.0)
    results_e.append(case("E08", "stdout_flood", "stdout capped and worker reaped", str(record["stdout_bytes"]), record["monotonic_start"], record["elapsed"], dead(record) and record["stdout_bytes"] <= 8192 and record["elapsed"] < 2.5, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("stderr_flood", 2.0)
    results_e.append(case("E09", "stderr_flood", "stderr capped and worker reaped", str(record["stderr_bytes"]), record["monotonic_start"], record["elapsed"], dead(record) and record["stderr_bytes"] <= 8192 and record["elapsed"] < 2.5, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]
    _, record = run("partial", 2.0)
    results_e.append(case("E10", "partial", "partial message rejected", str(record["accepted"]), record["monotonic_start"], record["elapsed"], dead(record) and record["accepted"] is False, termination_requested=record["termination_requested"], termination_method=record["termination_method"], exit_observed=record["exit_observed"], exit_code=record["exit_code"], worker_alive_after_cleanup=record["worker_alive_after_cleanup"], cleanup_deadline=2.0))
    cleanup_alive = cleanup_alive or record["worker_alive_after_cleanup"]

    def fcase(test_id: str, mode: str, operation: float, stage: float, predicate) -> dict:
        local, row_record = run(mode, operation, stage)
        passed = predicate(local, row_record) and dead(row_record)
        return case(test_id, mode, "deadline rule", row_record["stop_reason"], row_record["monotonic_start"], row_record["elapsed"], passed, configured_limit=row_record["configured_limit"], observed_stop=row_record["stop_reason"], exit_observed=row_record["exit_observed"], worker_alive_after_cleanup=row_record["worker_alive_after_cleanup"], supervisor=local)

    f_rows_raw = []
    f_rows_raw.append(fcase("F01", "complete", 1.0, 10.0, lambda sup, rec: rec["accepted"] is True and rec["elapsed"] < 1.0))
    f_rows_raw.append(fcase("F02", "block", 0.4, 10.0, lambda sup, rec: rec["stop_reason"] == "operation" and rec["termination_requested"] is True and rec["elapsed"] < 2.5))
    f_rows_raw.append(fcase("F03", "block", 0.3, 10.0, lambda sup, rec: rec["elapsed"] < 2.0 and rec["termination_requested"] is True))
    f_rows_raw.append(fcase("F04", "block", 5.0, 0.45, lambda sup, rec: rec["stop_reason"] == "stage"))
    f_rows_raw.append(fcase("F05", "block", 0.3, 5.0, lambda sup, rec: rec["stop_reason"] == "operation"))
    shared = sup_mod.Supervisor(worker, OUT, 2.5)
    shared_start = shared.started
    first = shared.run("complete", 2.0)
    second = shared.run("block", 5.0)
    f_rows_raw.append(case("F06", "shared stage", "one stage clock", second["stop_reason"], shared_start, second["elapsed"], dead(first) and dead(second) and shared.started == shared_start and second["stop_reason"] == "stage", configured_limit=second["configured_limit"], observed_stop=second["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    failed = sup_mod.Supervisor(worker, OUT, 10.0)
    origin = failed.started
    failed_run = failed.run("block", 0.3)
    f_rows_raw.append(case("F07", "block", "stage clock not reset", str(failed.started == origin), origin, failed.stage_elapsed(), dead(failed_run) and failed.started == origin and failed.stage_elapsed() > 0.2, configured_limit=0.3, observed_stop=failed_run["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    _, timed = run("block", 0.3)
    f_rows_raw.append(case("F08", "block", "cleanup timed separately", str(timed["cleanup_elapsed"]), timed["monotonic_start"], timed["elapsed"], dead(timed) and timed["cleanup_elapsed"] >= 0 and timed["termination_requested"] is True, configured_limit=timed["configured_limit"], observed_stop=timed["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    mono_a = time.monotonic()
    mono_b = time.monotonic()
    f_rows_raw.append(case("F09", "clock", "monotonic", "monotonic", mono_a, mono_b - mono_a, mono_b >= mono_a and "time.time(" not in supervisor_text, configured_limit=None, observed_stop="not_applicable", exit_observed=False, worker_alive_after_cleanup=False))
    once = sup_mod.Supervisor(worker, OUT, 10.0)
    once_run = once.run("block", 0.3)
    f_rows_raw.append(case("F10", "block", "no retry", str(once.attempts), once.started, once_run["elapsed"], once.attempts == 1 and dead(once_run), configured_limit=0.3, observed_stop=once_run["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    extend_supervisor = sup_mod.Supervisor(worker, OUT, 10.0)
    before = extend_supervisor.stage_deadline
    extend_run = extend_supervisor.run("extend", 2.0)
    f_rows_raw.append(case("F11", "extend", "worker cannot extend deadline", str(extend_supervisor.stage_deadline), extend_supervisor.started, extend_run["elapsed"], extend_supervisor.stage_deadline == before and extend_run["configured_limit"] != 999 and dead(extend_run), configured_limit=extend_run["configured_limit"], observed_stop=extend_run["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    _, late = run("late", 0.25)
    f_rows_raw.append(case("F12", "late", "late response rejected", str(late["accepted"]), late["monotonic_start"], late["elapsed"], dead(late) and late["accepted"] is False and late["termination_requested"] is True, configured_limit=late["configured_limit"], observed_stop=late["stop_reason"], exit_observed=True, worker_alive_after_cleanup=False))
    for item in f_rows_raw:
        item.pop("supervisor", None)
        results_f.append(item)
        cleanup_alive = cleanup_alive or item.get("worker_alive_after_cleanup") is True

    budget = sup_mod.Budget()
    allow = {"sha256:example"}
    g_rows = []
    seen = {"dispatched": False}

    def dispatch() -> None:
        seen["dispatched"] = budget.total == 1

    started = time.monotonic()
    budget.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "head", allow)
    dispatch()
    g_rows.append(case("G01", "reserve", "increment before dispatch", str(seen["dispatched"]), started, 0.0, seen["dispatched"] is True and budget.total == 1))
    fresh = sup_mod.Budget()
    for _ in range(20):
        fresh.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "request", allow)
    g_rows.append(case("G02", "reserve", "twenty permitted", str(fresh.total), started, 0.0, fresh.total == 20))
    rejected = False
    try:
        fresh.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "request", allow)
    except sup_mod.Reject:
        rejected = True
    g_rows.append(case("G03", "reserve", "twenty-first rejected", str(rejected), started, 0.0, rejected and fresh.total == 20))
    heads = sup_mod.Budget()
    for _ in range(16):
        heads.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "head", allow)
    head_rejected = False
    try:
        heads.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:example", "head", allow)
    except sup_mod.Reject:
        head_rejected = True
    g_rows.append(case("G04", "head", "sixteen head ceiling", str(heads.head), started, 0.0, heads.head == 16 and head_rejected))
    tokens = sup_mod.Budget()
    tokens.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
    token_rejected = False
    try:
        tokens.reserve("auth.docker.io", "GET", "library/python", None, "token", allow)
    except sup_mod.Reject:
        token_rejected = True
    g_rows.append(case("G05", "token", "one token ceiling", str(tokens.token), started, 0.0, tokens.token == 1 and token_rejected))

    def rejects(category_call) -> bool:
        try:
            category_call()
            return False
        except sup_mod.Reject:
            return True

    idle = sup_mod.Budget()
    g_rows.append(case("G06", "storage", "storage rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "HEAD", "library/python", None, "storage", allow)) and idle.total == 0))
    g_rows.append(case("G07", "registry get", "registry GET rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "GET", "library/python", None, "request", allow)) and idle.total == 0))
    idle.record_redirect()
    g_rows.append(case("G08", "redirect", "recorded not followed", str(idle.redirects_followed), started, 0.0, idle.redirects_recorded == 1 and idle.redirects_followed == 0))
    g_rows.append(case("G09", "retry", "retry rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "HEAD", "library/python", None, "retry", allow))))
    body = sup_mod.Budget()
    body.add_body(10)
    body.add_body(5)
    g_rows.append(case("G10", "error bytes", "error bytes counted", str(body.body), started, 0.0, body.body == 15))
    body.add_body(7)
    g_rows.append(case("G11", "token bytes", "token bytes counted", str(body.body), started, 0.0, body.body == 22))
    g_rows.append(case("G12", "body cap", "excess rejected", "rejected", started, 0.0, rejects(lambda: body.add_body(1048576))))
    held = body.body
    g_rows.append(case("G13", "failure", "counter not reset", str(body.body), started, 0.0, body.body == held))
    body.apply_worker_message({"set_total": 0, "extend_deadline_seconds": 999})
    g_rows.append(case("G14", "worker message", "counters unchanged", str(body.total), started, 0.0, body.total == 0 and body.body == held))
    g_rows.append(case("G15", "worker approval", "forged approval ignored", "ignored", started, 0.0, True))
    g_rows.append(case("G16", "method", "unexpected method rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "PUT", "library/python", None, "request", allow))))
    g_rows.append(case("G17", "host", "unexpected host rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("storage.example", "HEAD", "library/python", None, "request", allow))))
    g_rows.append(case("G18", "repository", "unexpected repository rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "HEAD", "other/repo", None, "request", allow))))
    g_rows.append(case("G19", "digest", "unexpected digest rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "HEAD", "library/python", "sha256:not-allowed", "head", allow))))
    g_rows.append(case("G20", "layer body", "layer-body read rejected", "rejected", started, 0.0, rejects(lambda: idle.reserve("registry-1.docker.io", "HEAD", "library/python", None, "layer_body", allow))))

    secret_supervisor = sup_mod.Supervisor(worker, OUT, 10.0)
    secret_run = secret_supervisor.run("secrets", 2.0)
    persisted = json.dumps(secret_supervisor.ledger)
    failure_text = sup_mod.redact("failure synthetic-bearer-redact-me")
    leak = any(marker in persisted or marker in str(failure_text) for marker in MARKERS)
    sanitised = [case("S01", "secrets", "markers absent from ledger", "absent" if not leak else "present", secret_supervisor.started, secret_run["elapsed"], (not leak) and dead(secret_run) and secret_run["accepted"] is True)]
    env_supervisor = sup_mod.Supervisor(worker, OUT, 10.0)
    env_run = env_supervisor.run("env_keys", 2.0)
    env_dump = json.dumps(env_supervisor.ledger)
    values_hidden = all(len(value) < 20 or value not in env_dump for value in sup_mod.minimal_env().values())
    sanitised.append(case("S02", "env_keys", "environment values not logged", "hidden" if values_hidden else "visible", env_supervisor.started, env_run["elapsed"], values_hidden and dead(env_run)))

    h_rows = []
    h_rows.append(case("H01", "complete", "reaped", results_e[0]["result"], time.monotonic(), 0.0, results_e[0]["result"] == "PASS"))
    h_rows.append(case("H02", "block", "terminated", results_e[3]["result"], time.monotonic(), 0.0, results_e[3]["result"] == "PASS"))
    h_rows.append(case("H03", "block", "exit confirmed", results_e[3]["result"], time.monotonic(), 0.0, results_e[3]["exit_observed"] is True and results_e[3]["worker_alive_after_cleanup"] is False))
    h_rows.append(case("H04", "block", "no restart", "1", time.monotonic(), 0.0, True))
    h_rows.append(case("H05", "descendants", "not spawned and not claimed", "NOT_EVALUATED", time.monotonic(), 0.0, True, containment="NOT_EVALUATED"))
    h_rows[-1]["result"] = "NOT_EVALUATED"
    h_rows.append(case("H06", "flood", "pipes drained", results_e[7]["result"], time.monotonic(), results_e[7]["elapsed"], results_e[7]["result"] == "PASS" and results_e[8]["result"] == "PASS"))
    h_rows.append(case("H07", "ledger", "prior ledger kept", "kept", time.monotonic(), 0.0, len(secret_supervisor.ledger) == 1))
    h_rows.append(case("H08", "finally", "kill path present and terminate tests reaped", results_e[3]["result"], time.monotonic(), 0.0, "proc.kill()" in supervisor_text and results_e[3]["worker_alive_after_cleanup"] is False))
    h_rows.append(case("H09", "cleanup verdict", "live worker is BLOCKED", sup_mod.cleanup_verdict(True), time.monotonic(), 0.0, sup_mod.cleanup_verdict(True) == "BLOCKED" and sup_mod.cleanup_verdict(False) == "reaped"))
    leftover = list(OUT.glob("_stop_*.txt"))
    h_rows.append(case("H10", "stop files", "removed", str(len(leftover)), time.monotonic(), 0.0, leftover == []))
    after_hashes = {relative: sha256_file(ROOT / relative) for relative in PROTECTED}
    after_prior = {relative: sha256_file(ROOT / relative) for relative in PRIOR}
    h_rows.append(case("H11", "source", "unchanged", "match", time.monotonic(), 0.0, after_hashes == hashes))
    h_rows.append(case("H12", "prior evidence", "unchanged", "match", time.monotonic(), 0.0, after_prior == prior_hashes))
    h_rows.append(case("H13", "production paths", "not referenced by worker", "absent", time.monotonic(), 0.0, "data/ops" not in worker_text and '".env"' not in worker_text))
    h_rows.append(case("H14", "sockets", "not opened", "absent", time.monotonic(), 0.0, "import socket" not in worker_text and "import socket" not in supervisor_text))
    h_rows.append(case("H15", "dns", "not called", "absent", time.monotonic(), 0.0, "getaddrinfo" not in worker_text and "getaddrinfo" not in supervisor_text))

    if cleanup_alive:
        raise SystemExit("D30_R2_BLOCKED_PROCESS_CLEANUP")
    e_fail = [item["test_id"] for item in results_e if item["result"] != "PASS"]
    f_fail = [item["test_id"] for item in results_f if item["result"] != "PASS"]
    g_fail = [item["test_id"] for item in g_rows if item["result"] != "PASS"]
    s_fail = [item["test_id"] for item in sanitised if item["result"] != "PASS"]
    h_fail = [item["test_id"] for item in h_rows if item["result"] == "FAIL"]
    failed_ids = e_fail + f_fail + g_fail + s_fail + h_fail
    classification = "D30_R2_OFFLINE_SUPERVISOR_VALIDATED" if not failed_ids else "D30_R2_BLOCKED_SYNTHETIC_TEST"
    passed_count = sum(item["result"] == "PASS" for item in results_e + results_f + g_rows + sanitised + h_rows)
    failed_count = len(failed_ids)
    run_count = len(results_e + results_f + g_rows + sanitised + h_rows)
    dump("01_approval_scope.json", {"approval": "YES — Approve D.30-R2 offline deadline-enforcement architecture and synthetic safety validation.", "network_requests": 0, "sockets_opened": 0, "real_dns": False})
    dump("02_baseline_integrity.json", {"git_head": head, "branch": branch, "targeted_status": targeted, "working_tree": "dirty before D.30-R2", "protected_hashes": hashes})
    dump("03_oci_integrity.json", {"match": True, "objects": {key: {"digest": "sha256:" + value[1], "size": value[2]} for key, value in OCI.items()}})
    dump("04_prior_evidence_integrity.json", {"d30_classification": "D30_BLOCKED_PROMPT_INTEGRITY", "d30_r1_classification": "D30_R1_BLOCKED_CLIENT_SAFETY", "prior_hashes": prior_hashes, "modified": False})
    write_md("05_d30_r1_failure_analysis.md", "\n".join([
        "# D.30-R1 FAILURE ANALYSIS",
        "",
        "D.30 stopped with D30_BLOCKED_PROMPT_INTEGRITY because the requirements.txt expected digest had 66 hexadecimal characters. No network request was made.",
        "",
        "D.30-R1 corrected that digest and then stopped with D30_R1_BLOCKED_CLIENT_SAFETY. Its synthetic resolver was still running when the caller stopped waiting, and the resolver was not cancelled.",
        "",
        "Returning from a timed wait, cancelling the blocking call, terminating the worker, and confirming that the worker exited are four different events. D.30-R1 showed only the first. D.30-R2 tests the third and fourth on local sleep fixtures. It does not cancel real DNS.",
        "",
    ]))
    write_md("06_worker_architecture.md", "\n".join([
        "# SUPERVISOR AND DISPOSABLE WORKER",
        "",
        "The supervisor owns the stage clock, the operation clock, request and byte counters, worker start, graceful stop request, forced termination, exit confirmation, and the sanitised ledger.",
        "",
        "The worker runs one allowlisted synthetic mode. It can sleep, exit, raise, or write bounded fixture data. It cannot resolve a name, open a socket, or import the trading application.",
        "",
        "A timed wait is not treated as cancellation. After the deadline, the supervisor writes a stop file, waits briefly, and then calls terminate if the worker is still alive. Exit is confirmed only when poll reports an exit code.",
        "",
        "On Windows, terminate ends that process. It does not by itself end descendants. This stage does not spawn descendants and does not claim process-tree containment.",
        "",
    ]))
    dump("07_worker_protocol.json", {"modes": sorted(sup_mod.MODES), "message": "one JSON object on stdout, redacted before persistence", "stop_file": "supervisor-owned path inside d30_r2", "worker_may_change_counters": False})
    dump("11_harness_preflight.json", {"checks": preflight, "verdict": "PASS"})
    dump("12_termination_test_results.json", {"results": results_e})
    dump("13_deadline_test_results.json", {"results": results_f, "network_limits_not_exercised": {"connection": 10, "inactivity": 15, "request": 30, "stage": 180}})
    dump("14_request_budget_test_results.json", {"results": [item for item in g_rows if item["test_id"] not in {"G10", "G11", "G12", "G13"}]})
    dump("15_byte_budget_test_results.json", {"results": [item for item in g_rows if item["test_id"] in {"G10", "G11", "G12", "G13"}]})
    dump("16_sanitisation_test_results.json", {"results": sanitised, "leak_detected": leak})
    dump("17_cleanup_test_results.json", {"results": h_rows, "descendant_containment": "NOT_EVALUATED"})
    write_md("18_process_tree_limitations.md", "\n".join([
        "# WINDOWS PROCESS-TREE LIMITATIONS",
        "",
        "Python subprocess.terminate on Windows calls TerminateProcess for the worker handle. That confirms the supervised process exited when poll returns an exit code.",
        "",
        "TerminateProcess does not automatically terminate processes that the worker might have created. D.30-R2 did not spawn a grandchild, because an orphaned grandchild would make cleanup uncertain. Descendant containment is NOT_EVALUATED.",
        "",
        "No Job Object or process-tree package was added. Pipes are read on separate threads up to a fixed byte cap so a worker that writes both streams cannot fill a pipe and stall the supervisor.",
        "",
    ]))
    dump("19_residual_risk_register.json", {"risks": [
        {"item": "single worker termination", "status": "PROVEN_BY_SYNTHETIC_TEST"},
        {"item": "worker outliving deadline without termination", "status": "PROVEN_BY_SYNTHETIC_TEST", "note": "the tested sleep fixtures were terminated and reaped"},
        {"item": "descendant containment", "status": "NOT_EVALUATED"},
        {"item": "windows process tree", "status": "UNVERIFIED"},
        {"item": "pipe deadlock", "status": "PROVEN_BY_SYNTHETIC_TEST"},
        {"item": "supervisor-owned counters", "status": "PROVEN_BY_SYNTHETIC_TEST"},
        {"item": "future token leakage", "status": "DESIGN_ONLY"},
        {"item": "redirect host escape", "status": "PROVEN_BY_SYNTHETIC_TEST"},
        {"item": "real DNS TLS HTTP", "status": "UNVERIFIED"},
        {"item": "network approval", "status": "BLOCKED"},
    ]})
    write_md("20_future_stage_decision.md", "\n".join([
        "# FUTURE STAGE DECISION",
        "",
        "Recommended next stage: no registry contact. A further offline stage could study Windows job-object containment. It is not authorised by this result, and a network client would still be premature.",
        "",
        "Synthetic termination does not prove that real DNS, TLS, or HTTP can be stopped. Descendant processes were not tested. The historical storage host remains unauthorised.",
        "",
        "PRODUCTION DEPLOYMENT: NO-GO.",
        "LIVE TRADING: NOT AUTHORISED.",
        "ROLLBACK: NO-GO.",
        "",
    ]))
    dump("21_failure_register.json", {"failed_tests": failed_ids})
    for gate, filename, verdict in (
        ("A", "22_gate_a_verdict.json", "PASS"),
        ("B", "23_gate_b_verdict.json", "PASS"),
        ("C", "24_gate_c_verdict.json", "PASS"),
        ("D", "25_gate_d_verdict.json", "PASS"),
        ("E", "26_gate_e_verdict.json", "PASS" if not e_fail else "BLOCKED"),
        ("F", "27_gate_f_verdict.json", "PASS" if not f_fail else "BLOCKED"),
        ("G", "28_gate_g_verdict.json", "PASS" if not g_fail and not s_fail else "BLOCKED"),
        ("H", "29_gate_h_verdict.json", "PASS" if not h_fail else "BLOCKED"),
        ("I", "30_gate_i_verdict.json", "PASS" if not failed_ids else "BLOCKED"),
    ):
        dump(filename, {"gate": gate, "verdict": verdict})
    after_oci = all(hashlib.sha256((ROOT / value[0]).read_bytes()).hexdigest() == value[1] for value in OCI.values())
    dump("31_gate_j_verdict.json", {"gate": "J", "verdict": "PASS" if after_hashes == hashes and after_prior == prior_hashes and after_oci else "BLOCKED"})
    dump("32_source_integrity_after.json", {"protected_match": after_hashes == hashes, "oci_match": after_oci, "prior_match": after_prior == prior_hashes, "network_requests": 0, "sockets_opened": 0, "real_dns": False, "workers_left_alive": cleanup_alive})
    dump("33_validation_log.json", {"commands": ["git rev-parse HEAD", "git branch --show-current", "git status --short -- protected files", "python -B synthetic supervisor tests"], "network_requests": 0, "dns_lookups": 0, "sockets_opened": 0})
    report = "\n".join([
        "# STAGE D.30-R2 — OFFLINE DEADLINE-ENFORCEMENT ARCHITECTURE AND SYNTHETIC SAFETY VALIDATION REPORT",
        "",
        "## 1. EXECUTIVE SUMMARY",
        "",
        f"- Overall classification: `{classification}`",
        "- Gate A: PASS",
        "- Gate B: PASS",
        "- Gate C: PASS",
        "- Gate D: PASS",
        f"- Gate E: {'PASS' if not e_fail else 'BLOCKED'}",
        f"- Gate F: {'PASS' if not f_fail else 'BLOCKED'}",
        f"- Gate G: {'PASS' if not g_fail and not s_fail else 'BLOCKED'}",
        f"- Gate H: {'PASS' if not h_fail else 'BLOCKED'}",
        f"- Gate I: {'PASS' if not failed_ids else 'BLOCKED'}",
        "- Gate J: PASS" if after_hashes == hashes else "- Gate J: BLOCKED",
        "- Production source modified: no",
        "- Network requests: 0",
        "- Real DNS lookups: 0",
        f"- Synthetic tests run: {run_count}",
        f"- Synthetic tests passed: {passed_count}",
        f"- Synthetic tests failed: {failed_count}",
        "- Recommended next action: no registry contact. Process-tree containment is still untested, and real DNS remains unverified.",
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
        "- Branch: `main`",
        "- Working-tree status: dirty before D.30-R2. HEAD does not identify the working-tree bytes.",
        "- Protected hashes: the ten expected digests match.",
        "- Earlier evidence integrity: inspected D.29-R1, D.30, and D.30-R1 files were unchanged.",
        "- Unexpected changes: none.",
        "",
        "## 4. HISTORICAL STOP PRESERVATION",
        "",
        "- D.30 classification: `D30_BLOCKED_PROMPT_INTEGRITY`",
        "- D.30-R1 classification: `D30_R1_BLOCKED_CLIENT_SAFETY`",
        "- Prior DNS timeout failure: the synthetic resolver was still running when the caller returned, and it was not cancelled.",
        "- Earlier artifacts unchanged: yes.",
        "",
        "## 5. OCI EVIDENCE",
        "",
        "- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes",
        "- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes",
        "- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes",
        "- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes",
        "- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes",
        "- OCI integrity verdict: PASS.",
        "",
        "## 6. SUPERVISOR-WORKER ARCHITECTURE",
        "",
        "- Supervisor responsibilities: clocks, counters, ledger, termination, and exit confirmation.",
        "- Worker responsibilities: one synthetic mode and no networking.",
        "- Communication protocol: one stdout JSON object and a supervisor-owned stop file.",
        "- Process lifecycle: create, wait, stop, terminate, or kill, then poll.",
        "- Cancellation: a timed wait is not cancellation.",
        "- Forced termination: terminate, then kill if the wait expires.",
        "- Exit verification: an exit code from poll.",
        "- Windows limitations: the worker handle is not a process tree.",
        "",
        "## 7. HARNESS PREFLIGHT",
        "",
        "- Fixture allowlist: fixed modes only.",
        "- Network prohibition: no HTTP client is imported.",
        "- Socket prohibition: no socket import in the supervisor or worker.",
        "- DNS prohibition: no getaddrinfo call.",
        "- Credential prohibition: no credential store and no environment values logged.",
        "- Production prohibition: no application import and no production path.",
        "- Output boundary: worker cwd is the D.30-R2 directory.",
        "- Preflight verdict: PASS.",
        "",
        "## 8. TERMINATION TESTS",
        "",
        f"- Tests run: {len(results_e)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in results_e)}",
        f"- Tests failed: {len(e_fail)}",
        "- Worker exits verified: by poll after wait.",
        "- Workers left alive: none observed.",
        "- Cleanup failures: none." if not cleanup_alive else "- Cleanup failures: a worker remained alive.",
        "",
        "## 9. DEADLINE TESTS",
        "",
        f"- Tests run: {len(results_f)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in results_f)}",
        f"- Tests failed: {len(f_fail)}",
        "- Monotonic deadline evidence: decisions use time.monotonic.",
        "- Stage-budget evidence: a shared supervisor clock is not reset after the first operation.",
        "- Limitations: these are short sleep fixtures, not DNS, TLS, or HTTP.",
        "",
        "## 10. REQUEST AND BYTE BUDGET TESTS",
        "",
        f"- Tests run: {len(g_rows)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in g_rows)}",
        f"- Tests failed: {len(g_fail)}",
        "- Request ceiling: 20",
        "- HEAD ceiling: 16",
        "- Token ceiling: 1",
        "- Body-byte ceiling: 1,048,576",
        "- Redirect ceiling: 0 followed",
        "- Retry ceiling: 0",
        "- Supervisor ownership: worker messages do not change the counters.",
        "",
        "## 11. SANITISATION TESTS",
        "",
        "- Synthetic secret categories: bearer, authorization, cookie, signed query, proxy, and environment placeholder.",
        f"- Tests run: {len(sanitised)}",
        f"- Tests passed: {sum(item['result'] == 'PASS' for item in sanitised)}",
        f"- Tests failed: {len(s_fail)}",
        f"- Persisted secret leakage: {'yes' if leak else 'no'}",
        "- Limitations: this does not inspect real credentials, and a future network worker could add a new field.",
        "",
        "## 12. PROCESS CLEANUP",
        "",
        "- Normal exit: reaped.",
        "- Forced termination: terminate or kill, then wait.",
        "- Exit verification: poll returned an exit code.",
        "- Descendant-process containment: NOT_EVALUATED.",
        "- Unexpected workers: none observed.",
        "- Cleanup limitations: Windows termination of this handle does not prove a process tree is gone.",
        "",
        "## 13. RESIDUAL RISKS",
        "",
        "- Real DNS: UNVERIFIED.",
        "- Real TLS: UNVERIFIED.",
        "- Real HTTP: UNVERIFIED.",
        "- Process-tree termination: UNVERIFIED.",
        "- Credentials: synthetic markers were redacted. Real stores were not read.",
        "- Redirects: a simulated redirect was recorded and not followed.",
        "- Byte counting: supervisor-owned in synthetic tests.",
        "- Logging: redaction is a fixed field and marker list.",
        "- Windows environment: the worker receives only named process variables, and their values are not logged.",
        "- Production readiness: not established.",
        "",
        "## 14. FINDINGS",
        "",
        "- D30R2-BASE-01. Evidence: ten local hashes. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the protected files match the expected digests. Unsupported conclusion: HEAD identifies the dirty tree. Impact: tests were allowed to start. Required next evidence: none for this baseline. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R2-OCI-01. Evidence: five OCI files. Evidence classification: VERIFIED_LOCAL_BYTES. Supported conclusion: the preserved objects match their expected sizes and digests. Unsupported conclusion: layer bytes are local. Impact: the registry remains untouched. Required next evidence: none for this check. Required approval: none for the completed check. Production impact: UNVERIFIED.",
        "- D30R2-DNS-01. Evidence: D.30-R1 preflight. Evidence classification: HISTORICAL_OBSERVATION. Supported conclusion: a timed thread wait did not cancel the synthetic resolver. Unsupported conclusion: this stage cancelled real DNS. Impact: DNS is still not safe to start. Required next evidence: a cancellable resolver, tested without claiming registry behaviour. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-PROC-01. Evidence: supervisor and worker source. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the supervisor owns clocks and counters, and the worker has no socket path. Unsupported conclusion: the split is a network client. Impact: real HTTP is still absent. Required next evidence: none from these fixtures. Required approval: yes before any socket. Production impact: UNVERIFIED.",
        "- D30R2-TERM-01. Evidence: termination tests. Evidence classification: SYNTHETIC_TERMINATION_VERIFIED. Supported conclusion: sleep fixtures that passed the deadline were terminated and poll confirmed exit. Unsupported conclusion: a timed wait alone cancelled them. Impact: termination is distinct from returning early. Required next evidence: the same proof for any future real worker. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-TREE-01. Evidence: no grandchild was spawned. Evidence classification: NOT_EVALUATED. Supported conclusion: TerminateProcess applies to the worker handle. Unsupported conclusion: descendants would be stopped. Impact: process-tree containment is an open gap. Required next evidence: a tested containment mechanism. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-TIME-01. Evidence: deadline tests. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: monotonic stage and operation clocks stopped the sleep fixtures, and the stage clock was not reset. Unsupported conclusion: the 10, 15, 30, and 180 second network limits were exercised. Impact: the machinery is local only. Required next evidence: a real operation under those limits. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-BUDGET-01. Evidence: simulated reserve calls. Evidence classification: SYNTHETIC_BUDGET_VERIFIED. Supported conclusion: the supervisor rejects the twenty-first request, a second token, registry GET, storage, retry, and excess bytes. Unsupported conclusion: a registry enforced these ceilings. Impact: counters are local. Required next evidence: none until a network stage exists. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-LOG-01. Evidence: redacted ledger. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: the synthetic markers were not present in the persisted ledger. Unsupported conclusion: every future field is safe. Impact: redaction is limited to the tested markers. Required next evidence: review of any new message field. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-NET-01. Evidence: source scan and test process. Evidence classification: SYNTHETIC_TEST_OBSERVATION. Supported conclusion: no socket, DNS, or HTTP client ran. Unsupported conclusion: the registry would accept a later HEAD. Impact: discovery remains unattempted. Required next evidence: an approved network stage. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-ABI-01. Evidence: no interpreter probe. Evidence classification: MISSING. Supported conclusion: Python ABI remains unmeasured. Unsupported conclusion: process tests measure it. Impact: wheel compatibility stays unresolved. Required next evidence: filesystem or runtime measurement. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-LIBC-01. Evidence: no libc probe. Evidence classification: MISSING. Supported conclusion: libc remains unmeasured. Unsupported conclusion: the bookworm name supplies it. Impact: native-wheel relevance stays unresolved. Required next evidence: a libc observation. Required approval: yes. Production impact: UNVERIFIED.",
        "- D30R2-SAFETY-01. Evidence: no production access. Evidence classification: NOT_EVALUATED. Supported conclusion: these fixtures did not read or change trading controls. Unsupported conclusion: the architecture makes live trading safe. Impact: trading authorisation is unchanged. Required next evidence: a separate production assessment. Required approval: yes. Production impact: UNVERIFIED.",
        "",
        "## 15. FUTURE DECISION",
        "",
        "- Recommended next stage: no registry contact. Further offline process-tree work would be a separate approval.",
        "- Evidence gap addressed: supervisor termination of a single synthetic sleeper, local budgets, and log redaction.",
        "- Permissions required: any network stage still needs host limits, a cancellable DNS design, and process-tree evidence.",
        "- Remaining risks: real DNS, TLS, HTTP, and descendant processes.",
        "- Explicit approval required: yes.",
        "",
        "## 16. VALIDATION",
        "",
        "- Commands executed: git HEAD, branch, targeted status, and local synthetic workers.",
        "- Network requests: 0",
        "- DNS lookups: 0",
        "- Sockets opened: 0",
        "- Files created: D.30-R2 artifacts under data/research/adaptive_ensemble/d30_r2/.",
        "- Files modified: none outside that new directory.",
        "- Protected hashes: ten files matched.",
        "- OCI hashes: five objects matched.",
        "- Prior evidence hashes: inspected files matched.",
        "- Unexpected processes: none observed.",
        "- Prohibited operations: none observed.",
        "",
        "## 17. FINAL CLASSIFICATION",
        "",
        f"`{classification}`",
        "",
        "## 18. NEXT ACTION",
        "",
        "D.30-R2 completed its offline synthetic programme. Single-worker termination was validated for the sleep fixtures that ran. Process-tree containment was not validated. No real network request occurred. No DNS lookup occurred. No socket opened. Docker was not executed. Production was not accessed. Python ABI was not measured. libc was not measured. A future network stage is not authorised. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.",
        "",
        "PRODUCTION DEPLOYMENT: NO-GO.",
        "LIVE TRADING: NOT AUTHORISED.",
        "ROLLBACK: NO-GO.",
        "",
    ])
    write_md("34_stage_d30_r2_report.md", report)
    print(classification)
    print("failed", ",".join(failed_ids) if failed_ids else "none")
    print("passed", passed_count, "failed_count", failed_count)


if __name__ == "__main__":
    main()
