"""Exact V2.6 transport adapter, currently synthetic-only pending evidence review.

The three-retry multi-batch downloader is not used by the one-shot worker.
This adapter fixes attempts=1 and calls request() with the reviewed literal UTC
parameters; candles() would reformat them. No real transport factory is exposed.
"""
from .oneshot import SPEC,request_guard
from .oanda_history_transport import CandleTransport


def fetch_fixture_once(sender):
    request_guard(**SPEC)
    transport=CandleTransport(environment='live',sender=sender,attempts=1)
    return transport.request(**SPEC)
