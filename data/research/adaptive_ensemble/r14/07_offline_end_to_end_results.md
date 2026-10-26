# Offline end to end

SHARED PRODUCTION PATH WIRED. SIMULATED BROKER DISPATCH.

Synthetic BUY and SELL each produced one FakeBroker request after the selector, the vote wrapper, the agreeing RL decision, the risk gates, and the reservation. RL SKIP produced zero requests. Inactive and unknown strategies, invalid and no-trade votes, missing candles, an open position, PENDING, PARTIAL, UNRESOLVED, historical FILLED, unconfirmed exposure, non-positive size, and persistence failure produced zero requests.

Fake rejection, partial fill, timeout, ambiguous, and malformed results were classified by the existing outcome path. Ambiguous and timeout hold exposure and do not retry. A second signal and a duplicate client id do not create a second request.

A missing account snapshot is not a new hard block. The existing path records `missing_account_snapshot_uses_current_equity` and can continue. That is the R.12 source gap, left in place.

A reconciliation token does not release exposure. `confirm_exposure_flat` stays false. Live permission with `simulation=False` stops before the fake broker. The iteration sets `scheduled_another` and `trading_ready` false.
