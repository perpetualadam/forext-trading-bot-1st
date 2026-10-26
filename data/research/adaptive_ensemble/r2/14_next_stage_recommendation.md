# Recommended next stage

Do not start it from this stage.

Name: R.3 — offline inactive-entry and uncertain-order fixtures.

Why this is next:

- R.2 showed the live side is the shared vote, not the six shadow rules.
- R.2 proved the default flags and the authorisation block with offline tests.
- R.2 did not execute the line that returns before sizing.
- R.2 did not execute the timeout path, and the source shows that path marks an uncertain send as failed.
- The session count is reproduced at 27. It cannot reach 40 without new market data, and downloading is a separate decision.

R.3 should:

- Call the inactive check and the order-classification functions directly.
- Use fake replies for fill, reject, and timeout.
- Avoid importing `forex_bot.app`.
- Avoid `asyncio.run` on Windows unless the local self-pipe is explicitly allowed. This stage's barrier correctly refused that pipe.
- Keep every write inside a new research directory.
- Leave strategies off and live orders blocked.

R.3 should not:

- Contact OANDA, Telegram, or Discord.
- Download candles.
- Enable a strategy.
- Claim a profit result.
- Continue Docker research.
