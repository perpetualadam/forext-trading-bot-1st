# R.81 submission call graph

Evidence class: static source inspection of the R.81 tree. Line numbers are the post-fix file.

## Entry sink

`_submit_order_create` in `forex_bot/oanda_exec.py`.

Callers that reach it:

- `_place_market_order_open_sync` (line 581) calls it directly.
- `execute_oanda_market_open` (line 630) calls `_place_market_order_open_sync` on a worker thread.
- `bot_loop.py` reaches the open helper from the cycle. R.81 did not execute `run_bot`.

Actual order inside `_submit_order_create`:

1. The permit must be an `EntrySubmissionPermit` (lines 506–507).
2. `live_management_permitted()` (lines 510–511). This is before the durable claim.
3. `assert_new_live_exposure_allowed` and `require_order_quote` (lines 512–513).
4. `claim_entry_permit` (line 515). This sets `network_permit=1`. A journal failure raises `EntryGuardRefusal` and does not request.
5. The `OrderCreate` object is built (lines 533–545). `clientExtensions.id` is a label. The comment in the request is not a broker idempotency key.
6. The R.80 check calls `live_management_permitted()` again (lines 546–547).
7. `acquire_oanda_rest_slot()` (lines 550–552).
8. The R.81 check calls `live_management_permitted()` again (lines 553–554).
9. `api.request` (line 555).

After the sink, `_place_market_order_open_sync` marks a timeout `ENTRY_OUTCOME_AMBIGUOUS` (lines 591–593). `record_entry_response` then calls `commit_verified_entry` and publishes memory only when `recovery_fence_allows_publication()` is true (`entry_capture.py` 103–117).

## Close sink

`_submit_position_close_body` in `forex_bot/oanda_exec.py`.

Callers:

- `run_guarded_live_close` in `broker_close_evidence.py` (around line 711) is the guarded operational path.
- `_place_market_order_sync` (line 474) calls the same sink.

Actual order:

1. `run_guarded_live_close` checks management permission, one trade id, the durable position, and `blocking_trade` before it reserves (`broker_close_evidence.py` 615–677).
2. The permit object is checked (lines 410–411).
3. `live_management_permitted()` (lines 414–415), before `claim_network_permit` (line 417).
4. The `PositionClose` object is built (lines 446–448). Client extensions are not sent.
5. The R.80 check (lines 449–450).
6. `acquire_oanda_rest_slot()` (lines 452–454).
7. The R.81 check (lines 455–456).
8. `api.request` (line 457).

`CloseGuardRefusal` and `EntryGuardRefusal` raised by the R.81 check propagate out of the rate-limit `try`. The close handler records `CLOSE_RECONCILIATION_REQUIRED` / `submission_authority_refused` / `NOT_SENT`. The permit stays consumed. A timeout is `CLOSE_OUTCOME_AMBIGUOUS` and is not retried.

## Other `api.request` sites

- `oanda_client._oanda_request` (line 301) is the read helper. It retries transient read failures. It is used for account summary, transaction details, and other reads. It is not an order or close sink.
- `oanda_candles_read.py` line 131 reads candles.

A repository search found no `TradeClose`, `TradeCRCDO`, `OrderCancel`, or `OrderReplace` submission function. The only write calls are the two sinks above, and both pass the R.80 and R.81 checks before `api.request`.

No unguarded operational write sink was found. Executable tests were not stopped.

## Residual race

The R.81 check and `api.request` are still separate statements. Authority can change after line 554 or 456 and before, or during, `api.request`. That remaining window is not atomic. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` stays.
