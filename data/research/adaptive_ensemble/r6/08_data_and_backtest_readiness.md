# Data and backtest readiness

Session evidence used: `data/research/adaptive_ensemble/g4/session_coverage.json` and `data/research/adaptive_ensemble/r2/11_session_recount.json`.

- Complete common sessions: 27.
- Required: 40.
- Shortfall: 13.
- R.2 recomputation matched 27.
- Additional eligible sessions in that recount: 0.
- Raw market files were not re-opened in R.6. No download was made. No profit test was run.

`forex_bot/backtest.py` lines 352–354 still do this:

```
direction = str(ai_decision.get("direction", "BUY")).upper().strip()
if direction not in ("BUY", "SELL"):
    direction = "BUY"
```

That file is not on the application startup path. It is unsafe for any future performance test until it is changed under a separate approval.

Research books mark overnight financing as unavailable. Spread and slippage exist as assumptions in `trading.py`. They are not a broker-validated cost model. Look-ahead and walk-forward status was not re-run. There is no credible performance result.
