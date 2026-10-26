# R.48 reconciliation with R.47 blockers

The authenticated read did not happen. No R.47 blocker moves to a verified state. `ACCOUNT_VERIFIED` is not used. The risk engine was not implemented. `MAX_POSITION_UNITS` and `MIN_STOP_DISTANCE_PRICE` were not changed. The fail-closed currency check remains.

| R.47 requirement | R.48 status |
| --- | --- |
| Size-unit interpretation | Still open. The ticket rejects £1 per pip. The API units field was not read. |
| Minimum and increment | `NOT_RETRIEVED` |
| Pip location | `NOT_RETRIEVED`. The local 0.0001 convention is unchanged and still not an account field. |
| GBP pip value | Still unknown. The printed 0.00 GBP is still not zero risk. |
| GBP conversion | `NOT_RETRIEVED`. Gain and loss factors were not observed, so neither was substituted. The USD path and the 1.35 fallback remain in conflict with the GBP profile. |
| Margin | The 0.03 GBP ticket estimate remains a rounded display. No account margin rate was returned. |
| Stop restrictions | `NOT_RETRIEVED` |
| Financing | Panel estimates are user-reported and unmatched. The model stays `UNAVAILABLE`. |
| Fill-currency semantics | `NOT_RETRIEVED`. Transaction history was prohibited. |
| Positive position-size cap | Unchanged. The default still does not clamp. 3,476 was not copied into configuration. |

The offline gate can parse a future sanitised response. That ability does not resolve any row above.
