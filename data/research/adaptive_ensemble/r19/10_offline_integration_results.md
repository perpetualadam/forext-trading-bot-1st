# Gate I — offline integration

Two tracks ran.

Shared path, actual `evaluate_one_instrument_iteration`, `select_strategy`, `AIEnsemble.vote`, and `RLAgent.decide`:

- I01/I02 valid synthetic BUY and SELL: FakeBroker once, production eligibility false.
- I03–I09 missing account, unverified account, missing quote time, stale quote, unapproved spread, missing margin, missing market provenance: blocked or recorded as non-PASS, broker zero where the gate is before reservation.
- I10–I13 portfolio, enabled gross-notional, unit-cap, and daily-loss breaches block before the inert adapter.
- I14–I18 existing position and FILLED, PENDING, PARTIAL, and UNRESOLVED holds block.
- I19–I22 RL veto, invalid vote, inactive strategy, and reservation failure block.
- I23–I26 timeout, ambiguous, partial fill, and position-record failure keep exposure held and do not retry.
- I27 duplicate client id is `reservation_refused`.

Production adapter track, real broker function replaced first:

- I28 forged eligibility: `untrusted_decision`, stub calls 0.
- I29 synthetic eligibility: `synthetic_context_rejected`, stub calls 0.
- I30 changed direction: `order_direction_mismatch`, stub calls 0.
- I31 stale decision: `decision_expired`, stub calls 0.
- I32 reused seal: `decision_already_used`, stub calls 0.
- I33 missing mandatory gate: `mandatory_gates_missing`, stub calls 0.
- I34 failed reservation: `reservation_not_permission`, stub calls 0.
- I35 cleanup leaves no PostgreSQL connection and no open positions.

No production-eligible decision was generated. ACTUAL STRATEGY SELECTOR EXECUTED. ACTUAL AI VOTE EXECUTED. ACTUAL RL VETO EXECUTED.
