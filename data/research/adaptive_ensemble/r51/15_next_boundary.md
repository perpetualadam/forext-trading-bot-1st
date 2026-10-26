# Next authorisation boundary

Do not begin R.52 from this stage.

R.51 prepares the adapter, proves the offline exchange, and leaves launch network-disabled. It does not approve a live session.

The next boundary is a separate written approval, after you review this report and `09_manual_procedure.md`. That later stage would have to add one new connection factory and one user-operated session for exactly two GET requests:

- Host `api-fxtrade.oanda.com` only.
- Certificate verification left on.
- Instruments, then pricing with home conversions, for the six names.
- Start-menu window, hidden token entry, no stored credential.
- Sanitised output only, with `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` unless a future authorised field actually returns the home currency.
- Stop on any other path, status, or instrument.

That boundary would still exclude orders, candles, backtests, strategy activation, deployment, and rollback.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
