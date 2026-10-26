# Remaining work before any real session

R.50 contains no function that sends an HTTPS request. A later stage would need its own authorisation before any of the following could be built:

- One reviewed HTTPS GET client, aimed only at `api-fxtrade.oanda.com`.
- The same two path templates and the same six instruments.
- Home-conversion pricing, with the four conversion factors kept separate.
- A short timeout, no redirects, no retries, no body, and no stream.
- Hidden credential entry in a Windows window opened from the Start menu, outside Cursor.
- Sanitised output written only after a leak check. No raw payload, no account identifier in a filename, and no token in a log.
- Fail-closed handling for a non-200 status, an unknown instrument, a bad number, or a missing field.

That later stage would still exclude orders, trades, position changes, account discovery, summaries, transactions, candles, historical prices, and streams. It would not calculate an executable size, would not apply the 1.35 fallback, and would not tune a strategy from the snapshot.

Broker-enforced read-only permission is a separate gap. A successful GET would not prove that the token is unable to trade.
