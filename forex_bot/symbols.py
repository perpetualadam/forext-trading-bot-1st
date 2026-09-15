"""Canonical OANDA forex instrument names (BASE_QUOTE). Single parse path for Config.SYMBOLS."""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

# Default runtime universe when FOREX_SYMBOLS is unset/empty/all-invalid.
DEFAULT_FOREX_SYMBOLS: list[str] = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
]

# OANDA v20 InstrumentName for spot FX: three-letter base, underscore, three-letter quote.
_FOREX_SYMBOL_RE = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


def normalize_oanda_symbol(raw: str) -> str:
    """Uppercase BASE_QUOTE. Converts ``-`` / ``/`` to ``_``. Does not reverse currencies."""
    return (raw or "").strip().upper().replace("-", "_").replace("/", "_")


def is_valid_oanda_forex_symbol(symbol: str) -> bool:
    """True only for canonical ``AAA_BBB`` (already normalized)."""
    return bool(_FOREX_SYMBOL_RE.fullmatch(symbol or ""))


def quote_currency(symbol: str) -> str | None:
    """Quote side of ``BASE_QUOTE``, or None if the name is not canonical."""
    s = normalize_oanda_symbol(symbol)
    if not is_valid_oanda_forex_symbol(s):
        return None
    return s.split("_", 1)[1]


def parse_forex_symbols(raw: str | None = None) -> list[str]:
    """
    Parse a comma-separated FOREX_SYMBOLS string into a de-duplicated canonical list.

    - Normalizes each token (upper, ``/`` and ``-`` → ``_``).
    - Skips empty tokens and malformed names (logged); does not guess a reverse pair.
    - Duplicates keep the first occurrence.
    - Unset/blank/all-invalid → :data:`DEFAULT_FOREX_SYMBOLS`.
    """
    if raw is None:
        raw = os.getenv("FOREX_SYMBOLS")
    text = "" if raw is None else str(raw)
    if not text.strip():
        return list(DEFAULT_FOREX_SYMBOLS)

    out: list[str] = []
    seen: set[str] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        norm = normalize_oanda_symbol(token)
        if not is_valid_oanda_forex_symbol(norm):
            logger.warning(
                "FOREX_SYMBOLS: skip malformed %r (need canonical BASE_QUOTE, e.g. EUR_USD)",
                token,
            )
            continue
        if norm in seen:
            logger.info("FOREX_SYMBOLS: skip duplicate %s", norm)
            continue
        seen.add(norm)
        out.append(norm)
    if not out:
        logger.warning("FOREX_SYMBOLS: no valid symbols; using default universe")
        return list(DEFAULT_FOREX_SYMBOLS)
    return out


def configured_symbols() -> list[str]:
    """Authoritative runtime instrument universe."""
    return parse_forex_symbols(os.getenv("FOREX_SYMBOLS"))
