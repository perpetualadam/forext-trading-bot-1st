# R55 B3 design report

Overall for design only: **PASS**

Option A is unchanged: at most two sequential GET requests, instruments then pricing with `includeHomeConversions=true`. Option B stays deferred. This pass means the design documents are complete for review. It does not pass Gate 1, Gate 2, or Gate 3.

## Documents

- `data/research/adaptive_ensemble/r55/b3_design/01_architecture_and_request_flow.md`
- `data/research/adaptive_ensemble/r55/b3_design/02_transport_security_spec.md`
- `data/research/adaptive_ensemble/r55/b3_design/03_credential_threat_model.md`
- `data/research/adaptive_ensemble/r55/b3_design/04_broker_evidence_contract.md`
- `data/research/adaptive_ensemble/r55/b3_design/05_offline_security_test_spec.md`
- `data/research/adaptive_ensemble/r55/b3_design/06_approval_gates.md`
- `data/research/adaptive_ensemble/r55/b3_design/07_baseline_integrity.md`
- `data/research/adaptive_ensemble/r55/b3_design/08_b3_design_report.md`

No executable, credential prompt, or network client was created.

## Proposed controls

Fixed host and port, TLS certificate and hostname verification, GET only, the Option A allowlist, no body, no stream, no redirect, no retry, two requests, 1 MiB, 5 seconds per request, and a 15-second session budget. In B2 those timeouts are configured numbers. They are not enforced on a socket. A future test must show the 15-second deadline before anyone calls it enforced.

## Highest remaining risks

- The token may still be allowed to trade. A GET-only design does not change that.
- A future token would exist in process memory and could appear in a dump even if files are clean.
- The worktree is already dirty. A session must not write a secret into it.
- Quote freshness is `NOT_VERIFIED`. There is no supported age limit, so these prices must not feed a trading decision.
- Home currency, stake mapping, GBP pip value, financing, and executable size stay unresolved.

## Unresolved contract questions

Account home currency, spread-bet stake mapping, GBP pip value, financing formula, token permission, executable size, and strategy profitability. The account-summary schema remains **DOCUMENTATION_VERIFICATION_REQUIRED**. Broker clock behaviour for timestamps is **DOCUMENTATION_VERIFICATION_REQUIRED**. Whether 5 seconds suits the broker is **DOCUMENTATION_VERIFICATION_REQUIRED**.

## Baseline

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Dirty tree unchanged at inspection. Five B2 Python hashes, three B1 hashes, and eight pins matched. No existing code was edited.

## Confirmations

No credential was read. No network request was made. No order or trade was sent. B1 and B2 were not executed.

## Next gate

The recommended next step is independent review for **Gate 1**. Gate 2 and Gate 3 stay closed. Gate 1, if later accepted, still authorises no connection.

- Future HTTPS implementation: NOT AUTHORISED.
- Real credential entry: NOT AUTHORISED.
- Authenticated OANDA requests: NOT AUTHORISED.
- Account-summary endpoint: NOT AUTHORISED.
- Practice orders: NOT AUTHORISED.
- Live trading: NOT AUTHORISED.
- Production changes: NOT AUTHORISED.
- Production deployment: NO-GO.
