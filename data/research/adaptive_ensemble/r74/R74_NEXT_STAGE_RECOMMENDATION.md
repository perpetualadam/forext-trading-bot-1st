# R.74 Next Stage Recommendation

Stop after R.74. Do not start R.75 from this stage.

Recommended before any later implementation:

1. Keep production at `NO-GO`.
2. Do not point `CLOSE_JOURNAL_PATH` at a sync folder until that filesystem's locking is tested.
3. Do not treat `acknowledge_empty` as a broker query. A first journal for an account that already has positions needs those trade ids supplied as preexisting blockers.
4. Any later stage that wants broker-enforced duplicate suppression has to prove an OANDA contract for it. This stage did not.
5. Linux operational coverage still needs the existing runtime dependencies. Do not install them as part of a drive-by fix.
6. Leave the historical hash pins in place. New behaviour belongs in new tests.

R.75 was not begun.
