# R.81 next-stage recommendation

Do not start R.82 from this stage. Production trading remains NO-GO.

The rate-limit window that R.80 left open is now refused for the executed entry and close cases. The next offline stage, if one is requested, should stay on synthetic brokers and disposable journals and should only pick up the remaining gaps:

1. Inject journal unavailability after the rate-limit slot and before `api.request`, separate from an epoch change.
2. Keep the compare-and-submit note as a design. Do not implement a new broker protocol unless that stage explicitly authorises it.
3. Do not treat a client id, a recorder row, or a flat snapshot as broker idempotency.

A clean reinstall of the R.80 lockfile still needs separate authorisation.
