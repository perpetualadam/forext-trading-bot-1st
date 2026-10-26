# R.31 review of the R.30 simulator

Reviewed before any candidate performance run. The simulator file was not modified.

## Checked against the frozen R.30 lifecycle

- A signal at bar T is filled at the open of bar T+1, and only when that bar exists.
- A long enters on `ask_open` and exits on the bid. A short enters on `bid_open` and exits on the ask.
- An opposite signal sets an exit for the next open. It does not open the other side on that bar.
- If that next open is already beyond the stop or take-profit, the open is used and the reason is `stop_gap` or `take_profit_gap`.
- Friday 20:45–21:00 UTC, a closed FX week, or a bar that is not exactly five minutes later closes an open position at the exit-side open. A gap that is worse than the stop is filled at the open, not at the stop.
- A bar that touches both the stop and the take-profit, with the open between them, fills at the stop.
- A stop or take-profit touched alone fills at that price.
- After the entry open, the same bar's exit-side high and low can reach the bracket. That is the rule "tested on the bar after the entry open." The intrabar path is unknown, so a touched stop is taken.
- Repeated same-direction states do not schedule another entry. A new entry requires a direction change, a flat book, and a session-valid signal bar.
- Size is `cash * 0.01 / 0.002`. Realised P&L is added to cash when the trade closes. Open profit is not used for the next size.
- Signals are an input. The historical driver must build them with `signal_from_arrays` so bar T does not read a later bar. The R.30 EUR_USD run already matched prefixes at bars 200, 1,000, and 10,000.

## Not treated as a defect

- Holds may remain open after 22:00 UTC. The frozen rule blocks new entries outside the session. It does not add a 22:00 exit.
- A weekend jump is labelled `gap_exit` when the timestamp gap and the flatten window occur together. The fill is still the next open.
- `signal_from_arrays` treats infinity as a number because its finite check uses `isnan` only. The EUR_USD file used in R.30 had no non-finite quotes. That helper was not changed in this review.
- The midpoint column is an accounting reference. Stop and take-profit references use the order price, not a second bid/ask print.

## Conclusion

No material execution defect was found. The R.30 scalp results stay the baseline. Candidate runs must call this same simulator without editing it.
