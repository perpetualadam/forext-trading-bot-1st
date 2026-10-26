# R.24 PostgreSQL repair impact assessment

Read-only. No binary was executed, no service was changed, no port was probed, and no cluster file was opened.

The approved test configuration is unchanged: `127.0.0.1:55432`, database `r24_synthetic_orders`, role `r24_tester`, data directory `data\research\adaptive_ensemble\r24\pgdata`.

## Existing service and installation

One PostgreSQL service is registered.

| Item | Evidence |
|---|---|
| Service name | `postgresql-x64-18` |
| Display name | `postgresql-x64-18 - PostgreSQL Server 18` |
| Status | Running. Queried only; the service was not controlled. |
| Startup | Automatic (`Start` DWORD 2) |
| Account | `NT AUTHORITY\NetworkService` |
| Command | `"C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" runservice -N "postgresql-x64-18" -D "C:\Program Files\PostgreSQL\18\data" -w` |
| Product | Uninstall record `PostgreSQL 18`, version `18.1-1`, location `C:\Program Files\PostgreSQL\18` |
| Repair entry | No `ModifyPath` |
| PATH | Neither the machine PATH nor the user PATH contains a PostgreSQL entry |

The cluster location is known from the service command and from `installation_summary.log`. The data directory was not opened and its contents were not read. The service must be treated as in use.

`installation_summary.log` records two completed installations into `C:\Program Files\PostgreSQL\18` on 2025-11-22, both naming port `5432`, service `postgresql-x64-18`, and data directory `C:\Program Files\PostgreSQL\18\data`. The detailed installer log is absent. No second server installation directory was found.

## Option A — repair in place

Not safe to approve.

`installer\server\initcluster.ps1` is the only local cluster-creation script. If it is run against a data directory, it does not first refuse an existing cluster. It removes inherited ACLs on that directory, runs `bin\initdb.exe` with `--pgdata` set to it, and rewrites `postgresql.conf` so `listen_addresses` is `'*'` and the port is the script argument. It also changes directory permissions.

Whether the Windows repair action invokes that script is **UNKNOWN**. There is no repair manifest and no `ModifyPath`. Replacing `pg_ctl.exe` or `postgres.exe` while `postgresql-x64-18` is running is also **UNKNOWN** in installer behaviour. Because the running service loads binaries from the same `bin` directory, a repair cannot be demonstrated safe without operational data or installer documentation that is not present.

## Option B — separate installation

Not safe to approve from the evidence on this machine.

No separate PostgreSQL 18 installer package or matching binary set is present. The installations already recorded used the same directory, the same service name, and port `5432`. A future run of that same installer family therefore cannot be assumed to leave `postgresql-x64-18` and `C:\Program Files\PostgreSQL\18` untouched.

A directory-only toolset that does not register a service, does not edit PATH, and does not write the existing registry keys would be a different method. No such package is on the machine, and its installer behaviour was not verified. It remains an assumption.

The stock `initcluster.ps1` path does not target `127.0.0.1:55432` or `data\research\adaptive_ensemble\r24\pgdata`. It writes the caller-supplied data directory and sets `listen_addresses` to all interfaces.

## Comparison

| Criterion | Repair existing installation | Separate installation |
|---|---|---|
| Existing service impact | Unknown. The service is running from this `bin`. | Unknown. Recorded installs used this service name. |
| Existing cluster impact | Unknown for repair. The local init script would alter the data directory it is given. | Unknown. Recorded installs named the existing data directory. |
| Configuration impact | Unknown for repair. The local init script rewrites `listen_addresses` and the port. | Unknown. The local script does not use the R.24 endpoint. |
| Installation feasibility | Product 18.1-1 is registered, but no repair procedure is present. | No side-by-side package or matching toolset is present. |
| Isolation confidence | Low | Low |
| Recommended | No | No |

Replacing only `initdb.exe`, or mixing binaries from different releases, is not a recommendation.

## Recommendation

Remain blocked. Neither option is supported as safe by the local evidence.

A later approval would be required before any repair, second installation, service change, binary replacement, or resumption of the R.24 cluster. That approval would need evidence that the chosen method does not stop or rewrite `postgresql-x64-18`, does not open `C:\Program Files\PostgreSQL\18\data`, and still produces one matching `postgres.exe` and `initdb.exe` pair.

## Classification

`R24_REPAIR_IMPACT_ASSESSED_AWAITING_APPROVAL`
