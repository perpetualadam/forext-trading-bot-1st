# R.46 redacted target-account profile

Source of the screen facts: the R.46 authorisation, which records what was displayed. The original screen text is not copied. No account identifier is stored. These facts are `USER_REPORTED_ACCOUNT_SCREEN`. They do not confirm API permission, order-ticket fields, or the account's state after the observation.

| Field | Reported display | Classification |
| --- | --- | --- |
| Broker | OANDA | `USER_REPORTED_ACCOUNT_SCREEN` |
| Environment | Live | `USER_REPORTED_ACCOUNT_SCREEN` |
| Platform / sub-account | v20 | `USER_REPORTED_ACCOUNT_SCREEN` |
| Product | Spread betting | `USER_REPORTED_ACCOUNT_SCREEN` |
| Home currency | GBP | `USER_REPORTED_ACCOUNT_SCREEN` |
| Balance | £97.15 | `USER_REPORTED_ACCOUNT_SCREEN`, historical snapshot |
| NAV | £97.15 | `USER_REPORTED_ACCOUNT_SCREEN`, historical snapshot |
| Observation | 21 October 2026, about 17:19 UK local time | `USER_REPORTED_ACCOUNT_SCREEN` |

The UK clock on that date was still British Summer Time, so the same moment is about 16:19 UTC. That UTC figure is a calendar conversion of the reported local time. It was not displayed as a broker timestamp.

OANDA One and MT4 are outside this profile. Professional-client terms are outside this profile. The screen did not display a client category, so retail versus professional stays `UNKNOWN`.

The balance and NAV are one historical pair of displayed figures. They are not a live reading, not available margin, and not an order size. Equality of the two displayed figures does not establish open positions, margin used, or financing. The amount is not assumed to be available now. It is not an input to sizing, simulation, or an order.

The shadow configuration constant `starting_nav_gbp` is 97.15 under the label `SIMULATED_SHADOW_NOT_BROKER`. That constant is an `IMPLEMENTATION_ASSUMPTION`. It matches the reported snapshot numerically. The match does not show that the constant was read from the broker, and it does not keep the snapshot current.

`Config.BASE_BALANCE` defaults to 10000 when the environment value is unset. That default is a different `IMPLEMENTATION_ASSUMPTION`. It is not this snapshot.
