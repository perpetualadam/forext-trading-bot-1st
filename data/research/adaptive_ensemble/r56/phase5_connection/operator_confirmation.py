"""Synthetic confirmation only. Agreeing here does not open a connection."""

from __future__ import annotations

SYNTHETIC_PHRASE = "SYNTHETIC OFFLINE CONFIRM"
_REQUIRED = (
    "Environment: OANDA LIVE",
    "Destination: api-fxtrade.oanda.com",
    "exactly two GET requests",
    "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF",
    "No orders or position changes.",
    "The supplied token may itself have trading permissions.",
    "The production bot must remain stopped.",
    "Sanitised log destination:",
    "Per-request deadline: 5 seconds.",
    "Session wall-clock deadline: 15 seconds.",
    "Maximum response: 1048576 bytes.",
    "does not authorise a real network connection.",
)


class ConfirmationRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def render_screen(*, log_destination: str) -> str:
    return "\n".join(
        (
            "Environment: OANDA LIVE",
            "Destination: api-fxtrade.oanda.com",
            "Requests: exactly two GET requests",
            "1. GET /v3/accounts/{accountID}/summary",
            "2. GET /v3/accounts/{accountID}/pricing",
            "Instruments: EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF",
            "No orders or position changes.",
            "The supplied token may itself have trading permissions.",
            "The production bot must remain stopped.",
            "Sanitised log destination: " + log_destination,
            "Per-request deadline: 5 seconds.",
            "Session wall-clock deadline: 15 seconds.",
            "Maximum response: 1048576 bytes.",
            "This confirmation does not authorise a real network connection.",
        )
    )


def confirm_synthetic(answer: str, *, screen: str) -> dict[str, object]:
    if not isinstance(screen, str) or any(part not in screen for part in _REQUIRED):
        raise ConfirmationRejected("SCREEN_INCOMPLETE")
    if answer != SYNTHETIC_PHRASE:
        raise ConfirmationRejected("CONFIRMATION_REJECTED")
    return {
        "confirmed": True,
        "network_permitted": False,
        "environment": "OANDA_LIVE",
        "data_source": "SYNTHETIC_TEST_ONLY",
    }


def confirm_live(*_args: object, **_kwargs: object) -> None:
    raise ConfirmationRejected("LIVE_CONFIRMATION_NOT_AUTHORISED")
