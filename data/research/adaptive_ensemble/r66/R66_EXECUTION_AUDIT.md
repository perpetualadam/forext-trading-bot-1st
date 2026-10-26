# R.66 Execution audit

Source review of order construction. No HTTP call was made. `REAL_NETWORK_EXECUTION_NOT_TESTED`.

## Who can submit

| Action | Function | Reached from `run_bot` today |
| --- | --- | --- |
| Market open with SL/TP on fill | `oanda_exec._place_market_order_open_sync` via `execute_oanda_market_open` | No. Only caller in production code is `production_execution_adapter`, which returns `refused` before the call (`bot_loop.py` 3122–3141 and 2922–2923) |
| Market close | `oanda_exec._place_market_order_sync` via `execute_oanda_market_close` | Yes, when a local position is closed with `execution_kind == "live"` (`trading.py` 391–398) |
| Read positions, candles, account, pending orders, trade details | `oanda_client`, `reconciliation`, `oanda_exec.fetch_*` | Yes, if the process is started. This audit did not start it |

`assert_broker_order_allowed` and `assert_new_live_exposure_allowed(action="open")` run inside the open helper (`oanda_exec.py` 463–466 and 503). Close is not a new-exposure action (`live_safety.py` 102–106), so a live close is not blocked by the live-order auth flag that blocks opens.

## Open order shape, if a future caller reached it

`_place_market_order_open_sync` (`oanda_exec.py` 453–541):

- `MarketOrderRequest`, `timeInForce=FOK`, `positionFill=OPEN_ONLY`.
- Units from `_order_units_for_open`: absolute units, negative for SELL (`oanda_exec.py` 123–131). The sign is the order side.
- Client extension id is the client order id, truncated to 128 characters.
- Optional `stopLossOnFill` and `takeProfitOnFill` as GTC prices from `_format_oanda_price`.
- No separate trailing-stop order type.
- Rate limit: `acquire_oanda_rest_slot` immediately before `api.request`.
- A second `assert_new_live_exposure_allowed` runs after the request object is built and before the HTTP call.

There is no retry loop around OrderCreate. A transport failure is classified and raised.

## Outcome classification for OrderCreate

`classify_order_create_response` (`oanda_exec.py` 210–269):

| Body | Outcome |
| --- | --- |
| Usable fill transaction | `FILLED` (a fill wins over a cancel in the same body) |
| Cancel transaction and no usable fill | `CANCELLED` |
| Reject transaction | `REJECTED` |
| Anything else, including a create transaction without a fill | `MALFORMED` |

`classify_order_create_transport_error` (`oanda_exec.py` 289–316): HTTP 400–499 except 408 becomes `REJECTED`. Timeouts, connection errors, other `V20Error` values, and any remaining exception become `AMBIGUOUS_TRANSPORT`.

The raised types are `OrderCreateCancelled`, `OrderCreateRejected`, and `OrderCreateOutcomeError` for ambiguous or malformed results (`oanda_exec.py` 336–349). The dead legacy tail maps those to cancelled, rejected, or `OrderStatus.UNRESOLVED` plus `remember_ambiguous_outcome` (`bot_loop.py` 1707–1753). It does not send a second OrderCreate in the `except` blocks. That tail is unreachable from `run_bot`, and its `try` returns before the request, so those handlers do not run today.

The shared simulation path distinguishes timeout, connection failure, ambiguous, malformed, rejected, accepted, filled, partial, and conflicting quantity (`bot_loop.py` 4227–4348). Uncertain kinds call `note_unconfirmed_exposure` and do not record a clean fill. That path uses `dependencies.broker.submit` and sets `production_authorised` false. It is not OANDA.

The words `ORDER_REQUESTED`, `ORDER_ACCEPTED`, `ORDER_FILLED`, `ORDER_REJECTED`, and `ORDER_STATUS_UNKNOWN` are not the enum the broker helper uses. The source equivalents are the classification outcomes above and `orders.OrderStatus` values including `PENDING`, `FILLED`, `PARTIAL`, `UNRESOLVED`, and `CANCELLED`. A successful HTTP response is not treated as a fill: only `_fill_usable` produces `FILLED`. A create transaction without a fill is malformed, not accepted.

Partial fills: `_parse_open_fill` returns a unit count, and the dead tail can mark `PARTIAL` when filled units are below the request (`bot_loop.py` 1769–1772). The current cycle never gets there.

## Close

`_place_market_order_sync` (`oanda_exec.py` 397–450) sends `PositionClose` with `longUnits` or `shortUnits` set to the absolute decimal size. It does not send an opposite market order that could flip the position. `OPEN_ONLY` is an open-order field, not used here.

Any exception from `api.request`, including a timeout, is logged and re-raised as `RuntimeError` (`oanda_exec.py` 431–433`). The caller in `_evaluate_impl` keeps the local position (`bot_loop.py` 1073–1083`). The exception text is scanned for "timeout" (`bot_loop.py` 686–690).

If the response is a dict and a fill transaction is missing, the code still parses P&L and returns (`oanda_exec.py` 441–450). A missing fill price becomes NaN and may be replaced by a local estimate (`oanda_exec.py` 666–671). The function does not return the closed unit count. `execute_trade` then lets the caller delete the whole local position. A partial close that did not raise can therefore be recorded as a full local exit. See `R66-10`.

There is no idempotency key on PositionClose in this helper. A later cycle that still sees the local row sends another PositionClose. If the first close had succeeded and the response was lost, the second call is a new close of a possibly flat position. The source does not query the trade before retrying. See `R66-11`.

## Idempotency of opens

`try_begin_order_submission` is the reservation. The shared simulation path refuses when an outstanding reservation already exists for the symbol (`bot_loop.py` 4145–4158). The production cycle does not reach reservation. The dead tail reserves and then returns without cancelling (`R66-02`).

Client ids are generated by `generate_client_order_id`. This audit did not execute that generator. The open request copies the id into `clientExtensions.id`.

## Timeouts and duplicates

An OrderCreate timeout is classified ambiguous and, on the dead tail, remembered as unresolved rather than retried. Because that tail does not run, the production cycle currently has no OrderCreate timeout behaviour in practice.

A PositionClose timeout keeps the local row and the next management cycle can close again. That is a duplicate-close hazard, not a duplicate-open hazard. Whether a given timeout leaves a flat or an open broker position was not tested.

Rate limiting exists as `acquire_oanda_rest_slot`. Its numerical budget was not re-derived in this audit. It is not a substitute for idempotency.

`use_oanda_live` gates whether broker orders are enabled (`execution.py` 198–202). The environment value was not read. Source default `PAPER_TRADING` is true, which yields execution mode `paper` when `EXECUTION_MODE` is unset (`execution.py` 89–114, `config.py` 63). In paper mode, `close_fill_path` for a non-live kind does not call OANDA. A row with kind `live` or an imported `reconcile_import` row is broker-backed. Imported rows use kind `reconcile_import`, and `close_fill_path` treats only kind `live` as a mandatory broker close (`execution.py` 225–234). An imported row therefore takes the non-live branch: simulate or mid, and `execute_trade` will not call PositionClose unless `execution_kind` passed in is `live`.

That distinction matters. `import_position_from_broker` sets `execution_kind="reconcile_import"` (`positions.py` 169). Management passes `pos.execution_kind` into `execute_trade` (`bot_loop.py` 1067). `execute_trade` calls OANDA only when that kind is `live` (`trading.py` 391). A weekend or protection close of an imported row books a local exit and does not send PositionClose. The broker position remains. The local book then says it is gone. See `R66-04` revised consequence in the findings register: the dangerous case is a false local flatten, not an unexpected broker flatten, for `reconcile_import` rows. A true `live` kind row does send PositionClose.
