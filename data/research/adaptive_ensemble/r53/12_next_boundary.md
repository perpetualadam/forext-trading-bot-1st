# Next approval boundary

Do not begin R.54 from this stage.

R.53 is the final offline connector. Normal execution stays disabled. A live session is a separate decision after you review this report and `09_manual_procedure.md`.

That later approval would have to name a new hash and then allow one Start-menu run that:

- Asks for the account identifier and a hidden token in that window.
- Uses the real HTTPS client on `api-fxtrade.oanda.com` port 443 with certificate verification left on.
- Sends instruments, then pricing with home conversions, for the six names, and stops.
- Writes only a sanitised file. `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` remains unless a permitted field actually establishes the home currency.
- Records the three counts separately.

That approval would still exclude orders, candles, backtests, strategy activation, deployment, and rollback.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
