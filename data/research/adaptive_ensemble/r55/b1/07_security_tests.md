# Offline security tests

Attempt 2 exercised all 51 behaviours under patched name lookup, patched connection creation, and a trapped live client class. The live function was not called. Attempt 5 is the offline-hardening run: 10 passed, 0 failed. The executable accepts only the built-in synthetic transport. The network-denial fixture is a testing safeguard, not a sandbox.

| # | Behaviour | Result |
| ---: | --- | --- |
| 1 | Offline mode does not use a real network path | Pass |
| 2 | Offline mode uses the synthetic readers only | Pass |
| 3 | Production modules are not imported | Pass |
| 4 | Host is `api-fxtrade.oanda.com` and port is 443 | Pass |
| 5 | Certificate mode is `CERT_REQUIRED` | Pass |
| 6 | Hostname verification stays on | Pass |
| 7 | POST, PUT, and DELETE are rejected; the session sends GET | Pass |
| 8 | The only endpoint names are instruments and pricing | Pass |
| 9 | The six pairs are required; `NZD_USD` stops the session | Pass |
| 10 | Pricing requests `includeHomeConversions=true` | Pass |
| 11 | Another host, path, or method is rejected before a client exists | Pass |
| 12 | HTTP 302 is rejected and the body is not read | Pass |
| 13 | Timeout and TLS failure do not retry | Pass |
| 14 | Streaming is rejected | Pass |
| 15 | Request bodies are empty and a supplied body is rejected | Pass |
| 16 | Each prepared call uses a five-second timeout | Pass |
| 17 | An oversized body is `RESPONSE_TOO_LARGE` and stops the session | Pass |
| 18 | A successful session makes two calls | Pass |
| 19 | The order is instruments, then pricing | Pass |
| 20 | The preview is shown before either credential reader | Pass |
| 21 | A refused confirmation stops before credentials | Pass |
| 22 | The token reader is a separate prompt; offline mode does not call hidden input | Pass |
| 23 | A token on the command line is ignored and is not printed | Pass |
| 24 | Credential environment names are not read | Pass |
| 25 | A file named `.env` is not opened | Pass |
| 26 | The Windows credential store is not opened | Pass |
| 27 | The token is absent from the preview, the result, and the written file | Pass |
| 28 | The account identifier is absent from the preview and the result | Pass |
| 29 | `Authorization` and `Bearer` are absent from the result | Pass |
| 30 | A full `https://` URL is absent from the result | Pass |
| 31 | Raw responses and secret-bearing documents are not written | Pass |
| 32 | Reader, timeout, and TLS details are absent from the returned errors | Pass |
| 33 | The three counters stay distinct for success and failure | Pass |
| 34 | Malformed JSON is rejected after one HTTP success and zero validated rows | Pass |
| 35 | An unknown instrument is rejected before pricing | Pass |
| 36 | A non-finite bid and an ask below the bid are rejected | Pass |
| 37 | Absent conversion factors are `NOT_RETURNED` | Pass |
| 38 | The value 1.35 is not inserted | Pass |
| 39 | No executable size is produced | Pass |
| 40 | An unknown output key and a token field fail validation | Pass |
| 41 | A failed validation does not create the output file | Pass |
| 42 | HTTP, timeout, and TLS failures close the client | Pass |
| 43 | Orders, trades, positions, transactions, and candles are rejected | Pass |
| 44 | No production process, production import, or extra thread is started | Pass |
| 45 | The authoritative hashes still match after the tests | Pass |
| 46 | The whole suite runs with DNS, sockets, and the live client class blocked | Pass |
| 47 | Environment variables, extra arguments, and a module boolean do not select live mode | Pass |
| 48 | Starting the file with no arguments does not start a session | Pass |
| 49 | The offline run does not call a credential prompt | Pass |
| 50 | No authenticated request was sent | Pass |
| 51 | New files are under `r55/b1`, and the pinned R.53 hash is unchanged | Pass |
