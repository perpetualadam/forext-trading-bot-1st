# R.47 six-pair applicability

Direct ticket evidence exists for EUR/USD only. The numbers 1, 3,476, 0.84, 0.00, 0.03, and 97.15 are not copied onto any other pair. None of the five is shown as enabled.

| Pair | Direct ticket | What may be reused only as a question | What needs its own evidence |
| --- | --- | --- | --- |
| EUR_USD | Yes. Unsubmitted Live ticket, units heading, GBP labels. | The questions below were opened by this ticket. | Unrounded pip value, API size field, minimum, increment, margin rate, stop distance |
| GBP_USD | No | Whether that ticket also labels quantity as units and GBP amounts to two decimals | Every number, eligibility, and the fact that GBP/USD is also a conversion pair |
| AUD_USD | No | Same question | Every number and eligibility |
| USD_CAD | No | Same question. Quote is CAD, so the conversion is not the EUR/USD conversion. | Every number and eligibility |
| USD_CHF | No | Same question. Quote is CHF. | Every number and eligibility |
| USD_JPY | No | Same question. Local pip size is 0.01 and local price text is 3 decimals. Those code conventions are not this ticket. | Every number, pip size, and eligibility |

Conceptual questions the EUR/USD ticket raises for a later pair-specific check:

- Does the quantity control sit under a units heading?
- Are trade value, pip value, and margin printed in GBP to two decimals?
- Is the stop type Normal, with Price and Pips inputs?
- Does a quantity of 1 print a pip value of 0.00 because the amount is below one penny, rather than because exposure is zero?

Those questions are not findings for the other pairs. A yes on EUR/USD would still leave each pair's pip value, margin, minimum, and eligibility to be read on its own ticket.
