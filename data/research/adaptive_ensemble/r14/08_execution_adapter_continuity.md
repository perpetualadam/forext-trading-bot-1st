# Execution adapter continuity

PRODUCTION EXECUTION CONTINUITY: SOURCE-VERIFIED ONLY.

`production_execution_adapter` is the only source reference to `execute_oanda_market_open`. The shared path assigns that function and does not call it. Tests recorded `production_adapter_invoked=false` and `real_broker=false`.

The fake request carries symbol, direction, units, client id, stop, and target. Reservation is before `fake_broker` in the phase list. An ambiguous result is one request. A veto, an invalid vote, and an exposure hold produce no request.

This does not show that the OANDA function works. It was not called.
