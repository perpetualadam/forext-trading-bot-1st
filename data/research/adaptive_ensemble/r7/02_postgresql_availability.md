# PostgreSQL availability

PostgreSQL binaries are installed. They were not started.

- `postgres.exe` reports PostgreSQL 18.1.
- `initdb.exe` reports PostgreSQL 18.0.
- Location: `C:\Program Files\PostgreSQL\18\bin`.
- `psql`, `postgres`, and `initdb` are not on PATH.
- The Python driver `psycopg2` is already installed. Nothing was downloaded.

A new data directory could have been created under the R.7 folder. That was not done.

Why it was not started:

- A Windows PostgreSQL server listens on localhost TCP unless that is turned off, and localhost TCP is an `AF_INET` socket.
- This stage forbids allowing `AF_INET`, `AF_INET6`, or `AF_UNIX`, and forbids treating localhost TCP as offline.
- A named-pipe-only setup was not demonstrated. Starting the server to find out whether it opens a socket would itself be the forbidden step.
- No existing cluster, credential, or data directory was opened.
- No port was probed.

Result: `POSTGRESQL_ENGINE_NOT_EVALUATED`.

SQLite and Python mocks are not used as a substitute for the engine.
