# Caller compatibility

Production caller:

- `forex_bot/app.py` `lifespan`, now line 417. Before D.14 the return value was ignored. It was not tested for truthiness, compared with `None`, logged, or passed onward. The caller assumes start does not raise. D.14 captures the result and reports it. Startup still does not raise for a string result.

Other production modules do not call `start_telegram_control`.

`tests/test_telegram_control.py` `test_start_telegram_control_noop_without_token` calls the function and checks `_poller_started` is false. It does not read the return value. After the edit that test passed.

Historical runners call the function and ignore the return, or store it without asserting `None`. D.10 records `second_start_return` and asserts the old overlapping-worker defect. Those tests are hash-pinned and were not edited.

No production caller changes safety behaviour because a string result is not used as a boolean gate. Classification: compatible. Historical hash pins remain `HISTORICAL_HASH_PIN_CONFLICT`. D.10's old overlap assertion is `HISTORICAL_DEFECT_ASSERTION_CONFLICT`. D.13's assertion that refusal is invisible is `HISTORICAL_CONTRACT_ASSERTION_CONFLICT`, reached only as a hash-pin error.
