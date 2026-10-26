# R.77 security review

This stage did not read `.env`, print the consumed marker, or create `one_session.permit`. The marker hash and the four source-gate hashes matched the values recorded before editing.

Account identity stored by the new paths is `account_binding`, a SHA-256 of the account string. Repair stores that binding and a hash of the journal path. The operator acknowledgement is free text supplied by the caller. The repair module has no field for a token, password, or raw account id.

`repair_abandoned_recovery` cannot enable a live session. It does not call the broker, the permit writer, or `execute_trade`. A wrong journal path does not open that other file. An active or unproven recovery owner does not lose the claim.

Client ids longer than the broker extension limit are rejected instead of being silently truncated into another id. Whitespace-only ids are rejected. The registry row survives archival of the operation row, so completion does not free the id inside that file.

The isolated tests scrub environment names that contain credential markers and replace `psycopg2.connect` and non-loopback sockets with `IsolationBreach`. The Windows suite's network assertion saw neither a Postgres connect nor an external socket from those guards.

The WSL import probe of `forex_bot.oanda_client` failed on `import oandapyV20` at line 13, before `from forex_bot.config import Config`. `load_dotenv` did not run for that probe.

Remaining exposure is operational, not a new secret store: a person who can write the SQLite journal can still insert rows, and a lost journal file drops the client-id registry. Those are stated as durability limits, not as broker guarantees.
