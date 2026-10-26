# R.74 Durable Journal Design

Module: `forex_bot/close_journal.py`.

Storage is a local SQLite file selected by `CLOSE_JOURNAL_PATH`. The close path does not create that file. `open_journal` (lines 577–599) raises `missing_journal` when the file is absent and `corrupt_journal` when SQLite rejects it. An empty or unacknowledged journal is not treated as a clean history.

## Settings

- `PRAGMA journal_mode=WAL`. Open fails if SQLite does not report `wal` (`_configure`, lines 505–514).
- `PRAGMA synchronous=FULL`. Open fails when the reported level is below 2. SQLite level 2 is FULL.
- `isolation_level=None`, so each transition uses an explicit `BEGIN IMMEDIATE` and `COMMIT`.
- `busy_timeout` comes from `CLOSE_JOURNAL_BUSY_MS`, default 5000. A lock that outlasts it becomes `journal_lock_or_disk`.
- `commit` returns only after SQLite has applied FULL synchronous mode. This stage did not kill the process inside that fsync.

## Transitions

1. `reserve` inserts `CLOSE_PREPARED` with `submission_intent=0` and commits.
2. `commit_submission_intent` sets `submission_intent=1`, a new `owner_token`, and `CLOSE_SUBMITTING`, then commits.
3. `submission_authorized` is true only when the stored token, intent, and `CLOSE_SUBMITTING` still match.
4. Only then does `run_guarded_live_close` call `_submit_position_close_body` (`broker_close_evidence.py` lines 660–707).

A journal exception before that call returns without a broker request. `test_fault_after_intent_does_not_submit` committed intent, raised, and recorded zero `PositionClose` calls. The reopened row was `CLOSE_OUTCOME_AMBIGUOUS`.

There is no lease and no takeover. Replacing the stored token makes the old token unauthorised. An expired clock is not used.

## Bootstrap

`bootstrap_journal` is explicit.

- Neither `acknowledge_empty` nor `preexisting` creates a file whose `closes_authorised` flag is 0. `reserve` then raises `bootstrap_does_not_authorise_closes`.
- `acknowledge_empty=True` sets the flag. It does not read the broker. It is only an operator statement that no preexisting broker position was supplied.
- `preexisting` inserts one reconciliation blocker per `(account binding, instrument, trade id)` and only then sets the flag. Those trades cannot be reserved.

The manage path never calls bootstrap.

## Limits

This is one-machine file locking. It was tested on a local temp directory, not on a synced OneDrive file as the live journal. It is not cross-machine coordination and it is not broker exactly-once execution.

Process memory remains a cache. The journal is the source of truth for whether another close may be submitted.
