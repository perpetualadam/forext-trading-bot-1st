# Next authorisation boundary

Do not begin R.51 from this stage.

R.50 shows that the offline workflow can prepare the two GET calls, reject everything else, parse a synthetic response, and keep secrets out of the output. It does not show that OANDA can be reached, that a token works, or that the account matches the spread-bet profile.

The next boundary, if it is authorised later as its own stage, is one reviewed live HTTPS send:

- Start-menu window, outside Cursor.
- One token entry and one account-identifier entry, neither written to disk.
- Exactly two GET requests on `api-fxtrade.oanda.com`.
- Instruments, then pricing with home conversions, for the six names only.
- Sanitised evidence only.
- Stop on any other endpoint, status, redirect, or extra instrument.

That boundary still would not authorise an order, a candle download, a backtest, strategy activation, deployment, or a rollback.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
