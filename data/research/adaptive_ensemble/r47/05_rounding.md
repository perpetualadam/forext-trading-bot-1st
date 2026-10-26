# R.47 rounding and precision

GBP amounts on the ticket are printed to two decimals. The rounding mode is `UNKNOWN`. No exact broker rate is recovered. The arithmetic below is `DERIVED_MATHEMATICAL_RELATION`, illustrative, and not broker-verified.

## What two decimals hide

| Display | Nearest-cent band, ties at ±0.005 unknown | Truncation toward zero, if the amount is non-negative | Identifiable fact |
| --- | --- | --- | --- |
| 0.00 GBP per pip | Magnitude at or below 0.005 GBP. Exact 0 is inside the band and is not selected by the text. | [0, 0.01) | The unrounded pip value is missing. Exposure is not zero. |
| 0.84 GBP trade value | About [0.835, 0.845], endpoints depending on the tie | [0.84, 0.85) | Not an exact EUR sterling price |
| 0.03 GBP margin | About [0.025, 0.035] | [0.03, 0.04) | Not a margin rate |

Nearest-cent and truncation disagree. Under nearest-cent, margin / trade value can sit roughly between 2.96% and 4.19%. The published 3.33% retail major cap sits inside that band, and so do other rates. Under truncation, the same ratio's lower end is about 3.5%, so 3.33% would sit outside. Because the mode is unknown, the ticket neither confirms nor rejects 3.33%. It does not identify a rate.

## One unit and the pip display

Local pip size for EUR/USD is 0.0001 price units. Under the conventional units equation, quantity 1 moves 0.0001 USD per pip before conversion. Dividing 0.0001 USD by the shadow fallback 1.35 gives about 0.000074 GBP, which prints as 0.00 at two decimals. Any GBP/USD in a wide plausible range does the same. The display is compatible with that equation and with the 1.35 fallback, and equally compatible with other conversions, as long as the result is below one displayed penny. The fallback is not confirmed. The equation is not confirmed.

## Units available, as an illustration only

If 3,476 were the integer floor of 97.15 divided by an unrounded margin per unit, that unit margin would sit just under 0.02795 GBP. Nearest-cent rounding of that neighbourhood is 0.03, which matches the printed margin. A linear extension of the printed 0.84 across 3,476 is about 2,920 GBP of trade value, and 2,920 / 97.15 is about 30. Those products use rounded inputs. They are not a measured leverage and not a measured margin rate.

3,476 remains a point-in-time estimate. It ignores spread, slippage, conversion charges, financing, stop distance, and closeout buffer. It is not a safe maximum and not an order size.

## Margin display

0.03 GBP is the ticket's estimate for quantity 1. It is not an executable guarantee that the broker will reserve 0.03 GBP, and it is not the reserve for any other quantity. Scaling 0.03 by a larger quantity repeats the rounding error. The unrounded per-unit margin is the missing input.
