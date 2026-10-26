# Security tests

Command:

`python -B -m pytest -p no:cacheprovider --noconftest -q data/research/adaptive_ensemble/r52/test_session.py`

Attempt 1: 12 passed, 0 failed. No assertion was changed.

The suite includes one test that repeats the flow while DNS lookup, connection open, and live HTTPS construction raise if called.

| Check | Result |
| --- | --- |
| 1. Default launch performs no network access | Passed under the network trap. |
| 2. Default launch requests no credentials | Passed. Hidden input and normal input raise if called. |
| 3. No production imports | Passed. `forex_bot.config` and `forex_bot.oanda_client` are absent. |
| 4. Fixed HTTPS hostname | Passed. `api-fxtrade.oanda.com`. |
| 5. TLS verification enabled | Passed. `CERT_REQUIRED` and hostname checking. |
| 6. Only GET accepted | Passed. POST is refused before the factory. |
| 7. Only two endpoint templates | Passed. Order is instruments, then pricing. |
| 8. Arbitrary paths rejected | Passed. An orders path does not reach the factory. |
| 9. Arbitrary hosts rejected | Passed. |
| 10. Redirects rejected | Passed. Status 302 stops after one call and does not read the body. |
| 11. Automatic retries absent | Passed. One factory failure produces one attempt. |
| 12. Streaming rejected | Passed before the factory. |
| 13. Request bodies rejected | Passed before the factory. |
| 14. Five-second timeout | Passed on both calls and on the prepared factory. |
| 15. Response-size cap | Passed. A body above 1,048,576 bytes is refused. |
| 16. Maximum two requests | Passed. One session opens two calls. |
| 17. No credentials in output | Passed. |
| 18. No account identifier in output | Passed. |
| 19. No secrets in exception messages | Passed. |
| 20. No raw-response persistence | Passed. A secret-bearing document is not written. |
| 21. Unknown instruments rejected | Passed. |
| 22. Missing conversion fields remain NOT_RETURNED | Passed. |
| 23. No 1.35 fallback | Passed. |
| 24. No executable position-size calculation | Passed. `executable_units` is absent. |
| 25. Malformed JSON fails closed | Passed. |
| 26. HTTP errors fail closed without leaking raw bodies | Passed. Status 400 does not read the body. |
| 27. Synthetic evidence labelled SYNTHETIC_TEST_ONLY | Passed. |
| 28. No real DNS or HTTP during tests | Passed. |
| 29. No environment credential loading | Passed. Credential-named lookups raise if attempted. |
| 30. No .env access | Passed. Opening `.env` raises if attempted. |
| 31. No credential store access | Passed. `winreg.OpenKey` raises if attempted. |
| 32. No live mode from arguments or environment variables | Passed. `--live` and `R52_LIVE=1` still print the disabled sentence. |

The application suite was not run. It imports the credential-reading configuration. R.28 PostgreSQL scripts were not run.
