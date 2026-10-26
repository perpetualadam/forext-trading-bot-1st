# R.86 Next Stage Recommendation

R.87 was not started.

Do not enable trading and do not release quarantine. The position adapter still cannot show that a snapshot is complete or that it includes the close transaction.

A later stage would need, before any recovery decision uses a snapshot as current evidence:

1. A read-only observation record with monotonic times, the recovery epoch, and an explicit pagination result. Do not infer that result from a parsed positions list.
2. A transaction watermark taken from a response that actually carries one, compared with the close transaction without treating a newer id as completeness.
3. Leave `portfolio_exposure.py` as the managed-book metric until a caller can show quarantined and unknown exposure under separate names.
4. Keep the R.85 entry guard and close-finalisation fence. The check-to-request race is still open.

Production trading remains NO-GO.
