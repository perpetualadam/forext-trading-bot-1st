# Offline security tests

All 50 behaviours were exercised by `test_session.py` under patched name lookup, patched connection creation, and a trapped live client class. Attempt 1 passed with no later change to an assertion.

| # | Behaviour | Result |
| ---: | --- | --- |
| 1 | Default launch stays disabled and prints the disabled sentence | Pass |
| 2 | Default launch does not call a credential prompt | Pass |
| 3 | No real DNS lookup during the suite | Pass |
| 4 | No real connection open during the suite | Pass |
| 5 | The live HTTPS client class is refused and is not constructed | Pass |
| 6 | Production modules are not imported | Pass |
| 7 | Host is fixed to `api-fxtrade.oanda.com`; another host is rejected | Pass |
| 8 | Port is 443 | Pass |
| 9 | Certificate mode is `CERT_REQUIRED` | Pass |
| 10 | Hostname verification stays on | Pass |
| 11 | POST, PUT, and DELETE are rejected; the session sends GET | Pass |
| 12 | The only endpoint names are instruments and pricing | Pass |
| 13 | The six pairs are required; `NZD_USD` stops the session | Pass |
| 14 | Pricing requests `includeHomeConversions=true` | Pass |
| 15 | An extra query key is rejected before a client is created | Pass |
| 16 | HTTP 302 is rejected, the body is not read, and pricing is not sent | Pass |
| 17 | Timeout and TLS failure do not retry | Pass |
| 18 | Streaming is rejected | Pass |
| 19 | Request bodies are empty and a supplied body is rejected | Pass |
| 20 | Each prepared call uses a five-second timeout | Pass |
| 21 | An oversized body is `RESPONSE_TOO_LARGE` and stops the session | Pass |
| 22 | A successful session makes two calls and does not use a third step | Pass |
| 23 | The order is instruments, then pricing | Pass |
| 24 | The token is absent from the preview, the result, and the written file | Pass |
| 25 | The account identifier is absent from the preview and the result | Pass |
| 26 | Reader, timeout, and TLS details are absent from the returned errors | Pass |
| 27 | Raw responses and secret-bearing documents are not written | Pass |
| 28 | The three counters stay distinct for success and failure | Pass |
| 29 | Malformed JSON is rejected after one HTTP success and zero validated rows | Pass |
| 30 | An unknown instrument is rejected before pricing | Pass |
| 31 | A non-finite bid and an ask below the bid are rejected | Pass |
| 32 | Absent conversion factors are `NOT_RETURNED` | Pass |
| 33 | The value 1.35 is not inserted | Pass |
| 34 | No executable size is produced | Pass |
| 35 | Evidence class is `SYNTHETIC_TEST_ONLY` and account evidence is `NOT_PRODUCED` | Pass |
| 36 | Credential environment names are not read | Pass |
| 37 | A file named `.env` is not opened | Pass |
| 38 | The Windows credential store is not opened | Pass |
| 39 | `--live` and a token argument do not enable the session and are not echoed | Pass |
| 40 | `R54_LIVE=APPROVE` does not enable the session | Pass |
| 41 | A confirmation phrase does not enable the session | Pass |
| 42 | Setting `LIVE` and `ENABLED` on the module does not enable the session | Pass |
| 43 | Both client objects are closed and no extra thread remains | Pass |
| 44 | HTTP, timeout, and TLS failures close the client | Pass |
| 45 | A failed session writes no result file | Pass |
| 46 | An unknown output key and a token field fail validation | Pass |
| 47 | A failed validation does not create the output file | Pass |
| 48 | Orders and account-summary paths are rejected before a client is created | Pass |
| 49 | No production process, production import, or extra thread is started | Pass |
| 50 | The three pinned hashes still match after the tests | Pass |
