# R.79 Next Stage Recommendation

R.80 was not started.

The next stage should stay offline until a separate authorisation says otherwise. Useful work, in order:

1. Reconstruct the R.75 and R.74 close cases and the R.76 entry-submit cases so the historical assertions run only after `execute_startup_sequence` has completed. Do not weaken the fence to make the old tests pass, and do not edit those tests in place unless a later stage explicitly allows it.
2. Add the missing one-cycle cases: several durable managed trades, an ambiguous entry during startup, and a journal fault armed after recovery has completed.
3. Specify a broker-side or durable compare-and-submit protocol for the race between `live_management_permitted()` and `api.request`. Do not treat the in-process check as that protocol.
4. Leave production trading NO-GO. Do not enable `REAL_SESSION_SOURCE_ENABLEMENT`. Do not create `one_session.permit`. Do not contact OANDA practice or live.

`R79_LINUX_OPERATIONAL_VERIFIED_OFFLINE` means the synthetic Linux startup and one-cycle path ran and the operational publication and write boundaries fail closed. It does not mean the bot may trade.
