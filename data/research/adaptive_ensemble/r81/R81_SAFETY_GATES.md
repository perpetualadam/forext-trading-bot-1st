# R.81 safety gates

The four live-session gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`. Their hashes were not changed. The permit is absent. The consumed-marker hash is unchanged.

The only operational edit is the post-rate-limit `live_management_permitted()` check in the two existing write sinks, plus re-raising `CloseGuardRefusal` and `EntryGuardRefusal` from that check. The check cannot authorise a write. A failed check leaves the consumed permit in place and does not retry.

`main.py`, `forex_bot.app`, and `run_bot` were not started. No package was installed. `requirements.txt` was not edited.

`R81_SOURCE_GATES_UNCHANGED`: PASS.
`R81_NO_LIVE_PERMIT`: PASS.
`R81_R80_INTEGRATION_PRESERVED`: PASS. The R.80 suite remained 17 passed on Windows and Linux after the edit.
