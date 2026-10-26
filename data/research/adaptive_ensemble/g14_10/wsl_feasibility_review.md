# Disposable WSL feasibility

Classification: `WSL_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Verified isolation: no. A running WSL service is not a disposable distribution and is not a mount policy.

## What was observed

Level 2, this stage:

- `WslService` is present, running, and automatic. The older name `LxssManager` is not present. That absence is only the older name.
- `C:\Windows\System32\wsl.exe` exists. It was not executed.
- No distribution was listed. `wsl.exe` would have been required, and it was prohibited.

Level 4, G.14.2, not refreshed:

- The Docker engine kernel string was `6.6.87.2-microsoft-standard-WSL2`.
- That string describes the engine kernel reported then. It is not a current distribution inventory. It is not this stage's measurement of WSL1 versus WSL2. It does not say whether host paths are mounted.

## What remains unknown

- WSL1 versus WSL2 for any distribution that would be used for acquisition.
- Whether any distribution exists, who owns it, and where its filesystem is stored.
- Automount behavior and `/mnt/c`.
- Windows executable interoperability.
- WSL DNS and network mode.
- Environment and credential inheritance.
- Whether a same-user host process can reach the distribution filesystem through a host path.
- Import, export, snapshot, and delete behavior.
- `.wslconfig` and `/etc/wsl.conf` were not read and were not edited.

None of those may be filled in from the service status or from the historical kernel string.

## Trust anchor

A useful anchor would be a distribution root that does not mount host paths and that this user cannot replace from outside. No such root was identified. The actor who can reconfigure WSL was not identified. This process is not elevated. Whether reconfiguration requires elevation is unknown because it was not attempted.

## Same-user interference

G.14.8 level 1 evidence shows this user can replace a Windows path before `CreateFileW`. If a future distribution is reached through a Windows path, that result applies. If the distribution filesystem is not a Windows path, that might differ. This stage has no observation that distinguishes the two. The historical Docker kernel string does not provide it.

## Export, import, and Linux wheels

Guest-side verification and host-side export were not tested. A host import through `CreateFileW` remains `ARTIFACT_IMPORT_TRUST_BOUNDARY_UNVERIFIED`.

A Linux distribution could eventually be a place to read a CPython build. No distribution was started, so patch level, SOABI, glibc, pip, and wheel tags stay unknown. WSL is not assumed to match `python:3.12-slim-bookworm`.

## Classification

`WSL_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

The service and the executable are present, so the category is not `UNKNOWN` and not `BLOCKED`. Presence is not a verified boundary and is not `SUPPORTED_BY_EXISTING_EVIDENCE` for isolation. No distribution is selected.
