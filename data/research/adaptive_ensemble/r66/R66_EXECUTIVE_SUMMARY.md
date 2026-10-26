# R.66 Executive summary

Read-only audit of the working tree at `d080d897945bc44fa37c02caab504ed707146bec`. The bot was not started. OANDA was not contacted. Profitability was not calculated. Production trading remains NO-GO. `REAL_NETWORK_EXECUTION_NOT_TESTED`.

## 1. What is the actual active trading strategy?

There is no active entry strategy on `run_bot`. The cycle loads completed M5 mid candles, manages a local position if one already exists, and otherwise asks `evaluate_one_instrument_iteration` for permission. That function returns `blocked` whenever `simulation` is false. The status required to continue into strategy selection is never produced.

The hybrid ATR router, meta-learner, sequence model, AI vote, and RL gate exist in source and are not reached. The quant stub abstains. RL returns `UNAVAILABLE` until a policy is marked persisted. Shadow mean-reversion and trend rules are not the live order path.

What can still change state is management of a RAM position: paper stop checks, profit-protection decisions, weekend flatten, and a live `PositionClose` when the row's kind is `live`. Reconciliation can insert a `reconcile_import` row in broker execution modes even when the reconcile action is `log_only`.

## 2. How does the bot decide to buy or sell?

It does not, on the current production path. A future path would take an AI ensemble direction and would block unless RL agrees or is skipped by not being invoked. The default ensemble has no local voter, so it would abstain. None of that runs after the shared decision returns `blocked`.

## 3. Are the risk controls consistently enforced?

New entries are refused before sizing. That refusal is consistent and fail-closed. The detailed controls (1% stop-risk versus notional, portfolio cap, USD-direction guard, daily loss, margin) are not all on one path, and the ones inside the shared function sit after the simulation gate. Margin is marked not implemented. Account-currency conversion assumes a USD result and is `NOT_VERIFIED` against the real account. Those formulas do not protect a running cycle today because the cycle does not size.

## 4. Are stop-losses and trailing stops logically correct?

Orientation for a new BUY or SELL stop is consistent in `sl_tp_distance_for_entry` and `entry_geometry`: long stop below the reference, short stop above. Profit-protection thresholds ratchet only tighter. That code is not a broker trailing-stop amend.

`broker_sl_tp_hit` always returns false. A local stop price is not proof of a broker stop. Import can store a 20-pip `local_fallback` without sending it. Application trailing state lives in RAM and disappears on restart. Paper stops use the bar close, not the bar extreme.

## 5. Can execution create duplicate or unprotected positions?

The current cycle does not send `OrderCreate`, so it does not create a duplicate entry. A live `PositionClose` that returns without a proven unit count can delete the whole local row (R66-10). A timeout keeps the row and the next cycle can send another PositionClose with no client id (R66-11). An imported `reconcile_import` row can be removed locally without any PositionClose, leaving the broker position in place (R66-04). A broker position that is not imported is invisible to management and can be unprotected by this process (R66-05).

## 6. Is reconciliation reliable?

It is not reliable enough to treat the RAM book as the broker book. Positions are not loaded from PostgreSQL. Import in broker mode ignores the log-only default. Auto-fix of a disappeared broker position is off unless `RECONCILE_ACTION=auto_fix`. The reconcile task and the trading task share the RAM dict. Runtime broker state was not fetched.

## 7. Is there evidence of a profitable strategy?

No. `PROFITABILITY_NOT_ASSESSED`. This stage did not use trade history, a backtest run, or broker fills.

## 8. Could Windows and Linux produce different decisions?

Not on the current entry path, because that path does not decide. If the unreachable tail were entered, unseeded strategy draws and the default noisy price hint would diverge by process, not only by operating system. Indicator math itself has no OS branch. Linux was not executed in this stage. Equivalence is `NOT_VERIFIED` by a run.

## 9. Five highest-priority improvements

1. Keep the entry producer refused. Do not return `continue_existing_production_broker` and do not delete the early return in the legacy tail until a reviewed design replaces that tail. The tail reserves an order id and then returns (R66-02).
2. Make reconcile import and local close agree with the broker. `log_only` should not create a `reconcile_import` row. A row that represents a broker position must not be deleted unless PositionClose reports a full fill (R66-04, R66-10).
3. Record whether a broker stop exists. `broker_sl_tp_hit` returning false plus `local_fallback` means unprotected, and the process should say so (R66-03, R66-05).
4. Give PositionClose one identity and do not send a second close while the first outcome is unknown (R66-11).
5. Before any sizing path is reachable, refuse unless stop-risk currency matches the account currency, and make the USD_JPY notional helper agree in every cap (R66-07, R66-08). Add the offline Windows and Linux fixtures from the cross-platform audit. Do not read `.env` to do that.

## 10. What the next stage should address

R.67 should stay offline and should not implement these fixes unless a later instruction says so. The useful scope is a design note for the import/close/stop-source invariants above, with synthetic fixtures and no broker client. It should not integrate R.62–R.65, not change strategy rules, and not enable a live session.

## Classifications

`R66_ARCHITECTURE_TRACED` for the operational startup and order graph. Research trees were classified by import reachability, not by reading every historical file.

`R66_SIGNAL_PATH_AUDITED` as source review. The production cycle does not reach a trade candidate.

`R66_RISK_PATH_AUDITED` as source review. Sizing is not on the current entry path. Account currency is `NOT_VERIFIED`.

`R66_STOP_MANAGEMENT_AUDITED` as source review. No broker stop was observed.

`R66_EXECUTION_PATH_AUDITED` as source review. OrderCreate is not reached. PositionClose was not sent.

`R66_RECONCILIATION_AUDITED` as source review. No broker snapshot was taken.

`R66_STRATEGY_EVIDENCE_ASSESSED` with the result that profitability is not assessed.

`R66_CROSS_PLATFORM_RISKS_ASSESSED` as source review. Linux execution in this stage is `NOT_VERIFIED`.

`R66_NO_OPERATIONAL_CHANGES`

Production trading remains NO-GO.
