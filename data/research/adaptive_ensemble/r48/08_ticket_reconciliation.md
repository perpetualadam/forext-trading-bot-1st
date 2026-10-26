# R.48 EUR/USD ticket reconciliation

The ticket remains `USER_REPORTED_TICKET_DISPLAY` from R.47: quantity 1, units available 3,476, trade value 0.84 GBP, one pip 0.00 GBP, margin required 0.03 GBP. It was unsubmitted and rounded. No later API snapshot exists to compare with those prices.

| Question | API result |
| --- | --- |
| Minimum size | `NOT_RETRIEVED` |
| Trade-unit precision | `NOT_RETRIEVED` |
| Pip location | `NOT_RETRIEVED` |
| GBP conversion factors | `NOT_RETRIEVED` |
| Monetary meaning of one unit | `NOT_RETRIEVED` |

The ticket still rejects reading quantity 1 as £1 per pip, because the printed pip line is 0.00 GBP and the trade value is 0.84 GBP. An instrument record, had one been returned, would still not by itself prove the spread-betting settlement convention. No order was submitted to test acceptance. The API values were not assumed to match the earlier ticket, because no API values were taken.
