# R.43 OANDA GBP spread-betting contract checklist

This is a checklist for a later, separately authorised read-only verification. R.43 did not open `.env`, did not call a broker, and did not fetch public pages. Local evidence is what prior stages already wrote down. Unknowns stay unknown.

The figure of about £97.15 appears in the R.43 brief as a test-account balance reminder. It was not read from operational state in this stage. It is not a spread, a pip value, or a financing rate. Account balance does not replace bid/ask transaction costs. R.27 already requires NAV and balance to remain separate fields. A missing NAV must not be copied from balance.

Conventional FX unit sizing is not assumed to equal spread-betting stake sizing.

| Item | Why it matters | Required source | Local non-secret evidence | Unknown | Blocks a later trade |
| --- | --- | --- | --- | --- | --- |
| Account jurisdiction and product type | Spread-bet, CFD, and spot FX have different stake, tax, and margin rules | Account-specific summary or account details from the authorised environment | R.2 recorded that spread-bet instrument identity was still unknown. A synthetic R.27 fixture used currency USD and is not this account | Product type and jurisdiction | Yes |
| GBP spread-betting account, yes or no | The research goal is GBP economic results | Account currency and product fields for this account | Not established. The G.3 request plan names a live candle host and does not identify the product | Whether this account is GBP spread-bet | Yes |
| Practice versus live | Practice prices and live prices are different environments | The environment used for the later read | G.3 plan label says `live` for a past candle pull. That is not a current account inspection | Which environment a later check must use | Yes, until the environment is named in the authorisation |
| Instrument availability on this account | A public symbol list does not grant access | Account instrument query or account-scoped instrument details | Six names exist as local files. Six shortlist names do not | Tradable set for this account | Yes |
| Broker instrument naming | Local names use `EUR_USD`. The broker name may differ | Account instrument identifier | Local files use underscore names. Broker name mapping is not stored | Exact broker identifier | Yes |
| Tradable status | An instrument can be listed and halted | Instrument `tradeable` or equivalent field, with timestamp | Not recorded | Current tradable flag | Yes |
| Bid/ask pricing format | Research candles need both sides | Candle price component list and a sample quote | Local M5, M1, and G.3 files contain bid and ask OHLC. That describes historical files, not the live quote schema | Current quote schema | Yes for a new pull |
| Pip location | P&L and distance depend on the decimal place | Instrument pip or display-precision field | Local code uses 0.01 for JPY quotes and 0.0001 otherwise. The code comment says this is not a broker check | Broker pip location | Yes |
| Display precision | Rounding changes stops and stake value | Instrument display precision | Local code has used three decimals for JPY and five for other majors. That is a code convention | Broker precision | Yes |
| Minimum and maximum trade size | A research size can be below the minimum | Instrument minimum, maximum, and increment | Not recorded | All three | Yes |
| Minimum stake or units and increment | Spread-bet stake is not FX units | Account product size rules | Not recorded. Unit sizing must not be assumed | Stake convention | Yes |
| GBP per point or GBP per pip | This is the economic unit for a GBP account | Product specification for this account | Not recorded | Pip value in GBP | Yes |
| Margin requirement | Position size can be rejected or force closeout | Instrument margin rate and account margin fields | R.27 saw margin fields in a library example and did not use them as risk limits | This account's rates | Yes |
| Leverage limits | Leverage is not a free choice if the account caps it | Account or instrument leverage field | Not recorded | Cap | Yes |
| Margin closeout rules | A weekend gap can close a position before a research stop | Account closeout percent and closeout NAV definitions | Library examples name `marginCloseoutPercent` and `marginCloseoutNAV`. Values for this account are absent | Closeout rule | Yes |
| Guaranteed stops and charges | A guaranteed stop is a different product with a charge | Instrument or account stop options | Not recorded | Availability and charge | Yes, if the later test assumes one |
| Standard stop distance | A stop closer than the minimum is rejected | Instrument minimum stop distance | Not recorded | Minimum distance | Yes |
| Financing or overnight charges | Multi-day holds need a financing model | Financing schedule for each instrument | R.2 recorded financing as unmodelled. No rate is in the candle files | Rate, time, and direction sign | Yes for any hold beyond one session |
| Weekend holding | The local files already show weekend gaps near two days | Financing plus weekend open policy | Gap behaviour is in the candles. The charge and the permission to hold are not | Weekend charge and dealing status | Yes |
| Currency conversion charges | USD, JPY, AUD, CAD, and CHF quotes may convert into GBP | Conversion rule and charge | G.3 stored a research conversion path through the local GBP_USD bid/ask. That path is not a broker fee schedule. R.27 returns `exposure_conversion_missing` when conversion is absent | Broker conversion charge | Yes when quote currency differs from GBP |
| Commission and other fees | Spread is not the only cost | Account fee schedule | Not recorded | Commission | Yes if the product charges one |
| Historical versus current spread | A backtest spread can differ from the spread at entry | Bid and ask in the historical file, plus a later quote sample | Files contain bid and ask. No comparison with a current quote was made | Current spread | Yes before claiming a cost model |
| NAV, balance, available margin | R.27 forbids replacing NAV with balance | Account summary field list | Adapter keeps NAV and balance separate. Margin available is not a risk limit yet | Live values | Yes. Balance alone is insufficient |
| Order fill and transaction accounting | Realised P&L and partial fills need a ledger | Transaction pages and fill fields | Local parser treats fill `pl` as account-currency realised P&L. Partial and unresolved states fail closed | Live ledger for this account | Yes |
| Instrument trading hours | Session filters in code are not the broker calendar | Instrument trading-hours field | Local candles show weekend gaps. Broker hours were not read | Official hours and holidays | Yes |

A public product page, if read in a later stage, can explain a product. It cannot prove this account has that product. Account-specific rows need an authorised read of the account. They cannot be completed from the candle files.
