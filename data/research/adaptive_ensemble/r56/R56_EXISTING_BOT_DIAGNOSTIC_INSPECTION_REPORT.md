# R.56 existing bot diagnostic inspection

Static source inspection only. The bot was not started. No OANDA call was made. No credential file was opened. No existing source file was modified.

`DATA_ONLY_MODE_NOT_PROVEN_SAFE`

## A. Executive summary

The production process can reuse its existing `oandapyV20` client in `forex_bot/oanda_client.py`. `main.py` does not use the R.55 research connector.

That client already requests account summary, pricing, and candles. It does not request the instruments catalogue, so pip location and display precision are not API fields in the operational parse. The pricing request does not set `includeHomeConversions=true`, so home-conversion factors are not captured. Financing is not read by the operational client.

There is no proven data-only mode. `EXECUTION_MODE=paper` blocks broker submission inside `assert_broker_order_allowed`, but `paper_broker` and `live_broker` still allow account-changing calls. A live-tagged position can reach `PositionClose`. The current new-order tail returns before `OrderCreate`, and the newer production adapter also returns before that call, but both functions remain in the running process. Starting `main.py` also starts the bot loop, reconciliation, and HTTP routes that rebuild the client.

Diagnostic logs can be added around existing parses without changing strategy maths, provided the patch does not alter request parameters or order decisions. That patch is not authorised by this stage.

The smallest next step is independent review of this report. After a separate authorisation, add structured logs at the existing summary and pricing parsers and at the sizing call, and keep `OrderCreate` and `PositionClose` unreachable from any diagnostic entry. Do not start `main.py` to collect the data.

## B. Operational architecture

### Entry

| Role | Location |
| --- | --- |
| Process start | `main.py` `if __name__` lines 19–25. It calls `uvicorn.run("forex_bot.app:app", host="0.0.0.0", port=8000)`. |
| Application lifespan | `forex_bot/app.py` `lifespan` line 660, which calls `initialise_application` with `_production_startup_ports` line 542. |
| Broker client build | `init_broker` lines 582–583 calls `build_api`. |
| Startup reads | `init_market_data` lines 585–596 calls `fetch_account_summary` and `run_reconciliation_once` on threads. |
| Trading task | `schedule_trading` lines 618–633 starts `reconciliation_loop`, `health_snapshot_loop`, `telegram_inbound_loop`, and `run_bot`. |

`run_bot` is `forex_bot/bot_loop.py` line 4402. Each cycle calls `fetch_account_summary` (line 4408), `_refresh_pricing_snapshot` (line 4409), then `_cycle_symbols` (line 4410), then sleeps `Config.TRADE_INTERVAL` (line 4429). That interval is 60 seconds at `forex_bot/config.py` line 49.

`_cycle_symbols` (line 693) calls `evaluate` (line 713). With no injected dependencies, `evaluate` calls `_evaluate_impl` (line 733). That is the operational signal, sizing, and execution path. `dispatch_production_iteration` (line 4391) is a separate boundary and is not what `run_bot` calls.

### Client construction

One module-level client lives in `forex_bot/oanda_client.py`.

- `_environment` lines 55–57: `Config.TRADING_MODE == "live"` selects `live`, otherwise `practice`.
- `official_rest_host` lines 60–64: `https://api-fxtrade.oanda.com` or `https://api-fxpractice.oanda.com`.
- `build_api` lines 104–126: constructs `oandapyV20.API` from `Config.OANDA_ACCESS_TOKEN`. The token value is not recorded here.
- `get_api` lines 129–132: reuses that client.
- `oanda_exec._access_token` lines 109–110 and `_account_id` lines 113–114 read the same environment names. They do not build a second client.
- `forex_bot/oanda_candles_read.py` `live_instruments_candles_request` lines 120–131 also uses `get_api`. Historical download code, not the `run_bot` cycle.
- `forex_bot/research/adaptive_ensemble/oanda_readonly.py` is a separate research client. `main.py` does not start it.

`_apply_trading_mode` in `forex_bot/app.py` lines 836–843 switches the host and calls `build_api` again. `GET /set_mode` is line 856. `POST /set_mode` is line 862. That changes where later requests go. It does not by itself submit an order.

### Request path

Most reads go through `_oanda_request` (`forex_bot/oanda_client.py` lines 291–321): rate-limit slot, then `api.request`, with retries on errors classified as transient.

`OrderCreate` and `PositionClose` call `api.request` directly in `forex_bot/oanda_exec.py` lines 430 and 510. They do not use `_oanda_request`, so they do not use that retry loop.

### Signal, size, and execution

`_evaluate_impl` loads M5 candles, manages an open position, or continues into strategy, AI, RL, and sizing. Sizing for a new entry is `position_sizing` then `cap_position_units` at lines 1428–1432. The broker-open branch starts at line 1597. At lines 1704–1706 the current source logs `legacy broker tail is not a dispatch path` and returns. The `execute_oanda_market_open` call is not on that path.

`production_execution_adapter` (`bot_loop.py` lines 3103–3163) does contain `execute_oanda_market_open` at line 3154. `production_adapter_refusal` (line 2830) returns a refusal string on every branch, including the final `production_authority_unavailable` at line 2923. The shared iteration also returns `production_execution_adapter_withheld` at lines 4196–4206 when `dependencies.simulation` is false. `run_bot` does not call that iteration.

Close is different. `_evaluate_impl` lines 1058–1072 calls `trading.execute_trade`. When `execution_kind == "live"`, `execute_trade` (`trading.py` lines 391–398) calls `execute_oanda_market_close`.

### Logs and background work

Operational logs are `logging` plus `alert`. `redact_log_text` (`forex_bot/log_redact.py` lines 47–58) masks bearer text and known configured secrets before some error strings. Account summary and pricing success logs are plain text, not structured JSON.

Background work started with the process:

- `reconciliation_loop`, `app.py` line 158, default every 60 seconds.
- `health_snapshot_loop`, line 173.
- `telegram_inbound_loop`, started at line 632.
- `run_bot`, line 633.

No APScheduler calendar was found on this path. The loops are asyncio tasks inside the uvicorn process.

## C. OANDA endpoint inventory

Confirmed operational paths are those reachable from `main.py` / `run_bot` / reconciliation / the execution helpers they call. Research-only callers are marked.

| Source | Method | Path pattern | Purpose | Invocation | Response handling | Existing logging | Missing evidence | Trading risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `oanda_client.py` `fetch_account_summary` lines 140–194. Request object line 154. | GET | `/v3/accounts/{accountID}/summary` | Account summary | Startup `app.py` 590; every `run_bot` cycle line 4408 | `account_core` then fields copied at lines 168–183 | Text line 185: environment, NAV, currency, balance, margin available, host | Account type, financing, full margin set, raw id is stored in memory and must not be logged | Read |
| `oanda_client.py` `fetch_pricing_snapshot` lines 503–584. Request line 542. | GET | `/v3/accounts/{accountID}/pricing` | Bid, ask, closeout, tradeable, time | Every cycle via `_refresh_pricing_snapshot` lines 434–443; also `entry_geometry.fetch_entry_pricing` line 393 before the legacy open return | First bid and ask, lines 557–575, into `ManageQuote` | Error line 546. Success values are not written as one JSON record | `quoteHomeConversionFactors` and `homeConversions` are not requested. Query is only `instruments` | Read |
| `oanda_client.py` `fetch_ohlcv` lines 425–488. Request line 443. | GET | `/v3/instruments/{instrument}/candles` | Latest M5 mid, bid, and ask bars | `_load_decision_candles` lines 597–606, called from `_evaluate_impl` line 736 | Rows built at lines 449–482 | Error line 447 | Pip location, financing, tradeable flag on the candle route | Read |
| `oanda_client.py` `fetch_ohlcv_range` lines 324–413. Request line 367. | GET | `/v3/instruments/{instrument}/candles` | Historical mid candles | `backtest.py` line 462. Not the `run_bot` cycle | Frame at lines 387–413 | Error line 371 | Same candle limits | Read. Backtest only if that script is run |
| `oanda_candles_read.py` `live_instruments_candles_request` lines 120–131 | GET | `/v3/instruments/{instrument}/candles` | Paged historical candles | Research download helper. Not called by `run_bot` | Caller parses | None in this function | Same | Read. Not an operational cycle path |
| `reconciliation.py` `fetch_broker_positions_detail` lines 215–241 | GET | `/v3/accounts/{accountID}/openPositions` | Open position units and average price | `run_reconciliation_once` line 849, from startup and `reconciliation_loop` | Loop lines 248–279 | Warning line 243 | SL/TP are not on this payload; code comments say to use trade details | Read |
| `oanda_exec.py` `fetch_pending_orders_sync` lines 577–592 | GET | `/v3/accounts/{accountID}/pendingOrders` | Pending orders | Reconciliation helpers that call this function | List at lines 591–592 | Warning line 589 | Full order body is not structured for diagnosis | Read |
| `oanda_exec.py` `fetch_trade_details_sync` lines 595–617 | GET | `/v3/accounts/{accountID}/trades/{tradeSpecifier}` | One trade, including SL/TP orders when present | Reconciliation, `reconciliation.py` around line 475 | Trade dict line 616 | Warning line 614 | Financing and home conversion are not parsed here | Read |
| `oanda_exec.py` `fetch_transaction_details_sync` lines 620–642 | GET | `/v3/accounts/{accountID}/transactions/{transactionID}` | One transaction | `broker_exit.py` documents a read after a close, line 178 comment | Transaction dict line 641 | Warning line 639 | Not a sizing source | Read |
| `oanda_exec.py` `_place_market_order_open_sync` lines 453–541. Request line 504. `api.request` line 510 | Account-changing order create. The verb is not stored as a string in this function. The object is `oanda_orders.OrderCreate` for a market order | `/v3/accounts/{accountID}/orders` | Open a position and attach SL/TP | `execute_oanda_market_open` line 562. Current `run_bot` tail returns at `bot_loop.py` 1706 before any call. `production_execution_adapter` can call it only if `production_adapter_refusal` returns empty, which the current function does not | `classify_order_create_response` line 520 and `_parse_open_fill` line 539 | Lines 505, 515, 522, 531, 540 | Reachable only if a later edit removes the early return | Changes account state: opens a trade |
| `oanda_exec.py` `_place_market_order_sync` lines 397–450. Request line 423. `api.request` line 430 | PUT, stated at line 398 | `/v3/accounts/{accountID}/positions/{instrument}/close` | Close units | `execute_oanda_market_close` line 663, from `trading.execute_trade` when `execution_kind == "live"` | `_parse_fill` line 446 | Lines 432 and 449 | Still reachable for a live-tagged position when broker mode is on | Changes account state: closes a position |

No operational call to `/v3/accounts/{accountID}/instruments` was found. No `OrderCancel` or `TradeCRCDO` submit was found. A position close can still produce a cancel transaction in the response (`oanda_exec.py` lines 443–445); that is broker-side, not a separate cancel request from this bot.

`_oanda_request` is the shared read transport. It does not choose the endpoint.

## D. Recommended logging points

Ranked by evidence gained per change. All of these are proposals. None is implemented.

### 1. Account summary, after a successful parse

- File: `forex_bot/oanda_client.py`, function `fetch_account_summary`, lines 168–193.
- Available from the broker response, already parsed: `currency`, `NAV`, `balance`, `marginAvailable`, `alias`. `account_core` also parsed `unrealised` and `last_transaction_id` (`oanda_account_adapter.py` lines 50–67) but the snapshot at lines 172–181 does not keep unrealised P/L.
- Unavailable: account type, spread-bet versus CFD, financing, margin rate, pip location. Currency being GBP is not proven by the source; the field is whatever the response contains.
- Direct OANDA data.
- Runs on startup and every cycle, before `_cycle_symbols`, so before an order decision.
- Suggested JSON fields: `event`, `endpoint`, `host_class` (`practice` or `live`), `currency`, `nav`, `balance`, `margin_available`, `unrealised_pl`, `currency_is_gbp` as `YES` or `NO` or `ABSENT`. Omit account id, alias, and token.

### 2. Pricing snapshot, one record per instrument

- File: `forex_bot/oanda_client.py`, function `fetch_pricing_snapshot`, lines 551–575.
- Available: instrument, first bid, first ask, closeout bid, closeout ask, `time`, `tradeable` or status.
- Unavailable with the current query: home-conversion factors, financing, pip location. The request at line 542 does not send `includeHomeConversions`.
- Direct OANDA data for the fields above. Spread in pips would be calculated and must be labelled calculated.
- The cycle call is before symbol evaluation. `fetch_entry_pricing` (`entry_geometry.py` lines 382–393) is a second GET and runs only after the broker-open branch has already started, still before the current early return at `bot_loop.py` 1706.
- Suggested JSON fields: `event`, `instrument`, `bid`, `ask`, `time`, `tradeable`, `status`, `conversion_factors` = `NOT_REQUESTED`, `source` = `oanda_pricing`. Do not log the account id.

### 3. Sizing inputs, before any order

- File: `forex_bot/bot_loop.py`, inside `_evaluate_impl`, lines 1425–1432, plus the currency read at lines 1541–1544.
- Available: symbol, direction, price used for the stop, ATR fallback, stop distance, equity from `current_equity`, units before and after `cap_position_units`, cached summary currency and NAV.
- Unavailable: broker pip location, home-conversion factor, GBP pip value, margin requirement for this order, financing, spread-bet stake mapping.
- Units and risk are calculated by `trading.position_sizing` and `stop_risk_account_ccy`. They are not an OANDA size quote.
- This block is before `open_fill_path` and before the broker branch.
- Suggested JSON fields: `event`, `instrument`, `units`, `equity`, `summary_currency`, `stop_distance_price`, `risk_model` = `quote_pnl_to_account_ccy_usd_approximation`, `gbp_conversion` = `NOT_USED`, `max_position_units_cap_enabled`.

### 4. Stop and take-profit actually prepared for an order

- File: `forex_bot/bot_loop.py` lines 1688–1690 and `oanda_exec.py` `_format_oanda_price` lines 131–136, used when an order object is built at lines 477–501.
- Available: numeric SL and TP from local geometry, and a 3-or-5 decimal format chosen by whether the name contains `JPY`.
- Unavailable: broker `pipLocation` and `displayPrecision`. The decimal choice is local.
- Calculated. The legacy path currently returns before the order object is built. Logging the geometry at line 1688 still sees the values on a broker-intent cycle.
- Suggested JSON fields: `event`, `instrument`, `sl_price`, `tp_price`, `sl_distance_price`, `tp_distance_price`, `price_format` = `local_jpy_3dp_or_5dp`, `broker_precision` = `NOT_READ`.

### 5. Request failures

- File: `forex_bot/oanda_client.py` `_oanda_request` lines 302–318 and `fetch_account_summary` line 159; `oanda_exec.py` lines 431 and 513.
- Available: context string, exception type, HTTP code when `V20Error` supplies one, redacted body excerpt from `_format_oanda_error` lines 23–47.
- Unavailable: a structured copy of the response fields that were never parsed.
- Direct error from the library. Do not log the request header or account id.
- Suggested JSON fields: `event` = `oanda_error`, `context`, `http_status`, `error_class`. Reuse `redact_log_text`.

Lower value until a later authorisation changes the request: a pricing query with `includeHomeConversions=true`, and a new instruments GET for `pipLocation`. Those are not log-only. They change the request. They are not part of the smallest log patch.

## E. Sizing and broker-data gaps

### Confirmed from source

- Summary currency is parsed and stored. `fetch_account_summary` lines 170–184 calls `set_broker_account`. `state.current_equity` lines 98–103 prefers `broker_nav`, else the equity curve, else `Config.BASE_BALANCE` (default 10000 at `config.py` line 48).
- Sizing does not check that currency. `quote_pnl_to_account_ccy` (`trading.py` lines 148–160) documents conversion to approximate account USD. `EUR_USD` and `GBP_USD` are treated as already USD. `USD_*` divides by the mid price. `position_sizing` lines 278–325 uses that function through `stop_risk_account_ccy`.
- `1.35` is not used in `position_sizing` or `quote_pnl_to_account_ccy`. It does appear as a research and shadow fallback: `forex_bot/research/adaptive_ensemble/conversion.py` `stage_g_fixed_estimate` line 139, `runner.py` line 74, and `forex_bot/shadow/config.py` line 55. Those modules are not the `run_bot` sizing call.
- Pip size is local. `profit_protection.pip_size` lines 73–80 returns `0.01` when the quote currency is `JPY` and `0.0001` otherwise. `oanda_exec._format_oanda_price` lines 131–136 uses 3 decimals when `JPY` is in the name and 5 otherwise. Neither reads `pipLocation`.
- `MAX_POSITION_UNITS` at `0` disables the cap. `cap_position_units` (`trading.py` lines 230–235) returns the units unchanged when the value is `<= 0`. `_configured_unit_cap` (`bot_loop.py` lines 2152–2157) documents zero as the cap off. The default of `_env_float` is `0.0`.
- `MIN_STOP_DISTANCE_PRICE` at `0` does not floor the stop. `sl_tp_distance_for_entry` lines 130–132 and `position_sizing` lines 316–318 apply the floor only when the value is `> 0`. A stop distance below `1e-15` returns 0 units (line 319). A small but non-zero stop is still allowed and increases units. The default is `0.0`.
- `position_sizing` line 290 states that broker margin and max position are not modeled. Financing is not an input there. Live spread for the broker path comes from the dedicated pricing quote in `entry_geometry`, not from the summary. Paper spread uses the local `SPREADS` table (`trading.py` lines 74–79 and `simulated_half_spread` lines 101–109).
- The pricing parser keeps a timestamp (`oanda_client.py` line 573). `market_provenance.py` lines 27–28 sets decision-bar max age at 30 minutes and order-quote max age at 15 seconds. Home-conversion age cannot be judged because those factors are not requested.
- Spread-bet stake to API units is not implemented in the operational sizer. Units are `risk_amount / risk_per_unit`, with a minimum of 1 (`trading.py` line 325), then possibly weighted by portfolio weight and confidence (`bot_loop.py` lines 1430–1431).

### Unresolved broker questions

- Whether this account's home currency is GBP: **UNVERIFIED**. The code can store a currency string. It does not require `GBP`.
- Account type, including spread bet versus CFD: **UNVERIFIED**. Not read.
- Broker pip location and display precision: **UNVERIFIED**. Not requested.
- Home-conversion factors and a GBP pip value from the broker: **UNVERIFIED**. Not requested.
- Financing charge in account currency: **UNVERIFIED**. Not read by the operational client.
- Margin rate and margin required for a proposed size: **UNVERIFIED**. Only `marginAvailable` is parsed, and only when present.
- Whether quantity 1 means one API unit or a GBP stake: **UNVERIFIED** in this code. The sizer treats the result as OANDA units.

## F. Trading-disable assessment

`DATA_ONLY_MODE_NOT_PROVEN_SAFE`

| Control | What the source does | Blocks every account-changing request |
| --- | --- | --- |
| `EXECUTION_MODE=paper`, or unset `EXECUTION_MODE` with `PAPER_TRADING` true (`config.py` line 63 default true; `execution.get_execution_mode` lines 100–114) | `assert_broker_order_allowed` lines 85–86 raises before an open or close submit | Yes for calls that go through that function. The process still performs GET summary, pricing, candles, and open positions when a token exists |
| `EXECUTION_MODE=paper_broker` | `use_oanda_live` lines 103–104 returns true. Host still follows `TRADING_MODE` | No. Practice is not implied. `TRADING_MODE=live` selects the live host |
| `EXECUTION_MODE=live_broker` | Broker orders enabled | No |
| `USE_OANDA_LIVE` | Used only when `EXECUTION_MODE` is unset (`oanda_exec.py` lines 103–106). `assert_broker_order_allowed` still rejects `EXECUTION_MODE=paper` first | Not a complete block |
| `KILL_SWITCH` and `halt_trading` | `trading_allowed` lines 68–74 blocks new risk. `app.py` line 886 states closes still run. `assert_new_live_exposure_allowed` lines 102–106 returns immediately for `close` | No. It does not wrap `PositionClose` |
| `POST /halt` | Calls `halt_trading` only | No |
| Legacy open tail | `bot_loop.py` lines 1704–1706 returns before `OrderCreate` | This current open tail does not send. It is not a mode, and the close path is separate |
| `production_execution_adapter` | Refusal currently always returns a reason before line 3154. Non-simulation shared iteration never calls the adapter (lines 4196–4206). `run_bot` uses `_evaluate_impl` instead | Does not define a data-only process |
| Reconciliation | Docstring at `app.py` line 159 says log-only comparison. The GETs do not submit orders | Those GETs are read-only. They do not disable `execute_trade` |

`close_fill_path` (`execution.py` lines 225–239) returns `broker` for `execution_kind == "live"` whenever `broker_orders_enabled()` is true, including after the live window. `_evaluate_impl` then calls `execute_trade`, which calls `PositionClose`. A paper-tagged position stays on the local simulate or mid path.

No separate market-data-only command exists. `main.py` starts the whole lifespan.

## G. Minimal implementation proposal

Do not implement this in R.56.

Later, and only after a separate authorisation:

1. Add one JSON logger used by the three points in section D. Files: `oanda_client.py` `fetch_account_summary` and `fetch_pricing_snapshot`; `bot_loop.py` `_evaluate_impl` immediately after `cap_position_units`. Pass text through `redact_log_text`. Do not log tokens, account ids, or raw response bodies.
2. Do not change `position_sizing`, strategy selection, RL, stops, or order payloads in that patch.
3. Do not add `includeHomeConversions` or an instruments GET in that same patch. Those change the request. They need their own authorisation because the current client does not send them.
4. Do not use `main.py` as the diagnostic entry. A later data-only entry would call only `fetch_account_summary`, `fetch_pricing_snapshot`, and `fetch_ohlcv`, and would not start `run_bot`, `reconciliation_loop`, or `/set_mode`.
5. Before any such entry exists, `execute_oanda_market_open` and `execute_oanda_market_close` need an explicit process guard that raises before `api.request` when the process was started for diagnosis. The current early return on the open tail is not that guard. `PositionClose` is still reachable.

Files that would change in that later patch: `forex_bot/oanda_client.py`, `forex_bot/bot_loop.py`, and `forex_bot/oanda_exec.py` for the hard refuse. No strategy file.

## H. Integrity and safety confirmation

- Git branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Working tree: dirty. Porcelain count before this report: 256. `data/research/adaptive_ensemble/r55/` was already one untracked directory, so the count may stay 256 after this new report if the parent research tree remains collapsed.
- File created: `data/research/adaptive_ensemble/r56/R56_EXISTING_BOT_DIAGNOSTIC_INSPECTION_REPORT.md`
- No existing file was modified.
- The bot was not started.
- No `.env` file, credential store, token, or account id was read or printed.
- No network request was made.
- No order or trade was placed.
- R.55 research files were not modified.

### Authorisation

- Static inspection: authorised and complete.
- Diagnostic logging implementation: not authorised.
- Data-only bot execution: not authorised.
- Authenticated OANDA requests: not authorised.
- Practice orders: not authorised.
- Live trading: not authorised.
- Production changes: not authorised.
- Production deployment: NO-GO.
