# Remaining blockers

R.55 Boundary A has no unresolved safety defect in the offline session. These items remain because no live response was collected:

- Boundary B is not approved. No live API session is authorised.
- `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` stays in force. A GBP conversion factor would not establish the account home currency.
- Instrument type `CURRENCY` does not establish spread-betting stake semantics. Quantity 1 is not treated as £1 per pip.
- `stake_settlement` remains `UNKNOWN`. No executable position size is produced.
- The displayed 3,476 units and the displayed £0.03 margin requirement stay historical observations. They are not a cap and not a general margin rate.
- A displayed one-pip value of £0.00 is not treated as zero exposure.
- Broker token permission remains `UNKNOWN`. The token may still be allowed to trade.
- The R.47 EUR/USD ticket and the financing-panel observation stay separate from API evidence. Their `api_confirmation` is `NO`.
- The real HTTPS client class is refused. A later program must have a new hash before it can construct that class.

R.56 is not started.
