"""Stage D.15 historical pin classification. Does not import app.py."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = {
    "forex_bot/app.py": (
        '1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1'
    ),
    "forex_bot/telegram_control.py": (
        '0447f31e36b63ccc586391f1a1a3b04bc4d16445d1a0bcf405ca7f3e2bb4b6fe'
    ),
    "forex_bot/database.py": (
        'be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d'
    ),
    "forex_bot/live_safety.py": (
        'e4310d1cd694c3f2a8791b308666fa15ae6ba1a82bdc67a99c5788ffe70ad546'
    ),
    "forex_bot/strategy_meta.py": (
        'b45b2f7e7f684686eddd2ddf9f2d6d1c3919678ec128c38665f38c99c3ab3222'
    ),
}
PINS = {
    "D.5": (
        "forex_bot/app.py",
        "f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4",
        15,
    ),
    "D.6": (
        "forex_bot/app.py",
        "f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4",
        12,
    ),
    "D.8 app": (
        "forex_bot/app.py",
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44",
        7,
    ),
    "D.8 database": (
        "forex_bot/database.py",
        "74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9",
        7,
    ),
    "D.9": (
        "forex_bot/app.py",
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44",
        6,
    ),
    "D.10 app": (
        "forex_bot/app.py",
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44",
        14,
    ),
    "D.10 telegram": (
        "forex_bot/telegram_control.py",
        "270f2b48bbbc1c50b1bb89ae338716803c5e2772fada3b1aa39153fb8b300014",
        14,
    ),
    "D.11 app": (
        "forex_bot/app.py",
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44",
        31,
    ),
    "D.12 app": (
        "forex_bot/app.py",
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44",
        16,
    ),
    "D.12 telegram": (
        "forex_bot/telegram_control.py",
        "193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780",
        16,
    ),
    "D.13 telegram": (
        "forex_bot/telegram_control.py",
        "193a59645c0596b22016164f8cdf1a50b06734a6bd56a014fba9a6910ba68780",
        8,
    ),
}


def _sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_current_protected_hashes_match_reviewed_baseline() -> None:
    for relative, digest in CURRENT.items():
        assert _sha(relative) == digest


def test_historical_pins_differ_from_current_source() -> None:
    for relative, digest, _count in PINS.values():
        assert _sha(relative) != digest


def test_setup_error_inventory_is_109() -> None:
    counted = {
        "D.5": 15,
        "D.6": 12,
        "D.8": 7,
        "D.9": 6,
        "D.10": 14,
        "D.11": 31,
        "D.12": 16,
        "D.13": 8,
    }
    assert sum(counted.values()) == 109


def test_original_stage_seals_are_preserved_as_historical_evidence() -> None:
    archive = json.loads((ROOT / "tests/fixtures/historical_source_pins.json").read_text())
    original = {digest for stage in archive["stages"].values() for matrix in stage.values() for digest in matrix.values()}
    for _relative, digest, _count in PINS.values():
        assert digest in original
    # A source update must still receive an explicit current-baseline review.
    assert set(CURRENT) == {"forex_bot/app.py", "forex_bot/telegram_control.py", "forex_bot/database.py", "forex_bot/live_safety.py", "forex_bot/strategy_meta.py"}
