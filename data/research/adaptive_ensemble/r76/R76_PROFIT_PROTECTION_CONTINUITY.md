# R.76 profit-protection continuity

`forex_bot/profit_protection.py` was not edited.

SHA-256: `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`

Preserved values, checked by tests 51–60 and the R.71 file (8 passed on Windows):

- trigger `0.67` via `profit_protection_trigger_percent`
- ATR period 14 and multiplier `0.5`
- fallback `profit_giveback_pips() == 4.0`
- BUY and SELL original TP distance through `activation_trigger_pips`
- `pip_size("USD_JPY") == 0.01` and `pip_size("EUR_USD") == 0.0001`

Initial capture stores MFE 0 and protection inactive. Later changes go through `persist_protection_progress` (`forex_bot/position_recovery.py` line 414), called from `bot_loop.py` after `apply_profit_protection` for a live position.

The function returns false, and does not write, when:

- no durable row exists
- the proposed `profit_protection_exit_pips` is lower than the stored value
- the stored row is active and the in-memory flag is inactive

Test 55 stores exit pips `11.0`, refuses `9.0`, and refuses a reset from active to inactive. The stored value stays `11.0`.

`_activated_without_ratchet` (line 264) quarantines an active row whose exit, activated MFE, activated ATR, activated giveback, or activated exit is null. Test 54 covers that case. The missing values are not rebuilt from the current price.

`profit_protection_last_logged_mfe` is not a durable column. A restart uses the last committed MFE and ratchet. An in-memory change that failed to persist is not reconstructed.

Weekend flattening was not modified. The R.76 management test reached the existing weekend helper only as an import side effect and did not change its calendar rule.
