# GBP sizing blocker matrix

Label: `SYNTHETIC_TEST_ONLY`.

The numbers below come from the injected fixture. They are not OANDA spreads, not account margin rates, and not a position-size input.

| Instrument | Eligibility evidence | Pip location | Trade-unit precision | Minimum size | Margin rate | Bid | Ask | Spread in pips | Conversion factors | Stop restrictions | Financing fields | Remaining GBP-sizing unknowns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EUR_USD | SYNTHETIC_TEST_ONLY | -4 | 0 | 1 | 0.051 | 1.10000 | 1.10020 | 2 | PRESENT | PRESENT | PRESENT | UNKNOWN |
| GBP_USD | SYNTHETIC_TEST_ONLY | -4 | 0 | 1 | 0.052 | 1.20000 | 1.20030 | 3 | PRESENT | PRESENT | PRESENT | UNKNOWN |
| AUD_USD | SYNTHETIC_TEST_ONLY | -4 | 0 | 1 | 0.053 | 0.65000 | 0.65010 | 1 | PRESENT | PRESENT | PRESENT | UNKNOWN |
| USD_CAD | SYNTHETIC_TEST_ONLY | -4 | 0 | 1 | 0.054 | 1.30000 | 1.30040 | 4 | PRESENT | PRESENT | PRESENT | UNKNOWN |
| USD_CHF | SYNTHETIC_TEST_ONLY | -4 | 0 | 1 | 0.055 | 0.90000 | 0.90020 | 2 | PRESENT | PRESENT | PRESENT | UNKNOWN |
| USD_JPY | SYNTHETIC_TEST_ONLY | -2 | 0 | 1 | 0.056 | 150.000 | 150.030 | 3 | PRESENT | PRESENT | PRESENT | UNKNOWN |

USD_JPY uses pip location -2. Its spread is 3 pips. A hardcoded pip size of 0.0001 would have produced a different figure, so the fixture checks that the connector uses the returned pip location.

When both conversion objects are removed, every conversion field is `NOT_RETURNED`. The connector does not insert 1.35.

The same remaining unknowns apply to every row:

- The spread-bet stake map is unknown. Returned instrument metadata does not prove it.
- The historical units-available figure 3,476 is not a position cap.
- The historical margin display 0.03 GBP is not a fixed rate.
- The historical one-pip display 0.00 GBP is not zero risk.
- No executable size is calculated.
- Account gain, account loss, positive units, and negative units stay in separate fields.
- Broker permission to place orders with a future token remains unknown.

The full sanitised document is `06_synthetic_matrix.json`.
