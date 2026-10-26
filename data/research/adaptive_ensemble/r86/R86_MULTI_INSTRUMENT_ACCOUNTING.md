# R.86 Multi-Instrument Accounting

Evidence: executed `test_39`, `test_40`, `test_41`, `test_42`, `test_54`, and `test_55`.

| Case | Result |
| --- | --- |
| EUR_USD BUY and USD_JPY BUY | Separate instrument keys. No raw total |
| EUR_USD SELL and USD_JPY SELL bodies | Direction preserved. Completeness unknown |
| Two BUY trades on EUR_USD | Two lines. Same-instrument same-direction units are 25 from 10 and 15 |
| BUY 10 and SELL 4 on EUR_USD | Both directions remain. They are not netted to 6 |
| GBP_USD active beside EUR_USD quarantine | Managed and quarantined maps differ |
| Broker trade and journal trade with the same id | Two categories, one identity each. Not one summed verified number |

Missing broker observations add `UNKNOWN_EXPOSURE` with null units. They do not cancel a quarantined remainder.

No conversion rate is applied. A common-currency total is not reported.
