# R.40 expanded currency-pair shortlist

The approved research files are EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY. No historical file exists for GBP_JPY, EUR_JPY, EUR_GBP, AUD_JPY, NZD_USD, or EUR_AUD. Those six names are a verification shortlist. They are not authorised instruments. This stage did not contact a broker and does not know whether a GBP spread-betting account can trade them.

Local code maps a JPY quote currency to pip size 0.01 and any other quote currency to 0.0001. That rule would label EUR_JPY, GBP_JPY, and AUD_JPY as 0.01, and EUR_GBP, NZD_USD, and EUR_AUD as 0.0001, if files of those names were later authorised. It is not evidence that a broker lists the instrument.

R.38 already measured strong association among the existing USD pairs, including EUR_USD with GBP_USD near 0.79 and EUR_USD with USD_CHF near −0.79. Adding another USD pair, or a cross built from currencies already in the six, does not automatically add an independent sample. A cross cannot be manufactured by dividing two local USD pairs. That construction would ignore the cross spread and would invent prices.

## Rank for future data and contract verification

The rank is verification priority. It is not an expected-profit ranking.

| Rank | Name | Why it is this high on a verification list | What is still unknown |
| --- | --- | --- | --- |
| 1 | NZD_USD | Only shortlist name that adds a currency absent from the six price files | Candles, spread, session gaps, and account eligibility |
| 2 | EUR_GBP | Both currencies already have USD pairs, but the cross is a different instrument and its quote is GBP | Candles and account eligibility. Shared EUR and GBP exposure remains |
| 3 | EUR_JPY | Both legs exist separately. The cross still needs its own bid/ask file. JPY quote uses the 0.01 local pip rule | Candles, spread, and eligibility |
| 4 | GBP_JPY | Same situation as EUR_JPY, with GBP instead of EUR. Verify after EUR_JPY if a JPY-cross question is authorised | Candles, spread, and eligibility |
| 5 | AUD_JPY | Same JPY-cross situation, and AUD_USD already covers the AUD leg against USD | Candles, spread, and eligibility |
| 6 | EUR_AUD | Both currencies already have USD pairs. Most redundant cross on this list | Candles, spread, and eligibility |

General characteristics that must stay qualitative until new data exists:

- JPY crosses can have a different pip and price precision from the five non-JPY files. Local execution code formats JPY prices with three decimals and other majors with five. That is a code convention.
- EUR_GBP is quoted in GBP. The other shortlist names are quoted in USD, JPY, or AUD. A GBP account may need a conversion on some of those quotes. The conversion rate is not in the local files.
- Tokyo, London, and New York hours affect when a cross is active. The local M5 files already show weekend gaps near 49 hours. A new pair needs its own gap count.
- Volatility and opening gaps of the shortlist pairs were not measured. There is no local candle to measure.
- Spread is unknown. No OANDA spread was estimated.

A later stage that wants any of these names needs a separate authorisation to acquire data and a separate check of the account contract. Until both exist, the research universe remains the six files.
