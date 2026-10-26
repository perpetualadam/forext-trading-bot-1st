# R.24 PostgreSQL archive verification

Classification: `R24_POSTGRESQL_ARCHIVE_VERIFIED_AWAITING_APPROVAL`

The exact ZIP was downloaded and its size and SHA-256 matched. Its central directory was inspected. The archive was not extracted and nothing inside it was executed. No cluster was created.

## Download

| Item | Value |
| --- | --- |
| Official page | https://www.enterprisedb.com/download-postgresql-binaries |
| Page control | Binaries from installer Version 18.6, Windows x86-64, file id `1260609` |
| First URL | https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609 |
| Redirect | HTTP 302 |
| Final URL | https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip |
| Final host | `get.enterprisedb.com` |
| Download request | That final URL, HTTPS, no further redirects, HTTP 200 |
| Filename | `postgresql-18.6-5-windows-x64-binaries.zip` |
| Saved to | `C:\R24_PostgreSQL_Test\downloads\postgresql-18.6-5-windows-x64-binaries.zip` |

The staging directory did not exist before this step. It was created empty. The saved ZIP is the only file under `C:\R24_PostgreSQL_Test`. `C:\R24_PostgreSQL_Test\pgdata` was not created.

The link is the Windows x64 binary ZIP for package revision 18.6-5. It is not an installer EXE, not another PostgreSQL version, and not a host outside EnterpriseDB.

## Size and checksum

| Check | Expected | Actual | Result |
| --- | --- | --- | --- |
| Size | `384620317` bytes | `384620317` bytes | Match |
| SHA-256 | `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2` | `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2` | Match |

Both matched, so the central directory was inspected. Members were not extracted.

## Central directory

Member count: `22098`.

Required server tools, each listed once:

- `pgsql/bin/postgres.exe`
- `pgsql/bin/initdb.exe`
- `pgsql/bin/pg_ctl.exe`
- `pgsql/bin/psql.exe`

Supporting DLLs in that same `pgsql/bin` directory:

- `pgsql/bin/libpq.dll`
- `pgsql/bin/libssl-3-x64.dll`
- `pgsql/bin/libcrypto-3-x64.dll`
- `pgsql/bin/libintl-9.dll`
- `pgsql/bin/libiconv-2.dll`
- `pgsql/bin/libwinpthread-1.dll`

`psql.exe` and the same six DLLs are also listed under `pgsql/pgAdmin 4/runtime/`. Those are separate pgAdmin copies. The server toolset for a future cluster is `pgsql/bin`.

No archive member uses an absolute path, a drive letter, a backslash, a null byte, or a `..` path segment. No two members normalise to the same filename. The second copies above are different paths, not conflicting names.

The archive is structurally complete for the required server executables and those supporting DLLs. Runtime compatibility is not proved. File versions were not read, because that would execute or load the binaries. `postgres.exe` and `initdb.exe` have not been shown to be the same build by running them.

## What was not done

- The ZIP was not extracted.
- `postgres`, `initdb`, `pg_ctl`, `psql`, and every other member were not executed.
- No database cluster was created or started.
- Windows services, PATH, and the registry were not modified.
- No database was contacted and no database port was probed.
- `.env` and credentials were not read.
- The bot, its production lifespan, and the broker adapters were not run.
- OANDA was not contacted.
- Docker, WSL, and virtual machines were not used.
- Application source was not modified.
- Git was not committed, reset, cleaned, stashed, or rolled back.

Left untouched:

- `postgresql-x64-18`
- `C:\Program Files\PostgreSQL\18`
- `C:\Program Files\PostgreSQL\18\data`
- The existing Compose PostgreSQL 16 service and its volume
- `C:\Users\Brian\OneDrive\Desktop\concensus-forecast`

## Proposed plan amendment

The future isolated database settings are unchanged:

- Host: `127.0.0.1`
- Port: `55432`
- Database: `r24_synthetic_orders`
- Role: `r24_tester`

Proposed cluster directory, outside OneDrive: `C:\R24_PostgreSQL_Test\pgdata`

This directory is a proposed amendment to the earlier R.24 plan. It is not approved for cluster creation, and it was not created.

## Still required before extraction or cluster creation

1. Separate approval to extract `pgsql/bin` into a project-specific tools directory outside OneDrive, without copying anything into `C:\Program Files\PostgreSQL\18`.
2. After extraction, compare the file versions of `postgres.exe` and `initdb.exe` before `initdb` is authorised. They must be the same version.
3. Confirm the Visual C++ runtime and Smart App Control will allow those unsigned binaries to load. That was not tested.
4. Separate approval to create `C:\R24_PostgreSQL_Test\pgdata` and to start a server only on `127.0.0.1:55432`.
5. Keep `postgresql-x64-18` and the Compose PostgreSQL 16 service unchanged.

## Hard stop

`R24_POSTGRESQL_ARCHIVE_VERIFIED_AWAITING_APPROVAL`

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
