# R.71 Operational Call Graph

Runtime execution of this graph was not performed. The edges are source calls.

```text
main.py:21
  uvicorn forex_bot.app:app
    app lifespan
      run_bot                         app.py:633
        fetch_account_summary         bot_loop.py:4422   NOT_VERIFIED, would use the network
        _cycle_symbols                bot_loop.py:4424
          evaluate                    bot_loop.py:720
            _evaluate_impl            bot_loop.py:732
              permitted position
                ownership guard       bot_loop.py:795
                apply_profit_protection bot_loop.py:854
                broker_sl_tp_hit      bot_loop.py:889   returns false
                paper SL/TP compare   bot_loop.py:890
                weekend flatten       bot_loop.py:908
                execute_trade         bot_loop.py:1072
                  live: PositionClose trading.py:396
                  else: local record
                close_position        bot_loop.py:1098
              no position
                dispatch_production_iteration bot_loop.py:1135
                  status blocked      bot_loop.py:3336
                  return              bot_loop.py:1148
                strategy, sizing, OrderCreate
                  source exists after the return and is not reached
      reconciliation_loop             app.py:630
        reconcile_positions_log_only
          fetch_broker_positions_detail
            _interpret_open_positions
            _publish_snapshot
```

## Feature reachability

| Feature | Entry | Mode required | Gate | Reachable now | Tested now |
| --- | --- | --- | --- | --- | --- |
| Profit protection | `_evaluate_impl` when a permitted row exists | Any mode that has the row in memory | `PROFIT_PROTECTION_ENABLED` default true; ownership | Yes, if the process is running and the row exists | Formula tested offline. Process not started |
| Paper SL/TP | Same branch, non-broker row | Paper kinds | Ownership | Yes, under the same condition | Not executed as a loop |
| Live close | `execute_trade` kind `live` | Broker orders enabled | `use_oanda_live` | No under the current disabled order gate | Not executed |
| New entry | After line 1139 | Would need the continuation status | Production seam returns blocked | No | Tail not executed |
| Reconciliation | App task | Process running | Snapshot contract | Code is connected. Process not started | Prior R.70 synthetic suite; R.71 checked the classifier |
| Persistence | Database helpers | PostgreSQL | Harness blocks connect | Not verified | Not run |

A static import of `ai_ensemble` in `app.py` is not an entry decision.
