# R.85 Next Stage Recommendation

R.86 was not started.

The next stage should not enable trading and should not auto-release quarantine. The missing evidence is a snapshot that can show freshness and completeness, and a representation of remaining units that does not overwrite original units.

A later stage can specify, without implementing a broker write:

1. A read-only snapshot contract that records retrieval time, page completion, and the account id, and that refuses an empty page unless completion is explicit.
2. A comparison of that snapshot with the close transaction time. Until that exists, freshness stays `NOT_AVAILABLE` and quarantine stays in force.
3. A durable distinction, only if separately authorised, between original units and reconciled remainder. The current columns already hold both numbers. The unsafe step would be publishing the remainder as manageable.
4. Leave the signed-unit parser on the documented fixtures. Do not replace it with `abs` until the TradeReduce sign conflict is resolved against a broker capture.
5. Keep the epoch check inside `finalise` and the second entry fence. Do not replace them with a lease.

Production trading remains NO-GO.
