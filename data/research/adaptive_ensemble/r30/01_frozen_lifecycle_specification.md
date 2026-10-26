# R.30 frozen scalp trade-lifecycle specification

Frozen at 2026-10-20T00:19:00+01:00, before any R.30 performance measurement.

This is an offline research model for the existing `scalp` shadow rule. It does not activate a strategy, change live selection, or authorise trading. The thresholds below are the existing source defaults. They are not claimed to be economically optimal.

## Signal

- Call `signal_from_arrays("scalp", i, pack)` on bid OHLC only.
- Lookback is 50, the source default. No parameter is changed.
- A bar yields `BUY`, `SELL`, or no direction. `INSUFFICIENT_DATA` is no direction.
- The signal at bar T uses indicator rows at or before T. The fill, if any, is on a later bar.

## Entry

- A new BUY event is a bar whose signal is BUY and whose previous bar signal is not BUY.
- A new SELL event is the same rule with SELL.
- Repeated same-direction states are not new events and do not add size.
- The book must be flat when the event is observed. One open position is allowed. Pyramiding is prohibited.
- A reversal does not open the opposite position. The opposite signal only schedules an exit. After the book is flat, a later bar can enter only if it is itself a new event under the rule above. The exit bar is not that event, because its direction matches the prior bar.
- The entry fills at the next bar's open: ask open for a long, bid open for a short.
- The next bar is eligible only when its timestamp is exactly five minutes after the signal bar, both bars are inside the session below, and neither bar is in the Friday flatten window. Otherwise the entry is cancelled. It is not delayed onto a later bar.
- There is no entry on the last bar, because no next bar exists.

## Exit

- Stop distance is `SL_FALLBACK_PIPS * pip_size`, which is 20 * 0.0001 = 0.002 for EUR_USD. `USE_ATR_STOPS` stays at its default of false, so ATR does not set the stop.
- Take-profit distance is that stop times `TP_RISK_REWARD` (2), so 0.004.
- Long stop = entry price − 0.002. Long take-profit = entry price + 0.004.
- Short stop = entry price + 0.002. Short take-profit = entry price − 0.004.
- Prices are measured from the actual fill, because that is the price at risk.
- No extra maximum holding period is added. The existing Friday flatten is the time stop.
- An opposite signal schedules an exit at the next eligible bar's open. Longs exit on the bid. Shorts exit on the ask.
- A position still open on the final bar exits at that bar's exit-side close. The reason is `end_of_data`.

## Position management

- At most one EUR_USD position.
- Decisions made at a bar close are filled at the next bar open.
- Resting stop and take-profit orders are tested on the bar after the entry open.
- On a normal bar, the open is tested first. If the exit-side open is already beyond the stop, the fill is that open (`stop_gap`), not the stop. If the open is already beyond the take-profit, the fill is that open (`take_profit_gap`).
- If the open is between the stop and the take-profit and the bar's exit-side range touches both, the stop is filled (`ambiguous_stop`). The intrabar sequence is unknown, so the adverse outcome is used.
- If only the stop is touched, fill at the stop. If only the take-profit is touched, fill at the take-profit.
- If the next observed bar is more than five minutes later, the position is closed at that bar's exit-side open (`gap_exit`). A missing interval is not held through. If that open is worse than the stop, the open is used.
- Friday 20:45 UTC through the 21:00 close flattens an open position at the bar open (`weekend_flatten`). The lead of 15 minutes and the 21:00 UTC close are the source defaults.

## Session

Copied from the source defaults, not from the process environment:

- EUR_USD entries require 08:00–22:00 UTC inclusive on the minute, and the FX week.
- The FX week is closed from Friday 21:00 UTC through Sunday 21:00 UTC.
- Saturday is closed. Sunday is closed before 21:00 UTC.
- A bar in the Friday flatten window is not an entry bar.
- These windows are research constraints taken from `session_rules.py`. They are not a claim about broker trading hours.

## Risk

- Starting cash is 10,000 USD. That is the synthetic equity used by the offline harness, not a live balance.
- Risk per trade is 1% of realized cash, the source default of `POSITION_RISK_PCT`. Open profit is not added to the sizing equity.
- Units = cash * 0.01 / 0.002 for a valid EUR_USD stop. Quote currency is USD, so one price unit of stop is one USD per unit.
- A non-finite, missing, or non-positive stop distance cancels the entry. Size below 1 unit cancels the entry. The production rounding floor that forces 1 unit is not used.
- Exposure is the single open position. A second position is not opened.
- Cash at or below zero cancels new entries.

## Costs

- The primary ledger uses the bid and ask fills above and no extra slippage. Spread is not subtracted a second time.
- A midpoint figure on the same trades is reported only as a reference for the spread difference.
- Hypothetical extra adverse slippage of 0.00005 and 0.00010 per side is reported separately. 0.00005 is the existing paper constant in `simulate_execution_deterministic`. It is not a measured EUR_USD cost.
- Commission is not in the file and is not estimated.
- Financing is not in the file and is not estimated. Trades held overnight can carry an unmeasured swap.
- Unknown costs are not treated as zero in any real-world profit statement.

## What this specification does not do

- It does not change `Strategy.active` or `authorised_for_live`.
- It does not tune any threshold after results are seen.
- It does not claim that 20 pips, 2R, 1%, or the session window is an optimal trading rule.
