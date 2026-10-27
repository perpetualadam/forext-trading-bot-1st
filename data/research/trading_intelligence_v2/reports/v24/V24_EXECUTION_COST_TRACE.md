# V2.4 Execution Cost Trace

Call path: isolated v24_run.py -> v24_pipeline.run -> study.acquire (local archive
hash verification) -> mtf_features.prepare -> v24_engine.run -> cost_ledger.reconcile.
Existing AST adapters supply unchanged signal and protection definitions.

Signal: previous completed candle; sizing: floor the minimum of per-trade risk,
remaining portfolio risk and remaining margin capacity. Entry BUY ask + slippage,
SELL bid - slippage. Stops/targets anchor to executed entry. Holding is chronological
M5 with MTF decisions only on completed higher candles. Opening gaps precede
entries; intrabar stop precedes target when both hit; time exits use closing quotes;
software protection requests the next open.

Accounting map (source, input, unit, sign, frequency):
- engine.run entry: observed bid/ask price, quote/base, embedded spread, one fill.
- engine.close: executable exit side, quote/base, embedded spread, one fill.
- both fills: Config.slippage_pips * pip_size, quote/base, adverse once per side.
- fee_unit: commission_per_100k_side / 100000, account/base unit; entry cash debit
  once, exit cash debit once. Net trade includes both fees; cash and trade net are
  alternative representations, never sequential debits.
- close funding: entry account notional * 0.0001 * UTC dates crossed, account debit.
- Quotes.convert: signed quote P/L to account money using causal graph; no cash fee
  deducted separately. Risk uses a liability conversion at planned stop fill.
- mark: unrealised liquidation P/L minus estimated exit commission; marks do not
  mutate cash or debit a second fee.
- gross: inferred midpoint-reference movement converted with exit FX override.
- cost_account = gross - net is reporting attribution, never a cash debit.
- optional spread/slippage components likewise never change cash.

Cost trace records actual entry quotes, assumed exit quotes, fills, currency graph,
override, fees and margin. Intrabar inferred quotes are explicitly labelled.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
