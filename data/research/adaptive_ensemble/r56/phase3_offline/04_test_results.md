# R.56 phase 3 test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase3_offline/test_phase3_offline.py -q`

Result: **48 passed, 0 failed, 0 skipped, 0.37s**.

The suite blocks `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` before the collector is loaded. It does not import or run the production bot.

| Coverage | Result |
| --- | --- |
| 01 `--offline` only, synthetic complete status | passed |
| 02 missing `--offline` rejected | passed |
| 03 `--live` rejected | passed |
| 04 `--connect` rejected | passed |
| 05 `--authenticate` and `--account` rejected | passed |
| 06 unknown arguments rejected | passed |
| 07 no production imports | passed |
| 08 no trading-engine imports | passed |
| 09 no OANDA SDK imports | passed |
| 10 DNS blocked | passed |
| 11 sockets blocked | passed |
| 12 HTTP libraries not loaded | passed |
| 13 fixed host | passed |
| 14 fixed port | passed |
| 15 HTTPS | passed |
| 16 GET only | passed |
| 17 summary pattern accepted | passed |
| 18 pricing pattern accepted, instruments only | passed |
| 19 summary path outside the pattern rejected | passed |
| 20 orders rejected | passed |
| 21 trades rejected | passed |
| 22 positions rejected | passed |
| 23 candles rejected | passed |
| 24 unknown endpoint rejected | passed |
| 25 arbitrary host rejected | passed |
| 26 extra query rejected | passed |
| 27 body rejected | passed |
| 28 redirects rejected | passed |
| 29 retries rejected | passed |
| 30 streaming rejected | passed |
| 31 two-request maximum and summary-before-pricing | passed |
| 32 session call order | passed |
| 33 summary failure does not call pricing | passed |
| 34 pricing failure is not a complete session | passed |
| 35 malformed summary | passed |
| 36 malformed pricing | passed |
| 37 account id omitted | passed |
| 38 bearer token omitted | passed |
| 39 exception text omitted | passed |
| 40 unknown response fields omitted | passed |
| 41 Phase 2 adapter files reused | passed |
| 42 no order payload and no `1.35` | passed |
| 43 logs stay in `phase3_offline/synthetic_logs` | passed |
| 44 failed session does not write a complete status | passed |
| 45 Phase 2 and inspected operational hashes unchanged | passed |
| 46 repeated sessions do not overwrite an unrelated file | passed |
| live transport raises `LIVE_TRANSPORT_NOT_AVAILABLE` | passed |
| `approved` bypass rejected | passed |

No existing source file was edited to obtain this result.
