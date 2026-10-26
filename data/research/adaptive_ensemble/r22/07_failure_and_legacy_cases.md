# Failure and legacy cases

All of these blocked before a second inert dispatch.

| Case | Result |
|---|---|
| Recovered PENDING | `active_reservation` |
| Recovered PARTIAL | `exposure_unconfirmed` |
| FILLED without a flat marker | `exposure_unconfirmed` |
| Recovered UNRESOLVED | `exposure_unconfirmed` |
| Legacy FILLED with missing metadata | `exposure_unconfirmed` |
| Unknown exposure marker | startup `OrderRecoveryUnreadable`, then `recovery_unreadable` |
| Missing file | `recovery_unreadable` |
| Corrupt file | `recovery_unreadable` |
| Truncated row | `recovery_unreadable` |
| Missing client id | `recovery_unreadable` |
| Duplicate client id | `recovery_unreadable` |
| Reservation status disagrees with order status | `recovery_unreadable` |
| Store write failure | `reservation_refused`, adapter calls 0 |
| Store read failure | `recovery_unreadable` |
| Caller flat marker | `confirm_exposure_flat` returned false and the hold remained |
| `CONFIRMED_FLAT` | not written by the FILLED or UNRESOLVED scenarios |
| Ambiguous retry | instance B adapter calls 0 |
| Duplicate dispatch after restart | instance B adapter calls 0 |
| Production adapter | forged eligibility rejected, broker calls 0 |
| Null selector | `NO_STRATEGY_SELECTED`, no store file created |

An empty valid store stays readable and does not invent a hold. A missing store does not.
