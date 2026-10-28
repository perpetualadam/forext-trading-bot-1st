# Existing client audit — source inspection only

No operational module was imported. No `.env`, actual token/environment value,
credential-manager secret or production credential file was read.

Source call graph:

- `forex_bot/bot_loop.py` / other consumers call the owner-client candle wrapper.
- `forex_bot/oanda_client.py::fetch_ohlcv` calls `get_api`, constructs
  `oandapyV20.endpoints.instruments.InstrumentsCandles(instrument, params)`, then
  `_oanda_request` and `API.request`. Defaults: M5, count 50, price MBA; incomplete
  candles are filtered from the returned frame.
- `fetch_ohlcv_range` uses the same SDK endpoint with from/to and price M. It
  chunks ranges and can make many requests; that loop is not reused here.
- `fetch_pricing_snapshot` constructs account-specific `PricingInfo`,
  `GET /v3/accounts/{accountID}/pricing`, with an instruments list. It is not a
  historical-candle substitute and is not imported by the adapter.
- No active `AccountInstruments` metadata request was found in the inspected
  repository call sites. Instrument normalization and rounding are local:
  `symbols.normalize_oanda_symbol`, `entry_geometry` precision, and
  `profit_protection.pip_size`. No metadata request was added to the one-shot budget.

`build_api` takes the existing configured token and creates the SDK API with
`Accept-Datetime-Format: RFC3339`; `_environment` selects fxTrade LIVE only when
`Config.TRADING_MODE == 'live'`, otherwise practice. `Config` declares
`OANDA_ACCESS_TOKEN`, falling back to `OANDA_API_KEY`; account ID is separate.
These are source-level names, not inspected values or verified credentials.

The installed `oandapyV20` 0.7.2 source decorates `InstrumentsCandles` with
`v3/instruments/{instrument}/candles` and inherits GET. It creates a general
`requests.Session`, capable of other SDK endpoints. It is not passed to research.

Connect/read timeouts default to 15/15 seconds and are supplied as request
parameters. `_oanda_request` defaults to six total attempts, including exponential
backoff for rate-limit, gateway and transport errors. Those retries, inherited
Session routing/redirect behaviour, shared account state and range pagination do
not meet the one-shot contract and are not reused.

Import boundary: `oanda_client` imports `Config`, whose module calls
`load_dotenv()` and evaluates credential getters. The existing read-only
`oanda_candles_read` helper also reaches configuration through
`history_cache -> session_rules -> read_scalp_windows -> Config`; its live
request function lazily imports `get_api`. Its schema is reusable; importing its
runtime graph is unnecessary here. No order/execution module is imported by the
new adapter, and no operational file changed.
