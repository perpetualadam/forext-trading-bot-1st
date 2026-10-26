# Offline end-to-end results

Real broker calls are 0 in every scenario. Production eligibility is false in every scenario. The inert adapter is invoked only for the isolated contract after the entry gates pass.

| Scenario | Synthetic contract | Production eligibility | Adapter |
|---|---|---|---|
| BUY and SELL inside the harness | completed | false | 1 each |
| Missing or unverified account | not completed | false | 0 |
| Missing bid or ask, crossed quote, bad spread | not completed | false | 0 |
| Missing, invalid, stale, or future quote time | not completed | false | 0 |
| Unapproved numeric spread with a valid quote | completed in the harness | false | 1 |
| Margin missing or caller-supplied | completed only in the harness | false | 1 or 0 if an earlier gate blocks |
| Disabled gross, unit, and daily-loss controls | completed | false | 1 |
| Enabled gross, unit, daily-loss, or drawdown breach | not completed | false | 0 |
| Short lookback or malformed candles | not completed | false | 0 |
| Position, FILLED, PENDING, PARTIAL, UNRESOLVED | not completed | false | 0 |
| RL veto, invalid vote, inactive strategy | not completed | false | 0 |
| Portfolio stop-risk breach | not completed | false | 0 |
| Reservation failure, duplicate client id | not completed | false | 0 |
| Timeout, ambiguous, partial, record failure | held, no retry | false | 1 |
