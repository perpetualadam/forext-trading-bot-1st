# V2.6B Secure Storage

Prepared C:\TradingResearchData\OANDA on2026-10-27. Both this path and its
parent were absent before creation; no unrelated directory was altered. Host .NET
DriveInfo verified local fixed NTFS and about153GiB free. The new path is outside
the repository, known OneDrive root and registered sync roots. Root and new
components were checked for reparse points/junctions/symlinks.

Created raw, validated, manifests, temporary_batches and research_outputs.
Directory ACLs were protected at creation using FileSystemAclExtensions, with
only the real current user and SYSTEM granted access. No sandbox-account grant,
Users/AuthenticatedUsers/Everyone grant or global OneDrive/security setting change.
Privileged administrators can take ownership; SYSTEM can access. This is ordinary
user isolation, not an encryption or privileged-adversary guarantee.

A representative unprivileged sandbox listing failed with PermissionDenied.
A clearly labelled synthetic JSON was flushed, atomically moved within this NTFS
volume and hash-verified. Its file ACL permits only user/SYSTEM identities.
The safe marker remains in research_outputs; raw/validated/manifests are empty.
No credentials, account data, journals or market data were copied.

Native evidence and limitations: storage_verification.json. WMI metadata access
was initially denied; .NET DriveInfo provided the required disk metadata instead.
No actual usernames, machine names or private SIDs are committed.

No authenticated requests. Production remains NO-GO.
