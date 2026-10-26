# Market data and decision path

J13–J32 passed. These results describe the current source. Missing gates were recorded and not added.

- Empty candles block before the session check.
- A missing close fails inside `compute_indicators` and does not dispatch.
- A non-finite close blocks before dispatch.
- An invalid timestamp and a stale bar are not the first result. `decision_frame_rejection` returns `missing_provenance` because the synthetic frame has no live seal. A real broker open would stop there.
- An excessive numeric spread and a non-numeric spread have no hard block in the current source. The simulated path can still reach the fake broker. This is a source gap.
- Fewer than 20 bars does not fail `volatility_ok`. Short lookback is not a hard block.
- BUY and SELL votes proceed only in simulation. A rejected vote, an unknown vote, and a vote-provider error stop before the broker.
- A second signal on the same symbol stops on the recorded position.
- A second symbol stops on the portfolio stop-risk cap.
- A closed EUR_USD session and the Friday flatten window stop before reservation.
- A missing account snapshot uses `current_equity`. A non-finite balance stops.
