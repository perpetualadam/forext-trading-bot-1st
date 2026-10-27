# Storage and security

Approved native root remains `C:\TradingResearchData\OANDA`. The existing C
adapter and identity pin are unchanged: fixed local NTFS, owner/SYSTEM ACLs,
ancestor/reparse/junction/symlink refusal, directory identity and held replacement
protection, traversal/hardlink/device-name rejection, atomic no-clobber staging
and hash verification. No fallback to repository/OneDrive for native archives.

The full 38-case HTTPS suite passes inside the native root's dedicated synthetic
session namespace. Its manifest is published by the same C response adapter used
for external archives. Portable tests use explicitly synthetic ignored fixtures.
No actual candle data, account identifier or runtime token is stored or committed.

Preserved native checks:
`python -I -S -B data/research/trading_intelligence_v2/v26c_native_check.py --check`
passes 11; `--session-check` passes 25. Both exit 0 with no failures/errors/skips.
The separate negative-security check covers a real junction and broad fixture
DACL: 3 passed, exit 0, no failures/errors/skips; no root permissions changed. Rejected native temporary fixtures remain
local synthetic evidence; no unrelated files are overwritten.

Ephemeral test keys/certificates/config are created only under ignored fixture
storage by a fixed OpenSSL req invocation, then removed. No private key is in
source, reports or Git. Runtime synthetic secrets are generated in memory,
delivered through bounded anonymous pipes after reservation and never persisted.
Tests scan every synthetic session file and ensure safe result/request records.
Even failure assertions avoid printing the generated token. No erasure guarantee.

Worker audit policy allows socket creation/connect only after synthetic permission
and credential validation, only IPv4 TCP to the fixture's 127.0.0.1 port. DNS,
public destinations, bind/listen and subprocesses refuse. The parent fixture
runner permits only an ephemeral loopback bind and fixed worker/OpenSSL argv.
No localhost addition to the production host allowlist, proxy/tunnel route,
arbitrary header, write method or account endpoint is introduced.

No actual OANDA token, .env, Windows Credential Manager, production database,
operational credential adapter or scheduler contents were inspected. Git work is
path-scoped. Operational raw hashes and historical C reports are preserved.
