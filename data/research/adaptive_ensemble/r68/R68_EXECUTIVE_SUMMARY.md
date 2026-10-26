# R.68 executive summary

## What was wrong

Reconciliation could copy a broker position into the RAM book that the manage loop treats as its own. `log_only` did not stop that copy. The copied row could then be locally deleted by weekend flatten or profit protection. A row stored as `live` could also reach `PositionClose`. A paper row could be removed when a broker position existed for the same instrument. A trade id, an execution-kind string, and the mere presence of a local row were being treated as permission.

## What changed

Discoveries are stored in `broker_observations` with `observation_only=True`. They are not inserted into `positions`. One predicate, `position_management_permitted`, refuses management, local delete, unit adjust, and the auto-fix disappear path for observation rows, `reconcile_import`, and unknown kinds. Case B keeps the paper row. The manage branch returns before `execute_trade` and `close_position` when the predicate is false.

Bot-opened rows whose kind is `live`, `simulated`, `window_paper`, or `synthetic`, with `observation_only` left false, still pass the predicate. Paper rows of kind `paper`, `simulated`, and `window_paper` do too.

## What stayed in place

Strategy, AI ensemble, RL, signal routing, sizing, stop formulas, profit-protection formulas, and quote selection were not edited. Their file hashes match the R.67C baseline. The production entry path still returns `blocked`. `REAL_SESSION_SOURCE_ENABLEMENT` remains false. No activation permit was created. The consumed marker was not rewritten. No broker call was made.

C2, C3, and C4 are recorded as design amendments. They are not implemented in the trading process.

## Invariant

Discovering a broker position does not by itself grant permission to manage, close, or delete it. That holds for the import function, the delete and adjust functions, and the manage-branch source prefix. It was not executed inside the live `run_bot` coroutine, and two concurrent tasks were not run.

## Remaining safety risks

R66-03, R66-05, R66-10, R66-11, and the broader shared-RAM part of R66-16 remain open. See `R68_REMAINING_RISKS.md`.

## Production

Production trading remains NO-GO.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`

## Classification

`R68_IMPLEMENTATION_PARTIALLY_VALIDATED`

The ownership functions and the source order are tested offline on Windows and WSL2. Full validation is withheld because `_evaluate_impl` was not executed, the concurrent interleaving is `NOT_VERIFIED`, and the older tests that expected a managed import were not run.
