# Financing

The synthetic fixture carries invented financing fields so the parser can be checked. For EUR_USD those synthetic values are a long rate of -0.011 and a short rate of 0.021. The other five pairs use the same pattern with a different last digit. These values are `SYNTHETIC_TEST_ONLY`.

The user-reported EUR/USD financing panel stays in its own section:

- Buy annualised rate: −2.43%.
- Buy estimated charge: £16.75 per 100,000 units.
- Sell annualised rate: +0.42%.
- Sell estimated credit: £2.90 per 100,000 units.
- Displayed application time: 22:00 GMT+1.
- Class: historical display.
- Confirmed by the synthetic fields: NO.

The synthetic rates are not those displayed rates. The displayed estimates are not fixed future rates. Neither set is passed to a backtest.
