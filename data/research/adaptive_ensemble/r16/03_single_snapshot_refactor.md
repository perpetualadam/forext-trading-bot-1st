# Single accepted snapshot

CODE MODIFIED in `forex_bot/bot_loop.py` only.

After `_account_entry_block` accepts a snapshot, the shared path copies the equity to a float, `accepted_equity`. That float is stored on the decision evidence and is the only equity passed to:

- `position_sizing`
- the portfolio stop-risk cap, `portfolio_risk_cap_exceeded(accepted_equity, new_risk)`
- the gross notional cap when `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV` is greater than 0

The notional comparison is the existing one: existing gross plus the proposed add, against `account_ccy_to_usd(accepted_equity * percentage)`. At the production default the percentage is 0, so that check stays off and does not read equity.

The shared function no longer calls `current_equity()`. Risk percentages, the sizing formula, and the portfolio-cap formula are unchanged. The only formula input that changed is the equity argument of the cap.

A production call still stops at the live-permission gate because `simulation` is false. `verified=True` and the isolated-test context do not authenticate a production snapshot. No account is fetched.
