# R55 B2 preparation report

Overall for preparation only: **PASS**

Recommendation: **Option A**. Option B is deferred and is not part of this plan.

Option A keeps the existing maximum of two sequential GET requests: account instruments, then account pricing with `includeHomeConversions=true`. That design could later record which of the six instruments and allowlisted fields were returned, the first bid and ask, the timestamp, the tradeable flag, and a spread only where `(ask - bid) / 10**pipLocation` is defined. It would not establish account home currency, spread-bet stake mapping, GBP pip value, financing cost, token permission, or an executable size. HTTP 200 would not verify the account.

Option B, `GET /v3/accounts/{accountID}/summary`, is not authorised. Local files do not document its schema, so whether it contains the home currency is **DOCUMENTATION_VERIFICATION_REQUIRED**. The response would have to be treated as able to expose balance, NAV, margin, positions, and orders. Adding it would change the request count and the allowlist and would need a separate approval and new offline tests.

## Files created

- `data/research/adaptive_ensemble/r55/b2_preparation/01_scope_and_endpoint_decision.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/02_credential_and_transport_safety.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/03_evidence_and_broker_contract.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/04_offline_test_plan.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/05_approval_gate.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/06_baseline_and_integrity.md`
- `data/research/adaptive_ensemble/r55/b2_preparation/07_preparation_report.md`

No executable, test harness, API client, or activation command was created.

## Outstanding documentation questions

- The response schema of `/v3/accounts/{accountID}/summary`, and whether any field is the account home currency. **DOCUMENTATION_VERIFICATION_REQUIRED**.
- A quote-age rule for treating a timestamp as stale. **DOCUMENTATION_VERIFICATION_REQUIRED**. No age cutoff is set here.
- Whether five seconds is enough for the broker's latency. **DOCUMENTATION_VERIFICATION_REQUIRED**. The per-request timeout stays 5.0 seconds and is not a session deadline.
- The broker's token-permission model for this account. Local status remains `UNKNOWN`.
- The spread-bet stake-to-unit map, the account product, and which financing formula applies. Those remain broker-contract questions.

## Security concerns

- A GET-only client would not make the token read-only. The token may still be allowed to trade.
- `run_test_session` is a test interface, not a network sandbox, and it is not a live entry.
- Hidden input would not protect a token from a debugger or process memory.
- A request that has already been sent cannot be cancelled.
- Option B would bring sensitive account-financial data into memory even if a report later omitted it.
- Home currency, stake mapping, and executable size remain unresolved. No position size is proposed.
- The six pairs are research-only. No strategy has established reliable profitability.

## Confirmations

- Real credentials read, printed, validated, or stored: zero.
- Network requests: zero.
- Orders, trades, and account modifications: zero.
- B1 remains disabled. `--live`, `run_live()`, and `run_session(mode="live")` were not run. The B1 hashes still matched the expected values at inspection.
- Boundary B2 was not activated.

## Status

- B2 preparation: complete for review.
- B2 implementation: NOT AUTHORISED.
- Authenticated OANDA GET requests: NOT AUTHORISED.
- Practice orders: NOT AUTHORISED.
- Live trading: NOT AUTHORISED.
- Production deployment: NO-GO.
