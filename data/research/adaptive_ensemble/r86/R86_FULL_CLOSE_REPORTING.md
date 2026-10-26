# R.86 Full Close Reporting

Evidence: executed `test_32` and `test_33`. The close row stays `CLOSE_FULLY_CONFIRMED` with remaining 0. That zero is journal arithmetic after a full confirmation. It is not an unknown value coerced to zero, and it is not a verified flat broker book.

| Observation | Report |
| --- | --- |
| No observation | Journal remainder 0 and an unknown broker line with null units |
| Empty positions list | Journal remainder 0. `flat_verified` false |
| Parsed 1,000 | Journal 0 and broker 1,000. Confirmation state unchanged |
| Parsed 600 | Same separation. The snapshot does not rewrite the close |
| Stale or failed | Broker evidence is not current. Unknown units stay null |

A full journal confirmation and an empty broker body are separate. The report shows the journal remainder and withholds a verified-flat claim. No second `PositionClose` is created by the report. Negative remaining units are rejected as malformed.
