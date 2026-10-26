# Remaining integration gaps

1. No approved numeric spread threshold. Production eligibility stays false for that gate.
2. Margin sufficiency is not implemented. Equity is not a substitute.
3. Production account provenance, production market provenance, and production quote provenance are missing.
4. A synthetic timestamp can satisfy the 90-second harness window. It does not prove production freshness.
5. Daily-loss durability across process restart was not executed.
6. Broker-flat release, PostgreSQL, OANDA, the production loop, and profitability were not evaluated.

These gaps are visible on the decision record. They are not passes.
