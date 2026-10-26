# EUR/USD ticket comparison

The historical unsubmitted ticket remains a rounded interface observation. The synthetic instrument and price rows are a separate class. Neither confirms an account field.

| Item | Class | Use |
| --- | --- | --- |
| Quantity 1 | Rounded interface observation | Not proof of the API unit or of a £1 pip stake. |
| Units available 3,476 | Rounded interface observation | Not a position-size cap. |
| Trade value £0.84 | Rounded interface observation | Not an account balance or a sizing input. |
| One pip £0.00 | Rounded interface observation | Two-decimal display. Not zero risk. |
| Margin required £0.03 | Rounded interface observation | Ticket estimate. Not a fixed margin rate. |
| Synthetic instrument metadata | SYNTHETIC_TEST_ONLY | Not confirmation of a live account field. |
| Synthetic pricing snapshot | SYNTHETIC_TEST_ONLY | Not a real OANDA spread and not a strategy input. |
| Stake-to-units mapping | UNKNOWN | Spread-bet contract semantics remain unresolved. |

The connector records these distinctions in the synthetic document and sets account confirmation to NO.
