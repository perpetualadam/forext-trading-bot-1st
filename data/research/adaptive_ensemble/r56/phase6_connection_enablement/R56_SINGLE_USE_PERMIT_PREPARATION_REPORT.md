# R.56 single-use permit preparation

## 1. Overall result

**PASS**

One activation permit was created by the existing preparation entry point. The diagnostic was not launched.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

## 2. Preflight results

All eight checks passed before the entry point was run.

1. `live_session_gate.py` contains `REAL_SESSION_SOURCE_ENABLEMENT = True`.
2. Its SHA-256 is `80c762692b5812aba965927cfca6afa147655e48795eafc5f6eda2f45495cb05`.
3. `prepare_one_session.py` SHA-256 is `59561926aca5f275ee38dee79206c44c9e8ad02c6f098392c667c95e70e7812d`.
4. `one_session_activation.py` SHA-256 is `2dd386c5607bf6e2af6a32ad7adfb40f7bb3af7ff07e471632ab5dd26806b3b5`.
5. `real_activation/one_session.permit` did not exist.
6. `real_activation/one_session.consumed` did not exist. The `real_activation` directory itself did not exist.
7. No production trading bot and no R.56 diagnostic process was running.
8. The other Phase 6 executable hashes matched the source-gate enablement report. No unexpected executable change was present.

## 3. Preparation entry point

`prepare_one_session.py` was run once from the project root, with no arguments. It exited 0 and printed `ONE_SESSION_PERMIT_CREATED`. It was not run again.

## 4. Permit and binding

`real_activation` contains exactly one file, `one_session.permit`.

The permit has only the seven binding fields. They match the unchanged two-request plan: schema `r56.phase6.activation.1`, program `r56.phase6.real_session_entry`, plan `r56.phase6.two-get.1`, host `api-fxtrade.oanda.com`, port `443`, requests `summary` then `pricing`, and methods `GET` then `GET`. There are no extra fields. The permit file was not edited by hand.

## 5. Consumed marker

`one_session.consumed` does not exist. The permit was not consumed.

## 6. Source gate

`REAL_SESSION_SOURCE_ENABLEMENT = True`.

SHA-256 of `live_session_gate.py` remains `80c762692b5812aba965927cfca6afa147655e48795eafc5f6eda2f45495cb05`.

## 7. Executable source

No executable source file was modified. The Phase 6 hashes listed in the preflight are unchanged, as are:

- `main.py` `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`
- `forex_bot/oanda_client.py` `02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a`
- `forex_bot/oanda_account_adapter.py` `191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5`

## 8. Production bot

After preparation, no process command line contained `main.py`, `real_session_entry`, `prepare_one_session`, `diagnostic_supervisor`, or `diagnostic_worker`. No process was started or stopped by this check.

## 9. Credentials

No credential was requested or read. No `.env` file was read. The permit fields do not include a token or an account identifier.

## 10. OANDA

No connection to OANDA Live or Practice was attempted.

## 11. Diagnostic

No diagnostic worker or supervisor was launched. `real_session_entry.py` was not run.

## 12. Trading

No production trading process was started. No order was placed, modified, or closed.

## 13. Uncertainty

One Python process was already running before this task: `scripts.prospective_cycle --start 2026-10-01`, process id 13276. It is not the production trading bot and not an R.56 diagnostic. It was left running.

The permit outcome is not ambiguous. The entry point was not retried.

## 14. Standing limit

`REAL_NETWORK_EXECUTION_NOT_TESTED`

The permit is not permission to launch the diagnostic.
