"""Research-only official BLS first-print CPI / Employment Situation dataset.

Does not import bot_loop, OANDA execution, or live strategy modules.
Does not scrape consensus or commercial calendars.
"""

from forex_bot.decision_quality.macro_first_print.parse_cpi import parse_cpi_release
from forex_bot.decision_quality.macro_first_print.parse_empsit import parse_empsit_release
from forex_bot.decision_quality.macro_first_print.schema import NormalizedEvent
from forex_bot.decision_quality.macro_first_print.validate import first_prints_immutable

__all__ = [
    "NormalizedEvent",
    "parse_cpi_release",
    "parse_empsit_release",
    "first_prints_immutable",
]
