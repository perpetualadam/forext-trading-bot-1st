# V2.4 Cost Ledger

cost_ledger.py recomputes the price arithmetic with Decimal precision 40,
independently converts quote P/L, then tests gross and net against engine outputs.
The ledger includes actual quotes/fills, inferred-quote status, currencies,
conversion book/override, fees and residual. Unknown numeric inputs reject;
unavailable conversion rejects. Full records: outputs/v24/cost_ledger.jsonl.gz
(ignored research artifact); tracked representative records: cost_ledger_examples.json.

Reconciled 30782 scenario-trades; maximum gross/net
residual 1.3362e-11 account units.
Absolute tolerance 1e-7 is below 0.00001 of a USD/GBP penny and permits only float
replay roundoff; it is not a trading-cost allowance.

Waterfall: converted mid-reference P/L minus spread attribution (converted gross
less converted unslipped side P/L), minus slippage attribution (unslipped side
P/L less filled P/L), minus both commissions and funding equals net. No separate
FX fee is invented. Negative controls deduct spread or commission twice and
must fail reconciliation. These tests validate the declared model, not true
contemporaneous intrabar quotes.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
