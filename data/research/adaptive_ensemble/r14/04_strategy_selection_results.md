# Strategy selection

ACTUAL STRATEGY SELECTOR EXECUTED.

The six names remain one inactive registry. `select_strategy` returns a name, a lookback, and a horizon label (`legacy`, `scalp`, or `swing`). It does not produce six independent signals. With the deterministic flag off, the production function uses the existing random meta-learner. Tests that need a stable name call `select_deterministic` with `persist=False` and a synthetic active map. That map does not write the production strategy objects.

C01–C06: each production strategy object stays `active=False` and the gate returns `STRATEGY_INACTIVE`.
C07: unknown name returns `UNKNOWN_STRATEGY`.
C08 and C14: no selected name returns `NO_STRATEGY_SELECTED`.
C09: two names enabled only in the synthetic map. The selector returns one of them. Production objects stay inactive.
C10: the same map returns `trend` twice.
C11: lookback is an integer and horizon is a label.
C12: production activation flags are unchanged.
C13: a selector exception returns `strategy_selection_error`.
C15: an unavailable selector returns `strategy_selection_unavailable`.
