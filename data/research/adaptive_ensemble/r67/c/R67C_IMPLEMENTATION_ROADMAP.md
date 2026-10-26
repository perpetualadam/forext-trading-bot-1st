# R.67C Implementation roadmap

Not implemented. Each stage is a later change to the operational bot. This stage does not edit those files. The production entry path stays blocked (`bot_loop.py` 3323–3328 and 1125–1134, `R66-01`). Do not open it in any stage. Do not change strategy, ensemble, RL, sizing, or trailing-stop parameters. Do not integrate R.62–R.65.

R.68, if it is authorised later, should do stage 1 only.

Broker facts that stay `NOT_VERIFIED` for every stage: live payloads, `PositionClose` idempotency, client-extension echo, decimal unit acceptance, partial allocation when `tradesClosed` is missing, hedging permission, and account currency. `.env` must stay unread.

## Stage 1 — Observation is not management

| Item | Plan |
| --- | --- |
| Files | `forex_bot/reconciliation.py` (`import_ok`, case C, `_import_broker_truth`), `forex_bot/positions.py` (`import_position_from_broker`), `forex_bot/execution.py` (`is_broker_backed`), `forex_bot/bot_loop.py` (the manage branch that treats a `reconcile_import` row as a position to flatten) |
| Findings | `R66-04`, `R66-16`. Invariants 1, 3, 4, 9 from R.67A. |
| Dependencies | R.67C clarifications C5 and C7. No database table. |
| Behaviour | A broker snapshot may be recorded as observation. `log_only` and broker mode do not create a row the manage loop will close or delete. `execution_kind` does not become a grant. |
| Offline tests | Import under `log_only` leaves management false. A weekend or protection path does not call `PositionClose` and does not delete the observation. |
| Database | None. Positions are RAM today. |
| Rollback | Restore the previous import and manage checks. Entry refusal stays. |
| Existing positions | RAM rows vanish on process restart already. A running process must be restarted for the new check to apply. Do not delete broker positions as part of rollback. |
| Cross-platform | Pure Python branch. No OS API. |
| Integration gate | Stage 1 tests pass on Windows and one Linux interpreter. Entry path still blocked. No broker call in the tests. |

## Stage 2 — Protection labels

| Item | Plan |
| --- | --- |
| Files | `forex_bot/reconciliation.py` (`_fields_from_broker_trade`, fallback block), `forex_bot/positions.py` (stop fields), `forex_bot/live_manage.py` (`broker_sl_tp_hit`) |
| Findings | `R66-03`, `R66-05`. R.67A protection states. Clarification C4. |
| Dependencies | Stage 1, so a fallback price is not sitting on a managed row. |
| Behaviour | Store local reference and broker stop id separately. Do not send a stop. `broker_sl_tp_hit` staying false is not `BROKER_PROTECTED`. Incomplete stop sections stay `PROTECTION_UNKNOWN`. |
| Offline tests | Fallback fixture is `LOCAL_REFERENCE_ONLY`. A trade payload without a complete stop section is `PROTECTION_UNKNOWN`. A payload with id and price is `BROKER_PROTECTED`. |
| Database | None until stage 4. RAM fields only if added. |
| Rollback | Previous price fields. Do not emit a corrective stop on rollback. |
| Existing positions | In-memory only. Restart loses them today. |
| Cross-platform | No OS API. |
| Unverified | Whether every TradeDetails body has a stop order id. |
| Integration gate | No order endpoint is called by the new label code. |

## Stage 3 — Close evidence

| Item | Plan |
| --- | --- |
| Files | `forex_bot/oanda_exec.py` (`_place_market_order_sync` return), `forex_bot/bot_loop.py` (the `close_position` call after `execute_trade`), `forex_bot/trading.py` (`execute_trade`) |
| Findings | `R66-10`. Clarification C1. |
| Dependencies | Stages 1 and 2. Still no new close authority for imports. |
| Behaviour | Parse fill units and `tradesClosed` when present. Do not delete the local row unless the evidence rule passes and a later read confirms flat. A shortfall keeps the remainder. |
| Offline tests | Synthetic bodies: full evidence, missing `tradesClosed`, sum mismatch, partial units. Assert the local row remains when evidence is short. |
| Database | No migration yet. Do not treat `exec_orders` as the close record. |
| Rollback | Restore the previous return pair. Do not replay closes on rollback. |
| Existing positions | A live-kind row in RAM can still be closed by today's code until this stage ships. Rollback must not invent a second close. |
| Cross-platform | Parser only. |
| Unverified | Live body shape. Decimal units. `ALL` is forbidden. |
| Integration gate | Tests use recorded bodies, not the network. Entry path stays blocked. |

## Stage 4 — One close at a time

| Item | Plan |
| --- | --- |
| Files | `forex_bot/oanda_exec.py`, `forex_bot/bot_loop.py`, `forex_bot/database.py` only if a new table is added in a reviewed migration |
| Findings | `R66-11`. Clarifications C2 and C3. |
| Dependencies | Stage 3 evidence parser. |
| Behaviour | Mint `close_operation_id` before send. Commit `CLOSE_SUBMITTING` first. Timeout becomes `CLOSE_OUTCOME_UNKNOWN` and blocks another close. Do not put this identity in `broker_exit_pending`, whose key is the symbol. |
| Offline tests | Two submitters, timeout, restart, commit failure before send, commit failure after send. |
| Database | Additive table only, in its own reviewed migration. Do not alter `exec_orders` or drop `broker_exit_ledger`. |
| Rollback | Stop reading the new table as permission to send. Leave rows in place. Do not resend unknowns. |
| Existing positions | No symbol-keyed pending row may be treated as a grant. |
| Cross-platform | SQL must be the same on the Windows and Linux database clients. The reference model does not prove that. |
| Unverified | Server-side idempotency. Extension echo. |
| Integration gate | `POSTGRESQL_INTEGRATION` still required before this stage is called done. `MODEL_TRANSACTION_TESTED` is not that gate. |

## Stage 5 — Versioned observation

| Item | Plan |
| --- | --- |
| Files | `forex_bot/positions.py`, `forex_bot/reconciliation.py`, `forex_bot/app.py` (task split only, no new broker call), `forex_bot/bot_loop.py` |
| Findings | `R66-16`. |
| Dependencies | Stages 1 and 4 so reconcile cannot grant and cannot clear a pending close. |
| Behaviour | Observation updates use a version. The loser re-reads and does not send. No lock is held across the broker call. |
| Offline tests | Stale version, reconcile during `CLOSE_SUBMITTING`, pending id preserved. |
| Database | Same additive records as stage 4 if the version is durable. RAM version is not enough across restart. |
| Rollback | Return to the dict updates. Pending close rows must still block sends. |
| Existing positions | One symbol key cannot represent two sides. Stage 5 must not blend them. |
| Cross-platform | Asyncio task split is already cross-platform. Lock duration is the risk, not the OS. |
| Integration gate | A test shows the loser does not call the close function. |

## Stage 6 — Restart

| Item | Plan |
| --- | --- |
| Files | `forex_bot/app.py` startup, `forex_bot/live_safety.py` (close exemption must not reload a grant), the stage 4 store |
| Findings | `R66-11`, `R66-17`. R.67A invariant 10. |
| Dependencies | Stage 4 rows exist. |
| Behaviour | `CLOSE_SUBMITTING` loads as `CLOSE_OUTCOME_UNKNOWN`. Unconsumed close grants load revoked. Execution memory starts empty. Protection evidence from the previous process loads stale or unknown. |
| Offline tests | Restart in `CLOSE_AUTHORISED`, `CLOSE_SUBMITTING`, and `CLOSE_OUTCOME_UNKNOWN`. |
| Database | Read path only if stage 4 already migrated. |
| Rollback | Do not treat a stored grant as sendable during rollback. |
| Existing positions | Order recovery (`app.py` 574–579) must not be reused as a close grant. |
| Cross-platform | Process start differs by service manager. The rule is in the first database read, not in the service manager. |
| Integration gate | A fresh process with a stored `CLOSE` row sends nothing. |

## What R.68 should not include

Stages 2 through 6, stop attachment, the entry tail, sizing, and process containment.
