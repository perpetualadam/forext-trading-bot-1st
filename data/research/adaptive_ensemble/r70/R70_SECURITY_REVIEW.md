# R.70 Security Review

Scope: the snapshot-completeness edit and its tests. This is not a production-readiness approval.

## Authority

- Snapshot classification does not change `position_management_permitted`.
- Import still forces `observation_only=True` and `reconcile_import`.
- No new close path, stop order, or order endpoint was added.
- `PositionClose` was not called in the synthetic suite.
- The blocked entry path in `bot_loop.py` was not edited. Hash unchanged.

## Fail-closed evidence

- Incomplete, malformed, conflicting, failed, stale, and unknown reads do not publish a book and do not run convergence.
- A previous published book is retained on those failures.
- A whole body is rejected when one entry is bad or an instrument is duplicated.
- Both-sided exposure is not blended into a smaller net.

## Secrets and network

- Tests import the R.69 harness first. `load_dotenv` is stubbed. `.env`, `one_session.permit`, and credential paths are refused by the harness `open`.
- The synthetic account id is `001-002-0000001-003`. The token is empty.
- The missing-client test logs the existing "token missing" warning from `get_api`. No token value is printed.
- No live or practice host was contacted. `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- Postgres connect is refused. `POSTGRESQL_INTEGRATION_NOT_TESTED`.

## Gates

- `REAL_SESSION_SOURCE_ENABLEMENT = False` in the R.56 phase-6 gate and the R.59, R.60, and R.61 gates.
- `one_session.permit` is absent.
- The consumed marker hash is unchanged: `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`.

## Residual exposure

- `COMPLETE_EMPTY` can still drop a permitted live row through the existing helper. That can hide an unresolved close. It is not a new privilege; it is the pre-existing R66-10 behaviour, now limited to a structurally valid empty list.
- Report metadata can race. A stale cycle can replace `last_error` after a newer book was published. The book itself is guarded.
- `_remember_broker_snapshot` remains an unguarded writer for direct callers.
- Account currency, sizing, and close idempotency were not in this patch and remain open.
