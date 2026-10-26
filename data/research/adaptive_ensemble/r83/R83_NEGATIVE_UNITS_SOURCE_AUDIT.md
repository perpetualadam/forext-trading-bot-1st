# R.83 negative closed-unit source audit

File: `forex_bot/broker_close_evidence.py`. SHA-256 remains `3c879729a0c70138f6a317473767e8dfec8d2417c2d38d236478a3a8a190e9db`. R.83 did not edit this file.

Function: `apply_transaction_body`. The changed lines are 526-528.

```python
units = _decimal(row.get("units"), label="units")
if units < 0:
    raise CloseReadError("negative_closed_units")
```

Previous behaviour, from the R.82 source review: `units = abs(_decimal(...))`. A `tradesClosed` value of `-100` was counted as 100 closed units.

Current behaviour: `CloseReadError("negative_closed_units")` before `matched` is increased. The exception leaves `apply_transaction_body` before a confirmation state is returned. The caller in `run_guarded_live_close` persists reconciliation or ambiguous state only when it catches `CloseReadError` from the surrounding confirmation path. The direct unit tests call `apply_transaction_body` and do not write a full confirmation.

`test_13` raises `CloseReadError` for `"-100"`. It does not become `CLOSE_FULLY_CONFIRMED`. The operational permit and second-close checks for a bad confirmation are covered by the close fault tests: a close that does not reach full confirmation is not removed and is not resent.

Positive strings `"400"`, `"999"`, `"1000"`, and `"400.5"` still parse. `"400.5"` is a partial close with remaining `599.5` because `_decimal` accepts a finite decimal and the classifier does not require an integer. That is the existing contract, not a new rule.

The signed fill field `orderFillTransaction.units` is separate. For a BUY close it must be negative or `direction_mismatch` is raised at line 509. The R.82 rejection applies only to `tradesClosed[].units`.
