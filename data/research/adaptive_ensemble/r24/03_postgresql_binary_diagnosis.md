# R.24 PostgreSQL binary mismatch diagnosis

Read-only. The binaries were not executed in this diagnosis. No cluster was created, no service was changed, and the PostgreSQL data directory was not opened.

## Verified file metadata

Previously reported runtime versions, not re-run here: `postgres.exe` printed PostgreSQL 18.1 and `initdb.exe` printed PostgreSQL 18.0. The Windows file versions below match those reports. File version is not a separate measurement from that earlier output; it agrees with it.

| | `postgres.exe` | `initdb.exe` |
|---|---|---|
| Path | `C:\Program Files\PostgreSQL\18\bin\postgres.exe` | `C:\Program Files\PostgreSQL\18\bin\initdb.exe` |
| Exists | Yes | Yes |
| Size | 10,223,104 | 243,200 |
| SHA-256 | `de2648a1d982c9ca511c663f3300ef3e381ab5a954174ecedd4b876e869ec078` | `340221ace1b2abcfe036c66da3af6a92839a2bc8d7c5756a5d57d0a64496768b` |
| File version | 18.1 | 18.0 |
| Product version | 18.1 | 18.0 |
| Description | PostgreSQL Server | initdb - initialize a new database cluster |
| Company | PostgreSQL Global Development Group | PostgreSQL Global Development Group |
| Authenticode | Not signed; no signer certificate | Not signed; no signer certificate |
| Source timestamp | 2025-11-12 06:42:34 UTC | 2025-09-24 07:16:34 UTC |
| Local creation | 2025-11-22 11:21:29 UTC | 2025-11-22 11:25:56 UTC |

## Installation consistency

`C:\Program Files\PostgreSQL` contains one server directory, `18`, plus `psqlODBC`. `C:\Program Files (x86)\PostgreSQL` contains `Npgsql` and `pgJDBC` only. Those are not server toolsets. No second `initdb.exe` was found under the PostgreSQL 18 tree.

In `bin`, `initdb.exe` is the only PostgreSQL executable whose file version is 18.0. The other server tools, including `postgres.exe`, `pg_ctl.exe`, and `psql.exe`, are file version 18.1 and share the source timestamp 2025-11-12 06:42:34 UTC. `stackbuilder.exe` is version 4.2.2 and has that same timestamp.

Windows uninstall records one product: display name `PostgreSQL 18`, display version `18.1-1`, install location `C:\Program Files\PostgreSQL\18`, install date 20251122. `installation_summary.log` records two completed installations into that same directory on 2025-11-22, at 11:45:37 and 12:17:37. It names service `postgresql-x64-18`, port `5432`, and data directory `C:\Program Files\PostgreSQL\18\data`. That data directory was not opened. The referenced installer log `C:\Users\Brian\AppData\Local\Temp\install-postgresql.log` is not present.

Both executables are unsigned, so the signatures do not show a publisher mismatch or an unexpected replacement. No upstream hash list was available, so the hashes identify the local files only.

`installer\server\initcluster.ps1` starts `bin\initdb.exe`. It does not contain another copy of the tool. `installer\server\createuser.exe` is file version 18.1.

## Compatible toolset

No matching pair was found. The only `initdb.exe` is 18.0. The only `postgres.exe` is 18.1. Files from different installations were not mixed and none are proposed as substitutes.

## Cause

Confirmed: the approved directory holds an 18.1 server binary and an 18.0 `initdb`, with different source timestamps. `initdb.exe` was created locally about four minutes after `postgres.exe`, but its source timestamp is older. The installed product is recorded as 18.1-1, and two installer completions were recorded the same day.

Not established: which installer step, repair, or copy left `initdb.exe` at 18.0. The detailed installer log is missing. Unsigned files do not by themselves show tampering.

## Resolution

Recommend a controlled repair or reinstall of this PostgreSQL 18 installation, only after a separate approval. The repair must leave `initdb.exe` and `postgres.exe` on the same patch, verified from file metadata before any cluster is created.

Do not use another installation, copy one binary over the other, or change the approved R.24 endpoint. Until a matching pair exists, R.24 stays blocked.

Approved configuration remains `127.0.0.1:55432`, database `r24_synthetic_orders`, role `r24_tester`, and data directory `data\research\adaptive_ensemble\r24\pgdata`.

## Classification

`R24_BLOCKED_DATABASE_ISOLATION`
