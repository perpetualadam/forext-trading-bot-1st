# R.46 stake-versus-units blocker

This remains the primary unresolved sizing issue. No conversion factor is chosen. No stake conversion is implemented. The charges-page example of 10,000 units, the CFD lot of 100,000 units, and `Config.BASE_BALANCE` default 10000 are not an intended trade size. `MAX_POSITION_UNITS` defaults to 0, and the code treats that as no clamp. The historical £97.15 snapshot is not a position size.

## Meanings that must stay separate

| Term | What the evidence supports | Classification |
| --- | --- | --- |
| Conventional FX units | Public examples and the local order path size a position as units. `units_for_notional` returns a whole unit count from a GBP notional divided through a USD conversion. | `LOCALLY_VERIFIED_IMPLEMENTATION` for the code. `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` for the public unit language. |
| GBP per pip | A pip in the code is a price increment, 0.0001 or 0.01. It is not a pound amount. | `UNKNOWN` as money |
| GBP per point | The spread-betting page uses the words pips and points. It does not define a point as a pound, or a point as a price increment, for v20. | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Price precision | The code prints 5 decimals, or 3 when the name contains JPY. The public pages did not publish that precision for these pairs. | `LOCALLY_VERIFIED_IMPLEMENTATION` versus `UNKNOWN` at the broker |
| Position notional | Shadow notional is a percent of a GBP NAV converted into units. Production risk multiplies price distance by units and stops at approximate USD. | `CONFLICTING_EVIDENCE` |
| Monetary P&L | Quote P&L is price change times units. Account money then depends on the currency path. Three local paths exist. | `CONFLICTING_EVIDENCE` |
| Risk at a stop | `stop_risk_account_ccy` returns an approximate USD amount. `stop_risk_gbp` then divides by GBP/USD or 1.35. Neither applies the v20 1.0% markup, and neither is a stake-per-point formula. | `IMPLEMENTATION_ASSUMPTION` |
| Margin required | Public candidate is margin rate times quantity times conversion, using v20 mid. The rate and the quantity unit are unverified. The bot does not apply the formula. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |

A spread-bet stake can be a money amount per point. A unit can be a quantity of base currency. Those are the same number only if the ticket defines that identity. R.45 did not find that definition. The screen did not display it. The identity is not assumed.

## What a later calculation would need

GBP value of a one-pip movement, for a stated size:

- The ticket's size field and its unit, in the broker's words.
- The price distance the broker calls one pip, and the price distance it calls one point, for that instrument.
- Whether one displayed size unit is one unit of base currency, one pound per point, or another quantity.
- The home currency, already reported as GBP for the profile and still not an API field.
- The conversion from quote P&L into GBP, including which markup applies.

GBP risk for a proposed stop distance:

- The items above.
- The stop distance in the broker's price units.
- Whether the stop can slip, and whether a guaranteed stop adds a premium.
- The size actually accepted, after minimum and increment.

Minimum possible monetary risk:

- The minimum accepted size.
- The size increment.
- The minimum stop distance, if one is enforced.
- The GBP value of one pip at that minimum size.
- The spread cost and any conversion charge on that loss.

Position size for a stated GBP risk budget:

- A confirmed GBP-per-pip amount at size 1, in the ticket's unit.
- The stop distance.
- The minimum and the increment, so the size can be rounded in the broker's step.
- Confirmation that the resulting margin fits the account. The £97.15 snapshot does not provide that margin figure.

Until those items exist, no research or production path may turn a GBP risk budget into an order quantity.
