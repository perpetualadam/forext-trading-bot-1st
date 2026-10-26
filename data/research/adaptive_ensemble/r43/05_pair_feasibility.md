# R.43 additional-pair feasibility

The approved historical instruments remain EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY. The six names below are a verification shortlist carried forward from R.40. They are not authorised trading instruments. No local candle exists for any of them. A cross price was not synthesised from the USD pairs.

Local code `research_pip_size` maps a JPY quote to 0.01 and any other quote to 0.0001. That is a code convention, not an OANDA contract. No spread, margin, financing rate, or account eligibility was invented.

Rank is future verification priority. It is not an expected-profit ranking. R.38 already recorded strong association among the existing USD pairs, including EUR_USD with GBP_USD near 0.79 and EUR_USD with USD_CHF near −0.79. Another USD pair, or a cross of currencies already in the six, is not an independent sample by itself.

| Rank | Instrument | Quote | Local pip convention | New currency | Overlap | Verification still required |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | NZD_USD | USD | 0.0001 | NZD | USD quote only | Candles, bid/ask history, session gaps, spread, margin, financing, GBP conversion, account eligibility |
| 2 | EUR_GBP | GBP | 0.0001 | None | EUR and GBP already present | Own bid/ask file. Shared EUR and GBP exposure remains. GBP quote may change conversion versus a USD quote |
| 3 | EUR_JPY | JPY | 0.01 | None | EUR and JPY already present | Own bid/ask file, JPY precision, spread, financing, eligibility |
| 4 | GBP_JPY | JPY | 0.01 | None | GBP and JPY already present | Same as EUR_JPY, after that check if a JPY-cross question is authorised |
| 5 | AUD_JPY | JPY | 0.01 | None | AUD and JPY already present | Same JPY-cross checks. AUD_USD already covers AUD against USD |
| 6 | EUR_AUD | AUD | 0.0001 | None | EUR and AUD already present | Own bid/ask file. Most redundant cross on this list |

Qualitative constraints that apply to every row:

- Tokyo, London, and New York hours change when a pair is active. The existing M5 files already show weekend gaps near two days. Each new pair needs its own gap count.
- Spread sensitivity cannot be ranked without bid and ask history. No OANDA spread is stated here.
- A GBP account may need a conversion when the quote is USD, JPY, or AUD. The conversion rate is not in the local files. R.27 already fails closed when a position quote currency differs from the account currency and no conversion is supplied.
- Broker eligibility is account-specific. A name in a generic instrument list would not prove this account can trade it. This stage did not fetch a list.
- Financing and margin are unknown for every shortlist name and also for the existing six.
- Data requirement for any later study: bid and ask OHLC, completeness, UTC timestamps, and a span that is not the exposed year. A few weeks remain insufficient.

NZD_USD stays first because it is the only name that adds a currency absent from the six price files. It still waits behind contract verification and fresh data for the existing six.
