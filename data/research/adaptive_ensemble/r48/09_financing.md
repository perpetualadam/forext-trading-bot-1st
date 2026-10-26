# R.48 financing reconciliation

The financing panel is `USER_REPORTED_TICKET_DISPLAY`, point-in-time, and not an API field.

| Panel item | Reported value |
| --- | --- |
| Buy annualised rate | −2.43% |
| Buy estimated daily charge | £16.75 per 100,000 units |
| Sell annualised rate | +0.42% |
| Sell estimated daily credit | £2.90 per 100,000 units |
| Displayed application time | 22:00 GMT+1 |

No instrument financing object was retrieved, so the panel was not matched to `longRate`, `shortRate`, or a days-charged list. The rates are not the R.45 worked example of −2.68%, and they are not a rate for a backtest. The 100,000-unit basis is the panel's own wording. It is not the ticket quantity of 1.

On 21 October 2026, 22:00 at GMT+1 is 17:00 US Eastern Daylight Time. R.45 records v20 financing as usually posted at 5pm ET. The clocks can name the same hour on that date. That is a calendar comparison, not proof that this panel is the v20 posting or that the estimated pounds are the full account charge.

The public FX formula remains a candidate only. These estimates were not inserted into it.
