# Historical implementation audit

Current source wins where it disagrees with an older report. Older reports were not overwritten.

| Claim | Still in the code | Connected now | Called by the app | Tested | Safe to treat as done |
| --- | --- | --- | --- | --- | --- |
| Live orders fail closed on process start | Yes, `live_safety.initialise_fail_closed` | Yes, `app.py` lifespan | Yes, in source | Historical safety tests. Not re-run here | The rule is in source. Startup was not executed |
| Six strategy names | Yes | Names are selected | Yes | Defaults tested in R.4 and R.5 | They are labels, not six live systems |
| Shadow rules for those names | Yes, `shadow/signals.py` | No | No | Shadow test files exist | Intentionally offline |
| Shared AI vote then RL | Yes | Yes | Yes | Not re-run | The live side path |
| Direction no longer defaults to BUY on the live path | Yes, `direction_action_gate` | Yes | Yes | R.4 and R.5 synthetic tests | Live path only. Backtest still defaults |
| Unresolved broker outcome blocks a new id | Yes | Yes | Yes, broker branch | Synthetic. PostgreSQL not run | Not engine-proven |
| 27 of 40 complete sessions | Research files still say 27 and 40 | Research only | No | R.2 recount matched | Not re-counted from raw files in R.6 |
| Docker deployment work | Files exist | No | No | Not run | Still NO-GO |
| Account risk limits | Code exists | Only if an env flag is on | Not by default | Repair tests exist | Default is off |

Conflicts:

- Older wording that six strategies are the live system is not what `bot_loop.py` does.
- R.5 said startup recovery is connected. That remains true as a source call. It is still not a completed startup.
- A no-vote AI result still carries the text BUY, with `allow` false. The loop returns on `allow` false before the direction gate. That is safe today and easy to break later.
