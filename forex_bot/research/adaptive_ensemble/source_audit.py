"""Read-only documentation of configured data sources. Does not call brokers."""

from __future__ import annotations

from typing import Any

DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL = "DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL"

PROPOSED_CANDLE_REQUEST = {
    "method": "GET",
    "path": "/v3/instruments/{instrument}/candles",
    "helper": "forex_bot.oanda_candles_read.live_instruments_candles_request",
    "params": {
        "granularity": "M5",
        "price": "MBA",
        "from": "2026-08-31T23:50:00.000000000Z",
        "to": "BOUNDED_OPERATOR_CHOSEN_UTC_END",
    },
    "instruments": ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"],
    "purpose": "completed M5 bid/ask OHLC after Stage E/G window for later independent validation",
    "not_requested": [
        "POST orders",
        "PUT/PATCH trades",
        "account configuration",
        "position close",
        "order cancel/replace",
    ],
    "pagination": "from/to windows; OANDA_MAX_CANDLES_PER_REQUEST example 5000, helper default delay 0.6s/page",
    "rate_limit": "process-wide oanda_rate_limit default 10 rps, official ceiling 120 rps",
    "completion": "parse_candles_payload keeps complete=true candles only",
    "invoked_in_g2": False,
}


def source_audit() -> dict[str, Any]:
    return {
        "label": "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE",
        "broker_api_calls_made": False,
        "credentials_read": False,
        "credential_environment_verified": False,
        "credential_environment_reason": (
            "Practice vs live cannot be verified without reading secret token/account values; not attempted."
        ),
        "sources": [
            {
                "class": "local_files_already_present",
                "path": "data/historical/*_M5.csv",
                "independent": False,
            },
            {
                "class": "configured_broker_market_data",
                "endpoint": "GET /v3/instruments/{instrument}/candles",
                "http_method": "GET",
                "demonstrably_order_mutating": False,
                "can_alter_account_state": "not_demonstrated_in_helper; helper constructs InstrumentsCandles only",
                "auth_required": True,
                "shared_with_production": "UNKNOWN_without_reading_secrets",
                "practice_or_live": "UNKNOWN_without_reading_secrets",
                "bid_ask": "price=MBA requests mid+bid+ask when the account is entitled",
                "status": DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
                "read_only_guarantee": (
                    "Helper uses oandapyV20 InstrumentsCandles. This stage does not treat GET as "
                    "automatically safe. No request was sent."
                ),
                "remaining_concerns": [
                    "Token may be live or practice and is likely the production bot token.",
                    "Rate limiter is process-wide and shared with order paths if called in-process.",
                    "Must not be invoked from the live bot container.",
                ],
            },
        ],
        "public_credential_free_source": [],
        "approval_required": True,
        "proposed_request_if_approved": PROPOSED_CANDLE_REQUEST,
        "status": DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
    }
