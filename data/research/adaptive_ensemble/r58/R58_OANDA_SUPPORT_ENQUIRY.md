# Enquiry to OANDA support

Not sent. Do not attach credentials or the full account identifier. Identify the account only by the method OANDA’s own secure form already uses.

Subject: GBP v20 sub-account — API unit and spread-betting stake

Please confirm the following for our OANDA Europe live v20 sub-account whose home currency is GBP. A read-only account summary on 24 October 2026 returned currency GBP. It did not return an account-type field.

1. Is this sub-account a spread-betting sub-account, a CFD sub-account, or another product? Which regulatory division holds it?

2. For FX instruments on this sub-account, what does one unit in a v20 REST order represent? In particular, for EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, and USD/CHF, is one unit one unit of the base currency?

3. If the answer to question 2 is yes, please confirm that a GBP-per-pip exposure is the result of converting quote-currency profit or loss into GBP, and that the order’s unit field is not itself a GBP stake. Please state the conversion to use for a loss.

4. If the answer to question 2 is no, please state the exact conversion from one API unit to GBP per pip, or GBP per point, for each of the six instruments. Please define the point.

5. Is the minimum size and the size increment fully described by `minimumTradeSize` and `tradeUnitsPrecision` on `GET /v3/accounts/{accountID}/instruments`? If this sub-account has a separate minimum stake or stake increment, please state it.

6. Do `pipLocation`, `marginRate`, `financing`, and the guaranteed-stop fields on that instruments response apply to this sub-account without a spread-betting adjustment? If `maximumPositionSize` is `0`, what does `0` mean?

7. Which margin rate is used in `Margin_Used = Margin_Rate * Trade_Quantity * Instrument_To_Home_Currency_Conversion_Rate` when the instrument rate and an account margin-rate override both exist?

8. Are financing rates, the daily cutoff, and the weekday multiplier the same on this spread-betting sub-account as on a v20 CFD sub-account? Does a guaranteed stop change the margin, or only add the documented execution premium?

9. Are any spread-betting charges, size limits, or stake rules absent from the REST v20 instrument, pricing, and account-summary responses?

Please reply in writing. This enquiry does not authorise any trade.
