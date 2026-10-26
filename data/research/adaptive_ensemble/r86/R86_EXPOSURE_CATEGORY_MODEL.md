# R.86 Exposure Category Model

Evidence: `exposure_report` executed on copied rows. The function does not read the live position dict unless a caller passes a copy.

| Category | Source | Units | Manageable | Aggregation |
| --- | --- | --- | --- | --- |
| `ACTIVE_MANAGEABLE_EXPOSURE` | In-memory managed rows supplied by the caller | Book units | Yes | Per instrument and direction only |
| `QUARANTINED_JOURNAL_REMAINDER` | Quarantine row plus the matching close remainder | Journal remainder, not original units | No | Not added to managed units |
| `BROKER_OBSERVED_EXPOSURE` | Trades on a parsed observation | Observed absolute units | No | Unverified. Not broker proof |
| `UNRESOLVED_EXPOSURE` | Close state other than partial, full, or finalised | Null | No | Not a number |
| `UNKNOWN_EXPOSURE` | Missing, failed, or empty-unknown observation | Null | No | Not zero |

Original units stay on `original_units`. Confirmed closed units stay on the close line when the journal has them. The same trade may appear once as a journal line and once as a broker line. Those lines are not summed into a verified total. `cross_instrument_raw_unit_total` is always null.

A journal remainder is labelled `journal_remainder_not_broker_proof`. A broker line from this adapter is labelled `unverified_single_response` or `stale_not_current`. Neither is `confirmed`.

Malformed rows return `status=unavailable` with unknown units null. They do not become zero.
