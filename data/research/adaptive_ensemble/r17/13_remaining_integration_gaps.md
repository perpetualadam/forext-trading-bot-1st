# Remaining integration gaps

1. No approved numeric spread threshold. Structural quotes are enforced. A wide finite spread is not a production spread block.
2. Missing quote timestamps have no freshness block. The 90-second window applies only when a timestamp is supplied.
3. Production market-data provenance is not verified. Synthetic harness quotes are not broker quotes.
4. Daily-loss and drawdown protection is off in production defaults. The JSON latch was not proven across a process restart and is not a production ledger.
5. The existing risk function treats the first positive equity as the drawdown peak.
6. Margin sufficiency is not implemented. Equity is not margin proof.
7. Broker-flat reconciliation is not implemented. `confirm_exposure_flat` still refuses every token.
8. Production account identity and freshness remain unverified.
9. PostgreSQL, OANDA, the production loop, and profitability were not evaluated.

Recommended next stage: an offline contract for an approved spread policy and a real margin-evidence source, still without orders, only after a separate authorisation. Do not start that work from this stage.
