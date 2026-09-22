FORENSIC VERDICT:
The external counts are correct once the export window is read as UTC 20 Sep 21:05 through 21 Sep 21:21 (the stated “20:05–20:21” is a one-hour label error). Realized P/L is −0.0309, win rate 23.4%, profit factor 0.38. The old ~61-second PositionClose bug is proven in the pre-09:40:11Z sample (34 closes in 46–90s; known IDs 1589/1597/1621/1629) and is absent after the live-management fix. A second production defect is proven on the entry path and is still live on the new build: attached SL/TP are computed from the last M5 mid close, not from the executable bid/ask, so decision-time R is always 2.00 while fill-based R is systematically distorted (median 1.59; 15 trades <1R; AUD_USD 2434 = 0.375R and stopped in 14s). The same geometry produced all 30 LOSING_TAKE_PROFIT / STOP_LOSS_ON_FILL_LOSS / TAKE_PROFIT_ON_FILL_LOSS rejects (no fill opened). New-build market closeouts are legitimate profit-protection winners, not the old bug. Direction remains weak (new-build forward mids negative; 12-month offline baseline also negative). Do not widen stops or add pair filters from this day. Next action is an entry-execution geometry fix, not a minimum-R filter that would hide the bug.

CONFIDENCE:
HIGH

SAMPLE START UTC:
2026-09-20T21:05:12.330Z

SAMPLE END UTC:
2026-09-21T21:21:47.228Z

TOTAL TRANSACTION ROWS:
893

TOTAL ENTRY ATTEMPTS:
148

TOTAL FILLED ENTRIES:
118

TOTAL CANCELED/REJECTED ENTRIES:
30

TOTAL COMPLETED EXITS:
117

OLD FAULTY BUILD FILLED ENTRIES:
73

NEW FIXED BUILD FILLED ENTRIES:
45

BOUNDARY/UNKNOWN BUILD FILLED ENTRIES:
0

STOP LOSS COUNT:
47

TAKE PROFIT COUNT:
7

MARKET POSITION CLOSE COUNT:
61

MARKET TRADE CLOSE COUNT:
2

OLD BUG CLOSE COUNT:
33 proven (32 PG profit_protection in 46–90s + 1629 sl_tp). 2101 (88s, no PG) is UNKNOWN — see live_24h_manual_close_attribution.md

LEGITIMATE PROFIT PROTECTION COUNT:
10 (new-build PG profit_protection only; manuals excluded)

LOSING_TAKE_PROFIT COUNT:
16

STOP_LOSS_ON_FILL_LOSS COUNT:
13

TAKE_PROFIT_ON_FILL_LOSS COUNT:
1

PRIMARY REJECTION ROOT CAUSE:
Attached SL/TP built from last M5 mid; executable bid/ask at OrderCreate already invalidates those levels (LOSING_TAKE_PROFIT / STOP_LOSS_ON_FILL_LOSS / TAKE_PROFIT_ON_FILL_LOSS). Decision-time R on every rejected order is 2.00. No rejected order filled.

AUD_USD 0.38R BUILD:
NEW

AUD_USD 0.38R ROOT CAUSE:
A. SL/TP calculated around stale M5/reference mid (0.71198); fill at bid 0.71176 compressed broker TP to 1.5 pips and expanded SL to 4.0 pips (0.375R). Spread 3.4 pips. Rounding 0.71162→0.71161. Not a 2R-formula bug.

MEDIAN DECISION-TIME R:
2.00

MEDIAN FILL-BASED R:
1.585

TRADES BELOW 1R:
15

TRADES BELOW 0.5R:
3

SPREAD COST CONCERN:
PARTIAL

DIRECTIONAL QUALITY:
Weak in this ~24h sample and consistent with the 12-month offline result (negative expectancy, ~26.7% win rate). New-build direction-adjusted M5 forwards are negative at 5/15/30/60m. Geometry and direction are both present; geometry is the proven production defect.

ENTRY EXECUTION GEOMETRY BUG:
YES

SL/TP CONSTRUCTION BUG:
NO

OLD ONE-MINUTE BUG PRESENT IN OLD SAMPLE:
YES

OLD ONE-MINUTE BUG PRESENT AFTER FIX:
NO

HIGHEST-PRIORITY NEXT ACTION:
A. ENTRY EXECUTION GEOMETRY FIX JUSTIFIED

PRODUCTION CHANGES MADE:
NO

OANDA WRITES PERFORMED:
NO

DOCKER RESTARTED:
NO

---

## 1. Executive summary

The independent analysis of the OANDA export is numerically correct on raw counts, P/L, pair P/L, spread-cost sum, and cancellation reasons. It is wrong, or at least unsafe, on two interpretations: (1) treating MARKET_ORDER_POSITION_CLOSEOUT aggregate P/L ≈ −0.0009 as evidence that early exits protect capital, and (2) treating the whole of 21 Sep as one build.

After UTC-normalizing Docker, logs, git, and OANDA times:

| Boundary | UTC | Evidence |
|---|---|---|
| OLD_MANAGEMENT_BUILD_END | 2026-09-21 09:40:11 | Previous container created 10:40:11 BST; first new-build fill 2125 at 09:40:20Z |
| NEW_MANAGEMENT_BUILD_START | 2026-09-21 09:40:11 | Live-manage fix (commit `ae1f878` 09:47:06Z committer / deploy ~09:40Z) |
| Second restart (broker-exit accounting) | 2026-09-21 11:41:55 | Current container created 11:41:49Z; `BOT STARTED` 11:41:57Z. Still new management. |

Old sample: 73 fills, 51 PositionClose, **33 proven** 46–90s bot closes (32 PG `profit_protection` + 1629 `sl_tp`; 2101 is UNKNOWN). New sample: 45 fills, 32 broker stops, **0 take-profits**, 10 PositionClose all winners held ≥15m (Postgres `exit_reason=profit_protection`), **2 TradeClose at 11:41Z = RESTART/FLATTEN_MANUAL_CLOSE** (bot never calls TradeClose; excluded from PP / early-exit / hold stats). The 61-second bug does not recur after 09:40:11Z among **proven** bot closes. Full 8-class table: `live_24h_manual_close_attribution.md`.

Independently of that fix, **every successful entry in both builds** has decision-time R = 2.00 when R is measured from the inferred/logged M5 mid to the submitted SL/TP, and a much worse fill-based R from the actual broker fill to those same submitted levels (median 1.585, min 0.13). Production `evaluate()` still does:

```
price = last M5 close
sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr)   # ATR×2 then TP=2×SL
broker_sl/tp = price ± sl_d / tp_d
OrderCreate(..., stopLossOnFill, takeProfitOnFill)
```

There is no pre-submit check that BUY: `SL < executable BUY < TP` or SELL: `TP < executable SELL < SL`. Live-management PricingInfo (`closeoutBid`/`closeoutAsk`) is **not** used for new-order SL/TP. That is the second production problem.

The AUD_USD 0.38R / 14-second stop is **NEW_FIXED_BUILD** (21:21:33Z), strategy `swing_breakout` / horizon `swing`. Logged mid 0.71198, fill 0.71176, submitted SL 0.71216 / TP 0.71161, broker `STOP_LOSS_ORDER` at 0.71217, realizedPL −0.0009.

## 2. Source data and methodology

| Source | Role | Write? |
|---|---|---|
| OANDA `TransactionIDRange` GET (ids 861–2460) | Authoritative types, reasons, prices, `halfSpreadCost`, SL/TP-on-fill | No |
| Running container `forexttradingbot1st-bot-1` inspect + logs | Deploy times, `[OPEN] mid=`, `[BROKER_CLOSE]`, `[BROKER EXIT]` | No |
| Postgres `trades.diagnostics`, `exec_orders`, `broker_exit_ledger` | Local `exit_reason` | No |
| Current `forex_bot` source | Entry SL/TP path vs manage path | Read only |
| Prior reports (`live_one_minute_close_investigation.md`, broker-exit audits) | Known IDs 1589/1597/1621/1629; 2125/2133/2137/2161 | — |
| OANDA M5 candles GET 20 Sep 20:00Z–21 Sep 21:30Z | Forward mid returns | No |
| Local `data/historical/*_M5.csv` | Ends 2026-08-31; unused for this window | — |

No OANDA CSV was present in the repo, Desktop, or OneDrive. Counts were reconstructed from a read-only transaction pull that matches the external analysis exactly in the 21:05–21:21 UTC window.

**Evidence labels** below: **PROVEN** / **STRONG INFERENCE** / **HYPOTHESIS** / **UNKNOWN**.

Account identifiers were stripped from this report.

## 3. Timezone normalization

| Clock | Representation | Conversion |
|---|---|---|
| OANDA `transaction.time` | `2026-09-21T21:21:33.148715647Z` | Already UTC (`Z`) |
| Docker `Created` / `StartedAt` | RFC3339 with `Z` | UTC |
| Container log prefix | `2026-09-21T21:21:33Z` | UTC |
| In-log `BOT STARTED` / `[OPEN]` | Naive `2026-09-21 22:21:33` | Europe/London BST = UTC+1 → subtract 1h |
| `ae1f878` committer date | `2026-09-21T10:47:06+01:00` | 09:47:06 UTC |
| Postgres `trades.time` | `TIMESTAMP` without TZ | Mixed: pre-restart rows match BST wall clock; later `broker_stop_loss` rows match OANDA UTC. **Not used as the clock of record.** |

Methodology: parse OANDA/Docker RFC3339 → UTC. Convert BST log lines by subtracting 01:00 (BST in force 21 Sep 2026). Never compare a naive Postgres timestamp to an OANDA `Z` time without that check.

**Discrepancy vs external “20:05–20:21”:** first CLIENT_ORDER is 21:05:12Z; last fill in the count-matched sample is 21:21:47Z. Shifting those stamps −1 hour reproduces “20:05–20:21”. **PROVEN** the external window labels are UTC-minus-one. All statistics below use true UTC. The count-matched window is `2026-09-20T20:05Z`–`2026-09-21T21:21:59Z` (empty until 21:05Z).

## 4. Exact deployment / build timeline

```
2026-09-20 21:05:12Z  first CLIENT_ORDER in sample (USD_JPY 1546)     OLD_FAULTY_BUILD
2026-09-20 21:33:50Z  1589 open — known PP bug
2026-09-20 22:08:28Z  1629 open — known local SL/TP bug
2026-09-21 09:39:46Z  last old-build close (2105, 33s hold)
2026-09-21 09:40:11Z  OLD_MANAGEMENT_BUILD_END / NEW_MANAGEMENT_BUILD_START
2026-09-21 09:40:20Z  2125 GBP_USD open (9s after new container)
2026-09-21 09:47:06Z  git commit ae1f878 (live-manage fix) — commit after deploy
2026-09-21 11:41:00Z  TRADE_CLOSE AUD_USD 2181  RESTART/FLATTEN_MANUAL_CLOSE
2026-09-21 11:41:10Z  TRADE_CLOSE USD_JPY 2155  RESTART/FLATTEN_MANUAL_CLOSE
2026-09-21 11:41:55Z  then-current container start (broker-exit accounting)
2026-09-21 11:41:57Z  BOT STARTED equity=97.30 live_tz=Europe/London BST +0100
2026-09-21 21:21:33Z  AUD_USD 2434 0.375R entry (NEW)
2026-09-21 21:21:47Z  AUD_USD 2434 STOP_LOSS — original 24h sample end
2026-09-21 21:58:46Z  EUR_USD 2458 STOP_LOSS (not flatten)
2026-09-21 21:59:34Z  TRADE_CLOSE USD_JPY 2454  POST-23:00 flatten
2026-09-21 21:59:37Z  TRADE_CLOSE GBP_USD 2470  POST-23:00 flatten
2026-09-21 22:00:04Z  POST-23:00 container Created (23:00:04 BST)
2026-09-21 22:00:13Z  BOT STARTED equity=97.28
```

Running env (current container): `EXECUTION_MODE=live_broker`, `USE_ATR_STOPS=true`, `SL_ATR_MULT=2.0`, `MIN_STOP_DISTANCE_PRICE` unset, `SL_FALLBACK_PIPS` unset (code default 20 pips only if ATR path off).

Broker-exit accounting is in the running container after 11:41:55Z but was **not** required for live-manage correctness. Both post-09:40:11Z segments are `NEW_FIXED_BUILD` for management and entry geometry.

No filled entry straddles the 09:40:11Z boundary (0 BOUNDARY_AMBIGUOUS).

## 5. Raw transaction-count verification

Window: 893 rows, ids 1546–2438.

| Item | This audit | External | Verdict |
|---|---:|---:|---|
| CLIENT_ORDER (`MARKET_ORDER` reason) | 148 | ~148 | Match |
| MARKET_ORDER (all reasons) | 211 | (not stated) | — |
| ORDER_FILL | 235 | (not stated) | — |
| Entry fills (`ORDER_FILL` + `tradeOpened` + `MARKET_ORDER`) | 118 | 118 | Match |
| Rejected unfilled CLIENT_ORDER | 30 | 16+13+1=30 | Match |
| Completed exits | 117 | ~117 | Match |
| STOP_LOSS_ORDER fills | 47 / P/L −0.0369 | 47 / −0.0369 | Match |
| TAKE_PROFIT_ORDER fills | 7 / +0.0073 | 7 / +0.0073 | Match |
| MARKET_ORDER_POSITION_CLOSEOUT | 61 / −0.0009 | 61 / −0.0009 | Match |
| MARKET_ORDER_TRADE_CLOSE | 2 / −0.0004 | 2 / −0.0004 | Match |
| Wins / losses / zeros (nonzero-PL win rate) | 25 / 82 / 10 (23.36%) | 25 / 82 (~23.4%) | Match |
| Average winner / loser | +0.000752 / −0.000606 | ~same | Match |
| Profit factor | 0.378 | ~0.38 | Match |
| Total realizedPL | −0.0309 | ~−0.0309 | Match |
| halfSpreadCost sum (ORDER_FILL) | 0.0277 | ~0.0277 | Match |
| Pair P/L AUD/CHF/EUR/JPY/CAD/GBP | −0.0098 / −0.0062 / −0.0052 / −0.0040 / −0.0033 / −0.0024 | same | Match |
| LOSING_TAKE_PROFIT | 16 | 16 | Match |
| STOP_LOSS_ON_FILL_LOSS | 13 | 13 | Match |
| TAKE_PROFIT_ON_FILL_LOSS | 1 | 1 | Match |

External `CLIENT_ORDER` count is `MARKET_ORDER.reason=CLIENT_ORDER`, not a separate `CLIENT_ORDER` type. **PROVEN.**

No row exists between 20:05Z and 21:05Z. Documented as a labelling error, not missing data.

## 6. Complete exit attribution

OANDA `ORDER_FILL.reason` is authoritative. Class is not inferred from price.

| Class | n | Notes |
|---|---:|---|
| BROKER_STOP_LOSS | 47 | All `STOP_LOSS_ORDER` |
| BROKER_TAKE_PROFIT | 7 | All `TAKE_PROFIT_ORDER`; **all OLD** |
| BOT_PROFIT_PROTECTION | 45 | PG `profit_protection` only: 35 OLD (32 in 46–90s) + 10 NEW (≥19 min, +0.0088) |
| BOT_OTHER_POSITION_CLOSE | 6 | PG `sl_tp`: 1607/1617/1629/1643/1731/1869 |
| BOT_WEEKEND_FLATTEN | 0 | Friday-only; sample is Sun–Mon |
| USER_MANUAL_CLOSE | 0 | No off-restart TradeClose in the 24h window |
| RESTART/FLATTEN_MANUAL_CLOSE | 2 | 2181 / 2155 `TRADE_CLOSE` at 11:41Z. Bot never issues TradeClose. Excluded from PP / early-exit / hold stats |
| UNKNOWN | 10 | `POSITION_CLOSEOUT` 09:13–09:39Z with **no** local `exit_reason`. Not scored as bot or manual |

Full reconstruction (117 rows). `class` in the table is the mechanical rule from §4/§8 of the analyzer; the 10 NEW `OTHER_BOT_CLOSE` rows are the valid PP set above.

| trade | pair | side | entry UTC | exit UTC | hold s | fill | SL | TP | fillR | PL | OANDA | class | build |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1547 | USD_JPY | BUY | 2026-09-20T21:05:12 | 2026-09-20T22:00:00 | 3288 | 156.914 | 156.785 | 157.009 | 0.74 | -0.0013 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1569 | USD_CAD | SELL | 2026-09-20T21:14:25 | 2026-09-20T22:00:04 | 2739 | 1.39822 | 1.39898 | 1.39738 | 1.11 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1589 | EUR_USD | BUY | 2026-09-20T21:33:50 | 2026-09-20T21:34:51 | 61 | 1.14803 | 1.14766 | 1.14868 | 1.76 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1597 | EUR_USD | BUY | 2026-09-20T21:41:57 | 2026-09-20T21:42:58 | 61 | 1.14806 | 1.14775 | 1.14879 | 2.35 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1607 | EUR_USD | BUY | 2026-09-20T21:55:16 | 2026-09-20T23:45:58 | 6642 | 1.14822 | 1.14778 | 1.1488 | 1.32 | -0.0006 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1617 | GBP_USD | BUY | 2026-09-20T22:04:24 | 2026-09-21T02:16:00 | 15096 | 1.33937 | 1.3381 | 1.33989 | 0.41 | -0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1621 | USD_JPY | BUY | 2026-09-20T22:06:26 | 2026-09-20T22:07:27 | 61 | 156.757 | 156.678 | 156.852 | 1.20 | 0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1629 | USD_JPY | BUY | 2026-09-20T22:08:28 | 2026-09-20T22:09:29 | 61 | 156.832 | 156.678 | 156.852 | 0.13 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_LOCAL_SLTP_OLD_BUG | OLD_FAULTY_BUILD |
| 1637 | USD_JPY | BUY | 2026-09-20T22:11:32 | 2026-09-20T22:47:53 | 2182 | 156.857 | 156.772 | 157.001 | 1.69 | 0.0014 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1643 | USD_JPY | BUY | 2026-09-20T22:49:10 | 2026-09-21T00:25:29 | 5779 | 157.028 | 156.856 | 157.237 | 1.22 | -0.0013 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1651 | AUD_USD | BUY | 2026-09-20T23:51:03 | 2026-09-20T23:58:02 | 420 | 0.71231 | 0.71205 | 0.71277 | 1.77 | -0.0004 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1657 | USD_CHF | SELL | 2026-09-21T00:05:14 | 2026-09-21T00:45:47 | 2434 | 0.82263 | 0.8231 | 0.82202 | 1.30 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1661 | AUD_USD | SELL | 2026-09-21T00:12:19 | 2026-09-21T00:13:20 | 61 | 0.71239 | 0.71253 | 0.71201 | 2.71 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1669 | AUD_USD | SELL | 2026-09-21T00:15:22 | 2026-09-21T00:16:22 | 61 | 0.7124 | 0.71264 | 0.71211 | 1.21 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1681 | AUD_USD | SELL | 2026-09-21T00:27:31 | 2026-09-21T00:28:32 | 61 | 0.71262 | 0.7129 | 0.7123 | 1.14 | -0.0004 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1689 | AUD_USD | SELL | 2026-09-21T00:35:38 | 2026-09-21T00:36:39 | 61 | 0.71278 | 0.71305 | 0.71242 | 1.33 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1697 | EUR_USD | SELL | 2026-09-21T00:40:42 | 2026-09-21T00:41:43 | 61 | 1.14849 | 1.14862 | 1.14795 | 4.15 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1705 | EUR_USD | SELL | 2026-09-21T00:42:44 | 2026-09-21T00:43:45 | 61 | 1.14834 | 1.14862 | 1.14795 | 1.39 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1717 | AUD_USD | BUY | 2026-09-21T00:47:49 | 2026-09-21T00:49:25 | 96 | 0.71299 | 0.71272 | 0.71337 | 1.41 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1721 | USD_CHF | BUY | 2026-09-21T00:47:49 | 2026-09-21T00:48:50 | 61 | 0.82228 | 0.82194 | 0.8228 | 1.53 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1731 | USD_JPY | SELL | 2026-09-21T00:51:52 | 2026-09-21T03:10:45 | 8333 | 156.738 | 156.983 | 156.414 | 1.32 | -0.0020 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1735 | USD_CAD | BUY | 2026-09-21T00:52:53 | 2026-09-21T02:15:10 | 4937 | 1.39944 | 1.39912 | 1.39995 | 1.59 | 0.0005 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1739 | USD_CHF | BUY | 2026-09-21T01:01:00 | 2026-09-21T01:10:31 | 571 | 0.82248 | 0.82221 | 0.82311 | 2.33 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1745 | EUR_USD | SELL | 2026-09-21T01:12:09 | 2026-09-21T01:13:10 | 61 | 1.14832 | 1.14861 | 1.14781 | 1.76 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1753 | USD_CHF | BUY | 2026-09-21T01:30:24 | 2026-09-21T03:02:40 | 5536 | 0.82241 | 0.82199 | 0.82298 | 1.36 | 0.0010 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1763 | GBP_USD | SELL | 2026-09-21T02:27:09 | 2026-09-21T04:29:27 | 7337 | 1.33859 | 1.33903 | 1.3378 | 1.80 | 0.0006 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1769 | AUD_USD | SELL | 2026-09-21T03:04:40 | 2026-09-21T03:16:36 | 716 | 0.71212 | 0.71251 | 0.71158 | 1.38 | -0.0010 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1779 | USD_CHF | BUY | 2026-09-21T03:17:51 | 2026-09-21T03:25:01 | 429 | 0.823 | 0.82276 | 0.82367 | 2.79 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1785 | USD_JPY | BUY | 2026-09-21T03:28:00 | 2026-09-21T04:25:47 | 3467 | 156.94 | 156.84 | 157.104 | 1.64 | 0.0008 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1789 | AUD_USD | BUY | 2026-09-21T04:06:31 | 2026-09-21T05:15:24 | 4133 | 0.71278 | 0.71248 | 0.71328 | 1.67 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1797 | USD_JPY | BUY | 2026-09-21T04:26:48 | 2026-09-21T07:18:24 | 10296 | 157.032 | 156.905 | 157.225 | 1.52 | 0.0018 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1803 | USD_CAD | BUY | 2026-09-21T04:30:51 | 2026-09-21T05:45:53 | 4501 | 1.40059 | 1.4002 | 1.40097 | 0.97 | 0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1809 | AUD_USD | BUY | 2026-09-21T05:25:36 | 2026-09-21T05:26:37 | 61 | 0.71246 | 0.71214 | 0.71292 | 1.44 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1821 | USD_CHF | BUY | 2026-09-21T05:45:53 | 2026-09-21T06:23:05 | 2232 | 0.82342 | 0.82304 | 0.82375 | 0.87 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1825 | AUD_USD | BUY | 2026-09-21T06:07:10 | 2026-09-21T06:08:11 | 61 | 0.71227 | 0.71193 | 0.71271 | 1.29 | -0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1835 | AUD_USD | SELL | 2026-09-21T06:24:24 | 2026-09-21T06:28:47 | 263 | 0.71226 | 0.7126 | 0.71182 | 1.29 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1841 | AUD_USD | SELL | 2026-09-21T06:29:28 | 2026-09-21T06:30:29 | 61 | 0.71251 | 0.71268 | 0.7119 | 3.59 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1849 | EUR_USD | SELL | 2026-09-21T06:31:30 | 2026-09-21T06:46:16 | 886 | 1.14739 | 1.1478 | 1.14697 | 1.02 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1855 | AUD_USD | SELL | 2026-09-21T06:46:43 | 2026-09-21T06:47:44 | 61 | 0.71263 | 0.71288 | 0.71209 | 2.16 | -0.0004 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1863 | USD_CHF | BUY | 2026-09-21T06:47:44 | 2026-09-21T07:10:19 | 1355 | 0.82334 | 0.82289 | 0.82376 | 0.93 | 0.0008 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 1869 | USD_CHF | BUY | 2026-09-21T07:14:06 | 2026-09-21T07:25:15 | 670 | 0.82391 | 0.82339 | 0.82441 | 0.96 | -0.0007 | MARKET_ORDER_POSITION_CLOSEOUT | OTHER_BOT_CLOSE | OLD_FAULTY_BUILD |
| 1875 | USD_JPY | BUY | 2026-09-21T07:20:10 | 2026-09-21T07:31:35 | 685 | 157.265 | 157.145 | 157.473 | 1.73 | -0.0012 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1883 | GBP_USD | SELL | 2026-09-21T07:26:16 | 2026-09-21T07:27:17 | 61 | 1.33764 | 1.33816 | 1.33672 | 1.77 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1891 | EUR_USD | SELL | 2026-09-21T07:28:17 | 2026-09-21T07:48:16 | 1199 | 1.14755 | 1.14779 | 1.14675 | 3.33 | -0.0004 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1897 | AUD_USD | BUY | 2026-09-21T07:32:21 | 2026-09-21T07:42:36 | 615 | 0.71278 | 0.71246 | 0.71337 | 1.84 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 1901 | GBP_USD | SELL | 2026-09-21T07:33:22 | 2026-09-21T07:34:23 | 61 | 1.3379 | 1.33835 | 1.33689 | 2.24 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1909 | USD_CHF | BUY | 2026-09-21T07:34:24 | 2026-09-21T07:35:25 | 61 | 0.82323 | 0.82289 | 0.82405 | 2.41 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1917 | USD_JPY | BUY | 2026-09-21T07:36:25 | 2026-09-21T09:20:45 | 6260 | 157.226 | 157.073 | 157.455 | 1.50 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 1925 | GBP_USD | SELL | 2026-09-21T07:50:37 | 2026-09-21T07:51:38 | 61 | 1.33802 | 1.33862 | 1.337 | 1.70 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1933 | USD_CHF | BUY | 2026-09-21T07:51:39 | 2026-09-21T07:52:40 | 61 | 0.82277 | 0.82233 | 0.82356 | 1.80 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1941 | EUR_USD | SELL | 2026-09-21T07:54:41 | 2026-09-21T07:55:42 | 61 | 1.14777 | 1.14817 | 1.14707 | 1.75 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1949 | AUD_USD | BUY | 2026-09-21T07:56:43 | 2026-09-21T09:13:33 | 4610 | 0.71291 | 0.71252 | 0.71349 | 1.49 | 0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 1953 | USD_CAD | BUY | 2026-09-21T08:00:47 | 2026-09-21T08:01:48 | 61 | 1.40155 | 1.40097 | 1.40252 | 1.67 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1961 | USD_CHF | BUY | 2026-09-21T08:01:48 | 2026-09-21T08:02:49 | 61 | 0.82325 | 0.82266 | 0.82393 | 1.15 | -0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1969 | GBP_USD | SELL | 2026-09-21T08:07:53 | 2026-09-21T08:08:54 | 61 | 1.33803 | 1.3387 | 1.33701 | 1.52 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1977 | USD_CAD | BUY | 2026-09-21T08:10:56 | 2026-09-21T08:11:57 | 61 | 1.40129 | 1.40073 | 1.40231 | 1.82 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1985 | USD_CHF | BUY | 2026-09-21T08:16:01 | 2026-09-21T08:17:02 | 61 | 0.82312 | 0.82247 | 0.82381 | 1.06 | -0.0004 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 1993 | GBP_USD | SELL | 2026-09-21T08:18:02 | 2026-09-21T08:19:03 | 61 | 1.33844 | 1.33907 | 1.3373 | 1.81 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2001 | USD_CHF | BUY | 2026-09-21T08:20:04 | 2026-09-21T08:21:05 | 61 | 0.82305 | 0.82247 | 0.82381 | 1.31 | -0.0004 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2009 | EUR_USD | SELL | 2026-09-21T08:31:13 | 2026-09-21T08:32:14 | 61 | 1.1481 | 1.14838 | 1.14718 | 3.29 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2017 | USD_CHF | BUY | 2026-09-21T08:32:15 | 2026-09-21T08:33:16 | 61 | 0.82273 | 0.82236 | 0.82371 | 2.65 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2025 | EUR_USD | SELL | 2026-09-21T08:35:17 | 2026-09-21T08:36:18 | 61 | 1.14836 | 1.14886 | 1.14762 | 1.48 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2033 | GBP_USD | SELL | 2026-09-21T08:36:18 | 2026-09-21T08:37:19 | 61 | 1.3386 | 1.33945 | 1.33759 | 1.19 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION_OLD_BUG | OLD_FAULTY_BUILD |
| 2041 | USD_CHF | BUY | 2026-09-21T08:37:20 | 2026-09-21T09:01:38 | 1458 | 0.8228 | 0.8221 | 0.82346 | 0.94 | 0.0012 | TAKE_PROFIT_ORDER | BROKER_TAKE_PROFIT | OLD_FAULTY_BUILD |
| 2045 | GBP_USD | BUY | 2026-09-21T09:00:39 | 2026-09-21T09:20:41 | 1202 | 1.33848 | 1.33765 | 1.3396 | 1.35 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2051 | USD_CAD | BUY | 2026-09-21T09:04:42 | 2026-09-21T09:20:36 | 953 | 1.40158 | 1.40094 | 1.40244 | 1.34 | 0.0001 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2059 | AUD_USD | BUY | 2026-09-21T09:14:51 | 2026-09-21T09:30:25 | 934 | 0.71323 | 0.71272 | 0.71387 | 1.25 | -0.0012 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | OLD_FAULTY_BUILD |
| 2075 | USD_JPY | BUY | 2026-09-21T09:21:57 | 2026-09-21T09:36:16 | 858 | 157.235 | 157.135 | 157.417 | 1.82 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2079 | USD_CHF | BUY | 2026-09-21T09:21:58 | 2026-09-21T09:39:42 | 1064 | 0.82311 | 0.82263 | 0.8241 | 2.06 | -0.0002 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2085 | GBP_USD | BUY | 2026-09-21T09:34:08 | 2026-09-21T09:37:10 | 183 | 1.33831 | 1.3377 | 1.33962 | 2.15 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2089 | AUD_USD | BUY | 2026-09-21T09:35:09 | 2026-09-21T09:39:34 | 266 | 0.71281 | 0.71236 | 0.71347 | 1.47 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2101 | GBP_USD | BUY | 2026-09-21T09:38:11 | 2026-09-21T09:39:39 | 88 | 1.33852 | 1.33758 | 1.3394 | 0.94 | 0.0000 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2105 | USD_JPY | BUY | 2026-09-21T09:39:12 | 2026-09-21T09:39:46 | 33 | 157.303 | 157.199 | 157.449 | 1.40 | -0.0003 | MARKET_ORDER_POSITION_CLOSEOUT | UNKNOWN | OLD_FAULTY_BUILD |
| 2125 | GBP_USD | BUY | 2026-09-21T09:40:20 | 2026-09-21T09:49:38 | 558 | 1.33863 | 1.33796 | 1.33982 | 1.78 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2129 | AUD_USD | BUY | 2026-09-21T09:41:22 | 2026-09-21T11:25:03 | 6222 | 0.71285 | 0.71248 | 0.71359 | 2.00 | 0.0010 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2133 | USD_CHF | BUY | 2026-09-21T09:45:27 | 2026-09-21T09:55:54 | 628 | 0.82328 | 0.82277 | 0.82419 | 1.78 | -0.0010 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2137 | USD_JPY | BUY | 2026-09-21T09:46:28 | 2026-09-21T10:03:30 | 1022 | 157.281 | 157.214 | 157.453 | 2.57 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2143 | GBP_USD | BUY | 2026-09-21T09:52:34 | 2026-09-21T11:40:19 | 6466 | 1.33821 | 1.33735 | 1.33923 | 1.19 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2149 | USD_CHF | BUY | 2026-09-21T09:56:38 | 2026-09-21T10:24:00 | 1642 | 0.82291 | 0.82238 | 0.82382 | 1.72 | -0.0010 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2155 | USD_JPY | BUY | 2026-09-21T10:08:49 | 2026-09-21T11:41:10 | 5541 | 157.274 | 157.158 | 157.386 | 0.97 | -0.0005 | MARKET_ORDER_TRADE_CLOSE | RESTART/FLATTEN_MANUAL_CLOSE | NEW_FIXED_BUILD |
| 2161 | USD_CAD | BUY | 2026-09-21T10:36:16 | 2026-09-21T10:42:40 | 384 | 1.40233 | 1.40178 | 1.40307 | 1.35 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2167 | USD_CAD | BUY | 2026-09-21T11:00:40 | 2026-09-21T11:09:37 | 537 | 1.40167 | 1.40123 | 1.40257 | 2.05 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2173 | USD_CAD | BUY | 2026-09-21T11:20:59 | 2026-09-21T11:35:47 | 887 | 1.40098 | 1.40057 | 1.40197 | 2.41 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2181 | AUD_USD | BUY | 2026-09-21T11:26:05 | 2026-09-21T11:41:00 | 895 | 0.71347 | 0.71306 | 0.71394 | 1.15 | 0.0001 | MARKET_ORDER_TRADE_CLOSE | RESTART/FLATTEN_MANUAL_CLOSE | NEW_FIXED_BUILD |
| 2199 | GBP_USD | BUY | 2026-09-21T11:45:01 | 2026-09-21T12:39:57 | 3296 | 1.33959 | 1.33898 | 1.3406 | 1.66 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2203 | USD_JPY | SELL | 2026-09-21T11:45:01 | 2026-09-21T12:14:09 | 1747 | 157.173 | 157.264 | 157.018 | 1.70 | -0.0009 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2207 | USD_CAD | BUY | 2026-09-21T11:47:04 | 2026-09-21T11:50:03 | 179 | 1.40036 | 1.39987 | 1.40133 | 1.98 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2213 | USD_CAD | BUY | 2026-09-21T11:52:09 | 2026-09-21T12:15:33 | 1404 | 1.39996 | 1.39955 | 1.40103 | 2.61 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2223 | USD_JPY | BUY | 2026-09-21T12:20:38 | 2026-09-21T13:50:07 | 5369 | 157.289 | 157.168 | 157.454 | 1.36 | 0.0012 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2227 | AUD_USD | BUY | 2026-09-21T12:20:38 | 2026-09-21T12:27:33 | 415 | 0.71389 | 0.71362 | 0.71459 | 2.59 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2233 | USD_CAD | SELL | 2026-09-21T12:28:46 | 2026-09-21T13:53:52 | 5105 | 1.40039 | 1.40094 | 1.39924 | 2.09 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2239 | EUR_USD | BUY | 2026-09-21T12:40:58 | 2026-09-21T13:30:08 | 2950 | 1.14855 | 1.148 | 1.14947 | 1.67 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2245 | USD_CHF | SELL | 2026-09-21T13:31:49 | 2026-09-21T13:44:22 | 753 | 0.82173 | 0.82221 | 0.8203 | 2.98 | -0.0009 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2251 | EUR_USD | SELL | 2026-09-21T13:45:01 | 2026-09-21T14:06:23 | 1282 | 1.14761 | 1.14823 | 1.14659 | 1.65 | 0.0011 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2255 | GBP_USD | BUY | 2026-09-21T13:50:06 | 2026-09-21T14:03:02 | 775 | 1.33826 | 1.33751 | 1.33957 | 1.75 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2263 | USD_JPY | BUY | 2026-09-21T13:51:08 | 2026-09-21T14:31:42 | 2434 | 157.43 | 157.34 | 157.591 | 1.79 | -0.0009 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2269 | USD_CAD | SELL | 2026-09-21T13:55:12 | 2026-09-21T14:03:09 | 477 | 1.40105 | 1.40183 | 1.39982 | 1.58 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2277 | USD_CAD | SELL | 2026-09-21T14:05:23 | 2026-09-21T16:11:01 | 7538 | 1.40186 | 1.4026 | 1.40056 | 1.76 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2285 | GBP_USD | BUY | 2026-09-21T14:06:24 | 2026-09-21T21:04:55 | 25111 | 1.33704 | 1.33639 | 1.33864 | 2.46 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2289 | EUR_USD | SELL | 2026-09-21T14:07:25 | 2026-09-21T14:31:36 | 1451 | 1.14672 | 1.14742 | 1.14575 | 1.39 | -0.0011 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2297 | EUR_USD | SELL | 2026-09-21T14:31:50 | 2026-09-21T18:05:18 | 12809 | 1.14737 | 1.14783 | 1.14609 | 2.78 | 0.0011 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2301 | USD_JPY | BUY | 2026-09-21T14:33:52 | 2026-09-21T14:57:15 | 1403 | 157.336 | 157.264 | 157.577 | 3.35 | 0.0013 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2309 | USD_JPY | BUY | 2026-09-21T14:59:17 | 2026-09-21T16:10:13 | 4256 | 157.465 | 157.371 | 157.716 | 2.67 | -0.0009 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2317 | USD_CAD | BUY | 2026-09-21T16:11:27 | 2026-09-21T18:40:53 | 8966 | 1.40249 | 1.40168 | 1.40392 | 1.77 | 0.0011 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2321 | USD_CHF | SELL | 2026-09-21T16:11:27 | 2026-09-21T21:04:55 | 17607 | 0.82125 | 0.82199 | 0.81999 | 1.70 | -0.0024 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2329 | EUR_USD | SELL | 2026-09-21T18:31:44 | 2026-09-21T19:27:40 | 3356 | 1.14637 | 1.14689 | 1.14597 | 0.77 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2337 | AUD_USD | SELL | 2026-09-21T18:41:54 | 2026-09-21T18:51:07 | 553 | 0.71191 | 0.7122 | 0.71153 | 1.31 | -0.0007 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2343 | AUD_USD | SELL | 2026-09-21T18:56:08 | 2026-09-21T19:10:12 | 844 | 0.71213 | 0.71239 | 0.71176 | 1.42 | -0.0006 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2351 | USD_CAD | BUY | 2026-09-21T19:38:51 | 2026-09-21T19:39:11 | 21 | 1.40337 | 1.40314 | 1.40425 | 3.83 | -0.0003 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2357 | EUR_USD | SELL | 2026-09-21T19:40:52 | 2026-09-21T20:00:12 | 1159 | 1.14686 | 1.14719 | 1.14636 | 1.52 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2361 | AUD_USD | SELL | 2026-09-21T19:40:53 | 2026-09-21T20:00:12 | 1159 | 0.71224 | 0.7125 | 0.71193 | 1.19 | 0.0005 | MARKET_ORDER_POSITION_CLOSEOUT | BOT_PROFIT_PROTECTION | NEW_FIXED_BUILD |
| 2373 | EUR_USD | SELL | 2026-09-21T20:02:14 | 2026-09-21T21:04:55 | 3761 | 1.14641 | 1.14671 | 1.14589 | 1.73 | -0.0010 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2377 | AUD_USD | SELL | 2026-09-21T20:04:16 | 2026-09-21T21:04:55 | 3638 | 0.71179 | 0.71212 | 0.71152 | 0.82 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2390 | USD_JPY | SELL | 2026-09-21T21:05:15 | 2026-09-21T21:18:23 | 788 | 157.272 | 157.371 | 157.213 | 0.60 | -0.0011 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2400 | EUR_USD | SELL | 2026-09-21T21:08:18 | 2026-09-21T21:09:57 | 99 | 1.14664 | 1.1471 | 1.14639 | 0.54 | -0.0008 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2420 | EUR_USD | SELL | 2026-09-21T21:14:25 | 2026-09-21T21:15:14 | 49 | 1.1466 | 1.14695 | 1.1462 | 1.14 | -0.0005 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |
| 2434 | AUD_USD | SELL | 2026-09-21T21:21:33 | 2026-09-21T21:21:47 | 14 | 0.71176 | 0.71216 | 0.71161 | 0.37 | -0.0009 | STOP_LOSS_ORDER | BROKER_STOP_LOSS | NEW_FIXED_BUILD |

## 7. Old-build vs new-build comparison

| | OLD_FAULTY_BUILD | NEW_FIXED_BUILD |
|---|---:|---:|
| Entry attempts (fills+rejects) | 92 | 56 |
| Filled entries | 73 | 45 |
| Rejected | 19 | 11 |
| Completed exits | 73 | 44 (45 fills; 1 new position still open at window end; 73+44=117 closes) |
| STOP_LOSS | 15 | 32 |
| TAKE_PROFIT | 7 | **0** |
| POSITION_CLOSEOUT | 51 | 10 |
| TRADE_CLOSE | 0 | 2 |
| Wins / losses / zeros | 14 / 49 / 10 | 11 / 33 / 0 |
| Total realizedPL | −0.0139 | −0.0170 |
| Win rate (nonzero) | 22.2% | 25.0% |
| Profit factor | 0.42 | 0.34 |
| Median hold | 183s | 1343s |
| Median decision R | 2.00 | 2.00 |
| Median fill R | 1.49 | 1.70 |
| Reject reasons | LTP 12, SL_ON_FILL 6, TP_ON_FILL 1 | LTP 4, SL_ON_FILL 7 |

New n=45 is large enough to prove (a) geometry defect persists, (b) 61s bug is gone, (c) broker SL dominates. It is **too small** for pair/direction policy or “new build is worse.” New P/L is slightly worse because the old sample’s 51 closeouts include many near-zero 61s scratches and all 7 TPs; new trades are left on broker SL/TP and the SL side is winning that contest.

## 8. MARKET_ORDER_POSITION_CLOSEOUT attribution

External: 61 closes, aggregate P/L −0.0009. **Do not read this as protective.**

| Category | n | W | L | 0 | P/L | Avg P/L | Median hold |
|---|---:|---:|---:|---:|---:|---:|---:|
| Old 46–90s PP (PG proven) | 32 | 1 | 26 | 5 | −0.0066 | −0.00021 | 61s |
| Old 61s local SL/TP (1629, PG `sl_tp`) | 1 | 0 | 0 | 1 | 0 | 0 | 61s |
| Old other **proven** bot close (PG `sl_tp` or longer PP) | 8 | 3 | 5 | 0 | −0.0026 | −0.00033 | mixed |
| New legitimate PP (PG) | 10 | 10 | 0 | 0 | **+0.0088** | +0.00088 | 3386s |
| Weekend flatten | 0 | | | | | | |
| Proven manual (TradeClose; **not** in these 61) | 0 in PositionClose / 2 TradeClose | | | | −0.0004 | | |
| UNKNOWN PositionClose (no PG) | 10 | 3 | 2 | 5 | +0.0004 | +0.00004 | 09:13–09:39Z |
| **All PositionClose fills** | **61** | 17 | 33 | 11 | **−0.0009** | ≈0 | 61s |

Hold buckets (all 61 closeouts): 0–30s 0; 31–45s 1; **46–90s 34** (32 proven old PP + 1629 + UNKNOWN 2101); 91–120s 0; 2–5m 2; 5–15m 2; 15m+ 22.

**How much of the near-breakeven comes from the old bug? PROVEN:** the 32-row PG-backed 46–90s PP cluster is −0.0066. Removing those, remaining PositionClose are +0.0057. The headline −0.0009 is the old bug offsetting later valid PP (+0.0088). **CONFOUNDED_BY_OLD_BUG.** Do **not** count the two 11:41Z TradeCloses as PP or as the 61s bug.

Attribution correction (manual flatten + UNKNOWN): `live_24h_manual_close_attribution.md`.

New PP examples (PG + logs): 2129 AUD +0.0010; 2143 GBP +0.0005; 2213 CAD +0.0005; 2223 JPY +0.0012; 2251 EUR +0.0011; 2297 EUR +0.0011; 2301 JPY +0.0013; 2317 CAD +0.0011; 2357 EUR +0.0005; 2361 AUD +0.0005. All `BROKER_CLOSE ... source=OANDA_CURRENT` after the second restart where logs exist.

Old longer `OTHER_BOT_CLOSE` includes PG `sl_tp` on 1607/1617/1643/1731/1869 (**STRONG INFERENCE**: same stale-M5 local SL/TP path as 1629, just not on the next 60s cycle) and some longer `profit_protection` that may still have used candle MFE (**HYPOTHESIS** — not labelled valid).

## 9. Stop-loss vs take-profit

Authoritative OANDA reasons: **47 SL / 7 TP**. External counts confirmed.

| | n | Total P/L | Avg P/L | Median P/L | Median hold |
|---|---:|---:|---:|---:|---:|
| STOP_LOSS | 47 | −0.0369 | −0.000785 | −0.0008 | 844s |
| TAKE_PROFIT | 7 | +0.0073 | +0.001043 | +0.0010 | 4937s |

SL by pair: AUD 12 / −0.0091; CAD 9 / −0.0054; EUR 8 / −0.0060; CHF 7 / −0.0070; JPY 7 / −0.0070; GBP 4 / −0.0024.  
SL by side: BUY 26 / −0.0186; SELL 21 / −0.0183.  
SL by build: OLD 15 / −0.0115; **NEW 32 / −0.0254**.

TP by build: **OLD 7 / +0.0073; NEW 0**. The SL/TP *count* imbalance is worse on the new build because the old 61s closer was removing trades before either broker level. That is not proof that “stops are too tight.” New median hold on SL is 865s (~14 min). AUD 2434 is the 14s exception, explained by 0.375R geometry + 3.4-pip spread, not by ATR being “too small” in isolation.

Possible explanations (this sample):

| Hypothesis | Verdict |
|---|---|
| Bad direction | **PARTIAL** — forwards mixed/negative, 12m offline negative |
| Bad entry timing | **PARTIAL** — M5 close used as entry reference |
| Bad SL geometry | **YES after fill** — SL widened when fill is adverse |
| Bad TP geometry | **YES after fill** — TP compressed; 0 new TPs |
| Fill displacement | **YES PROVEN** |
| Spread | **PARTIAL** — median 1.4 pips; AUD 2434 was 3.4 |
| Rapid noise | **PARTIAL** — some new SLs in <2 min (2351 21s, 2434 14s, 2420 49s) |
| Stops too tight vs ATR | **NOT PROVEN** — ATR×2 is the intended method |

## 10. Initial decision-time R distribution

Reference = inferred mid from submitted SL/TP under the production identity `TP = mid ± 2×(mid−SL)` (equivalently `(2×SL+TP)/3`). Logged `[OPEN] mid=` matches this to 1 pipette on AUD 2434 (0.71198).

All 118 filled entries: **decision-time R = 2.00** (min 1.9999999999976, max 2.0000000000011 — float).

| | below 0 | 0.25 | 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 1.75 | near 2.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Decision R | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 118 |

Old and new both median 2.00. **PROVEN:** intended 2R construction at the M5 reference is working. Low live R is **not** a TP-formula bug.

## 11. Initial fill-based R distribution

Same submitted SL/TP, actual broker fill.

| | n | min | p01 | p05 | p25 | median | p75 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All | 118 | 0.130 | 0.381 | 0.764 | 1.265 | **1.585** | 1.821 | 3.025 | 3.786 | 4.154 |
| OLD | 73 | 0.130 | 0.331 | 0.907 | 1.255 | 1.487 | 1.795 | 2.989 | 3.747 | 4.154 |
| NEW | 45 | 0.375 | 0.449 | 0.631 | 1.310 | 1.703 | 2.045 | 2.940 | 3.615 | 3.826 |

Counts below (all fills): 0R 0; 0.25R 1; **0.5R 3**; 0.75R 6; **1.0R 15**; 1.25R 29; 1.5R 54; 1.75R 74; near-2R 11.

New-build alone: 6 below 1R, 1 below 0.5R (AUD 2434). **The imbalance persists after the management fix.** **PROVEN:** distortion appears at fill, not at signal-time 2R construction.

Median fill R by pair: CAD 1.76, GBP 1.72, EUR 1.66, CHF 1.62, AUD 1.41, JPY 1.50. By side: BUY and SELL both sub-2 (see §18).

90 of 117 completed trades filled adverse to inferred mid (pay the spread / displacement). Median signed displacement is +0.67 pip adverse.

## 12. AUD_USD ~0.38R / 14-second stop reconstruction

**Build: NEW_FIXED_BUILD. PROVEN.** Entry 21:21:33.149Z, 9h40m after NEW_MANAGEMENT_BUILD_START, 9h40m after the second restart. Container log `BOT STARTED` 11:41:57Z is this process.

| Step | Value | Source |
|---|---|---|
| Decision time | 2026-09-21T21:21:33.108Z | `[HYBRID] AUD_USD horizon=swing strategy=swing_breakout` |
| Symbol / side | AUD_USD SELL | OANDA units −3; `[OPEN]` |
| Strategy / horizon | swing_breakout / swing | log |
| M5 reference | mid=**0.71198** | `[OPEN]` |
| Quant / RL | UNKNOWN (not logged). Order placed ⇒ quant SELL and RL did not block | — |
| ATR / sl_d | sl_d = 0.00018 (1.8 pips) = fill-based local SL 0.71194 − wait: SELL local SL=fill+sl_d=0.71176+0.00018=0.71194 | `[OPEN] SL=0.71194 TP=0.71139` |
| TP construction | tp_d ≈ 0.00037 (2R) | local TP 0.71139 = 0.71176−0.00037 |
| PricingInfo bid/ask at fill | bid **0.71176** ask **0.71210** spread **3.4 pips**; closeoutBid 0.71136 closeoutAsk 0.71251 | ORDER_FILL `fullPrice` |
| Submitted (from mid) | SL **0.71216** = 0.71198+0.00018; TP **0.71161** ≈ 0.71198−0.00037 | MARKET_ORDER 2433 `stopLossOnFill` / `takeProfitOnFill` |
| Fill | 0.71176 at 21:21:33.149Z trade 2434 | ORDER_FILL |
| Displacement | mid−fill = 2.2 pips (SELL filled through bid, worse than mid) | — |
| Fill-based SL / TP / R | 4.0 pips / 1.5 pips / **0.375R** | — |
| Decision R | **2.00** | mid vs submitted |
| Stop | 21:21:47.228Z price 0.71217 reason `STOP_LOSS_ORDER` P/L −0.0009 | ORDER_FILL 2437 |
| Hold | 14.08s | — |

**Cause classification:** **A** (SL/TP around M5 mid) **PROVEN**. **C** (fill vs precomputed levels) **PROVEN**. **D** (spread 3.4 pips vs 1.5-pip TP) **PROVEN** as amplifier. **F** (0.71162→0.71161) **PROVEN** minor. **B** (TP not 2R) **NO**. **E** (PP modified attached orders) **NO**. **G** (fallback 20-pip stop) **NO**. **I** (export misread) **NO**.

This is a production execution-geometry defect. Not fixed in this audit.

## 13. Complete order cancellation / rejection forensic analysis

Verified: 16 LOSING_TAKE_PROFIT, 13 STOP_LOSS_ON_FILL_LOSS, 1 TAKE_PROFIT_ON_FILL_LOSS. These 30 are **exactly** the 30 unfilled CLIENT_ORDERs. `had_fill=0`, `tradeOpened=0`. OANDA cancelled the market order itself; no unprotected position was left. **PROVEN.**

Every rejected MARKET_ORDER still carried `stopLossOnFill`/`takeProfitOnFill` with decision-time R = 2.00 and valid mid orientation. Old 19 / new 11 — **the reject path survived the management fix.**

| Root cause | n | Evidence |
|---|---:|---|
| A. SL/TP from stale M5 mid | 30 | Same code path as fills; R=2 at inferred mid |
| B. Spread crosses attached level | many | Mechanism of LTP / SL_ON_FILL |
| C. Market moved decision→exec | possible | Same second as HYBRID; movement is mostly spread not time |
| D. Rounding | possible pipette | `_format_oanda_price` 5dp / JPY 3dp; no instrument metadata |
| E. Wrong BUY/SELL orientation | 0 | Orientation at mid is correct |
| F. ATR too small | amplifier | Small ATR + spread ⇒ levels inside spread |
| G. Fallback stop | 0 | Rejected SL distances are ATR-scale, not 20 pips |
| H. Malformed request | 0 | Valid MarketOrderRequest |
| I. OANDA min-distance rule | possible overlap with B | Not separately logged |
| J/K | 0 | — |

Nearby same-symbol fills within 5 minutes exist for only 1/30 (rejects cluster when the book is wide / no one else fills). That is consistent with “levels already invalid at the would-be fill,” not a later move.

Primary rejection root cause: **A+B** — executable price vs mid-based attached orders.

## 14. Entry executable-price validation code path

Live `OrderCreate` (`oanda_exec._place_market_order_open_sync`): attaches whatever SL/TP `bot_loop.evaluate` computed. **No check** that:

- BUY: `SL < executable BUY < TP`
- SELL: `TP < executable SELL < SL`

Price used to construct attached SL/TP: **last completed M5 mid close** (`raw["close"].iloc[-1]`). Not PricingInfo, not closeoutBid/Ask, not estimated fill.

After fill, **local** Position SL/TP are recomputed from the **fill** (`entry_price ± sl_d`). Broker attached levels stay at the mid-based prices. Local book and broker levels **diverge**. `[OPEN]` prints the fill-based pair; OANDA prints the mid-based pair. AUD 2434: log SL/TP 0.71194/0.71139 vs broker 0.71216/0.71161.

Precision: `_format_oanda_price` hard-codes JPY=3dp else 5dp. No `displayPrecision` from instrument API. No minimum-stop-distance check (`MIN_STOP_DISTANCE_PRICE` empty). No spread-vs-target check. No fill-displacement check.

**Do not confuse with live management:** `fetch_pricing_snapshot` / `closeout_manage_price` run only on existing positions. New-order SL/TP never see that snapshot.

## 15. Spread / execution-cost analysis

OANDA `halfSpreadCost` on ORDER_FILL is the broker’s attribution of half-spread in **account currency** (account NAV ~97.3, currency GBP). Sign is a **cost** (positive numbers in this export). **Both entry and exit fills contribute.** Realized `pl` already uses the fill prices, so **you must not subtract 0.0277 from −0.0309**. The two figures are different decompositions of the same fills. **PROVEN.**

Sum across 235 ORDER_FILL rows: **0.0277**. Matches external.

Fill-time top-of-book spread (118 entries): median 1.4 pips, p95 2.4, max 10.0 (thin book). spread/TP: median 0.179; counts above 10/15/20/25/33/50/75/100%: **95 / 70 / 50 / 30 / 20 / 10 / 5 / 4**.

TP ≤ 1× / 2× / 3× spread: **4 / 10 / 20** accepted fills. Rejects do not carry `fullPrice`, so a reject-vs-accept spread test is **UNKNOWN** at tick level. The reject reasons themselves are OANDA saying the attached level is already on the wrong side of the would-be fill — economically the same family as “spread/target too large.”

AUD 2434: spread 3.4 pips vs TP 1.5 pips (spread/TP = 227%). Extreme, not typical.

**SPREAD COST CONCERN: PARTIAL** — spread is economically large relative to many TPs and explains some rejects/14s stops; it is not an extra −0.0277 on top of −0.0309, and it is not the 12-month directional failure.

## 16. Rapid-exit analysis

Completed 117 holds. Counts closed within:

| | ≤15s | ≤30s | ≤60s | ≤90s | ≤2m | ≤5m | ≤10m | ≤30m | ≥60m |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All | 1 | 2 | 4 | 38 | 40 | 44 | 53 | 82 | 25 |

The 38 within 90s are almost entirely the **old 61s PositionClose cluster** (34) plus a few genuine new broker stops (2434 14s, 2351 21s, 2420 49s, 2400 99s).

By exit cause × build:

- Old 46–90s: PositionClose / PP bug.
- New ≤60s: broker STOP_LOSS only (2434, 2351). **Not** PositionClose.
- New PP: all ≥15m.

**PROVEN:** do not mix old ~61s bot closes with new rapid broker stops.

## 17. Rapid re-entry / churn

Same-symbol next entry after a close:

| | ≤1m | ≤2m | ≤5m | ≤10m | ≤30m |
|---|---:|---:|---:|---:|---:|
| Any close → next | 5 | 18 | 41 | 55 | 88 |
| Same direction | 4 | 17 | 38 | 51 | 75 |
| After SL, same dir | 3 | 4 | 14 | 18 | 27 |
| After PositionClose | 1 | 11 | 22 | 31 | 51 |

Old build: churn is dominated by 61s PP → same-bar re-entry (same M5 close still in force). New build: 15 SL→same-dir re-entries within 10m — one slot per symbol, no cooldown, no signal reset. **PROVEN** the bot can re-enter the same persistent quant state on the next 60s cycle. Whether the bar or RL flip changed is **UNKNOWN** (not logged). Do not add a cooldown in this task.

## 18. Pair × direction diagnostics

Tiny ~24h sample. **Do not disable any pair or side.**

| Pair side | Fills | Exits | W | L | 0 | P/L | SL | TP | Bot | Med hold s | Med fill R | Med spr/TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD BUY | 6 | 6 | 0 | 6 | 0 | −0.0023 | 2 | 0 | 4 | ~ | 1.54 | ~ |
| EUR_USD SELL | 14 | 14 | 2 | 10 | 2 | −0.0029 | 6 | 0 | 8 | ~ | 1.70 | ~ |
| GBP_USD BUY | 8 | 8 | 1 | 5 | 2 | −0.0024 | 4 | 0 | 3 | ~ | 1.56 | ~ |
| GBP_USD SELL | 8 | 8 | 1 | 5 | 2 | +0.0000 | 0 | 1 | 7 | ~ | 1.77 | ~ |
| USD_JPY BUY | 17 | 17 | 7 | 8 | 2 | ~0 | 5 | 2 | 9 | 2434 | 1.52 | 0.10 |
| USD_JPY SELL | 4 | 3 | 0 | 3 | 0 | −0.0040 | 2 | 0 | 1 | 1747 | 1.21 | 0.33 |
| AUD_USD BUY | 11 | 11 | 2 | 8 | 1 | −0.0036 | 6 | 0 | 5 | ~ | 1.47 | ~ |
| AUD_USD SELL | 14 | 14 | 1 | 12 | 1 | −0.0062 | 6 | 0 | 8 | ~ | 1.36 | ~ |
| USD_CAD BUY | 12 | 12 | 4 | 8 | 0 | −0.0003 | 5 | 1 | 6 | 712 | 1.79 | 0.19 |
| USD_CAD SELL | 4 | 4 | 0 | 4 | 0 | −0.0030 | 4 | 0 | 0 | 3922 | 1.67 | 0.15 |
| USD_CHF BUY | 17 | 17 | 3 | 14 | 0 | −0.0034 | 5 | 3 | 9 | 571 | 1.53 | 0.22 |
| USD_CHF SELL | 3 | 3 | 1 | 2 | 0 | −0.0028 | 2 | 0 | 1 | 2434 | 1.70 | 0.12 |

AUD_USD is the largest loser **in this sample** (−0.0098), mostly SELL. Cells are n≤17. Old vs new split per cell is smaller still.

## 19. Forward BUY/SELL directional-quality analysis

Causal reference: **last completed M5 mid at or before entry time** (OANDA M5 pull; 290–294 bars/pair). Direction-adjusted: BUY `future−ref`, SELL `ref−future`, in pips. Independent of actual exit.

| Group | 5m mean / med / pos | 15m | 30m | 60m |
|---|---|---|---|---|
| All | −0.34 / −0.35 / 45% | +0.11 / −0.10 / 47% | +0.12 / +0.10 / 50% | −0.51 / −0.10 / 50% |
| BUY | −0.06 / 0.00 / 49% | +0.56 / +0.30 / 52% | +0.43 / +0.80 / 54% | −0.36 / +0.70 / 55% |
| SELL | −0.77 / −0.40 / 38% | −0.62 / −0.50 / 39% | −0.41 / −1.00 / 45% | −0.75 / −1.10 / 40% |
| OLD | −0.12 / −0.40 / 44% | +0.64 / +0.20 / 52% | +0.76 / +0.70 / 52% | +0.12 / +0.30 / 53% |
| NEW | −0.70 / −0.10 / 47% | −0.80 / −0.50 / 38% | −1.05 / −0.45 / 48% | −1.65 / −0.90 / 43% |

n ≈ 40–73 per cell. **Do not overinterpret.** Qualitatively: this day does **not** show a useful directional edge; new-build and SELL are the weaker slices; the 12-month offline study was negative at 5/15/30/60/120/240m. Combined with proven geometry distortion, the honest reading is **both**: weak direction **and** execution geometry. Geometry is the fixable production bug.

## 20. Stop-distance analysis

Submitted SL distance from **fill** (pips): median 4.85; p05 2.40; min 1.30. ATR path: `USE_ATR_STOPS=true`, `SL_ATR_MULT=2.0`. Fallback 20 pips was not the live path (AUD sl_d=1.8 pips).

SL/spread median roughly 4.85/1.40 ≈ 3.5×. New-build rapid SLs (14s, 21s) sit at small fill-based SL (AUD 4.0 pips with 3.4-pip spread). Alternative explanation tested via forwards: price often continued adversely (new-build 5–60m means negative). **Do not widen ATR multipliers from this day.**

Post-entry MFE/MAE before stop: not reconstructed tick-by-tick. Postgres has MFE for old PP closes; those MFEs were the *bug* (pre-entry candle). New broker SLs have no reliable local MFE in older rows. **INSUFFICIENT** for a “wider stops help” claim.

## 21. TP-distance analysis

Fill-based TP pips: median 7.95; min 1.50 (AUD 2434). Decision-time TP is 2× ATR stop from mid. Very small **fill-based** targets are created by displacement, not by a separate TP formula.

TP ≤ spread: 4 accepted. TP ≤ 2×spread: 10. TP ≤ 3×spread: 20. Rejected orders are the ones where TP or SL was already on the wrong side of the would-be fill (30). **PROVEN** small targets are mostly a fill/mid mismatch.

## 22. RL involvement where provable

Code (unchanged): RL is always called; unseen Q-states tie BUY/SELL/SKIP; random tie-break; RL must match quant side or the entry is skipped.

This sample: **no persisted RL action** on fills. Current-container logs were searched; no `RL gate blocked` / `RL decided to skip` lines were captured in the filtered pull (logger.info; uvicorn lastResort may hide some INFO). Old-container logs from before 11:41:55Z are gone.

Cannot infer missing RL decisions. Rapid re-entry **may** be RL-flip or same-state pass — **UNKNOWN**. Do not modify RL.

## 23. Execution-observability gaps

Reliably persisted today:

| Field | Where | Reliable? |
|---|---|---|
| Signal / M5 timestamp | No dedicated field | No (HYBRID has no bar time) |
| Reference / mid | `[OPEN] mid=` | Yes on fill, not on reject |
| Bid / ask / spread | OANDA fill `fullPrice` only | Not in bot logs |
| Requested vs fill | mid vs fill | Yes on fill |
| ATR | `diagnostics.atr_at_entry_pips` on **bot-closed** trades | Missing on broker SL before broker-exit deploy |
| Quant vote / score | No | No |
| RL action | No | No |
| Strategy / horizon | `[HYBRID]` + `[OPEN]` | Yes on fill |
| Submitted SL/TP | OANDA MARKET_ORDER | Not logged by bot |
| Local SL/TP | `[OPEN]` (fill-based, **different**) | Misleading vs broker |
| Decision R / fill R / spread/TP | No | No |
| Broker ids | `[OPEN]`, exec_orders, ledger | Partial |
| Exit source / OANDA reason / realizedPL | After 11:41: `[BROKER EXIT]` + ledger; before: Case D dropped many | Gap on 09:40–11:41 |

Minimal future schema (do **not** implement here):

```
[ENTRY DECISION] symbol= side= strategy= horizon= reference_price= bid= ask= spread_pips= atr= sl= tp= risk_pips= reward_pips= decision_r= quant_vote= rl_vote=
[ENTRY FILL] symbol= side= reference_price= fill= fill_delta_pips= sl= tp= fill_r= broker_id= transaction_id=
[ENTRY REJECT] symbol= side= reason= reference_price= sl= tp= bid= ask= decision_r=
[EXIT] symbol= broker_id= transaction_id= oanda_reason= local_reason= realized_pl=
```

## 24. Assessment of the 10 external-analysis claims

| # | Claim | Verdict | Why |
|---|---|---|---|
| 1 | Main problem is too many losing trades | **PARTIALLY_SUPPORTED** | 23.4% WR / PF 0.38 is real. Causes are mixed: old bug, geometry, direction. |
| 2 | Algo market closeouts protect capital | **CONFOUNDED_BY_OLD_BUG** | −0.0009 overall; 61s bug −0.0066; new PP +0.0088. |
| 3 | Investigate entry filter and stop logic before market-close logic | **PARTIALLY_SUPPORTED** | Entry **geometry** (not a new filter) is the proven next bug. Market-close old bug is already fixed. |
| 4 | LTP / SL_ON_FILL ⇒ SL/TP invalid by execution time | **SUPPORTED** | 30/30 unfilled; decision R=2; mid-based attach. |
| 5 | Spread is a major concern | **PARTIALLY_SUPPORTED** | 0.0277 is attribution not extra P/L; median spr/TP 18%; AUD 3.4-pip extreme. |
| 6 | Some trades open/close around one minute | **SUPPORTED** old; **UNSUPPORTED** as current manage behaviour | 33 proven ~61s old bot closes. After fix: no such **proven** bot PositionClose. 11:41Z / 21:59Z TradeCloses are manual flatten, not the bug. |
| 7 | AUD_USD is the largest loss contributor | **SUPPORTED** for this sample only | −0.0098. Not a pair-disable reason. |
| 8 | Pair/direction asymmetry | **INSUFFICIENT_DATA** | n≤17 per cell; 12m offline said every pair and both sides lose. |
| 9 | Some initial stop/target structures have poor R:R | **SUPPORTED** fill-based; **UNSUPPORTED** decision-time | Decision R always 2.00. |
| 10 | Stops should not simply be widened | **SUPPORTED** | Direction + geometry first; wider stops can enlarge 0.2R losers. |

## 25. Proposed-change classification

| Proposal | Classification | Note |
|---|---|---|
| 1. Minimum expected R filter | **NEEDS MORE INVESTIGATION** / **SUPPORTED FOR CONTROLLED OFFLINE TEST** | Would hide the mid-vs-fill bug. Do not ship until geometry is fixed. |
| 2. Spread-to-target filter | **SUPPORTED FOR CONTROLLED OFFLINE TEST** | After geometry uses executable prices. |
| 3. Live bid/ask SL/TP validation | **SUPPORTED FOR IMPLEMENTATION** | This **is** the geometry fix. Separate from manage-path PricingInfo. |
| 4. Signal persistence | **SUPPORTED FOR CONTROLLED OFFLINE TEST** | Churn is real; cooldown/persist is research. |
| 5. Volatility-normalized stops | **ALREADY PRESENT IN SOME FORM** | `USE_ATR_STOPS=true`, `SL_ATR_MULT=2`. Not new. |
| 6. Cooldown after stop | **SUPPORTED FOR CONTROLLED OFFLINE TEST** | Do not add live from this day. |
| 7. Pair/direction filters | **NOT SUPPORTED** | n too small; 12m already all-negative. |
| 8. Execution-quality logging | **SUPPORTED FOR IMPLEMENTATION** | Second to geometry; needed for RL/quant. |
| 9. Early thesis invalidation | **NEEDS MORE INVESTIGATION** | New PP already exists; old version was the bug. |

## 26. Findings ranked by severity and confidence

| Rank | Finding | Bucket | Confidence |
|---|---|---|---|
| 1 | Entry SL/TP attached from M5 mid, not executable bid/ask; fill R and 30 rejects | **PRODUCTION BUG** | HIGH / PROVEN |
| 2 | Local vs broker SL/TP diverge after fill (`[OPEN]` prints the wrong pair vs OANDA) | **PRODUCTION BUG** / observability | HIGH |
| 3 | Old 61s PP / stale-mid SL (1589/1597/1621/1629 + 30 more) | **PRODUCTION BUG** (fixed) | HIGH |
| 4 | No pre-submit orientation / min-distance / spread check | **EXECUTION ROBUSTNESS ISSUE** | HIGH |
| 5 | Hard-coded 5/3 dp vs instrument precision | **EXECUTION ROBUSTNESS ISSUE** | MEDIUM |
| 6 | Weak directional edge (this day + 12m offline) | **STRATEGY RESEARCH QUESTION** | HIGH for “no proven edge”; LOW for a new model |
| 7 | Missing bid/ask/ATR/quant/RL/decision_r on entries | **OBSERVABILITY/LOGGING GAP** | HIGH |
| 8 | Same-signal re-entry after SL / PP | **STRATEGY RESEARCH QUESTION** | HIGH that it happens |
| 9 | New-build 0 TP / 32 SL | **EXPECTED BEHAVIOUR** given geometry+direction; not a new closer bug | MEDIUM |
| 10 | halfSpreadCost 0.0277 | **EXPECTED BEHAVIOUR** (attribution) | HIGH |
| 11 | AUD_USD worst pair today | **INSUFFICIENT EVIDENCE** to act | HIGH |
| 12 | TradeClose at 11:41Z and 21:59Z | **RESTART/FLATTEN_MANUAL_CLOSE** (bot cannot TradeClose; ≤55s before recreate) | HIGH |
| 13 | RL random veto | **INSUFFICIENT EVIDENCE** in this sample | — |

## 27. Single recommended next action

**A. ENTRY EXECUTION GEOMETRY FIX JUSTIFIED.**

Proof: decision-time R is identically 2.00; fill-based R is not; 30 rejects and AUD 2434 (NEW build, mid 0.71198, fill 0.71176, broker TP/SL 0.71161/0.71216) are the same mechanism. The 2R formula is not wrong. Live-management PricingInfo must not be mistaken for a fix already in place.

Do not implement a minimum-R filter, spread filter, cooldown, pair disable, or stop widening until this attach-price path is designed and reviewed.

## 28. Tests / checks performed

- Read-only OANDA `TransactionIDRange` + `InstrumentsCandles` + `AccountDetails`.
- Docker inspect (created 2026-09-21T11:41:49Z) and log greps. **No restart, no compose down.**
- Postgres SELECT/COPY only.
- Source read: `bot_loop.evaluate`, `sl_tp_distance_for_entry`, `oanda_exec` OrderCreate, `live_manage.closeout_manage_price`.
- No pytest run (no implementation). No backtest. No `.env` edit. No order, PositionClose, SL/TP replace, or Telegram send.

PRODUCTION CHANGES MADE: NO  
OANDA WRITES PERFORMED: NO  
DOCKER RESTARTED: NO
