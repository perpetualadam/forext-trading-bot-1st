# Gross notional and unit limits

Production defaults were left unchanged.

- `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV` stays unset. The existing function then inherits `POSITION_NOTIONAL_PCT_OF_NAV`, whose default is 0. A zero percentage leaves the check off. Evidence records `gross_notional_enabled: false`.
- `MAX_POSITION_UNITS` stays unset. `_configured_unit_cap()` returns 0. Evidence records `unit_cap_enabled: false`. A disabled cap is not described as an active limit.
- `MAX_PORTFOLIO_RISK_PCT` remains 0.05. That is the existing portfolio stop-risk cap, separate from gross notional.

When a test sets the gross percentage above zero, the shared path runs before reservation and adapter dispatch:

- Open-position notional comes from `existing_gross_usd_by_symbol`.
- Candidate notional is absolute units times price.
- Pending, partial, and unresolved reservations on other symbols are added by `_pending_gross_usd`.
- A missing order, a missing price, a zero unit count, or a non-finite value returns `notional_exposure_unreadable`. Missing exposure is not replaced with zero.
- The existing comparison remains `resulting > cap + 1e-6`. Equal to the cap is allowed. That sentence remains in `portfolio_exposure.py`.

When a test sets `MAX_POSITION_UNITS` above zero and the sized units are larger, the shared path returns `unit_cap` before `cap_position_units` can clamp the order through. Equal to the cap is allowed. The existing helper is a per-order clamp. It does not sum open units, so this stage does not invent an aggregate unit book.

An invalid price still returns before sizing. The existing return uses the provenance label when one is present, so notional is not calculated.
