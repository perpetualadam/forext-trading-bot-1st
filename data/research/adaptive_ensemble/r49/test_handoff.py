"""Synthetic tests for the R.49 handoff. No real secrets and no network."""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNNER_PATH = Path(__file__).resolve().parent / "handoff_runner.py"
SOURCE = RUNNER_PATH.read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("r49_handoff_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)

TOKEN = "SYNTHETIC-TOKEN-R49-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R49-NOT-REAL"


def test_source_is_isolated() -> None:
    for banned in (
        "forex_bot",
        "dotenv",
        "getenv",
        "oandapy",
        "requests",
        "urllib",
        "http.client",
        "socket",
        ".env",
    ):
        assert banned not in SOURCE
    assert runner.NETWORK_EXECUTION is False


def test_default_run_accepts_no_arguments_and_does_not_prompt() -> None:
    assert runner.main([]) == 0
    try:
        runner.main(["--token", TOKEN])
    except SystemExit:
        raise AssertionError("arguments were accepted")
    assert runner.main([TOKEN]) == 2
    completed = subprocess.run(
        [sys.executable, "-B", str(RUNNER_PATH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert TOKEN not in completed.stdout
    assert "Network gate is closed" in completed.stdout
    assert "credential prompt" in completed.stdout


def test_network_stays_closed_after_the_confirmation_phrase() -> None:
    calls: list[str] = []

    class Boom(socket.socket):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append("opened")
            raise AssertionError("connection opened")

    original = socket.socket
    socket.socket = Boom  # type: ignore[misc]
    try:
        try:
            runner.arm_network("no")
        except runner.InputRejected as exc:
            assert str(exc) == runner.REJECTED
        else:
            raise AssertionError("bad phrase")
        try:
            runner.arm_network(runner.PHASE_B_PHRASE)
        except runner.NetworkClosed as exc:
            assert str(exc) == runner.CLOSED
            assert TOKEN not in str(exc)
        else:
            raise AssertionError("network opened")
    finally:
        socket.socket = original
    assert calls == []


def test_hidden_input_rejects_empty_values_and_does_not_log_them() -> None:
    seen: list[str] = []

    def reader(label: str) -> str:
        seen.append(label)
        return TOKEN

    assert runner.prompt_hidden("account identifier: ", reader) == TOKEN
    assert seen == ["account identifier: "]
    for bad in ("", "  ", "token\n", "token\r"):
        try:
            runner.prompt_hidden("token: ", lambda _label, value=bad: value)
        except runner.InputRejected as exc:
            assert str(exc) == runner.REJECTED
            if bad:
                assert bad not in str(exc)
        else:
            raise AssertionError(bad)


def test_synthetic_session_redacts_secrets_and_keeps_conversion_sides() -> None:
    instruments = {
        "accountID": ACCOUNT,
        "instruments": [
            {
                "name": "EUR_USD",
                "type": "CURRENCY",
                "pipLocation": "-4",
                "displayPrecision": 5,
                "tradeUnitsPrecision": 0,
                "minimumTradeSize": "1",
                "marginRate": "0.03",
                "financing": {"longRate": "-0.02", "shortRate": "0.01"},
                "unexpected": TOKEN,
            }
        ],
    }
    prices = {
        "prices": [
            {
                "instrument": "EUR_USD",
                "time": "2026-10-21T18:00:00Z",
                "tradeable": True,
                "bids": [{"price": "1.10000", "liquidity": 1}],
                "asks": [{"price": "1.10020", "liquidity": 1}],
                "quoteHomeConversionFactors": {"positiveUnits": "0.80", "negativeUnits": "0.81"},
                "homeConversions": [{"currency": "USD", "accountGain": "0.74", "accountLoss": "0.75"}],
            }
        ]
    }
    document = runner.offline_session(ACCOUNT, TOKEN, instruments, prices)
    blob = json.dumps(document)
    assert ACCOUNT not in blob
    assert TOKEN not in blob
    assert "Bearer" not in blob
    assert "https://" not in blob
    assert document["instruments"][0]["pipLocation"] == "-4"
    factors = document["prices"][0]["quoteHomeConversionFactors"]
    assert factors["positiveUnits"] != factors["negativeUnits"]
    home = document["prices"][0]["homeConversions"][0]
    assert home["accountGain"] != home["accountLoss"]
    assert document["prices"][0]["spread_pips"] == "2"
    plan = document["planned_calls"]["pricing"]
    assert plan["method"] == "GET"
    assert plan["retries"] == 0
    assert plan["redirects"] is False
    assert plan["body"] is None
    assert plan["stream"] is False


def test_missing_input_and_bad_payloads_do_not_write() -> None:
    try:
        runner.offline_session("", TOKEN, {"instruments": []}, {"prices": []})
    except runner.InputRejected:
        pass
    else:
        raise AssertionError("empty account")
    try:
        runner.offline_session(ACCOUNT, TOKEN, {"nope": True}, {"prices": []})
    except Exception as exc:
        assert TOKEN not in str(exc)
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("bad payload")
    target = Path(__file__).resolve().parent / "should_not_exist.json"
    try:
        runner.write_sanitised(target, {"token": TOKEN}, (TOKEN,))
    except runner.InputRejected:
        pass
    else:
        raise AssertionError("leak written")
    assert not target.exists()
