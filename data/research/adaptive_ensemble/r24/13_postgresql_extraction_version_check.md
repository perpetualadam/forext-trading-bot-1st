# R.24 PostgreSQL extraction and version check

Classification: `R24_POSTGRESQL_TOOLSET_VERIFIED_AWAITING_APPROVAL`

The verified ZIP was extracted under `C:\R24_PostgreSQL_Test\tools`. The extracted `postgres.exe` and `initdb.exe` both report PostgreSQL 18.6, and neither version command reported a missing DLL or a Windows security block. No cluster was created.

## 1. Archive recheck

Archive: `C:\R24_PostgreSQL_Test\downloads\postgresql-18.6-5-windows-x64-binaries.zip`

| Check | Required | Actual | Result |
| --- | --- | --- | --- |
| Size | `384620317` bytes | `384620317` bytes | Match |
| SHA-256 | `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2` | `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2` | Match |

The recheck completed before any file was written. The destination `C:\R24_PostgreSQL_Test\tools` did not exist.

## 2. Extraction

Destination: `C:\R24_PostgreSQL_Test\tools`

| Item | Count |
| --- | --- |
| Archive members | `22098` |
| Files written | `20554` |
| Directories present after extraction | `3890` |
| Symlink members | `0` |
| Reparse points on disk | `0` |

Uncompressed file bytes recorded from the central directory: `1010746573`. Every member was a relative path under `pgsql/`. None used an absolute path, a drive letter, a backslash, a null byte, a `..` segment, a reserved Windows device name, or a trailing dot or space. No two members collapsed to the same Windows path. No member was a symlink. Each output path resolved inside `C:\R24_PostgreSQL_Test\tools`.

No extraction script or installer was executed. Nothing was copied into `C:\Program Files\PostgreSQL\18`.

## 3. Version commands

Both commands used the extracted full path. PATH was not used, and `C:\Program Files\PostgreSQL\18` was not used.

`C:\R24_PostgreSQL_Test\tools\pgsql\bin\postgres.exe --version`

- Exit code: `0`
- Standard output: `postgres (PostgreSQL) 18.6`
- Standard error: empty

`C:\R24_PostgreSQL_Test\tools\pgsql\bin\initdb.exe --version`

- Exit code: `0`
- Standard output: `initdb (PostgreSQL) 18.6`
- Standard error: empty

No missing-DLL message, application-control block, or other runtime dependency error was returned. No Visual C++ runtime or other package was installed.

## 4. File metadata

| Executable | File version | Product version | Windows numeric version | Size | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `postgres.exe` | `18.6` | `18.6` | `18.0.6.0` | `10266624` | `8b8bf5d400487159e3e117053d3f5a89fad0c740b310a3ac69e5720ce4f818e1` |
| `initdb.exe` | `18.6` | `18.6` | `18.0.6.0` | `246784` | `d59423ea6106821670ea7289b6d5476feb8741d5fdc8537de25f22dda1f13532` |

The Windows numeric field `18.0.6.0` is the same on both files. The version strings and the `--version` output both say PostgreSQL 18.6. These two extracted programs are a matched 18.6 pair.

## 5. Operations that did not occur

- `initdb` was not run except for `--version`.
- `postgres` was not run except for `--version`.
- `pg_ctl`, `psql`, and every other database command were not run.
- `C:\R24_PostgreSQL_Test\pgdata` was not created.
- No cluster was initialised or started.
- Windows services, PATH, the registry, and installed software were not modified.
- No database was contacted and no port was probed.
- `.env` and credentials were not read.
- The bot, production lifespan, and broker adapters were not run.
- OANDA and Telegram were not contacted.
- Docker, WSL, and virtual machines were not used.
- Application source and tests were not modified.
- Git was not committed, reset, cleaned, stashed, or rolled back.

Left untouched:

- `postgresql-x64-18`
- `C:\Program Files\PostgreSQL\18`
- `C:\Program Files\PostgreSQL\18\data`
- The existing Compose PostgreSQL 16 service and its volume
- `C:\Users\Brian\OneDrive\Desktop\concensus-forecast`

`C:\R24_PostgreSQL_Test` now contains only `downloads` and `tools`.

## 6. Readiness

The extracted toolset is ready for a separately approved isolated cluster setup. `--version` does not prove that `initdb` can create a cluster or that the server can listen.

The proposed cluster remains unauthorised:

- Host: `127.0.0.1`
- Port: `55432`
- Database: `r24_synthetic_orders`
- Role: `r24_tester`
- Proposed data directory: `C:\R24_PostgreSQL_Test\pgdata`

## Hard stop

`R24_POSTGRESQL_TOOLSET_VERIFIED_AWAITING_APPROVAL`

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
