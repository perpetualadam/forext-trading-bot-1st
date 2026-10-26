# R.71 Regression and Conflict Register

No conflict was patched.

| ID | Trigger | Functions | Consequence | Reproduced | Blocked | Correction | Stage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | Profit protection and a broker stop both exist | `apply_profit_protection`, `broker_sl_tp_hit` | The bot can software-close while a broker stop is unverified, or miss a broker stop fill because hit detection returns false | Source only | Live close is gated | Stop evidence before relying on either path | Stage 2 and 3 |
| C2 | Protection threshold and the original target | `activation_trigger_pips`, paper SL/TP compare | Paper can hit the stored target and the protection threshold in one pass. The close reason prefers SL/TP when that flag is set (`bot_loop.py` 1028) | Source only | No for a paper row | Record which trigger won | Stage 3 |
| C3 | Friday flatten and protection | `flatten_for_weekend`, protection branch | Both can request the same close. Flatten is an additional reason, not a second order, on one pass | Source only | Live order gate | Keep one close identity | Stage 4 |
| C4 | Empty broker snapshot and a local close | `COMPLETE_EMPTY`, `account_disappeared_broker_position` | A permitted row can disappear without a fill attributed to the bot | Prior R.70 test | Invalid snapshots cannot do this. Valid empty still can | Close attribution | Stage 3 |
| C5 | Manual broker position | Import plus ownership guard | Discovery stays observation-only and is not managed | R.71 predicate test | Management is refused | Keep the guard | Retained |
| C6 | Unit resize and original target | `adjust_position_units_to_broker`, `original_tp_distance_pips` | Activation uses price distance, not units, so a resize does not by itself move the trigger. MFE stays on the same object | Source only | Resize is for permitted rows | Do not treat this as a partial close | Stage 4 |
| C7 | One slot per symbol and several broker trades | `positions` dict, close of one unit total | One local row cannot represent two trades. Close sends one unit quantity | Source only | New entries blocked | Identity model | Stage 4 and 6 |
| C8 | Snapshot replacement during management | Generation lock, then unprotected manage | An invalid snapshot does not publish. A newer valid book can change the next cycle. There is no lock around the manage read | Prior R.70 | Invalid evidence fails closed | Stage 5 consistency | Stage 5 |
| C9 | Sizing versus margin | `position_sizing` | Units ignore margin. A GBP balance is not converted in the quote-risk branch | Formula test | Entry call is blocked | Currency and margin | Stage 7 |
| C10 | Restart versus RAM MFE and positions | `positions` dict | A restart loses the book, the ratchet, and the generation counter | Source only | Process was not restarted here | Recovery design | Stage 6 |

C5 is the R.68 boundary and is the safe side of that conflict. The others need a later stage.
