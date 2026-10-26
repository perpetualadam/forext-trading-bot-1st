# Future authorised read-only session

This procedure is not authorised now. Phase 5 does not contain an executable live entry point. An affirmative answer to the synthetic screen is not permission to connect.

A later session would need a new written instruction that names OANDA Live and these two reads only:

1. `GET https://api-fxtrade.oanda.com/v3/accounts/{accountID}/summary`
2. `GET https://api-fxtrade.oanda.com/v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`

Before any credential is read, the operator would have to confirm that screen, including the warning that the token may still be allowed to trade and that the production bot must be stopped. The hidden token prompt and the separate account-id prompt would be built only under that later instruction. They must not appear on the command line, in the environment dump, in the child job, or in the log.

The parent would keep the 5 second request deadline and the 15 second session deadline, start one sealed child per GET, and kill a child that ignores the deadline. The child would still refuse every path except the two GETs. Raw responses would be reduced with the existing Phase 2 adapters and would not be stored. The session classification would change from `SYNTHETIC_TEST_ONLY` only when the bytes came from the broker, and a missing field would stay missing.

That work is a separate authorisation. Practice orders, live orders, production startup, and production deployment remain out of scope. Stopping the child cannot retract a GET that OANDA has already received.
