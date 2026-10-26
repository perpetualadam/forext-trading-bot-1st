# R56_PHASE2_OFFLINE_DIAGNOSTIC_LOGGER_REPORT

Overall: **PASS**

The result is an offline logger and a synthetic test suite. It is not an authenticated OANDA session and it is not a production data-only mode.

## Production functions inspected

Claims in `R56_EXISTING_BOT_DIAGNOSTIC_INSPECTION_REPORT.md` were checked against source. They match the current files.

| Claim | Source |
| --- | --- |
| Process entry is `main.py`, not the R.55 connector | `main.py` lines 19–25, `uvicorn.run("forex_bot.app:app")` |
| Account read | `forex_bot/oanda_client.py` `fetch_account_summary` lines 140–194, request at line 154, raw `data` at line 156 |
| Account parse | `forex_bot/oanda_account_adapter.py` `account_core` lines 24–69 |
| Pricing read | `forex_bot/oanda_client.py` `fetch_pricing_snapshot` lines 503–584, params at line 542, raw `data` at line 544 |
| Client construction reads the token | `build_api` lines 104–126. This phase did not call it |
| New-order tail returns before `OrderCreate` | `forex_bot/bot_loop.py` lines 1704–1706 |
| `OrderCreate` still exists | `forex_bot/oanda_exec.py` line 504 |
| `PositionClose` remains reachable from a live-kind close | `forex_bot/trading.py` `execute_trade` lines 391–398, `oanda_exec.py` line 423 |
| Sizing uses approximate USD | `forex_bot/trading.py` `quote_pnl_to_account_ccy` lines 148–160 |
| `MAX_POSITION_UNITS` at 0 disables the cap | `trading.py` `cap_position_units` lines 230–235 |
| `MIN_STOP_DISTANCE_PRICE` at 0 does not floor the stop | `trading.py` `position_sizing` lines 316–318 |
| `1.35` is not in those sizing functions | Confirmed by reading them. Research and shadow fallbacks were not changed |

`DATA_ONLY_MODE_NOT_PROVEN_SAFE` remains true for the production process.

## Architecture

Four stages, plus a writer:

- `response_adapter.py` accepts a dictionary or JSON and extracts allowlisted fields.
- `account_diagnostics.py` records home currency only from `currency`.
- `pricing_diagnostics.py` records bid, ask, and a quote-unit spread when the prices are valid.
- `sizing_diagnostics.py` stores supplied figures and does not size a trade.
- `diagnostic_writer.py` writes schema `r56.phase2.1` under `synthetic_logs` only.

`launch` processes local fixtures. Activation arguments return exit code 2.

## Schema

The envelope is `schema_version`, `collected_at`, `data_source`, `session_id`, `record_kind`, `outcome`, `missing_evidence`, `validation_warnings`, and `executable_order`.

Account currency, when missing or not a three-letter code, is `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. Pricing conversions, when absent, are `HOME_CONVERSION_NOT_VERIFIED`. Quote age is `QUOTE_FRESHNESS_NOT_VERIFIED` even when a timestamp parses. Pip spread is `NOT_CALCULATED`. GBP pip value status is `UNVERIFIED`. Stake mapping is `NOT_VERIFIED`.

## Example sanitised synthetic output

This account record was produced by the offline writer from `synthetic_fixtures.account_document`. The session id below is a fixed test value, not a random live id. The account id and alias are not in it.

```json
{
  "account_id_logged": false,
  "account_id_present": true,
  "account_identity_verified": false,
  "account_type": "NOT_RETURNED",
  "balance": "100.00",
  "balance_source": "BROKER_REPORTED",
  "data_source": "SYNTHETIC_TEST_ONLY",
  "executable_order": "NOT_PRODUCED",
  "home_currency": "GBP",
  "home_currency_is_gbp": true,
  "home_currency_source": "BROKER_REPORTED",
  "margin_available": "100.00",
  "margin_used": "NOT_RETURNED",
  "margin_used_operational_capture": "NOT_PARSED_BY_OPERATIONAL_CLIENT",
  "nav": "100.00",
  "outcome": "DIAGNOSTIC_RECORDED",
  "record_kind": "account_summary",
  "schema_version": "r56.phase2.1"
}
```

A matching synthetic EUR_USD quote stored bid `1.10000`, ask `1.10020`, spread_price `0.00020` with source `BOT_CALCULATED`, spread_pips `NOT_CALCULATED`, and `home_conversion` `HOME_CONVERSION_NOT_VERIFIED`.

## Security boundaries

- No production import, executed or declared.
- Socket and DNS calls from the test process are replaced and raise `network_blocked`.
- No credential read, no token prompt, no HTTP client.
- Full account ids, aliases, bearer values, and exception text are excluded from output.
- Failure outcomes are `REJECTED` and do not use `DIAGNOSTIC_RECORDED`.
- Logs cannot be written outside `phase2_offline/synthetic_logs`.

## Tests

35 passed, 0 failed, 0 skipped, in 0.59 seconds. Details are in `05_test_results.md`.

## Remaining broker-data gaps

These are unchanged, because this phase does not contact OANDA:

- Home currency on the real account: unverified.
- Account type, including spread bet versus CFD: no operational field, so the logger records `NOT_RETURNED`.
- Pip location and display precision: not in the operational pricing response. Pip spread is not calculated.
- Home conversions: not requested by `fetch_pricing_snapshot`. A supplied document can carry them, and the record says the operational request does not ask for them.
- Financing: not read.
- GBP pip value and stake-to-unit mapping: `UNVERIFIED` and `NOT_VERIFIED`.
- Margin used: recorded only when a supplied document contains `marginUsed`. The operational snapshot does not copy it.
- Quote freshness: not judged.

## Minimal future integration

Pass a deepcopy of `fetch_account_summary`'s local `data` at `oanda_client.py` line 156, and of `fetch_pricing_snapshot`'s local `data` at line 544, into this adapter. Do that from an entry that does not import `app`, `bot_loop`, `trading`, `execution`, or `oanda_exec`.

That entry does not exist. Importing `oanda_client.py` loads `Config` and the token-backed `API` object. `oanda_exec.py` uses the same object for `OrderCreate` and `PositionClose`. Starting `main.py` remains unsafe. `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.

Do not add `includeHomeConversions` or an instruments request in a log-only change. Both change the request.

## Confirmation

The bot was not started. No OANDA connection was made. No credential was read. No order was placed. No production file and no R.55 file was modified. The inspection report was not modified.

Hashes are listed in `06_integrity_manifest.json` after this file is sealed. The manifest hash is reported with the chat result so this file does not need to be rewritten.
