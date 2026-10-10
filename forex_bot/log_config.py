"""Process logging so skip/info lines appear under uvicorn, not only ``python main.py``."""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_forex_bot_logging() -> None:
    """Attach an INFO stream handler to ``forex_bot`` if uvicorn left it silent."""
    global _CONFIGURED
    log = logging.getLogger("forex_bot")
    log.setLevel(logging.INFO)
    if _CONFIGURED:
        return
    has_stream = any(isinstance(h, logging.StreamHandler) for h in log.handlers)
    if not has_stream:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
    log.propagate = True
    _CONFIGURED = True
