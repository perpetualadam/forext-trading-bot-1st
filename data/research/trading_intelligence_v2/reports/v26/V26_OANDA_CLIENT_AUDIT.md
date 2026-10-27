# V2.6 Oanda Client Audit

Read forex_bot/oanda_client.py as source only; never imported it.
Imports oandapyV20, pandas and forex_bot.config. Configuration optionally invokes
load_dotenv, so importing it is unsuitable for this isolated stage. No .env or
credential values were read. build_api selects live/practice from runtime config;
the standalone module does not inherit that selection.

fetch_ohlcv_range requests mid-only M candles, chunks by configured granularity,
drops duplicates then sorts, and returnsNone on request failure. These behaviours
cannot establish strict bid/ask provenance or coverage. Latest fetch_ohlcv uses
one candle request and can retain optional quote fields. The same API instance
and generic wrapper also support account summary/pricing reads. No write endpoint
is imported by the historical range function itself, but generic SDK/configuration
coupling makes direct reuse unsuitable for the narrow transport contract.

_oanda_request uses bounded retries for429/gateway/transport failures, jitter,
and the shared rate limiter. Defaults15s connection/read timeouts, configurable
500/5000 page sizes and shared10RPS are operational settings; none was changed.
The new implementation reuses validators and replay functions, not this client,
its account state, environment settings or operational execution adapter.

Production remains NO-GO.
