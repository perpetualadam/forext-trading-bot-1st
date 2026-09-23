"""Research-only Trading Economics calendar downloader and PIT validator.

Does not import bot_loop, OANDA execution, or live strategy modules.
Makes no API calls unless an explicit --confirm path is invoked with a key.
"""

from forex_bot.decision_quality.trading_economics.schema import (
    FORECAST_FIELD,
    TE_FORECAST_FIELD,
    NormalizedEvent,
    normalize_record,
)
from forex_bot.decision_quality.trading_economics.surprise import SurpriseResult, surprise_raw
from forex_bot.decision_quality.trading_economics.validate import PitVerdict, validate_event_vintages

__all__ = [
    "FORECAST_FIELD",
    "TE_FORECAST_FIELD",
    "NormalizedEvent",
    "normalize_record",
    "SurpriseResult",
    "surprise_raw",
    "PitVerdict",
    "validate_event_vintages",
]
