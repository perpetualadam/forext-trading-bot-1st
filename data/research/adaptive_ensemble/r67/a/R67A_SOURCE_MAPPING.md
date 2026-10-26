# R.67A Source mapping

The R.66 findings were rechecked against the working tree at commit `d080d897945bc44fa37c02caab504ed707146bec`. Hashes for `bot_loop.py`, `live_manage.py`, `reconciliation.py`, `oanda_exec.py`, `positions.py`, `execution.py`, `trading.py`, and `app.py` match `R66_SECURITY_REVIEW.md`. The design is for this source, not for an older copy. No operational file was edited.

Installed client used for endpoint names only: `oandapyV20` at `C:\Users\Brian\AppData\Roaming\Python\Python313\site-packages\oandapyV20`. No request was sent.

## Finding to contract

| Finding | Source today | Contract rule | Dimension affected |
| --- | --- | --- | --- |
| `R66-01` entry producer returns `blocked` when `simulation` is false. Status `continue_existing_production_broker` is never assigned. `production_adapter_refusal` returns `production_authority_unavailable` | `bot_loop.py` 1125–1134, 2922–2923, 3323–3328 | Leave this refusal in place. Do not mint `BOT_CREATED` or a `CLOSE` grant by opening the tail | Execution authority for opens stays absent |
| `R66-02` legacy tail reserves an id and returns before OrderCreate | `bot_loop.py` 1623–1706 | Out of scope for a behaviour change. The tail must stay unreachable. A reservation is not a position grant | None of the three dimensions may be set there |
| `R66-03` `broker_sl_tp_hit` returns false | `live_manage.py` 76–78, caller `bot_loop.py` 873–880 | False means "do not market-close from a local price." It does not mean `BROKER_PROTECTED`. Unknown stays unknown | Protection |
| `R66-04` broker mode imports under `log_only`. `reconcile_import` is deleted locally without `PositionClose` because only kind `live` calls the broker | `reconciliation.py` 530–534, 638–650; `positions.py` 169; `execution.py` 232–234; `trading.py` 391–398; `bot_loop.py` 1084 | Import writes observation only. `execution_kind` is not authority. Local delete requires broker evidence | Observation must not become management or execution |
| `R66-05` missing broker stop becomes a 20-pip `local_fallback` on the position | `reconciliation.py` 491–501; `positions.py` 171–211 | That price is `LOCAL_REFERENCE_ONLY`. It is never `BROKER_PROTECTED`. Do not send a replacement stop | Protection |
| `R66-06` import sets `profit_protection_seeded` so historical MFE is skipped | `positions.py` 215; `profit_protection.py` 524–526 | Not an authority grant. A monitor, if one existed, would treat the peak as unknown. This design does not enable the close that seeding would arm | Management request only, and only after a future `MONITOR` grant |
| `R66-10` close response has no closed-unit count; the whole local row is removed | `oanda_exec.py` 435–450; `bot_loop.py` 1058–1084 | Full close requires fill units or a later trade read plus a closing transaction. Otherwise the identity stays open or `CLOSE_AMBIGUOUS` | Execution result is not observation of flat |
| `R66-11` timeout becomes `RuntimeError`; the next cycle can `PositionClose` again; no client id on the request | `oanda_exec.py` 418–433; `bot_loop.py` 686–690. `PositionCloseRequest` can carry client extensions; the bot does not set them. Echo of those extensions on a fill is `NOT_VERIFIED` | One `pending_close_id` blocks another submit until a read resolves it. Restart does not restore a `CLOSE` grant | Execution authority is spent or absent |
| `R66-16` two tasks share the RAM dict | `positions.py` 8–9; `app.py` 630–633 | Observation writes and authority writes are different records. Reconcile must not write grants | All three |

## Identity mapping

| Contract field | Where a related value exists now | Gap |
| --- | --- | --- |
| `account_id` | `Config.OANDA_ACCOUNT_ID` is read inside reconcile and close helpers. The value was not printed | Not stored on `Position` |
| `instrument` | `Position.symbol`, one key in `positions` | Both sides of one instrument share that key |
| `book_side` | `direction` BUY or SELL derived from the sign of net units (`positions.py` 194) | Long and short together are blended (`reconciliation.py` 270–279) |
| `trade_ids` | `broker_trade_ids` comma string; `_last_trade_ids` from `tradeIDs` | First id is used for `TradeDetails` (`reconciliation.py` 465–474). Other ids are not a protection read |
| `broker_units` | Net units copied into `Position.units` | Not retained as a snapshot with an id |
| `local_tracking_id` | Absent. `client_order_id` is an order id when present | Import may leave it empty |
| `provenance` | `execution_kind` and `strategy_name="reconcile_import"` | Those strings are labels, not evidence classes |
| `authority_source` / `authority_scope` | Absent. Close uses `execution_kind == "live"` | The contract's grants do not exist |
| `snapshot_id` | `_last_broker_nets` after a successful OpenPositions (`reconciliation.py` 325–328) | Nets only. No hash, no per-trade snapshot |
| `pending_close_id` | Absent on `PositionClose` | `R66-11` |

## Endpoint mapping

| Desired evidence | Installed client | Bot caller | Verified from a live response |
| --- | --- | --- | --- |
| Open sides, units, trade id list | `OpenPositions` | `fetch_broker_positions_detail` | `NOT_VERIFIED` |
| Stop order id and price for one trade | `TradeDetails` | `fetch_trade_details_sync`; parser keeps price, open time, client id, trade id | `NOT_VERIFIED` |
| Instrument-side unit close | `PositionClose` | `_place_market_order_sync` | `NOT_VERIFIED` |
| Close one trade id | `TradeClose` | No caller | `NOT_VERIFIED` |
| Closing transaction after a trade disappears | `TradeDetails` then transaction details | `broker_exit.resolve_broker_exit` | `NOT_VERIFIED` |

Account hedging permission, partial-close allocation across trades inside one `PositionClose`, and whether client extensions return on that close are `NOT_VERIFIED`.

## Entry path

No row in this mapping authorises `evaluate_one_instrument_iteration` to return a continue status. No row authorises `production_execution_adapter` to pass `production_adapter_refusal`. Observation of an existing broker position is not an entry signal.
