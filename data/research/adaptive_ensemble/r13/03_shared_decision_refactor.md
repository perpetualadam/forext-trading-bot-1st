# Shared decision refactor

`dispatch_production_iteration` is the production single-iteration boundary.

It is called from:

- `_evaluate_impl`, after an open position has been managed and before any new-entry broker call.
- `evaluate`, when the caller supplies dependencies. That is the offline driver. It does not load candles from OANDA and it does not call `run_bot`.

Both calls delegate to `evaluate_one_instrument_iteration`.

The shared function still applies the live-order gate, the strategy gate, canonical direction validation, the existing sizing and risk functions, the position and exposure holds, and the in-memory reservation. A fake broker is used only when `simulation=True` and the live-order gate is blocking. Production construction of the dependency object sets `simulation=False` and `broker=None`.

`run_bot` remains the loop. It was not called.
