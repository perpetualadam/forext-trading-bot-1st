# R56_PHASE3_ISOLATED_DATA_ONLY_COLLECTOR_REPORT

Overall: **PASS**

The collector is an offline program. It does not connect to OANDA and it does not start the trading bot.

## Architecture

`collector_main.py` runs only with `--offline`. `readonly_request_plan.py` defines summary then pricing. `readonly_request_gate.py` rejects every other request before transport. `offline_transport.py` returns synthetic dictionaries. `collector_session.py` validates summary, then pricing, then calls the Phase 2 adapters and writes one `r56.phase3.1` record.

The pricing instruments are `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `USD_CAD`, `USD_CHF`, matching `forex_bot/symbols.py` `DEFAULT_FOREX_SYMBOLS`. The query key is only `instruments`, matching `fetch_pricing_snapshot` line 542.

## Phase 2

`account_diagnostics.build`, `pricing_diagnostics.build`, and `diagnostic_writer.stamp` are loaded from `phase2_offline` by file path. Phase 2 files were not edited. `write_record` stays in the Phase 2 log directory, so Phase 3 writes its own outer record around the stamped Phase 2 bodies.

## Example

A synthetic session recorded `SESSION_COMPLETE_SYNTHETIC`, home currency `GBP` with source `BROKER_REPORTED` from the fixture, `account_id_logged` false, EUR_USD bid `1.10000`, ask `1.10020`, spread `0.00020`, spread pips `NOT_CALCULATED`, and `HOME_CONVERSION_NOT_VERIFIED`. Session fields include `QUOTE_FRESHNESS_NOT_VERIFIED`, `GBP_PIP_VALUE_UNVERIFIED`, `STAKE_TO_UNIT_MAPPING_NOT_VERIFIED`, `FINANCING_NOT_VERIFIED`, `executable_order` `NOT_PRODUCED`, and `gbp_conversion_fallback` `NOT_USED`. The account id was not in the file. The GBP currency is the synthetic fixture, not a broker confirmation.

## Tests

48 passed, 0 failed, 0 skipped, in 0.37 seconds.

## Limits

These two responses do not establish pip location, home conversion, a GBP pip value, stake-to-unit mapping, financing, quote age, an executable size, or strategy profitability. No `1.35` fallback is present.

The production bot remains `DATA_ONLY_MODE_NOT_PROVEN_SAFE`. This gate does not open a socket. A later real session needs its own authorisation, a transport that can carry only the approved GET descriptions, and a process that does not import the order modules.

## Confirmation

The bot was not started. No credential was read. No network connection was made. No order was placed. Phase 2 and the inspected production files were not modified.

File hashes are in `06_integrity_manifest.json`. The manifest hash is reported with the chat result.
