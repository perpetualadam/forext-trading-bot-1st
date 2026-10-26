# Future approval plan

No stage is authorised. No approval carries forward. No stage authorises live trading or a change to `operator_preflight_blocked`.

## Stage 1 — receiver security contract

- Objective: accept or reject this design. Completed as a document by G.14.11. Not accepted as implementation.
- Preconditions: G.14.10 found no boundary.
- Allowed: reading the G.14.11 artifacts.
- Prohibited: creating the account.
- Evidence: the design documents.
- Pass: a reviewer can point at the principal, the anchor, and the blocked tests.
- Fail closed: if the contract is rejected, later stages do not start.
- Approval: a later prompt. This file is not that approval.
- Production: none.
- Recovery: none.

## Stage 2 — principal and ACL inspection

- Objective: read, not create, whether any existing principal already meets the anchor. Creating one is not this stage.
- Preconditions: Stage 1 accepted as a contract.
- Allowed: only read-only inspection a future prompt names.
- Prohibited: account creation, ACL writes, elevation unless that prompt explicitly allows a consent prompt. G.14.11 does not.
- Evidence: owner SID, DACL, and whether this medium token can rename the directory.
- Pass: either an existing anchor is shown, or the result is still unverified.
- Fail closed: a writable directory is not an anchor.
- Approval: separate.
- Production: do not open safety, database, or shadow paths.
- Recovery: inspection must not leave new ACLs.

## Stage 3 — synthetic receiving prototype

- Objective: a disposable receiver only after Stage 2 shows a real anchor.
- Preconditions: Stage 2 pass. If Stage 2 found nothing, this stage does not invent an account.
- Allowed: the approved prototype only.
- Prohibited: production mounts, network, package install.
- Evidence: token SID and handle identity.
- Pass: writes stay on the receiver handle.
- Fail closed: a sender path open stops the prototype.
- Approval: separate creation approval.
- Production: untouched.
- Recovery: delete only the prototype. Not historical probes, not staging.

## Stage 4 — same-user substitution

- Objective: run scenarios A through F, K, and L on temporary non-production resources.
- Preconditions: Stage 3.
- Allowed: medium-integrity rename and ACL attempts.
- Prohibited: live broker, database, operational state, shadow state, elevation unless separately named.
- Evidence: the swap fails and the substitute stays empty.
- Pass: failure of the attack.
- Fail closed: a successful swap withdraws the design.
- Approval: separate.
- Production: none.
- Recovery: keep the failed prototype as evidence.

## Stage 5 — authentication

- Objective: scenarios O, P, and AQ.
- Preconditions: Stage 4 passed.
- Allowed: local pipe only.
- Prohibited: a network listener.
- Evidence: wrong SIDs receive nothing.
- Pass: both directions check SIDs.
- Fail closed: an unauthenticated pipe is not a pass.
- Approval: separate.
- Production: none.
- Recovery: close the pipe. Do not leave it listening.

## Stage 6 — transfer limits

- Objective: T, U, V, W, X, Y, Z, AA, AB, AC, AP, AW, AX.
- Preconditions: Stage 5.
- Allowed: synthetic bytes.
- Prohibited: real wheels from the network.
- Evidence: each rejection reason.
- Pass: no partial publication.
- Fail closed: one missed limit stops later stages.
- Approval: separate.
- Production: none.
- Recovery: unpublished leftovers are not committed.

## Stage 7 — wheel and lock verification

- Objective: AD through AK on synthetic wheels.
- Preconditions: Stage 6.
- Allowed: existing verifier on handle bytes.
- Prohibited: executing package code.
- Evidence: verifier reasons.
- Pass: malformed inputs fail and a synthetic lock is not published.
- Fail closed: a hash-only accept fails the stage.
- Approval: separate.
- Production: none.
- Recovery: none beyond the prototype.

## Stage 8 — publication

- Objective: AM, AN, AO, and the state machine.
- Preconditions: Stage 7.
- Allowed: commit on the receiver handle.
- Prohibited: rename into a user directory or the 63-file staging tree.
- Evidence: commit file id.
- Pass: substitution after verification does not publish.
- Fail closed: a user-path rename presented as atomic is a failure.
- Approval: separate.
- Production: none.
- Recovery: a partial commit is not repaired into success.

## Stage 9 — receiver-to-build

- Objective: F and AQ, plus consumer re-hash.
- Preconditions: Stage 8.
- Allowed: byte pipe to an allowlisted consumer.
- Prohibited: Docker, and adding wheels to the existing staging directory.
- Evidence: consumer hash matches, and no path open.
- Pass: both sides verify.
- Fail closed: path consumption stops the stage.
- Approval: separate.
- Production: daemon not contacted.
- Recovery: the consumer's private copy is not called publication.

## Stage 10 — acquisition environment

- Objective: only if a later review still wants a guest sender.
- Preconditions: Stages 4 through 9 passed on the host receiver. A guest is optional, not a substitute.
- Allowed: whatever that prompt names.
- Prohibited: shared folders into the receiver directory.
- Evidence: guest isolation that G.14.10 did not have.
- Pass: the guest cannot replace the host directory.
- Fail closed: a mount withdraws the guest.
- Approval: environment creation approval.
- Production: container stays up.
- Recovery: discard only the new guest.

## Stage 11 — offline synthetic acquisition

- Objective: injected transport into the receiver.
- Preconditions: Stage 9, and Stage 10 only if a guest is in use.
- Allowed: `NETWORK_DISABLED`.
- Prohibited: DNS and indexes.
- Evidence: `SYNTHETIC_TEST_ONLY` is not published.
- Pass: synthetic bytes verify and stay unpublished as production.
- Fail closed: a synthetic success that publishes is a failure.
- Approval: separate.
- Production: application not started.
- Recovery: keep the marker.

## Stage 12 — package-source metadata

- Objective: metadata only, after a source approval names a host.
- Preconditions: Stage 11. Proposed hosts are not pre-approved.
- Allowed: that host only.
- Prohibited: wheel bodies, OANDA, database.
- Evidence: request log.
- Pass: no other host.
- Fail closed: any other host aborts.
- Approval: metadata approval.
- Production: no broker route.
- Recovery: discard partial metadata.

## Stage 13 — wheel downloads

- Objective: wheels from the approved artifact host.
- Preconditions: Stage 12.
- Allowed: wheels only.
- Prohibited: source builds and install.
- Evidence: receiver hashes.
- Pass: every selected wheel verifies.
- Fail closed: one failure publishes nothing.
- Approval: download approval.
- Production: unchanged.
- Recovery: no partial publication.

## Stage 14 — real wheelhouse and lock

- Objective: independent verification of a real set.
- Preconditions: Stage 13 and a complete target profile. The profile is not complete.
- Allowed: local reads.
- Prohibited: trusting the sender manifest alone.
- Evidence: both sides' inventories.
- Pass: agreement, and the lock is not broader than the approval.
- Fail closed: incomplete tags stop packaging.
- Approval: separate.
- Production: unchanged.
- Recovery: unpublished bytes stay unpublished.

## Stage 15 — candidate packaging

- Objective: a new context, not the 63-file tree.
- Preconditions: Stage 14.
- Allowed: bytes from the receiver.
- Prohibited: edits to production Dockerfile, requirements, dockerignore, or Compose.
- Evidence: candidate hashes.
- Pass: only verified inputs.
- Fail closed: any extra file stops the stage.
- Approval: packaging approval.
- Production: packaging unchanged.
- Recovery: leave production files.

## Stage 16 — candidate Docker build

- Objective: a candidate image only.
- Preconditions: Stage 15 and a real registry digest. The digest is unknown.
- Allowed: a build a future prompt grants, not the running container.
- Prohibited: unpinned base presented as verified.
- Evidence: image id and digest used.
- Pass: pinned base and verified inputs.
- Fail closed: unverified daemon context.
- Approval: Docker build approval. Not granted.
- Production: do not retag the running image.
- Recovery: `NO_VERIFIED_ROLLBACK_TARGET`.

## Stage 17 — isolated runtime

- Objective: run the candidate without OANDA or the live database.
- Preconditions: Stage 16.
- Allowed: only that prompt.
- Prohibited: live orders and production container control.
- Evidence: those routes absent.
- Pass: observed absence.
- Fail closed: any such route.
- Approval: runtime approval.
- Production: not stopped.
- Recovery: stop only the candidate, under that approval.

## Stage 18 — production safety and rollback

- Objective: a review.
- Preconditions: every preserved blocker cleared by its own evidence. None is cleared.
- Allowed: review.
- Prohibited: deployment and rollback from this plan.
- Evidence: the blocker list.
- Pass: only if each blocker is cleared.
- Fail closed: deployment stays NO-GO and rollback stays NO-GO.
- Approval: a production decision.
- Production: unchanged unless that decision says otherwise.
- Recovery: the running system stays.

Gate B is not a hidden stage. It would need its own approval. This plan does not grant it.
