# R.46 proposed read-only verification boundaries

Design only. This file is not an API script and not a request for a key.

## Minimum fields, if a later stage is authorised

- Home currency.
- Sub-account type and product, compared with v20 and spread betting.
- Environment label, compared with the reported Live display.
- For each of the six names: tradable flag, broker symbol, minimum size, increment, and the size unit's name.
- Margin rate and the margin-rate currency treatment for each enabled name.
- Closeout field names and the numeric trigger, compared with the v20 100% candidate.
- Financing charge timing: daily posting or another rule.
- One redacted description of how realised P&L is converted, including any markup.

## Permissible reads, to be approved one by one later

- Account summary, with the identifier removed before anything is written to disk.
- Instrument list or account instrument settings for the six names only.
- No candle request, no pricing stream, no order book history, and no transaction export.

## Prohibited

- Creating, amending, or cancelling an order.
- Any practice or live trade.
- Opening a position to observe financing.
- Reading or storing the API token.
- Printing an account identifier, alias, or personal detail.
- Storing a fresh balance, NAV, or margin-available amount unless that later stage says the figure may be stored.
- Calling hosts other than the one the approved stage names.
- Using the result to change production sizing.

## Credential isolation

The token stays in the existing secret store. The stage must not read `.env` into the evidence directory, must not log the authorisation header, and must not put the token in a command line that is recorded. If the token cannot be supplied through the process environment without writing it into evidence, the stage stops.

## Redaction and retention

Before a file is written: remove account identifiers, aliases, and names. Do not hash an identifier as a substitute for storing it. Compare currency, product, sub-account, and instrument fields to the R.46 matrix. Record match, mismatch, or still unknown. A mismatch with the user-reported v20, spread betting, Live, or GBP profile stops the stage and does not update production.

## Stop conditions

- Any order endpoint appears in the planned calls.
- The response includes an identifier that cannot be removed before logging.
- The product or sub-account contradicts the R.46 profile.
- The size unit is still unnamed after the instrument read.
- A network, parse, or permission error occurs. One failure stops the stage. There is no retry against a live order path.
- The operator has not separately authorised that stage.

## Comparison with this matrix

A later result may move a cell from `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` or `UNKNOWN` to a new class only when the redacted field is stored. It must not be labelled `ACCOUNT_VERIFIED` from a screen. It must not import OANDA One rules if the sub-account field still says v20. It must not treat a CFD instrument flag as a spread-bet permission. Cells that remain blank stay blockers.
