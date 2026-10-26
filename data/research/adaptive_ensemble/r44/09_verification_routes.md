# R.44 future verification routes

R.44 does not authorise a broker call. No client was created.

## A. User-supplied redacted documentation

The user may later provide a product or instrument sheet with account numbers, balances, and personal details removed. Useful fields are product type, currency, pip location, display precision, minimum size, size step, margin rule, financing rule, and the broker's instrument name. This route needs no credential and no network. A redacted sheet can still be incomplete. It should be stored as `USER_REDACTED_DOCUMENT`, not as `ACCOUNT_VERIFIED`, unless the user also states that it is their own product confirmation and the account identifiers stay redacted. R.44 does not ask for credentials, account numbers, or statements.

## B. Public broker documentation

A later stage could be authorised to read current public pages. Those pages can define a product. They cannot prove this account can use it. They cannot choose between the practice default and the old live candle label. R.44 did not fetch any page.

## C. Account-specific read-only verification

Not authorised. A later proposal would need a separate approval naming:

- The fields to retrieve, and no others.
- Practice or live, one environment.
- The exact read-only operations. Order, trade, and position-changing operations excluded.
- Where the credential comes from, and that logs omit it.
- What is redacted before anything is written to the research folder.
- That output stays under that stage's evidence directory and is not written to production state.
- Network permission for those reads only.
- A no-order guarantee in the client and in the test.
- Stop on a non-candle or non-summary document, on a 4xx contract error, and after the named fields are stored.

Until that approval exists, route C stays closed.
