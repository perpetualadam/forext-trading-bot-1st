# Optional and disabled controls

Production defaults are unchanged.

- Gross notional stays disabled at percentage 0 and is recorded as `DISABLED`.
- The unit cap stays disabled at 0 and is recorded as `DISABLED`.
- `DECISION_REPAIR_ACCOUNT_RISK` stays off. Daily loss and drawdown are `DISABLED`.
- When a test enables the existing gross or unit cap, a breach still blocks before reservation.
- When a test enables the existing account-risk flag, the existing 2% and 5% boundaries still block, and a fabricated payload does not clear the halt.
- A disabled control is not evidence that a mandatory gate passed.
