# R.45 margin and closeout

Source: https://www.oanda.com/uk-en/trading/spreads-margin/ and https://help.oanda.com/uk/en/faqs/margin-required.htm. Effective date `UNKNOWN`. Examples are hypothetical. The help page says they are for OANDA Europe Limited.

## Published retail caps

For retail clients, the spreads page states FCA maximum leverage: major forex 30:1, margin 3.33%; non-major forex and gold 20:1, margin 5%. Professional clients are a different table, including 1% and 100:1 on major forex. The page does not say which of the six pairs is major.

The retail margin-rate URL rendered a CFD heading and no forex card. Instrument-specific rates are `NOT_FOUND` in the retrieved text.

## Formula

Help text: margin needed = margin rate times trade quantity times the instrument-to-home conversion rate.

- v20 and v20 MT4: current mid price of the home/instrument pair. The example is GBPUSD for a EURUSD trade in a GBP account.
- OANDA One: top-of-book sided price at execution, ask for a buy and bid for a sell.

Worked examples on the spreads page use units and a GBP home currency. v20 margin used changes when the conversion rate changes. OANDA One margin in home-currency units stays at the opening amount. v20 unrealised P&L uses mid prices. OANDA One uses sided prices, so the spread affects the calculation even if the mid price does not.

## Closeout

- v20: closeout percent = half of margin used, divided by NAV mid. At 100% or higher, all open positions are liquidated.
- OANDA One: coverage = equity divided by margin. At 50% or below, the largest losing trade is closed, then the check repeats. Pending orders that are not tied to the closed trade stay active.
- A halted market is skipped.
- The FAQ also says the maintenance requirement is 50% of the margin needed to open, that a margin call is sent when balance is near that regulatory level, that alert emails are typically sent at 21:00 GMT, and that the account field "margin closeout percent" moving toward 100% is the warning. That 100% field matches v20, not the OANDA One coverage dial.

## What this does not support in the bot

The current code parses available margin and does not apply a closeout rule. Public text cannot choose v20 or OANDA One, cannot assign each pair to the 3.33% or 5% class, and cannot prove a GBP home currency. The bot's missing margin check is not validated by these pages. No margin rate was copied into code.
