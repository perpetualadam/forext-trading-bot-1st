# Remaining gaps

- No production-eligible decision can be sealed. Account, market, and quote provenance are still missing. Margin is `NOT_IMPLEMENTED`. Numeric spread is `POLICY_UNAPPROVED`.
- The production adapter remains closed. Durable replay prevention across a process restart is NOT_EVALUATED.
- The selector ran and returned no selected name. The iteration used the supplied `scalp` strategy for the gate. That is not a production strategy activation.
- The FILLED cycle records both a local position and an unconfirmed exposure hold. Cycle 2 stops on `position_already_open` after reading the hold. It does not reach a second reservation.
- An ambiguous attempt leaves the local order `PENDING`, plus an unresolved intent and an exposure hold. The status string is not rewritten to `UNRESOLVED`.
- The in-memory store is not PostgreSQL. The R.10 `WinError 5` file-replace limitation from R.19 did not recur in this run and is not fixed.
- SELL pricing at the bid is implemented and was not the observed two-cycle direction. The observed direction was BUY at the ask.
- The legacy `run_bot` loop was not executed.
