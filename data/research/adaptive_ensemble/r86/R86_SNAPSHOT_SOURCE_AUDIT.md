# R.86 Snapshot Source Audit

Evidence: source inspection of the operational read paths. No live request was made. Contract details that are not in the repository stay unverified.

## Producers

| Producer | What it reads | Account scope | Trade ids | Pagination | Watermark | Cache |
| --- | --- | --- | --- | --- | --- | --- |
| `reconciliation.fetch_broker_positions_detail` | One `OpenPositions` request | `Config.OANDA_ACCOUNT_ID` | `long.tradeIDs` and `short.tradeIDs` | Not represented | Not read from this body | Publishes process memory `_last_broker_nets` and `_last_trade_ids` |
| `reconciliation._interpret_open_positions` | The positions list | None inside the body | Preserved per instrument | None | None | None |
| `startup_recovery.load_startup_broker_view` | The detail map above | `account_binding` of the configured account | Kept when exactly one id has a nonzero net | None | None | Uses the published ids |
| `oanda_client.fetch_pricing_snapshot` | Pricing, not positions | Configured instruments | No | No | No | `bot_loop._refresh_pricing_snapshot` |
| `oanda_account_adapter` | Injected account document | Document fields | Transaction pages, not open trades | `pages` without `transactions` is incomplete | `lastTransactionID` when the injected document has it | Not the position snapshot |
| `bot_loop._unified_market_snapshot` | Candles and a quote | One symbol | No | No | No | Explicitly not production provenance |

`OpenPositions` quantities are signed nets. Long units are positive and short units are negative in the interpreter. A zero net is omitted from the detail map. Several trade ids on one instrument are not collapsed into one comparable trade; startup emits broker-only rows with empty direction and units.

## Consumers

`evaluate_durable_row` compares that view with durable original units. Labels `INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `UNAVAILABLE`, `UNKNOWN`, and `CONFLICT` are non-authoritative. `COMPLETE_EMPTY` and `COMPLETE_NONEMPTY` are assigned when the positions key parses. Those labels mean the single response parsed. They do not mean every page was read, because this path has no page cursor.

`known_broker_net` returns the last successful cache, or zero for a symbol absent from that cache once a snapshot exists. A cached success can therefore be reused after a close until another successful fetch replaces it. The cache is process-local and is not tied to the recovery epoch.

`portfolio_exposure.approx_gross_usd_notional` sums `positions` only. `daily_report`, Telegram status, and `app.py` use that managed-book figure or equity fields. They do not read `quarantined_positions`.

## What is absent

The position snapshot path does not store request monotonic time, UTC observation time, process id, recovery epoch, or a transaction watermark. `lastTransactionID` exists on account-summary and order responses elsewhere. It is not attached to `load_startup_broker_view`. No field was invented on that view.

An error becomes `BrokerSnapshotError` with a classification. A missing client is `UNKNOWN` or `REQUEST_FAILED`, not an empty book. An empty positions list becomes `COMPLETE_EMPTY` in the existing interpreter. The new report does not accept that label as verified flat.
