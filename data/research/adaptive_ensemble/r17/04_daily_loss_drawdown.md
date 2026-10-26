# Daily loss and drawdown

The production flag `DECISION_REPAIR_ACCOUNT_RISK` remains off. `account_risk_enabled()` is false unless a test sets it. The shared path calls `block_reason` only in that case.

Inputs when the flag is on:

- Equity is the R.16 accepted snapshot, not `current_equity()`.
- Unrealised is `IterationDependencies.unrealised`. The default is `None`. The existing function latches `account_unrealised_unavailable` when unrealised is missing or non-finite. This stage does not substitute zero.
- Thresholds remain the existing defaults: daily realised 2%, daily total 3%, max drawdown 5%. Equality is a breach in the existing function.
- A corrupt risk file latches `corrupt_risk_state`.

The halt is stored by the existing JSON writer. A later read in the same process keeps it. `verified=True`, a fabricated payload, and a caller token do not clear it. `operator_clear_latch` is not called by the entry path. Calling it with `operator_confirmed=False` raises `PermissionError`.

Limitations:

- The existing function sets the first positive equity as the peak. A missing historical peak is not a separate block.
- The risk file has no freshness window. Evidence records `risk_freshness: not_evaluated`.
- Process restart was not executed. The JSON file is not production durability. I181 remains NOT_EVALUATED.
- A passing offline calculation is not production daily-loss protection while the flag is off.
