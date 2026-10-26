# R.56 phase 2 test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase2_offline/test_phase2_offline.py -q`

Result: **35 passed, 0 failed, 0 skipped, 0.59s**.

The suite blocks `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` before the logger is loaded.

| Test | Result |
| --- | --- |
| 01 valid GBP summary | passed |
| 02 non-GBP summary | passed |
| 03 missing currency records `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` | passed |
| 04 missing NAV or margin | passed |
| 05 valid bid and ask, spread `0.00020` quote units | passed |
| 06 bid greater than ask | passed |
| 07 zero or negative price | passed |
| 08 missing bid or ask | passed |
| 09 multiple bid and ask levels use the first only | passed |
| 10 missing timestamp | passed |
| 11 malformed timestamp | passed |
| 12 missing tradeable flag is not inferred | passed |
| 13 missing home conversions | passed |
| 14 unexpected fields dropped | passed |
| 15 synthetic token in an unexpected field | passed |
| 16 synthetic account id not persisted | passed |
| 17 exception text not logged | passed |
| 18 malformed JSON | passed |
| 19 empty response rejected | passed |
| 20 incorrect types | passed |
| 21 missing sizing inputs | passed |
| 22 unverified GBP pip value | passed |
| 23 unverified stake-to-unit mapping | passed |
| 24 no executable order payload | passed |
| 25 no production imports | passed |
| 26 no trading-engine imports | passed |
| 27 DNS and socket blocked | passed |
| 28 live activation flags rejected | passed |
| 29 logs stay under `synthetic_logs` | passed |
| 30 no secret values in launch output | passed |
| 31 failure writes no `DIAGNOSTIC_RECORDED` record | passed |
| 32 repeated launches do not overwrite an unrelated file | passed |
| 33 supplied `marginUsed` labelled not parsed by the operational client | passed |
| 34 supplied home conversions labelled `NOT_REQUESTED` by the operational query | passed |
| operational modules remain unimported | passed |

No production source was edited to obtain this result.
