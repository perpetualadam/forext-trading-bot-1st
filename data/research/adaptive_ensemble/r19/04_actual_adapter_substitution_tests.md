# Gate C — inert substitution at the actual adapter

ACTUAL PRODUCTION ADAPTER INVOKED OFFLINE. REAL BROKER FUNCTION SUBSTITUTED. INERT BROKER STUB NOT CALLED.

Before each adapter invocation the test replaced `forex_bot.oanda_exec.execute_oanda_market_open` with an async recorder and asserted the replacement was the current attribute. The refusal path returns before that import, so the recorder received zero calls on every ineligible case.

C01–C25 (K036–K060) all refused. Reasons included `eligibility_missing`, `production_ineligible`, `untrusted_decision`, `synthetic_context_rejected`, `mandatory_gates_missing`, `mandatory_policy_unapproved`, `mandatory_not_implemented`, `mandatory_missing_evidence`, order mismatches, `decision_expired`, `account_identity_missing`, `reservation_not_permission`, `decision_already_used`, `unknown_gate_status`, and `eligibility_malformed`.

No real OANDA client was constructed. `oanda_client._api` stayed unset. Socket and DNS barriers recorded blocked constructor attempts and no successful connection.
