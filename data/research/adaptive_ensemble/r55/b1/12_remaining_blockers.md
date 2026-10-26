# Remaining account-contract unknowns

Boundary B1 did not collect a live response. These limits remain:

- Boundary B2 is not approved. The future live command must not be run on the strength of this stage.
- `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` stays in force. A conversion factor would not establish the account home currency.
- Instrument type `CURRENCY` does not establish spread-betting stake semantics. Quantity 1 is not treated as £1 per pip.
- `stake_settlement` remains `UNKNOWN`. No executable position size is produced.
- Historical ticket values, including 3,476 units and £0.03 margin, stay separate. Their `api_confirmation` is `NO`.
- A displayed one-pip value of £0.00 is not treated as zero exposure.
- Broker token permission remains `UNKNOWN`. The token may still be allowed to trade.
- Historical financing observations stay separate from API evidence.

R.56 is not started.
