# R.44 six-instrument contract matrix

Shared facts, then one row per instrument. Broker stake, margin, financing, stops, and fees are `UNKNOWN` for every row. No spread, margin, or financing number was invented. The historical files contain bid and ask for these names. That is a property of the files, not a current quote and not a fee schedule.

Shared implementation:

- Names are `BASE_QUOTE` in `forex_bot/symbols.py` `DEFAULT_FOREX_SYMBOLS`. Class `LOCALLY_VERIFIED_IMPLEMENTATION` for the code list. Broker name match is `UNKNOWN`.
- `quote_currency` takes the text after the underscore. That parse is local. It does not prove the broker instrument.
- Non-JPY pip size `0.0001` and JPY pip size `0.01` appear in `timeframes.research_pip_size`, `shadow/accounting.pip_size`, and the research pip maps. Class `LOCALLY_VERIFIED_IMPLEMENTATION` for the convention. Broker pip location is `UNKNOWN`.
- `oanda_exec._format_oanda_price` writes three decimals when the name contains `JPY` and five otherwise. The comment attributes that to OANDA. The format is implemented. The broker precision for this account is `UNKNOWN`.
- Sizing speaks in units, not stake. `shadow/accounting.units_for_notional` says "Whole OANDA units". Minimum size, increment, and GBP per point are `UNKNOWN`.
- If account currency is not the quote currency, `oanda_account_adapter._positions` returns `exposure_conversion_missing`. None of these six quotes is GBP, so a GBP account would fail that check until a conversion exists. That is an implementation fact, not proof the account is GBP.
- Margin, leverage, trading hours, guaranteed stops, financing, weekend charges, and commission are `UNKNOWN`. No guaranteed-stop field was found in the modules reviewed.
- Stop trigger side in `entry_geometry.sl_trigger_side` is bid for a long and ask for a short. That is a code assumption labelled as OANDA default. It is not an account stop-distance rule.

| Instrument | Base | Quote | Pip convention | Price-format convention | Position-value path in `trading.py` |
| --- | --- | --- | --- | --- | --- |
| EUR_USD | EUR | USD | 0.0001 | 5 decimals | Quote P&L treated as already account currency, and the function calls that currency USD |
| GBP_USD | GBP | USD | 0.0001 | 5 decimals | Same USD-account path |
| AUD_USD | AUD | USD | 0.0001 | 5 decimals | Same USD-account path |
| USD_CAD | USD | CAD | 0.0001 | 5 decimals | USD-base path: quote P&L divided by mid |
| USD_CHF | USD | CHF | 0.0001 | 5 decimals | USD-base path: quote P&L divided by mid |
| USD_JPY | USD | JPY | 0.01 | 3 decimals | USD-base path: quote P&L divided by mid |

Shadow accounting then divides a USD figure by GBP_USD mid, or by `gbp_usd_fallback` 1.35 if no mid is supplied. That fallback is `ASSUMPTION_ONLY`. It is a second currency model, not the `trading.py` model. See the accounting review.

Paper half-spreads in `shadow/cost_model.py` are estimates: EUR_USD, AUD_USD, USD_CAD, and USD_CHF 0.0001; GBP_USD 0.00015; USD_JPY 0.01. The same file also stores constants labelled as past fill-minus-mid means. Those order records were not reopened. The constants are not a current spread. Class `ASSUMPTION_ONLY` if used as a spread.
