# R.45 financing

Source: https://www.oanda.com/uk-en/trading/financing-costs/. Effective date `UNKNOWN`. The formula is public. The daily rate is not, and it was not retrieved.

FX, gold, and silver:

`size of position x applicable funding rate / 365 x duration x conversion rate to account currency`

Position value for the general statement is size times the price at 5pm ET. FX uses size rather than that position value in the FX row of the formula table.

The funding rate is an annual long rate and an annual short rate. A negative rate is a charge. A positive rate is a credit. FX market rates are described as liquidity-provider tom-next swap rates, plus an admin fee. Admin fee: TRY pairs 4%, named CZK, HUF, SAR, THB, and ZAR pairs 2%, other pairs 1%. The six research pairs are in "other" only by not appearing in the named rows. The tom-next part changes daily. The page says today's indicative rates can differ from the final rate published after the New York close. No historical rate table was downloaded. A rate from the worked example, a long EURUSD rate of -2.68% including the 1% admin fee, is an illustration for one unnamed day, not a rate to reuse.

Positions open at 5pm ET are overnight positions. FX, gold, and silver typically settle T+2, so weekend financing is usually applied on Wednesday at three times the daily amount, and a holiday can move that day. The actual rate on a day can therefore cover more than one day.

v20 and v20 MT4: the cost is credited or debited daily, usually at 5pm ET.

OANDA One: for most instruments the cost accrues inside unrealised P&L and is posted when the position closes. Commodities are posted daily. FX is not in the commodity exception, so the OANDA One FX timing is the accrue-until-close rule. The financing page points to a sub-account differences page. The guessed URL for that page returned 404, so the distinction above is only what the financing page itself says.

The GBP EURUSD example converts a negative EUR amount by buying EURGBP and applying a 0.5% markup to the midpoint. That 0.5% figure is in the financing example. It is not the 1.0% settlement fee on the charges page. Both numbers are recorded. They are not merged.

No financing rate was written into a backtest or into production code. Today's rate is not assumed to have applied in 2025 or 2026.
