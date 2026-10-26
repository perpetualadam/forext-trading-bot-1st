# Next authorisation boundary

Do not begin R.53 from this stage.

R.52 prepares the entry point, the TLS factory, and the credential function, and it leaves normal execution disabled. It does not approve a live call.

The next boundary is a separate written approval after you review this report and `09_manual_procedure.md`. That later change would have to:

- Publish a new hash for the file that is allowed to run.
- Pass the real HTTPS client class into the prepared factory, still on `api-fxtrade.oanda.com` port 443, with certificate verification left on.
- Ask for the account identifier and the hidden token only in a Start-menu window.
- Perform instruments, then pricing with home conversions, for the six names, then stop.
- Write only a sanitised document that still says `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` unless a permitted field actually establishes the home currency.

That boundary would still exclude orders, candles, backtests, strategy activation, deployment, and rollback.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
