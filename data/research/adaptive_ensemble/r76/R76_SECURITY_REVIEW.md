# R.76 security review

This stage did not start `main.py`, `forex_bot.app`, or `run_bot`. It did not read `.env`, print credentials, or create `one_session.permit`. The consumed marker hash is unchanged. Source gates remain `REAL_SESSION_SOURCE_ENABLEMENT = False`.

Network and database:

- R.76 tests install the R.69 isolation harness before importing `forex_bot`.
- Synthetic `api.request` implementations raise `IsolationBreach` for an unexpected endpoint name.
- The entry worker records `OrderCreate` in a temporary SQLite file.
- PostgreSQL was not contacted. Historical tests that reach the database stub log `PostgreSQL unavailable: postgres blocked`.
- No production journal path was used. Tests set `CLOSE_JOURNAL_PATH` to a temporary file.

Authority:

- `begin_entry_submission` does not make an entry eligible. `production_adapter_refusal` still runs first, and the production iteration still returns `production_execution_adapter_withheld`.
- `assert_new_live_exposure_allowed(action="open")` still runs before `claim_entry_permit`. Tests that need to reach a synthetic `OrderCreate` replace that function inside the test process. The source default stays blocked.
- A claim commits before `api.request`. A second claim or a stale token does not send.
- The close guard still requires `CloseSubmissionPermit`. Live `execute_trade` still raises before HTTP.
- Account ids are stored only as `account_binding` hashes. The synthetic test account is the isolation account. The real account id was not printed.

Fail closed:

- Missing, corrupt, locked, and version-2 journals block live management.
- An incomplete or failed snapshot blocks management and sets `empty_book_is_not_flat`.
- An ambiguous entry is not retried and is not turned into a managed position.
- A broker-only trade is not promoted because its instrument matches.
- Protection evidence with a pending stop keeps `exit_attribution = EXIT_ATTRIBUTION_UNKNOWN` and does not authorise a close.

Legacy callers of `_place_market_order_open_sync` or `execute_oanda_market_open` that omit `entry_permit` now raise `TypeError` before HTTP. Those historical unit tests were not rewritten and were not run through repository pytest. The refusal is fail-closed.

Not verified: broker-enforced idempotency, power-loss durability of SQLite, Linux operational imports, and a real OANDA response.
