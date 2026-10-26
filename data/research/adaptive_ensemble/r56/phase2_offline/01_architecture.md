# R.56 phase 2 architecture

The diagnostic logger is a separate tree under `phase2_offline`. It does not import `forex_bot`, does not construct an OANDA client, and does not start `main.py`.

## Parts

| Part | File | Role |
| --- | --- | --- |
| Response adapter | `response_adapter.py` | Accept a dictionary or JSON text. Recognise only an explicit field set. Collect sensitive literals so they can be blocked from output. |
| Account diagnostics | `account_diagnostics.py` | Copy currency, balance, NAV, margin available, unrealised P/L, and margin used when that key is present. |
| Pricing diagnostics | `pricing_diagnostics.py` | Copy the first bid and ask strings, timestamp, and tradeable flag. Calculate a quote-unit spread only when both prices are valid. |
| Sizing diagnostics | `sizing_diagnostics.py` | Record caller-supplied numbers. Do not compute a size. |
| Writer | `diagnostic_writer.py` | Stamp the allowlisted envelope and write one JSON file under `synthetic_logs`. |
| Fixtures | `synthetic_fixtures.py` | Local documents only. |

`launch` with no arguments, or with only `--synthetic`, writes three synthetic records and prints:

`R56 phase 2 diagnostic entry is offline. No credential prompt. No network connection.`

`--live`, `--connect`, `--authenticate`, `--account`, any other flag, and any positional argument return exit code 2 and write nothing.

## What the adapter treats as operational fields

Account fields recognised because `account_core` reads them:

- Wrapper `account`, or the account object itself.
- `id` (detected, never written).
- `currency`, `NAV`, `balance`, `unrealizedPL`, `marginAvailable`.
- `alias` and `lastTransactionID` are recognised and dropped.

`marginUsed` is accepted when present and labelled `NOT_PARSED_BY_OPERATIONAL_CLIENT`. `fetch_account_summary` does not copy it.

Pricing fields recognised because `fetch_pricing_snapshot` reads them:

- `prices[]`, `instrument`, `bids[].price`, `asks[].price`.
- `time`, `tradeable`, `status`, `closeoutBid`, `closeoutAsk`.

`quoteHomeConversionFactors` and `homeConversions` are recognised only so a supplied document can be recorded. The operational `PricingInfo` call does not send `includeHomeConversions`. The record says `NOT_REQUESTED`.

No account-type field and no account reporting timestamp are read by `fetch_account_summary`. Those outputs stay `NOT_RETURNED`. An unknown key such as `division` is dropped rather than promoted to account type.

## Spread and freshness

Spread in price units is `ask - bid` using `Decimal`, and only when both strings are positive and ask is greater than bid. The result is marked `BOT_CALCULATED`.

Spread in pips is `NOT_CALCULATED`. Pip location is not in the operational pricing response.

A parseable timestamp is stored as the original string. `quote_freshness` is always `QUOTE_FRESHNESS_NOT_VERIFIED`. This logger does not apply an age limit.

## Sizing

The sizing record is not an OANDA response. Every supplied number keeps the caller's source label when that label is one of `BROKER_REPORTED`, `BOT_CALCULATED`, `SYNTHETIC_TEST_ONLY`, or `UNVERIFIED`. Missing labels become `UNVERIFIED`.

`gbp_pip_value_status` stays `UNVERIFIED`. `stake_to_unit_mapping` stays `NOT_VERIFIED`. `sizing_formula_status` is `NOT_REUSED`. `order_payload` is `NOT_PRODUCED`.
