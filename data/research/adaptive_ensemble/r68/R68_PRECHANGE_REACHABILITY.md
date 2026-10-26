# R.68 pre-change reachability

Baseline commit `d080d897945bc44fa37c02caab504ed707146bec`. Hashes below are the R.67C working-tree hashes, confirmed unchanged at the start of R.68 before these edits.

| Path | SHA-256 before R.68 |
| --- | --- |
| `forex_bot/positions.py` | `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a` |
| `forex_bot/reconciliation.py` | `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b` |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/broker_exit.py` | `d9920eed6160c5f26e1db7ee34095488b3457755e5dbf21cffbeda08eb798c12` |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |

## Call graph

1. Broker position retrieval is `OpenPositions` inside reconciliation. A fetch failure keeps the previous snapshot.
2. Parsing keeps a stop price. It does not keep a stop order id.
3. `import_ok` is true when `RECONCILE_IMPORT_BROKER_POSITIONS` is set or the execution mode is `paper_broker` or `live_broker`. `RECONCILE_ACTION` default `log_only` does not turn `import_ok` off. `auto_fix` is a separate branch.
4. Case C, broker-only symbol: `_import_broker_truth` then `import_position_from_broker`, which assigned `positions[symbol]`.
5. Case B, paper-like local row and nonzero broker net: `displace_paper_position` removed the paper row, then the same import wrote a `reconcile_import` row.
6. `import_position_from_broker` stored `execution_kind` from its argument (default `reconcile_import`), `broker_order=True`, and `profit_protection_seeded=True`.
7. `get_position` reads that same `positions` dict.
8. `is_broker_backed` is true for kinds `live` and `reconcile_import`, and for `broker_order=True`.
9. `run_bot` calls the manage branch whenever `get_position` returns a row. `if pos:` at the former line 788 ran quote selection, profit protection, weekend flatten, stop comparison, `execute_trade`, and `close_position(symbol)`.
10. `execute_trade` calls `PositionClose` only when `execution_kind == "live"`.
11. `close_position` popped the dict unconditionally. A `reconcile_import` weekend or profit-protection close therefore deleted the local row without `PositionClose`.
12. If the imported row was stored with `execution_kind="live"`, the same branch could reach `PositionClose`.
13. `auto_fix` on a broker-backed local row with broker net near zero calls `account_disappeared_broker_position`, which `positions.pop`s the symbol even when the broker exit is unresolved. It also calls `adjust_position_units_to_broker` when the net differs.
14. `close_local_position` popped directly. No other production caller was found.
15. `broker_exit.py` does not send orders. Its disappear helper is the pop above.

## Classification before the patch

| Path | Provenance it can see | Action |
| --- | --- | --- |
| Case C import | Broker discovery, including a manual broker position | Inserts a managed RAM row |
| Case B | Paper local plus broker discovery | Deletes paper, inserts a managed row |
| `log_only` with import enabled by mode or flag | Broker discovery | Same insert. `log_only` does not keep it observational |
| `auto_fix` | Any broker-backed row already in `positions` | Can resize or pop it |
| Manage `if pos:` | Whatever is in `positions` | Quote, protect, weekend flatten, then local delete |
| `execute_trade` | Row whose kind is `live` | `PositionClose` |
| `close_position` | Any resident row | Local delete |
| Paper open path | `paper`, `simulated`, `window_paper` | Existing paper management |
| Bot `open_position` after a fill | `live` when the fill path is broker, otherwise `simulated` or `window_paper` | Existing management. This tail is not reached from `run_bot` while the entry status stays blocked |
| `orders.py` synthetic recorder | `synthetic` | Local row only. Not a broker close kind |

`execution_kind="live"` and a broker trade id were not proof that this process opened the trade. The pre-change import function would store a caller-supplied kind on the managed row.
