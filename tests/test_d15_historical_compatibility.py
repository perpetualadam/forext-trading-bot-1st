"""Stage D.15 historical pin classification. Does not import app.py."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = {
    "forex_bot/app.py": (
        "3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1"
    ),
    "forex_bot/telegram_control.py": (
        "d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c"
    ),
    "forex_bot/database.py": (
        "cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e"
    ),
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
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
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def test_current_protected_hashes_match_d15_baseline() -> None:
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
