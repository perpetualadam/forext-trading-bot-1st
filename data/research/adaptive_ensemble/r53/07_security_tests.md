# Security and accounting tests

Command:

`python -B -m pytest -p no:cacheprovider --noconftest -q data/research/adaptive_ensemble/r53/test_connector.py`

Attempt 1: 8 passed, 0 failed. One redundant assertion was then removed. The re-run also passed 8 tests. No security assertion was weakened. There was no failed attempt.

The suite repeats the flow while DNS lookup, connection open, and live HTTPS construction raise if called.

| Check | Result |
| --- | --- |
| 1–2. Disabled launch, no credential prompt | Passed. |
| 3. No production imports | Passed. |
| 4–5. Fixed host and certificate verification | Passed. Port 443. |
| 6–8. GET only, two templates, other paths refused | Passed before the client is constructed. |
| 9–12. No redirect, retry, stream, or body | Passed. A redirect does not read the body. |
| 13–14. Five-second timeout and size cap | Passed. |
| 15–18. Two calls, instruments then pricing, six names, home conversions | Passed. |
| 19–22. Redaction of token, account identifier, exceptions, and raw writes | Passed. |
| 23–25. Attempted, HTTP-success, and validated counts | Passed, including a case where HTTP success is 1 and validated is 0. |
| 26–29. HTTP error, timeout, TLS failure, malformed JSON | Passed. Each stops after one attempt. |
| 30–32. Missing conversions, unknown instrument, invalid number and crossed quote | Passed. |
| 33–35. No 1.35, no executable size, `SYNTHETIC_TEST_ONLY` | Passed. |
| 36–40. No DNS or HTTP, no environment credential, no `.env`, no credential store, no live switch | Passed. |

`account_specific_api_evidence` is `NOT_PRODUCED`. `ACCOUNT_VERIFIED` is not used.
