# R.66 Reconciliation audit

Source review only. No broker snapshot was fetched and no database was opened.

## Books

| Book | Store | Startup |
| --- | --- | --- |
| Local positions | `forex_bot.positions.positions` RAM dict | Empty. `recover_orders` does not load it (`app.py` 574–579) |
| Local orders | `orders` RAM, reloaded from PostgreSQL | `load_open_orders_from_db_into_memory` |
| Broker positions | Fetched each reconcile | Not cached as the position book across a restart except through a new import |
| Broker pending orders | Fetched each reconcile | Imported into the local order map when unseen (`reconciliation.py` 666–721) |
| Stops and targets | Fields on the local `Position`, plus whatever the broker trade already has | Local fallback prices are not broker orders |

`run_reconciliation_once` is invoked at startup (`app.py` 585–595) and on a loop defaulting to 60 seconds (`app.py` 158–170). The loop's docstring says "log-only". The import flag does not follow that docstring.

## When broker rows enter RAM

`import_ok` is true when `RECONCILE_IMPORT_BROKER_POSITIONS` is set or the execution mode is `paper_broker` or `live_broker` (`reconciliation.py` 530–534). Default `RECONCILE_ACTION` is `log_only` (`reconciliation.py` 82–84). Import does not require `auto_fix`.

Case C (`reconciliation.py` 638–650): a broker net that has no local row is imported, subject to the fix cap. Case B displaces a paper-like local row when a broker position exists in broker execution mode (`reconciliation.py` 537–560). Neither case sends an order. Both can create a `reconcile_import` position.

`_import_broker_truth` copies broker units and average price. Direction is the sign of the net. Stop and target come from the trade, else pending orders, else a local 20-pip fallback (`reconciliation.py` 477–501). The fallback is labelled `local_fallback` and is not submitted.

Source default execution mode is `paper` when `EXECUTION_MODE` is unset and `PAPER_TRADING` is true (`execution.py` 109–114). In that mode `import_ok` is false unless the import environment flag is set. The flag and the mode in the user's environment were not read. Runtime mode is `NOT_VERIFIED`.

`fetch_broker_positions_detail` still calls OpenPositions when an API client and account id exist, including in paper mode (`reconciliation.py` 215–235). Missing credentials in paper mode return an empty dict and do not pretend a broker book was confirmed. Missing credentials in broker mode raise, so an outage is not an empty book (`reconciliation.py` 226–233).

## When the books disagree

| Situation | Source behaviour | Local belief afterwards |
| --- | --- | --- |
| Broker open, no local, import off | Logged if the mismatch report runs. No import | Bot believes there is no position. Broker position remains. Management does not see it |
| Broker open, no local, import on | Case C import | Bot believes it owns the position. Stop may be `local_fallback` only |
| Local `reconcile_import`, broker still open, protection or weekend close | `execute_trade` does not call PositionClose because kind is not `live` (`trading.py` 391, `execution.py` 232–234). `close_position` still runs (`bot_loop.py` 1084) | Bot believes the position is closed. Broker position remains. Next import can recreate the local row |
| Local kind `live`, broker still open, close succeeds | PositionClose then local delete | Both flat, if the close filled the whole size. Residual size is not checked (`R66-10`) |
| Local kind `live`, close times out | Exception, local kept | Bot still believes the position exists. Next cycle can PositionClose again (`R66-11`) |
| Local broker-backed, broker flat, `RECONCILE_ACTION=auto_fix` | `account_disappeared_broker_position` (`reconciliation.py` 614–628) | Depends on that helper's pending versus booked result. Not re-executed here |
| Local broker-backed, broker flat, `log_only` | Auto-fix block skipped | Local row can remain while the broker is flat |
| Paper local, broker flat | Preserved (`reconciliation.py` 563–579) | Simulation row kept |
| Manual close at the broker | Same as broker flat | Seen only on the next successful fetch |

`_may_auto_fix_local` is false unless `RECONCILE_ACTION=auto_fix` and the mode is a broker mode, or paper with `RECONCILE_AUTO_FIX_IN_PAPER` (`reconciliation.py` 434–452). The default does not delete locals when the broker is flat.

Pending-order sync can mark a local pending order cancelled when its broker id is absent (`reconciliation.py` 671–678) and can import unknown broker pendings as `import-{id}` (`reconciliation.py` 706–720). Those imports are local records. They are not new OrderCreate calls. A pending import uses the sign of units as direction. It does not prove a position.

## Identity and idempotency

Position identity for management is the symbol string in the RAM dict. One row per symbol. Broker trade ids are stored on import when the trade-details lookup works. A failed lookup still imports (`reconciliation.py` 467–475).

Order identity for reservations is `client_order_id`. Ambiguous open outcomes are supposed to be remembered by `remember_ambiguous_outcome` on the dead tail. The production cycle does not create those outcomes today.

Reconcile metadata can be written to PostgreSQL when persistence is enabled (`reconciliation.py` 200–212). This audit did not inspect the SQL for transactional boundaries. Atomicity of the order table versus the RAM book is `NOT_VERIFIED`.

The cycle task and the reconciliation task share the RAM book. No lock is visible at `get_position` versus `import_position_from_broker`. See `R66-16`.

## Answers the phase asked for

- The bot can believe a position exists when the broker is flat: yes, after an unconfirmed live close, or when `log_only` leaves a broker-backed row in place. Source-confirmed mechanism. Not observed at runtime.
- The bot can believe no position exists when one remains: yes, if import is off, or after a `reconcile_import` row is locally closed without PositionClose. Source-confirmed mechanism. Not observed at runtime.
- The bot can "manage" a manually opened broker position once import is on, and then drop it locally without closing it. Source-confirmed.
- The bot does not open a duplicate after an OrderCreate timeout on the current cycle, because it does not send OrderCreate.
- The bot can fail to notice an unprotected broker position whenever import is off, and it can store a non-broker stop when import is on (`R66-05`).
