# R.45 future account-verification plan

Not authorised and not built. No broker client. No credential.

## Minimum facts still required

- Legal entity and whether the account is a spread-betting sub-account or a CFD sub-account.
- Practice or live.
- v20, v20 MT4, or OANDA One.
- Retail or professional.
- Home currency.
- Eligible instrument identifiers for the six names.
- Minimum size, increment, and the stake-to-units map.
- The margin rate that applies to each instrument on that sub-account.
- Which closeout dial is live, 100% v20 or 50% OANDA One.
- Whether settlement conversion is the 1.0% v20 rule, something else, or not charged.
- Whether financing is posted daily or only when the trade closes, and the admin fee actually assigned.
- GSLO availability, minimum distance, and premium.
- The currency field on a fill and on a financing posting.

## What a redacted document can answer

A user-supplied sheet with account numbers, balances, and personal details removed can answer product, sub-account, home currency, instrument names, minimum size, and published margin or financing terms if those words are on the sheet. It should be stored as a redacted document. It still does not prove the live account is allowed to trade unless the user identifies it as their own product confirmation.

## What still needs a separate read-only authorisation

Current tradable flags, the ticket's GSLO distance and premium, the transaction-report conversion rate, and the financing posting on a real position. That stage would have to name the read-only operations, forbid orders, redact identifiers, and stop when the listed facts are stored. R.45 does not approve it.

Until those facts exist, the public formulas stay unused in the bot and in backtests.
