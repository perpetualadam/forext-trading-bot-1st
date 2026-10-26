# Receiving principal options

Proposed design choice: a dedicated local Windows account that is not the interactive user and is not an administrator. The account does not exist. Classification of the live principal: `RECEIVING_PRINCIPAL_UNVERIFIED`.

G.14.10 observed this process at medium integrity with `BUILTIN\Administrators` deny-only. That is evidence this process is not elevated. It is not proof the account cannot elevate later. Protection against an elevated administrator is not claimed.

## Option R1 — dedicated Windows principal

- Owner: a new local account used for nothing except receiving. Not created.
- Created by: a future elevated configuration step under its own approval. This stage does not request elevation.
- Replaced by: anyone who can rewrite that account's profile directory or token. Whether the interactive user can do that at medium integrity is not measured.
- Reconfigured by: an administrator, including this account if it can elevate. Not tested.
- Terminated by: the same set. Not tested.
- Impersonated by: a process that can create a token for that SID. The named privileges `SeCreateTokenPrivilege`, `SeTcbPrivilege`, and `SeImpersonatePrivilege` were absent from this review's token in G.14.10. Other privileges were not stored. This is not a proof that impersonation is impossible.
- Executable modified by: whoever can write the directory that contains the receiver binary. That directory is part of the anchor and does not exist.
- Configuration modified by: the same write set.
- Destination modified by: whoever can write or rename the receiving directory or any ancestor. Unknown until an ACL test.
- ACL changed by: the owner and administrators. A same-user owner of an object can change its discretionary ACL. The receiver account would own the directory. The interactive user must not be that owner. Not shown.
- Service settings: R1 has no service. SCM is out of this option.
- Secrets: the account must hold no broker token, database password, or Docker credential. None were read here.
- Handles: only the receiver process. The interactive user must not receive `PROCESS_DUP_HANDLE` on it. Not shown.
- Privileges required to create it: account creation, which this unelevated process must not perform. Privileges required to run it: the receiver SID, not administrator.
- Identity evidence later: token SID equals the configured receiver SID, and medium-integrity processes of the interactive user fail to replace the directory.
- Same-user interference that remains: any medium-integrity writer who can still rename an ancestor. That is the G.14.8 attack, moved to the receiver's parent. The design forbids use until a test shows that writer fails.

## Option R2 — protected Windows service

A service is the R1 account plus a service binary and SCM configuration. It was not assumed safer.

- The binary path is another path open when the service starts. If the interactive user can replace the binary, the service is the attacker's code running as the receiver.
- SCM changes are normally limited to administrators. This was not read on this machine. G.14.10 said not to treat a service as protected from the current user.
- A service running as LocalSystem would be a larger privilege than the receiving job needs. That shape is rejected.
- Same-user interference remains if the service identity is still the interactive user. A different process is not a different authority.

R2 is not the preferred shape. It can be a later packaging of R1 only after the binary directory meets the same anchor test as the data directory.

## Option R3 — guest-side receiver

A VM, WSL distribution, or container was not verified in G.14.10. A guest does not become a receiver because the service is running.

- Who owns the guest disk or distribution filesystem is unknown.
- A shared folder or bind mount gives the host path race back to the sender.
- Export onto a Windows directory the interactive user can replace is the G.14.8 open again.
- The guest can be a future sender of bytes. It is not the host receiving authority.

R3 is not selected.

## Option R4 — another authority

Rejected shapes:

- The interactive user, with a careful path. That is the demonstrated failure.
- A launcher process of the same user. G.14.9: the launcher's first `CreateFileW` is the same race.
- A file id after the open. It names the opened object, not the intended one.
- A read-only file attribute. Not a Windows security boundary against the owner.

No fourth principal is justified.

## Preference

R1 is the proposed principal because the sender and the receiver must not share a write-capable token, and a service or a guest adds an unmeasured path. The preference is a design. The account was not created. `RECEIVING_PRINCIPAL_UNVERIFIED`.
