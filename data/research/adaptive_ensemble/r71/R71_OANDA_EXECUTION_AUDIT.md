# R.71 OANDA Execution and Reconciliation

No broker host was contacted.

## Client and environment

`oanda_client.get_api` builds a client from configuration. An empty token returns no client. `TRADING_MODE` selects practice or live host inside that module. This audit did not call it against a network. `use_oanda_live` is the order gate (`oanda_exec.py` 94). Close and open helpers both require a client and an account id.

## Orders

Opening: `_place_market_order_open_sync` builds a market order with FOK, `OPEN_ONLY`, a client extension id, and optional `stopLossOnFill` / `takeProfitOnFill` (477–504). `assert_new_live_exposure_allowed` runs before the request. The operational entry path does not reach this helper while the shared decision stays blocked.

Closing: `_place_market_order_sync` sends `PositionClose` with long or short units (418–430). There is no client extension on that request. A missing fill raises or synthesises P and L from the fill price (`execute_oanda_market_close` 666–671). The caller then deletes the local position. Filled units are not matched to the request. R66-10 remains open. A timeout has no stored operation id. R66-11 remains open.

## Reconciliation

`reconcile_positions_log_only` is scheduled from the app lifespan (`app.py` 630) and was not started here. R.68 remains in `position_management_permitted` and in the import writer. The R.71 test rejected an observation. R.70 remains in `_interpret_open_positions`: `{}` raises `INCOMPLETE`, and `{"positions":[]}` is `COMPLETE_EMPTY`. The test observed both.

A complete empty snapshot can still drop a permitted live row. That behaviour was not reclassified as safe.

## Still open

R66-03 broker stop hit is false. R66-05 local prices are not broker stops. R66-10 close without unit evidence. R66-11 close without an idempotency key. R66-16 concurrency and restart limits remain. This audit did not implement fixes.
