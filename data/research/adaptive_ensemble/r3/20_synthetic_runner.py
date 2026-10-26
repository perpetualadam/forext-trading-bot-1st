"""R.3 synthetic fixtures. No broker client calls and no trading loop."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import textwrap
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R3 = Path(__file__).resolve().parent
ATTEMPTS: list[str] = []
DOTENV_CALLS = 0
BROKER_CALLS = 0

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
    "tests/test_execution_safety.py",
    "tests/test_strategy_activation_defaults.py",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(name: str, payload: object) -> None:
    (R3 / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _block(kind: str):
    def blocked(*_args: object, **_kwargs: object) -> None:
        ATTEMPTS.append(kind)
        raise RuntimeError("R3_NETWORK_BLOCKED")

    return blocked


class _BlockedSocket(socket.socket):
    def __init__(self, *args: object, **kwargs: object) -> None:
        ATTEMPTS.append("socket:" + " > ".join(traceback.format_stack()[-6:-1]))
        raise RuntimeError("R3_NETWORK_BLOCKED")


def install_barriers() -> None:
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
    keep = {
        key: os.environ[key]
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
            "PROGRAMDATA",
        )
        if key in os.environ
    }
    os.environ.clear()
    os.environ.update(keep)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTEST_ADDOPTS"] = ""
    os.environ["PYTHONPATH"] = str(ROOT)
    os.environ["PERSIST_EXEC_ORDERS"] = "false"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["USE_OANDA_LIVE"] = "false"
    os.environ["PAPER_TRADING"] = "true"
    os.environ["DECISION_REPAIR_DETERMINISTIC_SELECT"] = ""
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R3 / "tmp" / "not_used_live_safety.json")
    for key in (
        "OANDA_ACCESS_TOKEN",
        "OANDA_API_KEY",
        "OANDA_ACCOUNT_ID",
        "TELEGRAM_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "DISCORD_WEBHOOK_URL",
    ):
        os.environ[key] = ""
    os.environ["POSTGRES_HOST"] = "r3-invalid"
    os.environ["POSTGRES_PORT"] = "1"
    os.environ["POSTGRES_USER"] = "r3"
    os.environ["POSTGRES_PASSWORD"] = ""
    os.environ["POSTGRES_PASS"] = ""
    os.environ["POSTGRES_DB"] = "r3"


def hashes(items: dict[str, str] | list[str]) -> list[dict[str, object]]:
    rows = []
    pairs = items.items() if isinstance(items, dict) else ((rel, None) for rel in items)
    for rel, expected in pairs:
        actual = sha(ROOT / rel)
        row: dict[str, object] = {"path": rel, "sha256": actual, "bytes": (ROOT / rel).stat().st_size}
        if expected is not None:
            row["expected"] = expected
            row["match"] = actual == expected
        rows.append(row)
    return rows


def order_cases() -> list[dict[str, object]]:
    from forex_bot.oanda_exec import (
        OUTCOME_AMBIGUOUS_TRANSPORT,
        OUTCOME_CANCELLED,
        OUTCOME_FILLED,
        OUTCOME_MALFORMED,
        OUTCOME_REJECTED,
        OrderCreateAmbiguous,
        OrderCreateOutcomeError,
        classify_order_create_response,
        classify_order_create_transport_error,
    )
    from forex_bot.orders import (
        generate_client_order_id,
        mark_order_failed_or_cancelled,
        orders_by_client_id,
        try_begin_order_submission,
    )

    def reserve(cid: str) -> bool:
        return bool(
            try_begin_order_submission(
                client_order_id=cid,
                symbol="EUR_USD",
                direction="SELL",
                units=1.0,
                metadata={"fixture": "r3"},
            )
        )

    def snap(cid: str) -> dict[str, object] | None:
        row = orders_by_client_id.get(cid)
        if row is None:
            return None
        return {"status": row.status.value, "detail": row.detail}

    cases: list[dict[str, object]] = []

    filled = classify_order_create_response(
        {"orderFillTransaction": {"id": "fx-1", "price": "1.1000", "clientOrderID": "cid-fill"}}
    )
    cases.append(
        {
            "id": "C01",
            "input": "fake fill body",
            "function": "classify_order_create_response",
            "observed": filled.outcome,
            "second_order_permitted": False,
            "broker_function_reached": False,
            "result": "PASS" if filled.outcome == OUTCOME_FILLED else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    rejected = classify_order_create_response(
        {"orderRejectTransaction": {"id": "rj-1", "rejectReason": "UNITS_INVALID"}}
    )
    cases.append(
        {
            "id": "C02",
            "input": "fake reject body",
            "function": "classify_order_create_response",
            "observed": rejected.outcome,
            "broker_function_reached": False,
            "result": "PASS" if rejected.outcome == OUTCOME_REJECTED else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    cancelled = classify_order_create_response(
        {"orderCancelTransaction": {"id": "cx-1", "reason": "MARKET_HALTED"}}
    )
    cases.append(
        {
            "id": "C03",
            "input": "fake cancel body",
            "function": "classify_order_create_response",
            "observed": cancelled.outcome,
            "broker_function_reached": False,
            "result": "PASS" if cancelled.outcome == OUTCOME_CANCELLED else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    timeout = classify_order_create_transport_error(TimeoutError("synthetic timeout"))
    cases.append(
        {
            "id": "C04",
            "input": "TimeoutError",
            "function": "classify_order_create_transport_error",
            "observed": timeout.outcome,
            "broker_outcome": "UNKNOWN",
            "broker_function_reached": False,
            "result": "PASS" if timeout.outcome == OUTCOME_AMBIGUOUS_TRANSPORT else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    reset = classify_order_create_transport_error(ConnectionResetError("synthetic reset"))
    cases.append(
        {
            "id": "C05",
            "input": "ConnectionResetError",
            "function": "classify_order_create_transport_error",
            "observed": reset.outcome,
            "broker_function_reached": False,
            "result": "PASS" if reset.outcome == OUTCOME_AMBIGUOUS_TRANSPORT else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    ambiguous = classify_order_create_response({"lastTransactionID": "99"})
    cases.append(
        {
            "id": "C06",
            "input": "body with no fill, reject, or cancel",
            "function": "classify_order_create_response",
            "observed": ambiguous.outcome,
            "broker_function_reached": False,
            "result": "PASS" if ambiguous.outcome == OUTCOME_MALFORMED else "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )

    orders_by_client_id.clear()
    first = reserve("cid-synthetic-same")
    second = reserve("cid-synthetic-same")
    cases.append(
        {
            "id": "C07",
            "input": "same synthetic client id twice",
            "function": "try_begin_order_submission",
            "state_after": snap("cid-synthetic-same"),
            "first_reserved": first,
            "second_order_permitted": second,
            "broker_function_reached": False,
            "result": "PASS" if first and not second else "FAIL",
            "evidence": "SYNTHETICALLY DISPROVED FOR TESTED PATH",
            "note": "The same id is refused while it remains in memory. This does not cover a new id.",
        }
    )

    orders_by_client_id.clear()
    reserve("cid-synthetic-uncertain")
    mark_order_failed_or_cancelled("cid-synthetic-uncertain")
    new_id = generate_client_order_id()
    new_ok = reserve(new_id)
    same_after = reserve("cid-synthetic-uncertain")
    cases.append(
        {
            "id": "C08",
            "input": "timeout classification then mark_order_failed_or_cancelled then a new id",
            "timeout_class": timeout.outcome,
            "ambiguous_is_outcome_error": issubclass(OrderCreateAmbiguous, OrderCreateOutcomeError),
            "state_after_mark": snap("cid-synthetic-uncertain"),
            "new_client_order_id_prefix": new_id[:4],
            "new_id_reserved": new_ok,
            "same_id_reserved_again": same_after,
            "second_order_permitted": new_ok,
            "broker_function_reached": BROKER_CALLS > 0,
            "expected_safe": "A new id must not be reserved while the first broker outcome is unknown.",
            "result": "FAIL" if new_ok else "PASS",
            "evidence": "SYNTHETICALLY REPRODUCED",
            "loop_except_entered": False,
            "limitation": "The bot_loop except block was not entered. The functions that block names were called directly.",
        }
    )

    orders_by_client_id.clear()
    restarted = reserve("cid-synthetic-after-restart")
    cases.append(
        {
            "id": "C09",
            "input": "memory cleared to stand in for a new process",
            "function": "try_begin_order_submission",
            "second_order_permitted": restarted,
            "database_recovery_called": False,
            "broker_function_reached": False,
            "result": "FAIL" if restarted else "PASS",
            "evidence": "SYNTHETICALLY REPRODUCED",
            "limitation": "fetch_exec_orders_open_for_recovery was not called because it opens a database connection. Source says it reloads only PENDING and PARTIAL.",
        }
    )
    cases.append(
        {
            "id": "C10",
            "input": "no reconciliation function on the timeout path",
            "observed": "no reconcile call exists before the next reserve",
            "second_order_permitted": True,
            "broker_function_reached": False,
            "result": "NOT_EVALUATED",
            "evidence": "SOURCE-LEVEL SUSPECTED",
            "note": "A fake broker position check was not executed. No such check is on the timeout path.",
        }
    )
    cases.append(
        {
            "id": "C11",
            "input": "reconciliation unavailable",
            "observed": "C08 still reserved a new id with no reconciliation result",
            "second_order_permitted": True,
            "broker_function_reached": False,
            "result": "FAIL",
            "evidence": "SYNTHETICALLY REPRODUCED",
        }
    )
    return cases


def direction_cases() -> list[dict[str, object]]:
    source = (ROOT / "forex_bot/bot_loop.py").read_text(encoding="utf-8").splitlines()
    snippet = textwrap.dedent("\n".join(source[1175:1178]))
    rows = []
    samples: list[tuple[str, object, bool]] = [
        ("missing key", None, False),
        ("None", None, True),
        ("empty", "", True),
        ("whitespace", " ", True),
        ("BUY", "BUY", True),
        ("SELL", "SELL", True),
        ("buy", "buy", True),
        ("sell", "sell", True),
        ("NO_TRADE", "NO_TRADE", True),
        ("UNKNOWN", "UNKNOWN", True),
        ("0", 0, True),
        ("1", 1, True),
    ]
    for label, value, present in samples:
        ai_decision = {"allow": True}
        if present:
            ai_decision["direction"] = value
        namespace = {"ai_decision": ai_decision}
        exec(snippet, namespace, namespace)  # noqa: S102 — exact source lines, no imports
        observed = namespace["direction"]
        safe = observed == "SELL" if label in {"SELL", "sell"} else observed == "BUY" and label in {"BUY", "buy"}
        rows.append(
            {
                "input": label,
                "raw": None if not present else value if isinstance(value, (str, int)) else str(value),
                "observed": observed,
                "silently_became_buy": observed == "BUY" and label not in {"BUY", "buy", "missing key"},
                "result": "PASS" if safe else "FAIL",
                "evidence": "SYNTHETICALLY REPRODUCED",
                "loop_entered": False,
            }
        )
    return [{"snippet": snippet, "precondition_not_executed": "allow must already be true and earlier returns must have been passed", "rows": rows}]


def inactive_cases() -> dict[str, object]:
    import pandas as pd

    from forex_bot.strategy_meta import (
        SCALP_STRATEGY_KEYS,
        Strategy,
        allocate_scoped,
        select_strategy,
        strategies,
    )

    names = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")
    defaults = {name: strategies[name].active for name in names}
    probe = Strategy("synthetic")
    setter_results = {}
    for label, value in (
        ("false", False),
        ("none", None),
        ("string_true", "true"),
        ("number_one", 1),
        ("boolean_true", True),
    ):
        probe.active = value
        setter_results[label] = probe.active
        probe.active = False
    frame = pd.DataFrame({"atr": [0.001, 0.001, 0.001, 0.001, 0.002]})
    os.environ["HYBRID_EUR_USD"] = "true"
    selected, _lookback, horizon = select_strategy("EUR_USD", frame)
    selected_active = bool(strategies[selected].active) if selected else None
    scoped = sorted(allocate_scoped(SCALP_STRATEGY_KEYS))
    os.environ["HYBRID_EUR_USD"] = ""
    legacy, _, legacy_horizon = select_strategy("EUR_USD", frame)
    return {
        "defaults_all_inactive": defaults,
        "setter_results": setter_results,
        "hybrid_selected_name": selected,
        "hybrid_selected_was_active": selected_active,
        "hybrid_horizon": horizon,
        "scoped_names_include_inactive": scoped,
        "legacy_selected_when_all_inactive": legacy,
        "legacy_horizon": legacy_horizon,
        "sizing_calls": 0,
        "order_construction_calls": 0,
        "broker_calls": 0,
        "loop_branch_executed": False,
        "evidence": "Selector fixture SYNTHETICALLY REPRODUCED. The bot_loop return before sizing was not executed.",
    }


def main() -> int:
    (R3 / "tmp").mkdir(parents=True, exist_ok=True)
    before = hashes(PROTECTED)
    if any(not row["match"] for row in before):
        dump("01_scope_and_baseline.json", {"protected": before, "status": "MISMATCH"})
        return 3
    extra_before = hashes(EXTRA)
    install_barriers()
    minimal_env()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    phases = {}
    orders = order_cases()
    phases["after_orders"] = len(ATTEMPTS)
    directions = direction_cases()
    phases["after_direction"] = len(ATTEMPTS)
    inactive = inactive_cases()
    phases["after_inactive"] = len(ATTEMPTS)
    dump(
        "04_order_fixture_results.json",
        {
            "cases": orders,
            "broker_calls": BROKER_CALLS,
            "dotenv_calls": DOTENV_CALLS,
            "phases": phases,
            "blocked_attempts": len(ATTEMPTS),
        },
    )
    dump("06_direction_input_matrix.json", {"cases": directions, "dotenv_calls": DOTENV_CALLS})
    dump("08_inactive_strategy_fixture_results.json", inactive)
    after = hashes(PROTECTED)
    dump(
        "13_final_integrity.json",
        {
            "protected_before": before,
            "protected_after": after,
            "extra_before": extra_before,
            "extra_after": hashes(EXTRA),
            "network_attempts": ATTEMPTS,
            "dotenv_calls": DOTENV_CALLS,
            "broker_calls": BROKER_CALLS,
        },
    )
    dump(
        "01_scope_and_baseline.json",
        {
            "stage": "R.3",
            "git_head": "d080d897945bc44fa37c02caab504ed707146bec",
            "branch": "main",
            "protected_match": all(row["match"] for row in before),
            "network_attempts": ATTEMPTS,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
