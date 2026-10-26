# R.33 synthetic safety results

These calls use synthetic votes, a fixed in-memory agent, an inert broker, and `PERSIST_EXEC_ORDERS=0`. They test wiring. They are not historical model performance.

Every blocked case below kept `broker_requests == 0`, `reservation_attempted == false`, and `production_eligible == false`. All six `Strategy.active` and `authorised_for_live` flags stayed false. The harness set those flags only on the `IterationDependencies` object.

| Case | Observed block |
| --- | --- |
| Empty ensemble, fallback direction `BUY`, `allow` false | `ai_vote_rejected` |
| Supplied `HOLD` with `allow` true | `invalid_entry_direction` |
| Non-finite confidence | `ai_vote_nonfinite` |
| RL action `SKIP` | `rl_veto` |
| RL action opposite the AI side | `rl_direction_mismatch` |
| RL action `UNAVAILABLE` | `rl_state_unavailable` |
| Stop distance NaN | `sizing_input_invalid` |
| Snapshot NAV missing | `broker_value_nonfinite` |

A fresh `RLAgent` has `persisted_ok` false. The shared vote path has no strategy lookback gate before the vote, so an insufficient-history case was not added as a separate block. Conflicting extra votes and unresolved execution state were left to the earlier R.12–R.26 suites, which passed again in this stage. Production fallbacks were not changed.
