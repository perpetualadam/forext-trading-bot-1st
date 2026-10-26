# R.80 next-stage recommendation

Do not start R.81 from this stage. Production trading remains NO-GO.

The next authorised stage, if one is requested, should stay offline and should close the gaps that kept this classification partial:

1. Kill a close owner before PositionClose and after PositionClose has been entered. Assert one or zero synthetic submissions and no successor permit.
2. Run `repair_abandoned_recovery` on an abandoned in-progress owner, then show the stale owner cannot submit and the new owner does not receive an automatic second permit.
3. Replay the historical rejected-close case under a completed recovery session, including whether a later reservation is allowed only for a confirmed rejection.
4. Restart through `execute_startup_sequence` after an ambiguous entry and after an ambiguous close. Assert both stay blocked.
5. Leave the compare-and-submit proposal as a design. Do not implement a new broker protocol unless that stage explicitly authorises it.

A clean reinstall of the lockfile needs separate authorisation. It is not required to interpret the concurrency results above.
