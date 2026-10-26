# Remaining gaps

- Production account freshness and account identity are NOT_EVALUATED. The harness timestamp check is not a broker-verified freshness policy.
- `verified=True` cannot certify a production snapshot. The non-harness path fails closed.
- The portfolio stop-risk cap still reads `current_equity()` after an accepted snapshot.
- The production adapter was source-mapped and not invoked. Broker execution is NOT_EVALUATED.
- PostgreSQL, the production loop, broker-flat release, and profitability are NOT_EVALUATED.
- The legacy fill-classification tail remains unreachable and cannot dispatch.
