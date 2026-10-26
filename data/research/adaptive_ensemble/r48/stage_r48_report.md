# STAGE R.48 — CONTROLLED READ-ONLY OANDA v20 API VERIFICATION REPORT

Classification: `R48_READ_ONLY_OANDA_VERIFICATION_BLOCKED`

The block is the credential gate. Offline preparation and synthetic transport tests were completed. No authenticated OANDA request was sent. No account contract field was retrieved. The block is an acceptable safety result. `ACCOUNT_VERIFIED` is not used.

## Branch, HEAD, and preservation

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty and those unrelated changes were left in place. R.24–R.47 evidence is present. All six strategies are inactive. The quant stub source still returns `quant_stub_removed`. RL on an unseen state is `UNAVAILABLE`. Research lifecycle code is not imported by `bot_loop.py` or `ai_ensemble.py`. Operational hashes are unchanged. No production module was edited.

## Credential isolation

The production client reads `OANDA_ACCESS_TOKEN` when `forex_bot.config` is imported, and that runtime also contains order methods. R.44–R.47 do not show that an OANDA token is limited to GET. This stage did not import `forex_bot.config` or `forex_bot.oanda_client`, did not read `.env`, and did not read the token from the environment. No token was requested, printed, hashed, or stored.

A standalone gate in `data/research/adaptive_ensemble/r48/readonly_transport.py` accepts no credential and raises `R48_AUTHENTICATED_EXECUTION_BLOCKED` from `perform_request`. `EXECUTION_PERMITTED` is false. That is an offline design, not a session.

## Endpoints considered

Only two patterns were allowed, and neither was called: GET `/v3/accounts/{accountID}/instruments` and GET `/v3/accounts/{accountID}/pricing` on `api-fxtrade.oanda.com`, for the six named instruments, with home conversions on the pricing pattern. Orders, trades, positions, summary, balance, candles, history, streams, and account discovery are rejected. Redirects and retries are rejected. Timeout is 5 seconds.

## Authenticated requests

None. The authorisation record is closed. A token must not be pasted into chat to reopen it. A later call needs a separate instruction and a protected injection path.

## Six-instrument findings

Not available. Eligibility, type, pip location, display precision, trade-unit precision, minimum size, maximum sizes, margin rate, trailing-stop distance, guaranteed-stop mode, and financing fields are `NOT_RETRIEVED` for EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY.

## Pricing and GBP conversion

Not available. No bid, ask, spread, or conversion factor was stored. There is no `POINT_IN_TIME_API_SNAPSHOT` for the account. The parser would keep gain factors apart from loss factors, and positive-unit factors apart from negative-unit factors. It was not applied to a live payload.

## Ticket and financing

The R.47 ticket is unchanged: quantity 1, units available 3,476, trade value 0.84 GBP, one pip 0.00 GBP, margin required 0.03 GBP. The API did not confirm a minimum, a precision, a pip location, a conversion factor, or the meaning of one unit. No order was submitted.

The financing panel is a separate user-reported estimate: buy −2.43% and £16.75 per 100,000 units, sell +0.42% and £2.90 per 100,000 units, displayed at 22:00 GMT+1. Those figures were not matched to an API financing object and were not put into a backtest. On this date, 22:00 at GMT+1 is 17:00 US Eastern Daylight Time, the same hour of day as the R.45 "usually 5pm ET" candidate. That is a clock comparison, not a confirmation of the charge.

## Remaining blockers

Every R.47 sizing blocker remains. The USD production path, the 1.35 fallback, the missing positive unit clamp, the unknown GBP pip value, and the unknown fill currency are unchanged. The printed 0.00 GBP pip value is still not zero risk.

## Tests and preservation

Transport tests, synthetic only: attempt 1 failed 2 and passed 4; attempt 2 failed 1 and passed 5; attempt 3 passed 6. The failures were a forbidden word in docstrings and a spread string `2.0` versus `2`. The source scan and the spread assertion stayed in place. The application regression suite was not run, because it would import the module that reads the access token. R.28 PostgreSQL scripts were not run. `live_safety.py` was not edited.

## Recommended R.49 direction

Do not start R.49 from this stage. Do not send a token or an account identifier. A later stage may reuse the gate only after a separate authorisation of a protected credential path that still forbids orders, logging, and stored identifiers. Until then the gate stays closed. Leave the R.42 range rule and `MAX_POSITION_UNITS` unchanged.

PRODUCTION DEPLOYMENT: NO-GO

PRACTICE ORDERS: NOT AUTHORISED

LIVE TRADING: NOT AUTHORISED

ROLLBACK: NO-GO
