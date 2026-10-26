# Security and failure tests

The suite is `test_connector.py`. Tests call the connector. They do not accept a pass merely because a forbidden word is absent from source.

Attempt 1: 25 passed, 1 failed. `test_24_gbp_fallback_is_not_applied` removed both conversion objects. The connector still reported conversion availability as `PRESENT` because the R.48 parser supplies a placeholder dictionary. The assertion was left unchanged.

Correction: availability is `PRESENT` only when at least one factor value was actually returned. Placeholder and missing values stay `NOT_RETURNED`.

Attempt 2: 26 passed. Together with the unchanged R.48 suite (6) and R.49 suite (6), 38 passed.

| Check | Result |
| --- | --- |
| 1. Default launch performs no network access | Passed. DNS and connection functions were replaced with failures. |
| 2. Default launch does not request credentials | Passed. The printed line says there is no credential prompt. |
| 3. No production imports | Passed. `forex_bot` is absent from `sys.modules`. |
| 4. Only GET | Passed on the prepared calls. |
| 5. Only the two templates | Passed. Call order is instruments, then pricing. |
| 6. Fixed host | Passed. Host is `api-fxtrade.oanda.com`. |
| 7. Arbitrary URL rejection | Passed before the fake transport. |
| 8. Redirect rejection | Passed. Status 302 stops after one call. |
| 9. Retry rejection | Passed. A transport exception stops after one call. |
| 10. Streaming rejection | Passed before the fake transport. |
| 11. Request-body rejection | Passed before the fake transport. |
| 12. Short timeout | Passed. Timeout is five seconds. |
| 13. No credential in output | Passed. |
| 14. No account identifier in output | Passed. |
| 15. No credential in exceptions | Passed. |
| 16. No account identifier in exceptions | Passed. |
| 17. No raw response persistence | Passed. A document containing the token is refused and the file is not created. |
| 18. Six-pair filtering | Passed on the query. |
| 19. Unknown instrument rejection | Passed. An added name fails closed. |
| 20. Missing-field handling | Passed. A removed margin rate is `NOT_RETURNED`. |
| 21. Invalid numeric handling | Passed. |
| 22. Invalid bid/ask handling | Passed. Ask below bid fails closed. |
| 23. Conversion-factor separation | Passed. A removed positive-units factor is not copied from the negative-units factor. |
| 24. GBP fallback prohibited | Passed after the correction above. `1.35` is absent. |
| 25. Synthetic evidence classification | Passed. The label is `SYNTHETIC_TEST_ONLY`. |
| 26. Prohibited order endpoint | Passed before the fake transport. |
| 27. Malformed response | Passed. |
| 28. No DNS or HTTP during testing | Passed. The synthetic run and `enable_live` were executed while DNS and connection functions raised. |

The application regression that imports `forex_bot.config` was not run. That import reads the OANDA access token. R.28 PostgreSQL scripts were not run. `live_safety.py` was not edited.
