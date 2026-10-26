# R.86 Snapshot Freshness and Chronology

Evidence: source inspection of the position cache, plus executed classifications with caller-supplied clocks. Broker transaction order was not observed.

Local labels the tests set include `LOCAL_BEFORE_CLOSE`, `STALE_CACHE`, `LOCAL_AFTER_CLOSE`, `AFTER_JOURNAL_COMMIT`, and `AFTER_CONFIRMATION`. Those labels describe the test's local order. They do not prove the broker snapshot contains the close.

| Case | Executed result |
| --- | --- |
| Snapshot chronology before the close | `STALE`, not suitable for recovery |
| Cached snapshot | `STALE` |
| Epoch on the observation differs from the current epoch | Broker line quality `stale_not_current`, `authoritative_current` false |
| Missing timestamp | Not current |
| Timestamp after the controlled reference clock | `stale_not_current` |
| After journal commit, no watermark | `transaction_watermark` is null and `broker_order_known` is false |
| Apparently newer local chronology | Still not recovery-suitable |

Monotonic request start and completion are stored when the caller supplies them. Wall-clock order alone is not used as broker order. A future timestamp is rejected as current evidence.

The position adapter does not read `lastTransactionID`. A watermark older or newer than the close cannot be compared. Chronology against the broker remains unverified.

`known_broker_net` can reuse the last successful OpenPositions cache after a close until another fetch replaces it. The report marks a cached observation stale. Startup recovery was not changed to clear that cache.
