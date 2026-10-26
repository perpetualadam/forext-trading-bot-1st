# R.67A Protection status contract

Design only. No protective order is sent by this stage. A missing stop stays missing until some later reviewed stage, which this document does not authorise. `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Fields

These fields are separate. A price in `local_stop_reference` must not be copied into `confirmed_broker_stop_price` by import.

| Field | Contents | Current source |
| --- | --- | --- |
| `local_stop_reference` | A price the bot calculated or copied for display. Source tag required: `local`, `local_fallback`, `pending_order_price`, or `trade_price_without_id` | `Position.stop_loss` plus `sl_source` (`positions.py` 18–28). Import default `local_fallback` (`positions.py` 171) |
| `confirmed_broker_stop_price` | Price from a broker stop order that also has an id | Not stored. `_fields_from_broker_trade` keeps `stopLossOrder.price` only (`reconciliation.py` 375–388) |
| `broker_stop_order_id` | The stop order's broker id, bound to `trade_id` | Not parsed. `NOT_VERIFIED` whether every TradeDetails payload includes that id. The current parser cannot enter `BROKER_PROTECTED` even if the payload has it |
| `broker_stop_verified_at` | Timestamp of the read that produced the id and price together | Absent |
| `take_profit_source` | `broker_order_id`, `pending_price_only`, `local_fallback`, or `absent` | `tp_source` is a string. `broker_trade` today means a price was found, not an id (`reconciliation.py` 485–490) |
| `protection_confidence` | The state enum below. One state per trade id, not per blended instrument | Absent. `broker_sl_tp_hit` ignores the row (`live_manage.py` 76–78, `R66-03`) |
| `protection_missing` | True only in `UNPROTECTED_CONFIRMED` | A fallback price hides the miss (`R66-05`) |
| `protection_stale` | True only in `PROTECTION_STALE` | Absent |
| `protection_unknown` | True in `PROTECTION_UNKNOWN` and whenever the trade id is missing | The honest state for every current import |

Take-profit uses the same evidence rule. A target price without an order id is `LOCAL_REFERENCE_ONLY` for the target and does not confirm protection. This contract's stop states are about loss protection. A target is not a stop.

The freshness window is not chosen here. A later stage must name it. This design uses the symbol `PROTECTION_FRESHNESS` and does not set a number, so it does not change a trading parameter.

## States

| State | Evidence required to enter | Evidence that forbids the state |
| --- | --- | --- |
| `BROKER_PROTECTED` | A successful `TradeDetails` read for one `trade_id` on one `book_side` of one account, containing a stop order id, a finite price, and that trade id, with `broker_stop_verified_at` inside `PROTECTION_FRESHNESS`. A second read is not required to enter. A later disagreeing read ejects the state | Price only. `sl_source` of `local_fallback`, `local`, `broker_pending`, or `broker_trade` as those tags exist today. `OpenPositions`, which the bot's own comment says omits stops (`oanda_exec.py` 599) |
| `LOCAL_REFERENCE_ONLY` | A local or copied price exists, and the broker stop id is absent. This includes the 20-pip fallback from `sl_tp_distance_for_entry` (`reconciliation.py` 491–498, `R66-05`) | Must not be labelled `BROKER_PROTECTED` |
| `UNPROTECTED_CONFIRMED` | A fresh `TradeDetails` read for that trade id succeeded, and the stop order field is null or absent. The read is inside `PROTECTION_FRESHNESS` | A fallback price. A failed read. An unread trade |
| `PROTECTION_UNKNOWN` | No successful trade read, the read errored, the trade id list is empty, both sides have units, or the account id is missing | Must not be relabelled by writing a fallback price |
| `PROTECTION_STALE` | The last state was `BROKER_PROTECTED` or `UNPROTECTED_CONFIRMED`, and the verification time is outside `PROTECTION_FRESHNESS`, or a newer snapshot does not repeat the same stop order id | A stale `BROKER_PROTECTED` must not remain `BROKER_PROTECTED` |

`broker_pending` prices (`reconciliation.py` 392–401 and 477–483) are `LOCAL_REFERENCE_ONLY` until the pending order id is stored and a later trade read shows that id attached to the trade. A pending stop that is not attached is not `BROKER_PROTECTED`. Attachment is `NOT_VERIFIED` from a live order. The current code copies the price and drops the distinction by falling through to one `stop_loss` float.

## Confidence and missing protection

`protection_confidence` is exactly one of the five states per trade id. Instrument-level confidence is the worst state among that side's trade ids. Worst order, from least confirmed to most:

`PROTECTION_UNKNOWN`, then `PROTECTION_STALE`, then `LOCAL_REFERENCE_ONLY`, then `UNPROTECTED_CONFIRMED`, then `BROKER_PROTECTED`.

If any trade id is unknown, the instrument side is unknown. A blended net (`reconciliation.py` 277–279) is `PROTECTION_UNKNOWN` for management purposes even if one trade looked protected.

`protection_missing` is true only for `UNPROTECTED_CONFIRMED`. Unknown is not the same fact as missing. The bot must not "repair" unknown or missing by sending a stop. This stage has no authority to change broker state, and the ownership contract would still require a separate grant for any future protective order. No such grant is defined here.

## What management may do with each state

Management itself is off for imports. If a later `MONITOR` grant exists:

| State | Allowed monitoring | Forbidden |
| --- | --- | --- |
| `BROKER_PROTECTED` | Record that the broker stop is the hard exit. Do not also pretend the local price is that stop unless the prices were both on the verified order | Sending a replacement stop because the local ratchet moved (`profit_protection.py` 265–280 is local only) |
| `LOCAL_REFERENCE_ONLY` | Show the reference. It can inform a human. It is not a broker exit | `broker_sl_tp_hit` true. Calling the reference a confirmed stop |
| `UNPROTECTED_CONFIRMED` | Show unprotected. A close still needs a `CLOSE` grant | Automatically attaching a stop |
| `PROTECTION_UNKNOWN` | Show unknown. Fail closed for any claim of safety | Treating `broker_sl_tp_hit`'s false return as proof that the broker is protecting the trade (`R66-03`) |
| `PROTECTION_STALE` | Show stale. Do not keep the old "protected" label | Using the expired id as current proof |

`broker_sl_tp_hit` returning false is compatible with "the application does not market-close on a local price." It is not evidence for `BROKER_PROTECTED`. The contract keeps the hard broker exit at the broker only when the state is `BROKER_PROTECTED`. In every other state the position is not described as protected.

## Restart

Protection evidence older than the process, or unverified in this process, loads as `PROTECTION_STALE` if a prior verification record exists, and as `PROTECTION_UNKNOWN` if it does not. A RAM `stop_loss` does not survive today (`positions` is in-memory). A future row that only stored the price loads as `LOCAL_REFERENCE_ONLY` or `PROTECTION_UNKNOWN`, never as `BROKER_PROTECTED`, until a new trade read in the new process supplies the order id.
