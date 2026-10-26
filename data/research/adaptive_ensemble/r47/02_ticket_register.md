# R.47 redacted EUR/USD ticket register

The original screenshot is not stored. Personal names, email addresses, and account identifiers are not recorded. The rows below are the field values reproduced in the R.47 authorisation. They are `USER_REPORTED_TICKET_DISPLAY`. They are not an API response. The order was a new, unsubmitted market-order ticket. No order was placed in this stage.

The interface was identified as Live. That word remains `USER_REPORTED_ACCOUNT_SCREEN` from R.46, repeated on this ticket. It does not authorise a live order.

No clock was printed in the redacted fields. The observation is the R.47 authorisation on 21 October 2026. A broker timestamp is `UNKNOWN`.

| Field | Displayed value | What the display does not establish |
| --- | --- | --- |
| Instrument | EUR/USD | That the other five bot names are enabled, or that this spelling is the API instrument name |
| Order quantity | 1 | The minimum, the increment, or the API units field |
| Quantity heading | Units Available | That "units" in the heading is the v20 order-size contract |
| Units available | 3,476 | A maximum safe size or a risk-budget approval |
| Trade value | 0.84 GBP | An exact conversion rate, or a GBP stake per point |
| One-pip value | 0.00 GBP | Exact zero exposure. The figure is rounded to two decimals. |
| Margin required | 0.03 GBP | A general margin rate. It is an estimate for the displayed quantity. |
| Margin available | 97.15 GBP | Current funds after this observation, or a risk budget |
| Stop-loss type | Normal | A minimum distance, a guaranteed stop, or protection from slippage |
| Stop-loss inputs | Price and Pips | The pip distance the broker uses in money |
| Order state | New Order, not submitted | Broker acceptance or rejection of quantity 1 |
