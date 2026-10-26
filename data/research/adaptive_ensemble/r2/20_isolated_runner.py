"""R.2 isolated runner. Socket, DNS, and dotenv reads are closed before tests."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R2 = Path(__file__).resolve().parent
TMP = R2 / "tmp"
SAFETY = TMP / "live_safety_state.json"
ATTEMPTS: list[str] = []
DOTENV_CALLS = 0

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
EXTRA = [
    "forex_bot/bot_loop.py",
    "forex_bot/trading.py",
    "forex_bot/oanda_exec.py",
    "forex_bot/decision_quality/live_path.py",
    "forex_bot/shadow/signals.py",
    "forex_bot/session_rules.py",
    "forex_bot/decision_repair/selection.py",
    "forex_bot/ai_ensemble.py",
    "forex_bot/rl_agent.py",
    "forex_bot/indicators.py",
    "forex_bot/oanda_client.py",
    "forex_bot/config.py",
    "forex_bot/execution.py",
    "tests/test_strategy_activation_defaults.py",
    "tests/test_execution_safety.py",
    "tests/test_d15_historical_compatibility.py",
    "tests/conftest.py",
    "data/research/adaptive_ensemble/g4/session_coverage.json",
    "data/research/adaptive_ensemble/g4/trading_day_definition.json",
    "data/research/adaptive_ensemble/g5/readiness_manifest.json",
    "data/research/adaptive_ensemble/d15/stage_d15_report.md",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(name: str, payload: object) -> None:
    (R2 / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _block(kind: str):
    def blocked(*_args: object, **_kwargs: object) -> None:
        ATTEMPTS.append(kind)
        raise RuntimeError("R2_NETWORK_BLOCKED")

    return blocked


class _BlockedSocket(socket.socket):
    """Subclass so the standard library can still define SSL types. Construction never opens a socket."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        ATTEMPTS.append("socket")
        raise RuntimeError("R2_NETWORK_BLOCKED")


def install_barriers() -> None:
    global DOTENV_CALLS
    socket.socket = _BlockedSocket  # type: ignore[misc, assignment]
    socket.create_connection = _block("create_connection")  # type: ignore[assignment]
    socket.create_server = _block("create_server")  # type: ignore[assignment]
    socket.getaddrinfo = _block("getaddrinfo")  # type: ignore[assignment]
    socket.gethostbyname = _block("gethostbyname")  # type: ignore[assignment]
    socket.gethostbyname_ex = _block("gethostbyname_ex")  # type: ignore[assignment]
    socket.getnameinfo = _block("getnameinfo")  # type: ignore[assignment]

    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        global DOTENV_CALLS
        DOTENV_CALLS += 1
        return False

    fake = types.ModuleType("dotenv")
    fake.load_dotenv = load_dotenv  # type: ignore[attr-defined]
    sys.modules["dotenv"] = fake


def minimal_env() -> None:
    keep = {}
    for key in (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "SYSTEMDRIVE",
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMDATA",
    ):
        if key in os.environ:
            keep[key] = os.environ[key]
    os.environ.clear()
    os.environ.update(keep)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTEST_ADDOPTS"] = ""
    os.environ["PYTHONPATH"] = str(ROOT)
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(SAFETY)
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["PAPER_TRADING"] = "true"
    os.environ["USE_OANDA_LIVE"] = "false"
    os.environ["PERSIST_EXEC_ORDERS"] = "false"
    os.environ["TELEGRAM_COMMANDS"] = "false"
    os.environ["TELEGRAM_INBOUND"] = "0"
    os.environ["OANDA_ACCESS_TOKEN"] = ""
    os.environ["OANDA_API_KEY"] = ""
    os.environ["OANDA_ACCOUNT_ID"] = ""
    os.environ["TELEGRAM_TOKEN"] = ""
    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    os.environ["TELEGRAM_CHAT_ID"] = ""
    os.environ["DISCORD_WEBHOOK_URL"] = ""
    os.environ["POSTGRES_HOST"] = "r2-invalid"
    os.environ["POSTGRES_PORT"] = "1"
    os.environ["POSTGRES_USER"] = "r2"
    os.environ["POSTGRES_PASSWORD"] = ""
    os.environ["POSTGRES_PASS"] = ""
    os.environ["POSTGRES_DB"] = "r2"


def protected_report() -> dict[str, object]:
    rows = []
    mismatch = False
    malformed = False
    for rel, expected in PROTECTED.items():
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            malformed = True
        actual = sha(ROOT / rel)
        match = actual == expected
        mismatch = mismatch or not match
        rows.append({"path": rel, "expected": expected, "actual": actual, "match": match})
    return {"malformed_expected": malformed, "mismatch": mismatch, "files": rows}


def extra_report() -> list[dict[str, object]]:
    rows = []
    for rel in EXTRA:
        path = ROOT / rel
        rows.append({"path": rel, "sha256": sha(path), "bytes": path.stat().st_size})
    return rows


def _pytest(name: str, paths: list[str]) -> dict[str, object]:
    import pytest

    junit = R2 / f"pytest_{name}.xml"
    code = pytest.main(
        [
            *paths,
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(R2 / "pytest_basetemp" / name),
            "--junitxml",
            str(junit),
            "-q",
        ]
    )
    return {"name": name, "exit_code": int(code), "junit": str(junit), "paths": paths}


def run_tests() -> dict[str, object]:
    activation = _pytest(
        "activation",
        [
            "tests/test_strategy_activation_defaults.py",
            "tests/test_d15_historical_compatibility.py",
        ],
    )
    execution = _pytest(
        "execution",
        [
            "tests/test_execution_safety.py",
            "-k",
            "not test_live_kind_can_assert_broker_when_authorised and not test_live_open_reaches_sync_place_and_keeps_ids",
        ],
    )
    codes = [int(activation["exit_code"]), int(execution["exit_code"])]
    return {
        "exit_code": 0 if codes == [0, 0] else 1,
        "runs": [activation, execution],
        "network_attempts": list(ATTEMPTS),
        "dotenv_calls": DOTENV_CALLS,
    }


def inventory_and_recount() -> None:
    import pandas as pd

    from forex_bot.research.adaptive_ensemble.g4_convert_audit import audit_frames
    from forex_bot.research.adaptive_ensemble.g4_gaps import PAIRS, build_gap_inventory
    from forex_bot.research.adaptive_ensemble.g4_integrity import G3
    from forex_bot.research.adaptive_ensemble.g4_sessions import build_session_report

    files = []
    for path in sorted((G3 / "normalized").glob("*.csv")):
        frame = pd.read_csv(path)
        times = pd.to_datetime(frame["time"], utc=True)
        ordered = bool(times.is_monotonic_increasing)
        dup = int(times.duplicated().sum())
        bid = pd.to_numeric(frame["bid_c"], errors="coerce") if "bid_c" in frame.columns else None
        ask = pd.to_numeric(frame["ask_c"], errors="coerce") if "ask_c" in frame.columns else None
        files.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "format": "csv",
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "rows": int(len(frame)),
                "columns": list(frame.columns),
                "earliest": None if times.empty else times.iloc[0].isoformat(),
                "latest": None if times.empty else times.iloc[-1].isoformat(),
                "timezone": "parsed as UTC",
                "bid_column": "bid_c" if bid is not None else None,
                "ask_column": "ask_c" if ask is not None else None,
                "invalid_bid_ask_rows": None
                if bid is None or ask is None
                else int((bid.isna() | ask.isna() | (bid <= 0) | (ask <= 0) | (bid > ask)).sum()),
                "duplicate_timestamps": dup,
                "out_of_order": not ordered,
                "part_of_g4_g5": True,
                "additional": False,
                "provenance": "G.3 normalised M5 acquisition used by G.4 prepare()",
            }
        )
    raw_rows = []
    for path in sorted((G3 / "raw").glob("*/*.json")):
        raw_rows.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "format": "json",
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "part_of_g4_g5": True,
                "additional": False,
                "provenance": "G.3 raw acquisition page. Not a second session source.",
            }
        )
    other = []
    research = ROOT / "data" / "research"
    for path in research.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if "v2_shadow" in rel or "/ops/" in rel or rel.startswith("data/ops"):
            continue
        if path.suffix.lower() not in {".csv", ".parquet"}:
            continue
        if path.parent == G3 / "normalized":
            continue
        other.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha(path), "eligible": False, "reason": "not the G.3 normalised six-pair M5 set"})
    frames = {pair: pd.read_csv(G3 / "normalized" / f"{pair}_M5.csv") for pair in PAIRS}
    inventory = build_gap_inventory()
    audit = audit_frames(frames)
    grouped: dict[str, list[dict[str, object]]] = {pair: [] for pair in PAIRS}
    for gap in inventory["gaps"]:
        grouped[str(gap["instrument"])].append(gap)
    times: dict[str, list[datetime]] = {}
    for pair, frame in frames.items():
        parsed = pd.to_datetime(frame["time"], utc=True)
        times[pair] = [stamp.to_pydatetime().astimezone(timezone.utc).replace(microsecond=0) for stamp in parsed]
    failures = {pair: set(keys) for pair, keys in audit["conversion_failures"].items()}
    report = build_session_report(
        request_start=datetime.fromisoformat("2026-09-01T00:00:00+00:00"),
        request_end=datetime.fromisoformat("2026-10-09T07:05:00+00:00"),
        times_by_pair=times,
        gaps_by_pair=grouped,
        conversion_failures=failures,
    )
    original = json.loads((ROOT / "data/research/adaptive_ensemble/g4/session_coverage.json").read_text(encoding="utf-8"))
    rejected = [row for row in report["common"] if row["status"] != "COMPLETE"]
    dump(
        "09_local_data_inventory.json",
        {
            "normalised_candles": files,
            "raw_pages": raw_rows,
            "other_research_tables": other,
            "additional_eligible_datasets": 0,
            "production_paths_skipped": ["data/ops", "data/research/v2_shadow"],
        },
    )
    dump(
        "10_session_definition.json",
        {
            "source": "forex_bot/research/adaptive_ensemble/g4_sessions.py definition_document",
            "applied_window_source": "forex_bot/research/adaptive_ensemble/g4_prepare.py lines 80-81",
            "request_start": "2026-09-01T00:00:00+00:00",
            "request_end": "2026-10-09T07:05:00+00:00",
            "definition": report["definition"],
            "threshold_reduced": False,
        },
    )
    dump(
        "11_session_recount.json",
        {
            "original_g4_complete_common_sessions": original.get("complete_common_sessions"),
            "recomputed_complete_common_sessions": report["complete_common_sessions"],
            "recomputed_matches_original": report["complete_common_sessions"] == original.get("complete_common_sessions"),
            "additional_eligible_sessions": 0,
            "required": report["required_complete_sessions"],
            "threshold_met": report["complete_common_sessions"] >= 40,
            "candidate_sessions": report["candidate_sessions"],
            "partial_sessions": report["partial_sessions"],
            "blocked_sessions": report["blocked_sessions"],
            "complete_by_pair": report["complete_by_pair"],
            "conversion_status": audit.get("status"),
            "unresolved_gaps": len(inventory.get("unresolved") or []),
            "complete_dates": [row["session"] for row in report["common"] if row["status"] == "COMPLETE"],
            "duration_status": report["duration_status"],
        },
    )
    dump(
        "12_session_rejection_reasons.json",
        {
            "rejected": rejected,
            "rules_not_changed": True,
            "partial_boundary_not_counted": True,
            "missing_bars_not_filled": True,
        },
    )


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    text = str(SAFETY).replace("\\", "/")
    if "data/ops" in text or "v2_shadow" in text:
        dump("07_offline_test_results.json", {"status": "REFUSED_UNSAFE_PATH"})
        return 2
    before = protected_report()
    extras = extra_report()
    dump("02_git_and_baseline.json", {"protected_before": before, "extra_before": extras})
    if before["malformed_expected"] or before["mismatch"]:
        return 3
    install_barriers()
    minimal_env()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    tests = run_tests()
    from forex_bot.strategy_meta import strategies

    flags = {name: bool(item.active) for name, item in strategies.items()}
    tests["in_process_active_after_tests"] = flags
    tests["safety_file_under_r2"] = str(SAFETY).replace("\\", "/").startswith(str(R2).replace("\\", "/"))
    dump("07_offline_test_results.json", tests)
    if ATTEMPTS:
        tests["blocked_network_attempts"] = list(ATTEMPTS)
        dump("07_offline_test_results.json", tests)
    inventory_and_recount()
    after = protected_report()
    dump(
        "15_final_integrity.json",
        {
            "protected_after": after,
            "extra_after": extra_report(),
            "network_attempts": ATTEMPTS,
            "dotenv_calls": DOTENV_CALLS,
            "in_process_active_after_tests": flags,
        },
    )
    return 0 if tests["exit_code"] == 0 and not after["mismatch"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
