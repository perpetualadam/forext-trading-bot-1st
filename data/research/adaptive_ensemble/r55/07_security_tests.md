# Offline security tests

All 55 behaviours were exercised by `test_session.py` under patched name lookup, patched connection creation, and a trapped live client class. Attempt 1 passed with no later change to an assertion.

| # | Behaviour | Result |
| ---: | --- | --- |
| 1 | Default launch stays disabled and prints the disabled sentence | Pass |
| 2 | Default launch does not call a credential prompt | Pass |
| 3 | No real DNS lookup during the suite | Pass |
| 4 | No real connection open during the suite | Pass |
| 5 | No real HTTP request; the live client class is refused | Pass |
| 6 | Production modules are not imported | Pass |
| 7 | Host is fixed to `api-fxtrade.oanda.com`; another host is rejected | Pass |
| 8 | Port is 443 | Pass |
| 9 | Certificate mode is `CERT_REQUIRED` | Pass |
| 10 | Hostname verification stays on | Pass |
| 11 | POST, PUT, and DELETE are rejected; the session sends GET | Pass |
| 12 | The only endpoint names are instruments and pricing | Pass |
| 13 | The six pairs are required; `NZD_USD` stops the session | Pass |
| 14 | Pricing requests `includeHomeConversions=true` | Pass |
| 15 | Another host or path, including orders and summary, is rejected | Pass |
| 16 | HTTP 302 is rejected, the body is not read, and pricing is not sent | Pass |
| 17 | Timeout and TLS failure do not retry | Pass |
| 18 | Streaming is rejected | Pass |
| 19 | Request bodies are empty and a supplied body is rejected | Pass |
| 20 | Each prepared call uses a five-second timeout | Pass |
| 21 | An oversized body is `RESPONSE_TOO_LARGE` and stops the session | Pass |
| 22 | A successful session makes two calls and does not use a third step | Pass |
| 23 | The order is instruments, then pricing | Pass |
| 24 | The preview is shown before either credential reader | Pass |
| 25 | A refused or inexact confirmation stops before credentials | Pass |
| 26 | The token reader is a separate prompt and the default launch does not call hidden input | Pass |
| 27 | A token passed as an argument is ignored and is not printed | Pass |
| 28 | Credential environment names are not read | Pass |
| 29 | A file named `.env` is not opened | Pass |
| 30 | The Windows credential store is not opened | Pass |
| 31 | The token is absent from the preview, the result, and the written file | Pass |
| 32 | The account identifier is absent from the preview and the result | Pass |
| 33 | `Authorization` and `Bearer` are absent from the result | Pass |
| 34 | A full `https://` URL is absent from the result | Pass |
| 35 | Raw responses and secret-bearing documents are not written | Pass |
| 36 | Reader, timeout, and TLS details are absent from the returned errors | Pass |
| 37 | The three counters stay distinct for success and failure | Pass |
| 38 | Malformed JSON is rejected after one HTTP success and zero validated rows | Pass |
| 39 | An unknown instrument is rejected before pricing | Pass |
| 40 | A non-finite bid and an ask below the bid are rejected | Pass |
| 41 | Absent conversion factors are `NOT_RETURNED` | Pass |
| 42 | The value 1.35 is not inserted | Pass |
| 43 | No executable size is produced | Pass |
| 44 | Evidence class is `SYNTHETIC_TEST_ONLY` and account evidence is `NOT_PRODUCED` | Pass |
| 45 | An unknown output key and a token field fail validation | Pass |
| 46 | A failed validation does not create the output file | Pass |
| 47 | `--live` does not enable the session | Pass |
| 48 | `R55_LIVE=APPROVE` does not enable the session | Pass |
| 49 | `CONFIRM PREVIEW` on the command line does not enable the session | Pass |
| 50 | Setting `LIVE` and `ENABLED` on the module does not enable the session | Pass |
| 51 | HTTP, timeout, and TLS failures close the client | Pass |
| 52 | Orders, trades, positions, transactions, and candles are rejected | Pass |
| 53 | No production process, production import, or extra thread is started | Pass |
| 54 | The R.51–R.54 hashes still match after the tests | Pass |
| 55 | The whole suite runs with DNS, sockets, and the live client class blocked | Pass |
