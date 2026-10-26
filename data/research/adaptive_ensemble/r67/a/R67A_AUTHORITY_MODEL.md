# R.67A Authority model

Design only. Evaluated against the source rechecked for R.67A. No grant in this document is implemented. Production entries remain blocked. `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Identity

OANDA objects in the installed client `oandapyV20` (read from local package source, not from a broker call):

| Client type | Endpoint in the installed package | What the bot does |
| --- | --- | --- |
| `OpenPositions` | `v3/accounts/{accountID}/openPositions` | `reconciliation.fetch_broker_positions_detail` reads it (`reconciliation.py` 239–286) |
| `PositionClose` | `v3/accounts/{accountID}/positions/{instrument}/close` | `_place_market_order_sync` sends `longUnits` or `shortUnits` (`oanda_exec.py` 397–425) |
| `TradeDetails` | `v3/accounts/{accountID}/trades/{tradeID}` | `fetch_trade_details_sync` reads one trade (`oanda_exec.py` 595–611) |
| `TradeClose` | `v3/accounts/{accountID}/trades/{tradeID}/close` | Present on the client. Not called by `oanda_exec.py` |

`PositionCloseRequest` accepts `longUnits`, `shortUnits`, and optional client-extension dicts. The bot sets units only. It does not set `longClientExtensions` or `shortClientExtensions`. The package docstring describes units as an integer. The bot passes a decimal string from `_abs_units_decimal`. Whether the practice or live host accepts that string is `NOT_VERIFIED`.

`OpenPositions` in the bot is parsed as an instrument object with a `long` side and a `short` side, each with `units`, `averagePrice`, and `tradeIDs` (`reconciliation.py` 248–286). The comment in `oanda_exec.py` 599 states that this payload does not include stop, target, or open time. That limitation is source-confirmed for the parser. A live sample was not fetched.

The bot then stores one `Position` per symbol (`positions.py` 1–9). Multiple trade ids are joined into `broker_trade_ids` (`broker_exit.py` 105–117). If both sides have units, the average price is a blend (`reconciliation.py` 277–279). This contract forbids that blend as a management identity.

### Required identity fields

| Field | Rule |
| --- | --- |
| `account_id` | The account the snapshot was read from. Empty is `PROVENANCE_UNKNOWN` and cannot be managed |
| `instrument` | Canonical `BASE_QUOTE` from the snapshot. A symbol key alone is not enough |
| `book_side` | `LONG` or `SHORT`, matching the OpenPositions side. A net of both sides is not a side |
| `trade_ids` | The trade ids on that side. Empty when the snapshot listed none: identity is incomplete and stays observation |
| `broker_units` | Units from the last fresh snapshot for that side, signed as the broker reported. Local `units` is not a substitute |
| `local_tracking_id` | An id minted by the bot for its record. It does not equal a broker trade id |
| `provenance` | One class from the ownership contract |
| `authority_source` | `NONE`, or the grant id. Never `execution_kind`, never the trade id |
| `authority_scope` | Empty, `MONITOR`, or one action (`CLOSE` with a unit quantity and attempt id). Scope does not imply a wider scope |
| `authority_expiry` | A timestamp on the grant. Missing expiry on a grant means the grant is invalid |
| `revoked_at` | Set by an explicit revoke or by process start for every execution grant |
| `snapshot_id` | Id of the last verified broker read: time, endpoint name, and a hash of the identity fields plus units. `NOT_VERIFIED` as a wire format. The field is required before management |
| `pending_close_id` | Empty, or the single attempt id of an unresolved close |

Hedging: the parser can see both sides on one instrument. Whether this account is allowed to hold both is `NOT_VERIFIED`. Until a snapshot shows only one side with units, management of that instrument is forbidden. The bot must record both sides as separate observations and must not net them.

Partial reduction: the identity remains the trade ids that the fresh snapshot still lists. Closed units are a child record (`PARTIAL_REDUCTION`) tied to a fill or a closing transaction. The local unit count becomes the new broker unit count only after that read. Deleting the parent because a close response lacked units is forbidden (`R66-10`).

`TradeClose` is the client operation that names one trade. `PositionClose` names an instrument side and a unit count. This design allows a future `CLOSE` grant to name either operation. The grant must say which one. A `PositionClose` grant does not authorise `TradeClose`, and the reverse is also false. The current sender only implements `PositionClose`. Using `TradeClose` is `NOT_VERIFIED` in this bot. The design does not switch the sender.

## Grants

A grant is a record, not a mode flag.

| Grant | Fields that must match the observation | Effect |
| --- | --- | --- |
| `MONITOR` | account, instrument, book side, trade ids, snapshot id | Management becomes true. Execution stays false |
| `CLOSE` | those same fields, plus units not greater than `broker_units`, plus one `attempt_id` | One submission of the named endpoint may be attempted |

Grants are single-purpose. A `MONITOR` grant does not contain a hidden close. A `CLOSE` grant does not remain valid after the attempt starts, after expiry, after revocation, or after the snapshot id changes.

Who may create a grant is an operator action or a future bot-create ceremony that records the fill transaction of an order this bot submitted. Import, reconcile, restart, and `execution_kind` are not creators. The production entry path is blocked, so the bot-create ceremony has no current event to attach to (`R66-01`). This design does not enable that path in order to mint grants.

Process start clears effective execution authority even if a database row remembers an old grant. Remembering history is allowed. Treating the row as permission is forbidden. That follows the same shape as `initialise_fail_closed`, which ignores a stored "allowed" open flag for the new process (`live_safety.py` 401–402), and it closes the hole where close is exempt (`live_safety.py` 105–106). Reloading orders from PostgreSQL (`app.py` 574–579) must not reload a close grant as effective.

## Invariants

| # | Invariant | Evaluation against current source |
| --- | --- | --- |
| 1 | Observation does not imply management | Violated. Import writes the row that `_evaluate_impl` manages (`R66-04`) |
| 2 | Management does not imply execution authority | Violated for kind `live`: the manage branch calls `execute_trade`, which calls `PositionClose` (`trading.py` 391–398). For `reconcile_import` the broker is not called, but the local row is still removed, which is a different breach (invariant 7) |
| 3 | Importing a broker position cannot authorise a close | Violated as a local close for `reconcile_import`, and not a broker close. The import itself is the step that creates the manageable row (`R66-04`) |
| 4 | A broker close requires explicit action-scoped authority | Absent. Close authority is `execution_kind == "live"` plus broker orders enabled |
| 5 | Missing authority fails closed | True for new entries (`R66-01`). False for live closes, which proceed without a close grant |
| 6 | A locally stored stop cannot prove a broker-side stop | Violated by storing fallback prices on the same `stop_loss` field (`R66-05`). `broker_sl_tp_hit` does not treat that field as a hit (`R66-03`), which avoids one false close and does not create proof |
| 7 | A position cannot be declared fully closed without broker evidence | Violated. `close_position` follows any non-raising `execute_trade` (`bot_loop.py` 1084, `R66-10`) |
| 8 | An ambiguous close blocks further close submission until resolved | Violated. Timeout keeps the row and the next cycle can send again (`R66-11`). There is no `pending_close_id` |
| 9 | Reconciliation cannot silently grant new authority | Violated. `import_ok` follows broker mode, not an authority record (`reconciliation.py` 530) |
| 10 | Restart cannot restore execution authority from RAM or a database row | RAM positions are empty after restart, which accidentally satisfies this for positions. Order recovery and a future position table must not be treated as a grant. Effective execution authority after start is defined to be empty |

Invariants 1–4 and 7–9 fail in the current source. Invariant 5 holds for entries and fails for live closes. Invariant 6 fails as proof and holds as "the hit function does not fire." Invariant 10 holds only because positions are not persisted. The contract requires it to keep holding if persistence is added later.

## Ambiguous close

Before any close bytes are sent, the bot writes `pending_close_id` equal to the attempt id and marks the identity `CLOSE_AMBIGUOUS`. If the process dies after the send and before the response, restart loads that pending id as ambiguous and loads no execution authority.

Resolution is a read of `TradeDetails` and, when the source already does this for disappeared trades, the closing transaction (`broker_exit.resolve_broker_exit`, `broker_exit.py` 176). Resolution may set `OBSERVED_FLAT` or `PARTIAL_REDUCTION`. It does not mint a new `CLOSE` grant. A second close needs a new grant and a new attempt id. The current `PositionClose` has no attempt id (`R66-11`). Whether `longClientExtensions` is returned on the fill is `NOT_VERIFIED`. Until that echo is verified, the bot must not treat a missing echo as failure or as success. It stays ambiguous until trade and transaction reads classify the units.

## Human control

The bot must not disable the account, revoke an OANDA login, or reject an external client. The traced open and close helpers do not call such an endpoint. A person can close or amend a trade in the broker's own tools while the bot has no grant. The bot's duty is to notice that change on a later read and to record `OBSERVED_FLAT` or a reduced unit count without claiming it performed the close.

If the bot holds `CLOSE_AMBIGUOUS`, it still must not send a competing close. The human action remains possible. The bot waits for a read. It does not sit on an account lock. No account-lock API was found in the bot's close path. Whether OANDA offers one elsewhere is `NOT_VERIFIED` and is out of scope.

Emergency flatten by the bot is not created here. An emergency still requires a `CLOSE` grant with a named attempt. Absence of that grant fails closed inside the bot and leaves the broker's own controls available.
