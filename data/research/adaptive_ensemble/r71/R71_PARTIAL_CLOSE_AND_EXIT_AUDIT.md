# R.71 Partial Close and Exit Audit

## What exists

- A full local close after `execute_trade` returns (`bot_loop.py` 1098).
- A full `PositionClose` for a live kind, using the absolute unit size (`oanda_exec.py` 411–424). There is no client order id on that request.
- An entry path that can mark `OrderStatus.PARTIAL` when filled units are below requested units (`bot_loop.py` 1783–1786). That code sits after the early `return` at line 1719 in the legacy tail, and the shared entry status never continues into it. It is unreachable.
- Reconcile can resize a permitted local row toward a broker net. That is a book adjustment, not a bot partial-close order.
- Weekend flatten, local SL/TP, and profit protection share the same close call.
- `account_disappeared_broker_position` can pop a permitted row when a complete empty snapshot says the broker is flat. R.70 still does not treat that snapshot as proof that this bot's close filled.

## What is missing

- A strategy partial close that requests a fraction and retains the remainder.
- A comparison of broker-confirmed closed units with the requested units before `close_position`.
- A stable close-operation identity.
- Timeout handling that blocks a second close. The protection cooldown is 30 seconds in memory and is not a broker identity.
- Attribution from a closing transaction back to the bot's attempt.

R66-10 and R66-11 remain open. The R.67B close state machine was not implemented. This audit did not add one.

## Exit path by trigger

| Trigger | Function | Broker write | Local delete |
| --- | --- | --- | --- |
| Paper SL/TP | `_evaluate_impl` then `execute_trade` | No | Yes, if `execute_trade` returns |
| Profit protection, non-live | Same | No | Yes, if it returns |
| Profit protection, live, orders off | `execute_trade` raises | No | No |
| Profit protection, live, orders on | `PositionClose` | Yes, not executed here | Yes after the helper returns, without a unit match |
| Weekend flatten | Same close call | Depends on kind | Same |
| Broker stop fill | Not detected | Not inferred | Not inferred |
| Manual broker close | Reconcile disappear on a complete empty book | No close from the bot | Possible for a permitted row |
