"""Offline build-context checks. No Docker daemon and no secret contents."""

from __future__ import annotations

from pathlib import Path

from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
    context_excluded,
    load_repo_rules,
)

RULES = load_repo_rules(Path(__file__).resolve().parents[1])


def test_credentials_and_data_are_excluded() -> None:
    assert context_excluded(".env", RULES)
    assert context_excluded(".env.local", RULES)
    assert context_excluded("secrets/id_rsa", RULES)
    assert context_excluded("data/ops/live_safety_state.json", RULES)
    assert context_excluded("data/research/adaptive_ensemble/g14/context_inventory.json", RULES)
    assert context_excluded(".git/config", RULES)
    assert context_excluded("tests/test_g14_context.py", RULES)


def test_env_backup_names_are_not_excluded() -> None:
    """Current policy excludes .env but not gitignored env-backup text files."""
    assert context_excluded(".env", RULES) is True
    assert context_excluded("main example .env backup.txt", RULES) is False
    assert context_excluded("# Copy to .env and fill in. docker.txt", RULES) is False


def test_allowlisted_runtime_sources_are_not_excluded() -> None:
    assert context_excluded("Dockerfile", RULES) is False
    assert context_excluded("requirements.txt", RULES) is False
    assert context_excluded("main.py", RULES) is False
    assert context_excluded("forex_bot/app.py", RULES) is False
    assert context_excluded("forex_bot/live_safety.py", RULES) is False
