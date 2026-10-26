# R.82 close state transition matrix

State names are the constants in `broker_close_evidence.py`. `CLOSE_SUBMITTED` and `CLOSE_CONFIRMATION_PENDING` are blocking names. `CLOSE_CONFIRMATION_PENDING` is written when transaction retrieval fails for a transport-class reason. On the next `active_journal().recover()`, intent-1 rows in `CLOSE_SUBMITTING`, `CLOSE_RESPONSE_RECEIVED`, `CLOSE_CONFIRMATION_PENDING`, and `CLOSE_PREPARED` become `CLOSE_OUTCOME_AMBIGUOUS`.

| State | Broker evidence required | Journal evidence | Permit | New operation | Memory | Quarantine | Manual reconciliation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `CLOSE_SUBMITTING` before claim | None | Reservation only | Unconsumed | No | Unchanged | No | No |
| `CLOSE_SUBMITTING` after claim | None yet | Intent and permit | Consumed | No | Unchanged | Successor treats it as ambiguous | Yes, until evidence exists |
| `CLOSE_RESPONSE_RECEIVED` | Response stored, units not final | Response row | Consumed | No | Not removed | Recover promotes it to ambiguous | Yes |
| `CLOSE_CONFIRMATION_PENDING` | Retrieval failed | Pending error | Consumed | No | Not removed | Recover promotes it to ambiguous | Yes |
| `CLOSE_OUTCOME_AMBIGUOUS` | Request outcome unknown | Ambiguous row | Consumed | No. `test_18` repeat uses the same operation and sends nothing | Not removed | Yes while outstanding | Yes |
| `CLOSE_PARTIALLY_CONFIRMED` | Matched units greater than 0 and below requested | `confirmed_units`, `remaining_units` | Consumed | No. `test_15` | Original units kept. Not deleted | Restart quarantine. `test_17` | Yes. Not a full close |
| `CLOSE_FULLY_CONFIRMED` | Matched units equal requested, remaining 0, transaction id | Full row with transaction ids | Consumed | The same trade is finished for that operation | Removal only if the journal row passes `close_confirmed_live_position` | Awaiting finalisation if still on the book | No extra close |
| `CLOSE_REJECTED_CONFIRMED` | Reject or cancel section, no fill | Reject row | Consumed for that operation | A new operation is allowed. `test_18` sent a second, distinct close | Not treated as flat from the reject alone | No, once the new operation is authorised | No for the reject itself |
| `CLOSE_RECONCILIATION_REQUIRED` | Overfill, zero matched units, identity mismatch, or authority loss after claim | Reconciliation error | Consumed if claim happened | No automatic resubmit | Not removed | Yes when recovery sees the blocker | Yes |

Confirmed rejection and an ambiguous outcome are different. `test_18` reserved a new operation after `CLOSE_REJECTED_CONFIRMED` and refused a new send after `CLOSE_OUTCOME_AMBIGUOUS`. A partial confirmation is not stored as a full close. `test_16` keeps 999/1000 at remaining 1 and 1000/1000 at remaining 0.
