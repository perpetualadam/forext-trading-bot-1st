# Stage R.27 — OANDA account contract and risk-data adapter

**Classification: `R27_OANDA_ACCOUNT_CONTRACT_PARTIAL`**

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Existing work was left in place. No commit, reset, stash, clean, deploy, or rollback.

**PRODUCTION DEPLOYMENT: NO-GO**
**PRACTICE ORDERS: NOT AUTHORISED**
**LIVE TRADING: NOT AUTHORISED**
**ROLLBACK: NO-GO**

R.28 was not started. No OANDA endpoint was contacted. No `.env`, credential, or operational account file was read. No PostgreSQL connection was opened and the isolated R.24 cluster was not started. The six strategies were not activated. Production risk thresholds were not selected.

The fully validated classification is withheld because essential OANDA financial semantics are still unverified in local evidence. The offline adapter tests passed.

## 1. Contract inventory

Local sources, read from disk:

| Source | What it establishes |
| --- | --- |
| Installed `oandapyV20/endpoints/accounts.py` | `AccountSummary` is `GET v3/accounts/{accountID}/summary`. `AccountDetails` is `GET v3/accounts/{accountID}` and is documented as including pending orders, open trades, and open positions. |
| Installed `oandapyV20/endpoints/responses/accounts.py` | Example account objects contain separate `id`, `currency`, `NAV`, `balance`, `unrealizedPL`, `marginAvailable`, `marginUsed`, `marginCloseoutPercent`, `marginCloseoutNAV`, and `lastTransactionID`. Position examples use `instrument`, `long.units`, `short.units` (the short example is a signed string), and `averagePrice`. Order examples use `state: "PENDING"`, signed `units`, `price`, `id`, and `partialFill: "DEFAULT_FILL"`. |
| Installed `oandapyV20/endpoints/transactions.py` and `responses/transactions.py` | A transaction list example returns `pages` URLs, not transaction bodies. A since-id example returns transaction objects with contiguous numeric ids through `lastTransactionID`. Sample types include `LIMIT_ORDER`, `ORDER_CANCEL`, `CLIENT_CONFIGURE`, and `HEARTBEAT`. |
| `forex_bot/oanda_exec.py` `_parse_fill` | This repository treats `orderFillTransaction.pl` as realised P&L in account currency, with `price`, `units`, `id`, and `time`. |
| `forex_bot/oanda_client.py` `fetch_account_summary` | The live-facing summary helper. Before this stage it copied balance into NAV. |
| `forex_bot/account_reconciliation.py` | R.26 normalization, durable ledger, and provenance gate. |
| `forex_bot/execution_risk.py` | R.25 daily-loss, drawdown, and exposure checks. |
| `forex_bot/bot_loop.py` `evaluate_one_instrument_iteration` | Shared evaluate, reservation, and inert dispatch path. |

The only substitution of balance for a missing NAV was in `fetch_account_summary`:

```python
nav = float(str(acct.get("NAV") or acct.get("balance") or "0").replace(",", ""))
...
balance = nav  # used when balance failed to parse
```

Malformed numbers became `0.0`, including `marginAvailable`. A failed parse still called `set_broker_account`. No other `get("NAV") or` site was found. `bot_loop.py` reads a cached summary for shadow exposure reporting; it was not the substitution site and was not given a new fallback.

## 2. Verified fields and provisional fields

Verified from the local client fixtures or from this repository's own fill parser:

- Account `id` and `currency` are separate strings.
- `NAV`, `balance`, and `unrealizedPL` are separate numeric strings. In the details example they are not equal to one another. The summary example happens to show NAV equal to balance while unrealised P&L is zero. That coincidence is not an identity rule.
- `marginAvailable`, `marginUsed`, `marginCloseoutPercent`, and `marginCloseoutNAV` appear in the account examples. They are not used as risk limits. `fetch_account_summary` still omits `marginUsed` and `marginCloseout` so the R.19 source checks remain intact.
- Open positions carry signed `long.units` and `short.units`. The local short example is negative.
- A pending order has `state: "PENDING"`. `partialFill: "DEFAULT_FILL"` is a fill policy on that pending order, not evidence of a partially filled order.
- `lastTransactionID` is a numeric string. The since-id sample is contiguous up to that id.
- Transaction-list `pages` are URLs. Those URLs were not requested.
- `orderFillTransaction.pl` is realised P&L in account currency for an order-create response in this repository.

Provisional, and therefore fail-closed:

- `observed_at` is a test stamp added to injected documents. It is not an OANDA field. `createdTime` is not used as snapshot freshness.
- Financing, commissions, fees, deposits, withdrawals, corrections, and reversals have no local ledger rule. Those rows return `pnl_classification_unresolved`.
- The type name `ORDER_FILL` does not appear in the local transaction fixtures. A bare object of that type is unresolved. Only the evidenced `orderFillTransaction` object becomes `trade_pl`.
- `PARTIALLY_FILLED`, `CANCELLED`, `FILLED`, and `UNRESOLVED` order states are not in the local account example. They return `order_state_unverified`. Filled exposure is accepted only as a position.
- A position with both sides open, or a positive `short.units` value, returns `position_book_unresolved`. The local example does not define hedge netting.
- An instrument whose quote currency differs from the account currency returns `exposure_conversion_missing`. No conversion identity was invented.
- A summary without explicit `positions` and `orders` arrays is not a complete risk book and returns `position_book_missing` or `order_book_missing`.
- `NAV == balance + unrealizedPL` is not applied, even though one local example happens to satisfy it.

## 3. NAV fallback repair

`fetch_account_summary` now parses through `account_core`. Missing NAV returns `broker_equity_missing` even when balance is present. Non-finite or non-numeric NAV returns `broker_value_nonfinite`. NAV at or below zero returns `broker_equity_invalid`. Missing or non-positive balance is its own failure and is not copied from NAV. A request exception, an error payload, or a parse failure clears `_account_summary`, returns `None`, and does not call `set_broker_account`. A previous in-memory `broker_nav` is left unchanged. A successful parse caches the NAV field and the balance field separately.

The shared evaluate path accepts an injected OANDA-shaped document through `IterationDependencies.oanda_summary` and `oanda_transactions`. `normalize_oanda_risk_inputs` runs before `reconcile_for_entry`. An adapter rejection returns immediately, with reservation still false. When those fields are absent, the R.26 injected-snapshot path is unchanged. `evaluate_one_instrument_iteration` does not contain the string `fetch_account_summary`.

`account_reconciliation.py` now accepts provenance `injected_synthetic` and `oanda_account_summary`. Any other provenance, including `live`, remains `broker_provenance_rejected`.

## 4. Adapter fixtures

All fixtures are synthetic and labelled by the test module. They follow the local field names above.

Account summaries: valid NAV and a different balance; missing NAV with a valid balance; missing balance; wrong id; wrong currency; malformed, NaN, infinite, and negative NAV; stale and future `observed_at`; an empty body; an `errorMessage` payload.

Positions and orders: a long `EUR_USD` and a short `GBP_USD`; a `PENDING` order whose `partialFill` is `DEFAULT_FILL`; a position plus a pending order on the same symbol; `PARTIALLY_FILLED`, `CANCELLED`, `FILLED`, and `UNRESOLVED` states; both sides open; an `EUR_GBP` position against a USD account.

Transactions: an `orderFillTransaction` with `pl`; out-of-order ids `2` then `1`; a gap between `1` and `3`; duplicate id `1`; an empty page whose `lastTransactionID` is `4`; a since-id-shaped page `2307`–`2311`; `pages` without bodies; `LIMIT_ORDER`, `DAILY_FINANCING`, `TRANSFER_FUNDS`, bare `ORDER_FILL`, and `CLIENT_CONFIGURE`.

## 5. Adapter-to-reconciliation integration

The tests call `evaluate_one_instrument_iteration` with `simulation=True` and `FakeBroker`. No production launcher and no real order function ran.

A valid document with NAV `10000` and balance `10010` reconciled to NAV `10000`, source `broker_nav`, status `verified`, account `101-004-1435156-001`, currency `USD`. The phase order was `account_reconciliation`, then `execution_risk`, then `reservation`. The inert broker recorded one request. `production_eligible` stayed false.

The same path stored long and short positions, counted a `DEFAULT_FILL` order as `PENDING`, and counted a position together with a pending order. Realised P&L from ids `1` and `2`, supplied out of order, summed to `2.5` once.

## 6. Shared evaluate blocking

Every invalid, stale, incomplete, or unreconciled case returned a specific reason, `reservation_attempted == false`, `broker_requests == 0`, and `production_eligible == false`. The durable file was unchanged for those rejections.

Reasons exercised: `broker_equity_missing`, `broker_balance_missing`, `broker_account_mismatch`, `broker_currency_mismatch`, `broker_value_nonfinite`, `broker_equity_invalid`, `account_snapshot_stale`, `account_timestamp_future`, `broker_response_invalid`, `order_state_unverified`, `position_book_unresolved`, `exposure_conversion_missing`, `total_exposure_limit`, `transaction_pages_incomplete`, `pnl_classification_unresolved`, `event_gap`, `risk_state_missing`, `risk_state_unreadable`, `daily_realised_loss_limit`, and `max_drawdown_limit`.

A missing state file was not created. A corrupt file stayed corrupt.

`fetch_account_summary` was exercised only with a stubbed `get_api` and `_oanda_request`. A raised request and a balance-only body both returned `None`, cleared the cache, and did not call `set_broker_account`. A body with NAV `35454.4740` and balance `35524.8000` cached those two values separately.

## 7. Separate-process restart

Two operating-system processes shared an isolated synthetic state file. The child process installs its own socket and DNS barrier.

| Check | Writer PID | Reader PID | Result |
| --- | --- | --- | --- |
| Daily-loss baseline and realised loss | 16184 | 15580 | Reader blocked `daily_realised_loss_limit`. Realised stayed `-200`. Account id survived. Broker requests `0`. |
| Drawdown peak | 12088 | 19748 | Peak rose to `11000`, then the reader blocked `max_drawdown_limit` at equity `10450`. |
| Pending exposure | — | 5920 | Order `204` remained and blocked `total_exposure_limit`. |
| Replay | — | 1680 | Realised stayed `-50`. Event ids stayed `["1"]`. |
| Incomplete history | — | 20240 | `event_gap`. Realised stayed `-50`. Reservation was not attempted. |

The drawdown writer used the inert fake broker once, while the new peak was inside the limits. The reader did not. No production order function was called.

## 8. Regression results

Focused R.27: **10 passed, 0 failed, 0 skipped, 0 deselected.**

The offline runner then ran R.26 back through R.8 behind the socket, DNS, and dotenv barriers. Pytest counts:

| Suite | Result |
| --- | --- |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 | 69 passed, 5 skipped |
| R.11 first attempt | 50 passed, 1 failed, 5 skipped |
| R.11 retry | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

The R.11 failure was `test_i35_live_permission_remains_blocked`. Windows denied `os.replace` on `data/research/adaptive_ensemble/r11/synthetic_live_safety_state.json` (`WinError 5`). `live_safety.py` was not changed and the file was not deleted. The same suite then passed. No assertion was weakened and the shared evaluate path was not mocked.

`pytest_isolation_log.txt` records the first full-suite `r11_exit=1` and `r11_retry_exit=0`. Every other suite exited 0.

## 9. Source files and hashes

SHA-256 of the working-tree bytes. The before values are the R.26 working-tree hashes recorded before this edit.

| File | Before | After |
| --- | --- | --- |
| `forex_bot/bot_loop.py` | `dc7c229fe09c9c2adafdcc1ed4c96c9ad534a67758773069049d3d4c5ce02683` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/oanda_client.py` | `6d7d5d2b6ce1c228af0629c3e2a8b674b02965c57d1a3ed41c3b4015e531ca2b` | `02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a` |
| `forex_bot/account_reconciliation.py` | `73e2b24bb17f576c5eabb1e4a730483ef89c87d8e419034a5a9c7bf2b4f7164a` | `300feb0363a7182cd20dc24effeaee575e9669f35c97e8c567242c2bb5620c72` |
| `forex_bot/oanda_account_adapter.py` | new file | `191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5` |

Unchanged by this stage: `forex_bot/execution_risk.py` `8ffa0ef4b38ded1f0aa72362352d0935f43071b4df85f4531be014c889d09661`, `forex_bot/database.py` `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6`. The R.8, R.10, and R.11 source pins for `bot_loop.py` were updated to the new hash.

New tests: `tests/test_r27_oanda_account_contract.py`, `tests/r27_restart_driver.py`, and `data/research/adaptive_ensemble/r27/20_run_offline_tests.py`.

## 10. Unresolved contract questions and production blockers

These remain open, so the stage is partial:

- No local rule says how financing, commissions, fees, deposits, withdrawals, corrections, or reversals change the durable ledger.
- The transaction type string `ORDER_FILL` is not in the local transaction fixtures. Only `orderFillTransaction.pl` is evidenced, and only as an order-create field in this repository.
- Transaction history that begins above id `1`, including the local since-id sample `2307`–`2311`, cannot prove continuity and fails closed.
- Page URLs in a transaction list were not fetched. A pages-only response is incomplete.
- Margin used and margin closeout are present in the local account example and are not risk inputs.
- Quote conversion for a non-account currency is unresolved.
- `observed_at` is a harness timestamp. OANDA account freshness for a live summary is still unresolved.
- The R.24 PostgreSQL reservation deadlock is unchanged. Processes 10224 and 18916 competed for `NZD_USD`. PostgreSQL aborted one transaction inside `insert_exec_order_pending_if_absent` after `pg_advisory_xact_lock`, with `RowExclusiveLock` against `AccessExclusiveLock` on relation 16428 of database 16389. Locking was not modified and PostgreSQL was not started.

Production trading remains unauthorised. Practice orders remain unauthorised. This stage does not authorise a live or practice account read.
