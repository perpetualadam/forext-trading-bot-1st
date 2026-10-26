# Remaining integration gaps

- No producer can seal `production_eligible=true`. That is intentional.
- In-process seal reuse is rejected. Restart-durable single-use state is NOT_EVALUATED.
- Production account, market, quote, and margin provenance are missing. The summary and pricing helpers exist and were not called.
- GBP spread-betting compatibility is not checked.
- `marginUsed` and margin closeout are not parsed. No margin rate was invented.
- Numeric spread policy is `POLICY_UNAPPROVED`. `pip_size` is not a spread cap.
- Sizing uses `dependencies.price`; the spread gate uses bid/ask; the shared broker request leaves `entry_quote` empty.
- Broker-flat release is not implemented. `confirm_exposure_flat` stays false.
- PostgreSQL, OANDA, the production loop, loss-halt durability, and profitability were not evaluated.
- Optional gross-notional, unit, and account-risk controls stay off at their existing defaults.
