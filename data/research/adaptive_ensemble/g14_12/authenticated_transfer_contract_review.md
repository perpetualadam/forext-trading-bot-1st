# Authenticated transfer contract

The pipe does not exist. It was not created. Locality is not authentication. A SID check without the order below is not this contract.

## Creation and identity

1. Pipe name trust: the name is only a rendezvous. Matching the name is not identity.
2. Creation authority: only the receiver SID may create the instance.
3. Pipe DACL: receiver SID can create and listen. The configured sender SID can connect and transfer bytes. The interactive SID, Everyone, and anonymous have no access. FILE_CREATE_PIPE_INSTANCE is not granted to the sender.
4. Server identity: the user SID of the server process.
5. Client identity: the user SID of the client process.
6. Token check: each side reads the peer SID. A mismatch fails closed before artifact bytes are stored.
7. Impersonation: the server must not call ImpersonateNamedPipeClient. Impersonation is not the authentication step.
8. Pipe squatting: if the interactive user creates a pipe of the same name first, the real sender still fails because the server SID is not the receiver SID.
9. Unauthorised server: same check. The client disconnects and sends no wheel.
10. Unauthorised client: the server creates no file.

## Session

11. Establishment order is fixed: connect, client checks server SID, server checks client SID, server sends a nonce and session id, client echoes the nonce, only then frames.
12. The nonce is 32 random bytes from the receiver. It is not a signature of the wheel.
13. Replay: a repeated nonce or session id fails. A new nonce does not make an unapproved source acceptable.
14. Framing: count and total size first, then length-prefixed bodies.
15. Count limit: if the approved configuration has no maximum, fail closed before the first body is stored.
16. Byte limit: same rule. This stage does not invent the number. Absence of a number is refusal, not an unlimited transfer.
17. Timeout: a stalled frame fails the session. Nothing is published.
18. Duplicate names: fail, no overwrite.
19. Unicode: names must be NFC. A second normalization that collides fails.
20. Case-insensitive collisions: fail before the second create.
21. Path traversal: a name that is not one segment fails.
22. Alternate data streams: a colon fails.
23. Reserved device names: the existing reserved-stem rule fails the name.
24. Partial messages: short read fails.
25. Interrupted sessions: `FAILED_CLOSED`, unpublished.
26. Concurrent sessions: a second session fails while one is active.
27. Authentication failure: no file created.
28. Receiver restart: the old nonce is dead. Leftover files are not a commit.
29. Sender restart: must begin at step 11 again.
30. Audit: SIDs, nonce id, names, sizes, hashes, and the failure reason. No secret values.

## What this does not prove

No peer was connected. Pipe DACLs on this machine were not read. `PIPE_SQUATTING_RESISTANCE_UNVERIFIED`, `SENDER_AUTHENTICATION_UNVERIFIED`, and `RECEIVER_AUTHENTICATION_UNVERIFIED` remain.
