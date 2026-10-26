# Receiver feasibility

Compared with G.14.10 only. No new host probe was run. Missing values were not filled in.

Host evidence that still stands as prior observation, not a new measurement: Windows Professional, AMD64, medium integrity, process not elevated, Administrators deny-only, hypervisor present, Hyper-V services running, WSL service running, Docker historical only.

## Components

| Component | Class |
| --- | --- |
| R1 account that is not the interactive user | DESIGNED_NOT_IMPLEMENTED. REQUIRES_PRIVILEGED_CONFIGURATION. The account does not exist. |
| Proof the medium-integrity user cannot reconfigure that account | UNSUPPORTED_BY_CURRENT_EVIDENCE. REQUIRES_FUTURE_EMPIRICAL_VERIFICATION. |
| Receiving directory and parent ACL | DESIGNED_NOT_IMPLEMENTED. REQUIRES_PRIVILEGED_CONFIGURATION. REQUIRES_FUTURE_EMPIRICAL_VERIFICATION. |
| Service binary protection | UNSUPPORTED_BY_CURRENT_EVIDENCE. R2 is not preferred. |
| Named-pipe SID checks | DESIGNED_NOT_IMPLEMENTED. A local pipe is not authentication by itself. |
| Same-user resistance | UNSUPPORTED_BY_CURRENT_EVIDENCE. The opposite was demonstrated for a user-owned path. |
| Publication that is not a user-path rename | DESIGNED_NOT_IMPLEMENTED. |
| Build consumer that does not open a sender path | DESIGNED_NOT_IMPLEMENTED. |
| Guest receiver | UNSUPPORTED_BY_CURRENT_EVIDENCE. INFEASIBLE_UNDER_STATED_ASSUMPTIONS if a shared folder is the export. |
| Same-user ACL as the only control | INFEASIBLE_UNDER_STATED_ASSUMPTIONS. G.14.8. |
| Verifier on handle bytes | DESIGNED_NOT_IMPLEMENTED as a call into existing helpers. The helpers exist. The call from a receiver process does not. |
| Real provenance and target tags | UNSUPPORTED_BY_CURRENT_EVIDENCE. |

## What a later implementation would need

- Windows account creation and an ACL the interactive medium token cannot rewrite. Not authorised.
- No service, unless a later design repeats the anchor test for the binary. Not authorised.
- A protected directory. Not authorised.
- No guest until G.14.10's gap is closed by a different approval.
- An IPC endpoint. Not authorised. Not created.
- A receiver process. Not authorised.
- Reuse of `verify_member_bytes` and `inspect_wheel_bytes`. Editing those files was not done and is not approved here.
- The publication state machine. Not authorised.
- The 50 adversarial scenarios. Not run.

## Unknowns left unknown

Whether a dedicated principal can be established. Whether this user can reconfigure it. Whether a directory can be protected. Whether a service binary can be protected. Whether SID-checked IPC can be established. Whether publication and the build consumer resist substitution. G.14.10 did not answer these. This stage does not invent the answers.

Implementation is not approved. The blocker is empirical: the design's same-user claim has no supporting ACL result, and the token evidence leaves elevation untested.
