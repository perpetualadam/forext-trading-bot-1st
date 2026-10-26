# R.70 Test Report

Classification: tested offline on Windows. Linux execution of the operational modules is not verified. No real network execution.

## Commands

```text
python -B data/research/adaptive_ensemble/r70/poc/test_r70_snapshot.py
python -B data/research/adaptive_ensemble/r69/poc/test_r69_integration.py
python -B data/research/adaptive_ensemble/r68/poc/test_r68_observation_boundary.py
```

The suites are run as files because `poc` is not a package. Pytest was not used, so project `conftest.py` was not loaded.

## Windows results

| Suite | Tests | Failures | Skipped | Time |
| --- | --- | --- | --- | --- |
| R.70 snapshot | 26 | 0 | 0 | 7.821s |
| R.69 integration, after the contract updates | 48 | 0 | 1 | 4.797s |
| R.68 observation boundary | 31 | 0 | 1 | 0.216s |

The R.69 skip remains `test_entry_tail_was_not_executed`. The entry tail was not executed. `bot_loop.py` still contains `status="blocked"` and the comparison against `continue_existing_production_broker`. Its hash is unchanged.

The R.68 skip remains the pre-existing concurrency interleaving that R.68 marked not verified. R.70 adds its own generation tests and does not claim that older skip is now a proof.

## What the R.70 suite exercised

- Real reconcile and real fetch.
- Synthetic `OpenPositions` bodies listed in `R70_SYNTHETIC_TEST_MATRIX.md`.
- A wrapped `account_disappeared_broker_position` so a call is observable. The wrapper calls the real helper.
- `FakeAPI.calls` so `PositionClose` would be visible. It was not called on invalid evidence or on the valid-empty live drop.
- Isolation attempts: no `load_dotenv` and no non-loopback `socket.connect` recorded by the harness.

## Fixture correction, not a weakened assertion

The first R.69 rerun failed `test_04` and `test_two_reconcile_threads_do_not_grant_management` because `_payload` put a positive unit string on the short side. The operational rule rejects that sign. The helper now emits the negative short string. The assertions are unchanged: the paper row stays, and the broker row is observation-only. After that correction the R.69 suite passed.

The R.69 hash pin for `reconciliation.py` was updated to the R.70 digest. The pins for `positions.py`, `bot_loop.py`, and `broker_exit.py` were not changed. That is a pin update after an intentional edit, not a removed check.

## Legacy tests

`tests/test_reconcile_conflict.py`, `tests/test_execution_safety.py`, `tests/test_live_position_management.py`, `tests/test_forex_symbols.py`, and `tests/test_logic_fixes.py` were not executed. They import the operational config path. They were not rewritten and were not weakened.

`tests/test_forex_symbols.py` expects `AUD_USD` 12, `usd/cad` normalised to `USD_CAD` at -7, and `USD_CHF` 3, with missing trade IDs allowed. The R.70 parser accepts that shape; the R.70 suite covers the `usd/cad` negative-short form. The legacy module itself remains not executed.

`tests/test_logic_fixes.py` expects `RuntimeError` matching `unavailable` when the client is missing. The new `UNKNOWN` message contains that word. The legacy module itself remains not executed. The R.70 suite does call the real fetch with a missing client and observes `UNKNOWN`.

## PostgreSQL

Several successful reconciles log `PostgreSQL unavailable: postgres blocked`. That is the isolation harness refusing `psycopg2.connect`. It is not a database integration test.

`POSTGRESQL_INTEGRATION_NOT_TESTED`
`REAL_NETWORK_EXECUTION_NOT_TESTED`
