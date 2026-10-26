# R.71 Remaining Risks

Production trading remains NO-GO.

## Open safety behaviour

- `broker_sl_tp_hit` returns false. A broker stop fill is not detected here.
- Local stop and target prices are not broker stops.
- A managed close deletes the local row when `execute_trade` returns. Live mode does not prove filled units first.
- `PositionClose` has no idempotency key.
- A valid empty broker snapshot can still drop a permitted live row. That is not close attribution.
- Stop-risk for EUR_USD is quote USD, not a converted account currency.
- MFE, the ratchet, and the position book die with the process.
- The strategy tail is unreachable, which is the safe state, and it also means historical entry features are not active.

## Not verified

- The original Trailing Stop Strategy conversation.
- Legacy pytest modules.
- Linux execution of the operational import.
- PostgreSQL.
- Any broker practice or live call.
- Whether the live candle loader drops the forming bar before ATR.
- Profitability.

## Intentionally untouched

Operational source, source gates, the consumed marker, reconciliation, ownership, sizing formulas, and profit-protection formulas.

The next implementation stage, when separately authorised, is broker protection evidence. This audit does not start it.
