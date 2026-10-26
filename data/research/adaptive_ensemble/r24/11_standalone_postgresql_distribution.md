# R.24 standalone PostgreSQL distribution

Classification: `R24_STANDALONE_DISTRIBUTION_IDENTIFIED_AWAITING_APPROVAL`

Research only. The archive was not downloaded, extracted, or executed. No cluster was created. The existing PostgreSQL 18 service, its installation directory, its data directory, and the Compose PostgreSQL 16 service were not changed.

## Recommended distribution

Use the EnterpriseDB Windows x64 binary ZIP for installer version 18.6, package revision 5.

| Item | Value |
| --- | --- |
| Filename | `postgresql-18.6-5-windows-x64-binaries.zip` |
| PostgreSQL version | 18.6 |
| Package revision | 5 |
| Platform | Windows x64 |
| Type | ZIP archive of binaries, not an executable installer |
| Official binaries page | https://www.enterprisedb.com/download-postgresql-binaries |
| Page control | “Binaries from installer Version 18.6”, Windows x86-64, file id `1260609` |
| Redirect | `https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609` returns HTTP 302 to the ZIP URL below |
| ZIP URL | https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip |
| Response checked | HTTP 200, `Content-Type: application/zip`, `Content-Length: 384620317`, `Last-Modified: Mon, 05 Oct 2026 07:57:33 GMT` |
| Community index | https://www.postgresql.org/download/windows/ links “zip archive of the binaries, without the installer” to the EDB binaries page |

The header check read response headers only. The ZIP body was not saved.

## Published checksum

The checksum below belongs only to `postgresql-18.6-5-windows-x64-binaries.zip`.

| Source | Published value |
| --- | --- |
| https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip.sha256 | `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2` |
| Same sidecar, filename field | `postgresql-18.6-5-windows-x64-binaries.zip` |
| Sidecar response | HTTP 200, `text/plain`, 110 bytes, `Last-Modified: Wed, 14 Oct 2026 08:30:18 GMT` |
| GitHub confirmation | https://github.com/EnterpriseDB/edb-installers/issues/733 comment by `mayankjaiswal-dev` on 2026-10-06, association `CONTRIBUTOR`, gives the same filename and the same SHA-256 |

An MD5 sidecar is also published at `postgresql-18.6-5-windows-x64-binaries.zip.md5`: `a396b007a6b20172b939a106b636c6e3` for the same filename. The SHA-256 sidecar is the checksum to use.

The S3 `ETag` on the ZIP response is not a SHA-256 and is not a substitute.

These other artifacts are different files. Their checksums must not be applied to this ZIP:

- Community source archive `postgresql-18.6.tar.gz`, SHA-256 `983ee554ec53dbeb9b70797bef9fcf4e67e117e7e48ca1463cc80b3ff8e8ff3f`, from https://download.postgresql.org/pub/latest/postgresql-18.6.tar.gz.sha256
- Package revision `18.6-1`, discussed in https://github.com/EnterpriseDB/edb-installers/issues/742
- Package revision `18.6-4`, file `postgresql-18.6-4-windows-x64-binaries.zip`
- The executable installer `postgresql-18.6-5-windows-x64.exe`

The local ZIP bytes were not hashed, because the archive was not downloaded.

## Expected tools

Verified from vendor wording:

- The EDB binaries page describes these downloads as archives of the files installed by the EDB PostgreSQL installers.
- The PostgreSQL Windows page describes the same download as a zip of the binaries without the installer.
- The EDB installer is documented to include the PostgreSQL server. An EDB maintainer, in https://github.com/EnterpriseDB/edb-installers/issues/275, describes the binary archive as the route for running `initdb` manually, while the executable installer is what creates services, menus, and registry entries.

Not verified for this revision, because the archive was not opened:

- The member list.
- The presence of `postgres.exe`, `initdb.exe`, `pg_ctl.exe`, and `psql.exe`.
- A matching file version on `postgres.exe` and `initdb.exe`.
- The supporting libraries that those programs load, including the usual `libpq`, OpenSSL, `libintl`, `libiconv`, and `libwinpthread` DLLs.
- Whether pgAdmin or Stack Builder files are also inside the archive.

Earlier EDB Windows binary ZIPs unpack under a `pgsql` directory with the server tools in `pgsql\bin`. That layout is prior-revision evidence, not a listing of 18.6-5.

## Dependencies and extraction limits

- Extracting a ZIP into a new directory does not itself register a Windows service, edit `PATH`, write installer registry entries, or replace `C:\Program Files\PostgreSQL\18`.
- The EDB installer option `--install_runtimes` installs Microsoft Visual C++ runtime libraries and defaults to yes. The ZIP does not run that option. Whether 18.6-5 needs a system Visual C++ runtime, or carries every required DLL inside the archive, is unverified. Source: https://www.enterprisedb.com/docs/supported-open-source/postgresql/installing/command_line_parameters/
- The issue that requested this checksum states that the binaries inside the ZIP are not Authenticode-signed. EDB’s 2026-10-07 reply on https://github.com/EnterpriseDB/edb-installers/issues/713 says code-signing coverage is planned for an upcoming release. This ZIP was last modified on 2026-10-05, before that reply. Signature status of 18.6-5 was not inspected. If Smart App Control is enabled, an unsigned `postgres.exe` or DLL can be blocked. That state was not read on this computer.
- A future `initdb` from this archive must not be mixed with `C:\Program Files\PostgreSQL\18\bin`. The existing tree has `postgres.exe` 18.1 and `initdb.exe` 18.0. Those files stay untouched.
- A default new cluster listens on port 5432. The approved R.24 port is `55432` and the approved listen address is `127.0.0.1`. Those settings have to be applied to the new cluster before any start, so the new server does not meet the existing `postgresql-x64-18` service on port 5432.
- `pg_ctl register` would create a Windows service. That command is not part of extraction and is not authorised.
- The project directory is under OneDrive. Sync of an extracted tool tree, and later of `data\research\adaptive_ensemble\r24\pgdata`, can lock or copy database files. That risk is unresolved. The approved cluster path is unchanged.

## Isolation

A later approved extraction can stay isolated if all of the following remain true:

- The only downloaded file is `postgresql-18.6-5-windows-x64-binaries.zip` from the URL above.
- Its SHA-256 matches the sidecar before anything is extracted.
- Extraction goes to a new directory under this project, for example `data\research\adaptive_ensemble\r24\tools\postgresql-18.6-5`, and nowhere else.
- Commands use the full path to that extracted `bin` directory.
- Nothing is copied into `C:\Program Files\PostgreSQL\18`.
- `postgresql-x64-18` is not started, stopped, or reconfigured.
- `C:\Program Files\PostgreSQL\18\data` is not opened.
- PATH, the registry, and installed software are not modified.
- The Compose PostgreSQL 16 service and its volume are not started or changed.
- No service registration, no `initdb`, and no server start happen in the download-and-extract step.

That extraction directory was not created.

## Unresolved until a separately approved download

1. Hash the saved ZIP and compare it with `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2`.
2. List the archive members and confirm one matched pair of `postgres.exe` and `initdb.exe`, plus `pg_ctl.exe` and the DLLs those programs require.
3. Read file versions without executing the programs, and reject the package if `postgres.exe` and `initdb.exe` differ.
4. Decide whether the Visual C++ runtime is already present or must be supplied without changing the existing PostgreSQL installation.
5. Check whether Smart App Control will block the unsigned programs.
6. Decide how OneDrive sync will be kept off the extracted tools and the future `pgdata` directory.

## Actions that still require approval

- Download the ZIP.
- Verify the SHA-256.
- Extract it into the project test-tools directory.
- Create the cluster at `data\research\adaptive_ensemble\r24\pgdata`.
- Start PostgreSQL on `127.0.0.1:55432` with database `r24_synthetic_orders` and role `r24_tester`.
- Resume R.24 integration tests.

None of those actions is authorised by this report.

## Hard stop

`R24_STANDALONE_DISTRIBUTION_IDENTIFIED_AWAITING_APPROVAL`

PRODUCTION DEPLOYMENT: NO-GO. PRACTICE ORDERS: NOT AUTHORISED. LIVE TRADING: NOT AUTHORISED. ROLLBACK: NO-GO.
