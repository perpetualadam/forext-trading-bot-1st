# Preferred architecture decision

Decision: `NO_OPTION_READY_FOR_IMPLEMENTATION`

Environment selection, if a later evidence stage is ever approved: `ENVIRONMENT_SELECTION_REQUIRES_FURTHER_EVIDENCE`

This decision does not approve implementation, package sources, network access, Docker, Gate B, deployment, or rollback.

## Rationale

G.14.8 showed that a same-user process can choose the directory that `CreateFileW` opens. Every later handle-relative operation is correct relative to that directory and silent about whether it was the intended one.

Option A puts the same open in a launcher. Unless the launcher is a different principal whose objects this user cannot replace, the test result does not change. That principal was not found. The option is `TRUST_ANCHOR_UNVERIFIED` and ineligible.

Option B is the only class that could put the writes somewhere this user cannot swap. No subtype has evidence for that property. A restricted process is the same user. WSL, a virtual machine, and a container were not inspected. A container is not assumed to be isolated from the historical production daemon. `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` remains. Export back onto a user-writable path would repeat the race even if a guest were sound. The aggregate score was not computed, because filling the unknowns with hopeful numbers would invent a winner. The option is `TRUST_ANCHOR_DESIGNED_NOT_IMPLEMENTED` and not ready.

Option C calls the demonstrated attacker trusted. That keeps the vulnerability and fails the mandatory condition. It is `TRUST_ANCHOR_ASSUMPTION_ONLY` and ineligible. It is not recommended as the cheaper path.

## Mandatory conditions before any later implementation

- The pre-open substitution demonstrated in G.14.8 is prevented, or the import path is shown not to be a path this user can replace.
- The producer and the receiver both verify bytes they read themselves.
- The receiver does not trust the producer manifest alone.
- No production mount, operational-state mount, shadow mount, database, broker credential, or Docker socket is in the acquisition boundary.
- Network stays denied until a separate source approval and a separate download approval.
- The production container and the 63-file staging tree stay untouched.
- Symlink behaviour that was skipped stays recorded as not executed.

## Assumptions that are not granted

- This user is benign.
- A launcher is trusted because it runs first.
- A file id proves intended-path identity.
- A container, WSL distro, or restricted token is a boundary.
- A guest hash binds a host path open.
- The historical image id is a registry digest.

## Alternative

The alternative worth a future evidence stage, not an implementation, is to identify whether any boundary already exists that this user cannot rewrite, without creating one and without Docker commands against the running bot. If that evidence never appears, no acquisition architecture in this review becomes ready.

## Rejected

- Option A as an implementation, because it relocates `CreateFileW`.
- Option C as a security boundary, because it excludes the demonstrated attacker.
- Every Option B subtype as a selection, because none is evidenced.
- A score-based choice of A over C. A scored 190 and C scored 178 out of 520. Both are ineligible.

## Future stages

See `future_stage_approval_plan.md`. None of them starts from this decision.

## Remaining blockers

`FILESYSTEM_TRUST_BOUNDARY_UNVERIFIED` stays, together with the absent sender, the unapproved package source, the missing lock and wheelhouse, the incomplete target profile, the unverified image digest, and the production NO-GO blockers.
