# R.57 GBP spread-betting risk and position sizing audit

## 1. Executive result

**FAIL**

Production trading is not safe on this OANDA Live GBP account. The live sizing path treats quote-currency profit and loss as if it were the account currency, and the comments call that currency USD. It does not convert the result to GBP. It does not define a spread-betting stake, and it does not read broker pip location, minimum size, margin rate, or financing. A wrong unit meaning on a spread-betting contract can make the real GBP loss many times the intended budget. No trade should be placed until those facts are verified and the bot refuses to trade when they are missing.

This audit did not call OANDA, did not read credentials, did not change executable source, and did not change any R.56 activation file.

## 2. R.56 diagnostic evidence

`R56_FIRST_LIVE_DIAGNOSTIC_REPORT.md` does not confirm a successful live session. That file records **FAIL**. It says the summary and pricing requests were not attempted, home currency was not observed, no quotes were received, and the permit was not consumed. It does record that the source gate was restored to `False` and that no order was attempted. Those last two statements were true of the aborted attempt described in that file.

A later operator run, not described in that report, wrote one sanitised log:

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_diagnostic_logs/r56-phase6-r561f34518e0da44a79a0477cad84ee53a3-0001.json`

Collected at `2026-10-24T17:09:36Z`. From that log, and from the activation directory as it stands now:

- Summary and pricing both have result `BROKER_RESPONSE_RECEIVED`. Session error is `NONE`. Two children started. `child_alive` is false. `record_persisted` is true.
- Home currency is `GBP`, with `home_currency_is_gbp` true. The account id was not written into the log.
- All six instruments have a broker-reported bid and ask.
- Every quote has `tradeable` false and status `non-tradeable`. Quote timestamps are `2026-10-23T20:59:05Z`, about twenty hours before the session. They are stale weekend prices and are not executable.
- `real_activation` now contains only `one_session.consumed`. The permit file is absent.
- `REAL_SESSION_SOURCE_ENABLEMENT = False` in `live_session_gate.py`.
- `executable_order` and `order_payload` are `NOT_PRODUCED`. No order endpoint was part of that session.

The log also contains balance, NAV, and margin available of `97.1539`, and margin used of `0.0000`. Those figures are a historical snapshot. They are not a live balance.

## 3. Production sizing call graph

The live entry path in `forex_bot/bot_loop.py` does this:

1. Around lines 1425–1432, `sl_tp_distance_for_entry` sets the stop distance, `current_equity()` supplies the balance, and `position_sizing` returns units. Units are then scaled by portfolio weight and confidence unless a notional percentage is set, then passed through `cap_position_units`.
2. Around lines 3684–3804, a later iteration path blocks on account presence, then calls the same `position_sizing` with the accepted equity. Margin is explicitly not evaluated: lines 3701–3703 set `equity_is_not_margin_proof` true, `margin_evidence` to `not_implemented`, and `margin_sufficiency` to `NOT_EVALUATED`.
3. Around lines 3860–3921, a gross-notional cap and `portfolio_risk_cap_exceeded` can block. Both use the same USD-shaped conversion as the sizer.

The calculation functions are:

| Step | Function | Location |
| --- | --- | --- |
| Equity used for size | `current_equity` and the accepted snapshot balance | `forex_bot/state.py`, called at `bot_loop.py` 1428 and 3697 |
| Risk budget | `position_sizing` | `forex_bot/trading.py` 278–325 |
| Stop distance | `sl_tp_distance_for_entry`, `sl_tp_price_distances` | `forex_bot/trading.py` 92–135 |
| Pip size | `pip_size` | `forex_bot/profit_protection.py` 73–80 |
| Account P/L | `quote_pnl_to_account_ccy`, `stop_risk_account_ccy`, `pnl_account_ccy` | `forex_bot/trading.py` 142–189 |
| Spread and slippage | `apply_execution_costs`, `simulated_half_spread` | `forex_bot/trading.py` 73–109 and 243–275 |
| Notional units | `units_for_account_notional` | `forex_bot/portfolio_exposure.py` 75–85 |
| GBP to USD fallback | `account_ccy_to_usd` | `forex_bot/portfolio_exposure.py` 23–72 |
| Unit ceiling | `cap_position_units` | `forex_bot/trading.py` 230–235 |
| Book cap | `portfolio_risk_cap_exceeded` | `forex_bot/trading.py` 211–227 |
| Minimum of 1 unit | `return max(units, 1.0)` | `forex_bot/trading.py` 325 |
| Shadow-only GBP path | `stop_risk_gbp`, `units_for_notional`, `usd_to_gbp` | `forex_bot/shadow/accounting.py` 50–131 |

`position_sizing` states at lines 286–296 that it is not affected by practice versus live, and that broker margin and maximum position are not modeled. The account-currency helpers at lines 148–151 say they convert to approximate account USD. `portfolio_exposure.py` line 1 calls the exposure math a USD-quoted heuristic. `account_ccy_to_usd` uses a hardcoded GBP rate of `1.35` when no `GBP_USD` mid is stored (lines 23–24 and 68–72). That number is not a verified rate and must not be used as one.

No production function reads `pipLocation`, `minimumTradeSize`, `tradeUnitsPrecision`, `marginRate`, or a financing rate. A search of `forex_bot` found no spread-betting stake model.

Tradeable status is checked in `forex_bot/entry_geometry.py` around line 286 and in `forex_bot/live_manage.py` around line 65. The primary `bot_loop.py` sizing calls above do not consult that flag before computing units.

## 4. Instrument mathematical model

These identities are conventional FX. They are not an OANDA spread-betting contract. Stake-to-unit mapping, financing, and broker pip metadata are **UNVERIFIED**. The R.56 prices are historical examples only.

| Instrument | Base | Quote | Conventional pip | P/L currency of one currency unit | GBP conversion required |
| --- | --- | --- | --- | --- | --- |
| EUR_USD | EUR | USD | 0.0001 | USD | USD to GBP |
| GBP_USD | GBP | USD | 0.0001 | USD | USD to GBP |
| USD_JPY | USD | JPY | 0.01 | JPY | JPY to USD, then USD to GBP |
| AUD_USD | AUD | USD | 0.0001 | USD | USD to GBP |
| USD_CAD | USD | CAD | 0.0001 | CAD | CAD to USD, then USD to GBP |
| USD_CHF | USD | CHF | 0.0001 | CHF | CHF to USD, then USD to GBP |

For one standard currency unit, the pip value in the quote currency is the pip size. In USD that is:

- `XXX_USD`: `0.0001` USD.
- `USD_JPY`: `0.01 / price` USD.
- `USD_CAD`: `0.0001 / price` USD.
- `USD_CHF`: `0.0001 / price` USD.

GBP value is that USD amount divided by a verified GBP per USD price, which is the `GBP_USD` rate. The weekend `GBP_USD` bid `1.33713` and ask `1.33842` must not be used as that rate. They were non-tradeable.

A spread-betting stake in GBP per point is a different object. The bot would need the broker's definition of a point, the GBP amount per point per API unit, and the allowed stake increment. None of that is in the code or in the sanitised log as a verified rule. The log does contain broker-reported home-conversion factors on those stale quotes. They are not a verified sizing input.

Executable sizing still needs, for each instrument: `pipLocation`, display precision, trade-unit precision, minimum and maximum units, margin rate, financing, and whether the account's API unit is a currency unit or a spread-bet stake. All of that is **UNVERIFIED**. Margin rate and financing are missing. The weekend quotes do not supply them.

## 5. GBP risk examples

Snapshot NAV, balance, and margin available: `97.1539` GBP. Margin used: `0`. Illustrative only.

| Fraction of NAV | GBP risk budget |
| --- | --- |
| 0.25% | 0.2429 |
| 0.50% | 0.4858 |
| 1.00% | 0.9715 |

The live formula for `EUR_USD`, `GBP_USD`, and `AUD_USD` is `units = NAV * risk_pct / (pips * 0.0001)`, then at least 1. It treats one quote-currency unit of loss as one GBP. At 1% risk and 10 pips on `EUR_USD`, that is `0.971539 / 0.001 = 971.539` units. The bot calls that a `0.9715` account-currency loss. If the unit is one euro, the loss is `0.9715` USD, not `0.9715` GBP. The GBP amount is smaller by the GBPUSD rate and was not calculated by the bot.

For `USD_JPY`, `USD_CAD`, and `USD_CHF`, `stop_risk_account_ccy` divides the quote loss by the price (`trading.py` 167–171). That approximates USD, and the sizer then spends the GBP budget as if it were that USD amount.

At these stop distances the calculated size stays above one unit, so the floor at `trading.py` line 325 does not bind:

| Risk | 5 pips | 10 pips | 20 pips | 30 pips |
| --- | --- | --- | --- | --- |
| 0.25% | 485.8 units | 242.9 | 121.4 | 81.0 |
| 0.50% | 971.5 | 485.8 | 242.9 | 161.9 |
| 1.00% | 1943.1 | 971.5 | 485.8 | 323.8 |

Those counts are the bot's `XXX_USD` formula, not a spread-bet stake and not an order.

The stale `EUR_USD` spread was `0.00009`, which is 0.9 of a conventional pip. On 971.539 units that spread costs about `0.087` USD before slippage, roughly 9% of a 10-pip USD stop. `position_sizing` does not subtract spread or slippage from the risk budget. The fixed allowances in `trading.py` lines 73–79 are one pip for the other five instruments and 1.5 pips for `GBP_USD`, and the comment there says they are not used for live OANDA fills. `apply_execution_costs` then scales them for paper prices only.

If a spread-bet minimum stake is larger than the GBP budget for the chosen stop, the trade cannot be kept inside the budget. The minimum is **UNVERIFIED**. The correct action when it is unknown, or when it exceeds the budget, is to refuse the trade. No illustrative size in this section is executable.

## 6. Broker assumptions and unknowns

| Item | Status |
| --- | --- |
| Account home currency GBP | Reported by the later sanitised summary. Not re-checked live in this audit. |
| API unit equals one base-currency unit | Assumed by `portfolio_exposure.py` 75–85 and by `stop_risk_account_ccy`. **UNVERIFIED** for a spread-bet account. |
| Quote P/L is account currency, described as USD | Implemented in `trading.py` 148–172. Incorrect for GBP. |
| Pip is 0.01 for JPY and 0.0001 otherwise | Implemented in `profit_protection.py` 73–80. **UNVERIFIED** against `pipLocation`. |
| GBPUSD fallback `1.35` | Implemented in `portfolio_exposure.py` 23–24. Not a verified rate. |
| Margin available equals permission to trade | Not implemented. `bot_loop.py` 3701–3703. |
| Financing | Missing from the live sizer. Research copies mark it unavailable. |
| Guaranteed stop | Not modeled. |
| Bid for sells and ask for buys | Paper costs do this in `apply_execution_costs`. The risk formula uses one mid-style price. |
| Weekend quotes are executable | They are not. `tradeable` was false. |

## 7. Current safety failures and gaps

| Input | Source the bot uses | Evidence | If wrong | Refuse until verified |
| --- | --- | --- | --- | --- |
| Equity | Accepted balance or `current_equity` | Summary snapshot showed NAV `97.1539` | Size scales with a stale or wrong NAV | Yes, when NAV is missing or inconsistent with balance |
| Risk budget | `POSITION_RISK_PCT`, default 1%, cap 1% | Code only | A GBP account is sized as if losses were USD or quote currency | Yes |
| Stop distance | 20 pips times pip size, or ATR | Code only | Wrong pip size scales both stop and size | Yes, when pip size is unverified |
| Pip size | Quote currency is JPY or not | Convention only | JPY and non-JPY sizes differ by 100 | Yes, until `pipLocation` matches |
| GBP conversion | Not in the live P/L path. Fallback `1.35` on the notional path | None | GBP loss is misstated | Yes |
| Spread and slippage | Fixed pips in paper mode | Weekend spread is not the live spread | Risk budget ignores the real spread | Yes, when the quote is non-tradeable or stale |
| API units | `risk / price_distance` or USD notional over price | None for this account type | Spread-bet stake can be a different multiple of units | Yes |
| Minimum size and precision | Floor of 1, optional `MAX_POSITION_UNITS` | None from the broker | A forced 1 unit, or a rounded stake, can exceed the GBP budget | Yes |
| Margin | Recorded as not implemented | Snapshot margin used was 0, which proves nothing about a new trade | Order rejected, or a position opened without a margin check | Yes |
| Aggregate exposure | USD notional cap, default portfolio risk 5% | Heuristic | Caps the wrong currency | Yes |
| Financing | Not in the sizer | Missing | Overnight cost is outside the stop budget | Yes, before any hold that can incur it |
| Spread-bet stake | Missing | Missing | The entire GBP-per-pip figure is wrong | Yes |
| Stop guarantee | Missing | Missing | A non-guaranteed stop can lose more than the budget | Yes, until the stop type is known |

The unsafe implemented behaviour is the live conversion in `trading.py` 148–172 together with `position_sizing` at 314–325. It will produce a positive unit count for this NAV. It will not keep a demonstrated GBP loss inside 0.25%, 0.5%, or 1% of NAV.

## 8. Fail-closed requirements

These are proposed. They are not implemented in this phase.

The bot must refuse a new trade when any of the following is true:

- Bid or ask is missing, non-finite, or older than a stated freshness limit.
- The instrument status is `non-tradeable`, or the tradeable flag is false. The weekend quotes meet this condition.
- Home currency is not GBP, or the summary currency is missing.
- NAV is missing, non-finite, not positive, or inconsistent with the balance and unrealised profit used for the decision.
- GBP conversion for that instrument is missing or not tied to a fresh `GBP_USD` price.
- Stake-to-unit mapping is not a verified broker rule for this account.
- Stop distance is missing, non-finite, or not positive.
- `pipLocation`, trade-unit precision, or minimum size is missing.
- The minimum legal size, after precision rounding, has a GBP stop loss above the allowed budget.
- Required margin is unknown, or available margin is below that requirement.
- Estimated GBP loss at the stop, including spread and slippage, exceeds the GBP budget.
- Open risk plus the new trade exceeds the stated aggregate GBP cap.
- Financing is unknown for a trade that can be held over the financing cutoff.
- The stop is not known to be guaranteed, and the budget assumes a guaranteed fill.
- Broker metadata contradicts the value the sizer used.

Existing safeguards, which are not sufficient, are: block when equity is missing, block a non-positive computed size, optional unit cap, optional USD notional cap, optional portfolio risk cap, and a tradeable check on some geometry and manage paths. Margin sufficiency is explicitly not evaluated. The main sizing call does not require GBP conversion or a verified stake.

## 9. Ranked corrective actions

1. Keep production trading stopped. Do not enable another live order path.
2. Obtain the broker facts in section 10 with a separately authorised read-only request. Do not infer them from the weekend prices.
3. Specify the spread-bet contract: what one API unit is in GBP per point, and what the point size is.
4. Change the live sizer so quote-currency loss is converted to GBP with a fresh rate, or refuse. Do not use `1.35`.
5. Refuse when `pipLocation`, minimum units, or precision disagree with the local pip table, or when they are absent.
6. Subtract spread and slippage from the GBP budget before sizing, and refuse if the remainder is not positive.
7. Replace the unimplemented margin marker with a real margin check, or keep refusing.
8. Only after those checks exist in code should any further sizing test be considered. That work is not part of this audit.

## 10. Evidence a later read-only diagnostic would need

No such request is authorised by this audit. If one is authorised later, the useful reads are instrument metadata and account financing fields, not another trade. For each of the six instruments the record would need:

- `pipLocation`, display precision, and trade-unit precision.
- Minimum and maximum order units, and the unit increment.
- Margin rate.
- Financing long and short, and the financing cutoff.
- The broker's definition of a spread-bet point and of one API unit in GBP.
- A fresh tradeable bid and ask, with timestamps, only as a quote check. The `2026-10-23T20:59:05Z` prices must not be reused.
- Confirmation that the account currency is still GBP and that NAV, balance, and margin available still refer to that currency.

Home-conversion factors already present on the stale pricing document are not a substitute for that metadata.

## 11. Recommendation

Production trading is not safe. The account snapshot shows a small GBP balance and no margin in use. The bot can still calculate a non-zero unit count from that balance while measuring the loss in the wrong currency and without a spread-bet stake rule. Until section 8 is true in code, and section 10 has been verified, the bot must not place, modify, or close a trade on this account.
