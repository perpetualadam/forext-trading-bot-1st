"""Stage G.8 packaging tests. No Docker daemon and no broker calls."""

from __future__ import annotations

import json
from pathlib import Path

from forex_bot.research.adaptive_ensemble.g8_audit import (
    EXPECTED_MANIFEST,
    EXPECTED_MEMBERS,
    audit_snapshot,
)
from forex_bot.research.adaptive_ensemble.g8_dependencies import classify_unknowns
from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
    context_excluded,
    load_repo_rules,
    parse_dockerignore,
)

ROOT = Path(__file__).resolve().parents[1]


def test_independent_g7_snapshot_audit() -> None:
    report = audit_snapshot()
    assert report["classification"] == "SNAPSHOT_INDEPENDENTLY_VERIFIED"
    assert report["manifest_sha256"] == EXPECTED_MANIFEST
    assert report["archive_sha256"] != report["manifest_sha256"]
    assert report["member_count"] == EXPECTED_MEMBERS
    assert report["ordered"] is True
    assert report["missing"] == []
    assert report["unexpected"] == []
    assert report["duplicates"] == []
    assert report["unsafe_paths"] == []
    assert report["safety"]["provenance_v2"] is True
    assert report["safety"]["order_gate_before_create"] is True
    assert report["safety"]["protective_close"] is True
    assert report["safety"]["missing_candle_returns_before_position_block"] is True
    g8 = ROOT / "data" / "research" / "adaptive_ensemble" / "g8"
    g8.mkdir(parents=True, exist_ok=True)
    (g8 / "snapshot_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def test_unknown_modules_are_classified() -> None:
    report = classify_unknowns()
    assert report["previously_unknown"] == 86
    assert report["unresolved"] == []
    assert report["minimal_production_set_approved"] is False
    labels = {row["path"]: row["classification"] for row in report["rows"]}
    assert labels["forex_bot/decision_repair/harness.py"] == "TEST_ONLY"
    assert labels["forex_bot/live_safety_preflight.py"] == "OPTIONAL_OPERATIONAL_TOOL"
    assert labels["forex_bot/csv_ohlcv.py"] == "RESEARCH_ONLY"
    assert labels["forex_bot/oanda_candles_read.py"] == "RESEARCH_ONLY"
    assert labels["forex_bot/backtest.py"] == "RESEARCH_ONLY"
    assert labels["forex_bot/shadow/engine.py"] == "RESEARCH_ONLY"
    assert labels["forex_bot/decision_quality/engine.py"] == "RESEARCH_ONLY"
    assert "forex_bot/market_provenance.py" not in labels
    g8 = ROOT / "data" / "research" / "adaptive_ensemble" / "g8"
    g8.mkdir(parents=True, exist_ok=True)
    (g8 / "dependency_classification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_dockerignore_excludes_sensitive_context_and_keeps_production_source() -> None:
    rules = load_repo_rules(ROOT)
    excluded = [
        ".env",
        "nested/secret/.env",
        ".env.local",
        "config/id_rsa",
        "keys/server.pem",
        "keys/server.key",
        "credentials.json",
        "data/ops/live_safety_state.json",
        "data/research/adaptive_ensemble/g3/raw/EUR_USD/page_000.json",
        "data/research/adaptive_ensemble/g3/normalized/EUR_USD_M5.csv",
        "data/research/adaptive_ensemble/g7/source_snapshot.tar",
        "data/research/adaptive_ensemble/g4/data_quality_policy.json",
        "local.sqlite",
        "logs/bot.log",
        "backup/state.bak",
        ".venv/lib/python/site.py",
        "venv/bin/activate",
        ".git/config",
        ".git/objects/ab/cd",
        "forex_bot/__pycache__/app.cpython-312.pyc",
        "tests/test_g8_packaging.py",
        "forex_direction_audit_bundle.zip",
        "docker-compose.yml",
    ]
    for path in excluded:
        assert context_excluded(path, rules), path
        assert context_excluded(path.replace("/", "\\"), rules), path
    retained = [
        "main.py",
        "requirements.txt",
        "Dockerfile",
        ".env.example",
        "forex_bot/app.py",
        "forex_bot/live_safety.py",
        "forex_bot/market_provenance.py",
        "forex_bot/oanda_exec.py",
        "forex_bot/oanda_client.py",
        "forex_bot/bot_loop.py",
        "forex_bot/live_manage.py",
    ]
    for path in retained:
        assert not context_excluded(path, rules), path


def test_pattern_precedence_and_hidden_paths() -> None:
    rules = parse_dockerignore("*.log\n!keep.log\n/data\n")
    assert context_excluded("dir/error.log", rules) is True
    assert context_excluded("keep.log", rules) is False
    assert context_excluded("data/ops/live_safety_state.json", rules) is True
    assert context_excluded(".hidden/notes.log", rules) is True
    assert context_excluded("forex_bot/alias.py", rules) is False
