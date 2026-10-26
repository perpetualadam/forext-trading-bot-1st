# Future approval and verification plan

No stage below is authorised. No approval carries forward. No stage authorises live trading, a strategy change, or a change to `operator_preflight_blocked`.

G.14.10 is Stage A. It did not select a candidate. Stages B through M do not start.

## Stage A — feasibility confirmation

- Objective: decide whether existing evidence selects an isolation boundary.
- Preconditions: G.14.9 recorded no option ready.
- Permitted: read-only Git, hashing, staging verification, historical reports, and the Windows metadata listed in the validation log.
- Prohibited: Docker, WSL, VM commands, network, creation, ACL changes.
- Evidence: the G.14.10 artifacts.
- Pass: all four categories evaluated and the absence of a verified boundary stated.
- Fail closed: baseline or staging mismatch would have stopped the review.
- Approval: this stage's prompt only.
- Production: not touched.
- Recovery: none. No guest was created.

## Stage B — offline isolation-boundary design

- Objective: write a design only after a later evidence stage actually identifies a principal and an import path.
- Preconditions: new evidence, not this review. Service-running status is not that evidence.
- Permitted: documents.
- Prohibited: implementation and environment creation.
- Evidence: trust anchor, same-user test plan, export plan, production exclusion list.
- Pass: the design does not use `CreateFileW` on a path this user can replace.
- Fail closed: if no boundary was identified, do not invent one.
- Approval: separate from Stage A.
- Production: no interaction.
- Recovery: documents only.

## Stage C — environment creation

- Objective: create one approved environment.
- Preconditions: Stage B passed for a named subtype.
- Permitted: only that subtype, no production mounts, network denied.
- Prohibited: stopping the production container, mounting the repository, credentials, Docker socket.
- Evidence: identity, mounts, network deny, and an outside same-user swap attempt.
- Pass: the swap cannot redirect writes.
- Fail closed: any production mount or a successful swap stops the sequence.
- Approval: explicit creation approval. Elevation, if needed, needs to be named in that approval.
- Production: must stay up and unchanged.
- Recovery: discard only the new environment.

## Stage D — offline isolation verification

- Objective: repeat the swap, junction, and mount checks against the created environment.
- Preconditions: Stage C.
- Permitted: local tests inside the approval.
- Prohibited: network, pip, broker, database.
- Evidence: failed substitution and an empty unintended target.
- Pass: writes stay in the intended guest object.
- Fail closed: a write outside that object stops later stages.
- Approval: separate even after creation.
- Production: no mounts.
- Recovery: keep the failed environment for evidence. Do not clean host staging.

## Stage E — synthetic acquisition

- Objective: run the injected transport only.
- Preconditions: Stage D.
- Permitted: `NETWORK_DISABLED` and synthetic bytes.
- Prohibited: DNS and real indexes.
- Evidence: `COMPLETE_SYNTHETIC` and `SYNTHETIC_TEST_ONLY` on the intended object.
- Pass: synthetic success does not land on a substitute.
- Fail closed: success on a substitute stops the sequence.
- Approval: separate.
- Production: application not started.
- Recovery: do not promote synthetic files.

## Stage F — package-source metadata

- Objective: fetch metadata only from a host this approval names.
- Preconditions: Stage E and a source approval. The proposed index is not pre-approved.
- Permitted: that host only.
- Prohibited: wheel bodies, OANDA, database.
- Evidence: request log, certificate result, redirect failures.
- Pass: no unapproved host.
- Fail closed: any other host aborts before downloads.
- Approval: metadata approval distinct from source approval.
- Production: no broker route.
- Recovery: discard partial metadata.

## Stage G — wheel-only downloads

- Objective: download wheels from the approved artifact host.
- Preconditions: Stage F.
- Permitted: wheels only.
- Prohibited: source builds, hooks, install.
- Evidence: handle-read hashes and sizes.
- Pass: every selected wheel verifies.
- Fail closed: one failure publishes nothing.
- Approval: download approval.
- Production: unchanged.
- Recovery: do not publish a partial set.

## Stage H — wheelhouse and lock verification

- Objective: independent verification.
- Preconditions: Stage G and a complete target profile. The profile is not complete now.
- Permitted: local reads.
- Prohibited: trusting the producer manifest as the receiver's measurement.
- Evidence: receiver inventory. Incomplete tags stay labelled.
- Pass: both sides agree and the lock does not overclaim provenance.
- Fail closed: mismatch or incomplete profile stops packaging.
- Approval: separate.
- Production: unchanged.
- Recovery: leave bytes unpublished.

## Stage I — export and import

- Objective: cross the boundary and verify again.
- Preconditions: Stage H and a receiving anchor.
- Permitted: the one approved exit.
- Prohibited: a host path this user can swap presented as success.
- Evidence: the far side's own hashes and a failed swap.
- Pass: substitution is detected or impossible.
- Fail closed: a raced `CreateFileW` is not a pass.
- Approval: export approval.
- Production: staging tree not used as the destination.
- Recovery: do not delete the source copy in place of a failed import.

## Stage J — candidate packaging

- Objective: a candidate context that is not the running image and not the 63-file staging tree.
- Preconditions: Stage I.
- Permitted: copies of verified wheels under the import rule.
- Prohibited: edits to production Dockerfile, requirements, dockerignore, or Compose.
- Evidence: candidate file list and hashes.
- Pass: only verified inputs.
- Fail closed: any extra file or packaging edit stops the stage.
- Approval: packaging approval.
- Production: packaging bytes unchanged.
- Recovery: leave production packaging as it is.

## Stage K — candidate Docker build

- Objective: build a candidate only.
- Preconditions: Stage J and a real registry digest. The digest is unknown.
- Permitted: only a build a future prompt grants, not aimed at the running container.
- Prohibited: refresh-by-accident of the production container, unpinned base presented as verified.
- Evidence: image id and the digest actually used.
- Pass: verified inputs and a pinned base.
- Fail closed: unverified daemon context or any risk to the running container.
- Approval: Docker build approval. Not granted here.
- Production: do not tag or replace the running image.
- Recovery: `NO_VERIFIED_ROLLBACK_TARGET` still applies.

## Stage L — isolated runtime testing

- Objective: run the candidate where it cannot reach OANDA or the live database.
- Preconditions: Stage K.
- Permitted: only what that prompt allows.
- Prohibited: production container control and live orders.
- Evidence: no broker route and no live database route.
- Pass: those absences are observed.
- Fail closed: any such route stops the stage.
- Approval: runtime approval.
- Production: not stopped or restarted.
- Recovery: stop only the candidate, under that approval.

## Stage M — production safety, rollback, and deployment

- Objective: a review.
- Preconditions: every preserved blocker cleared by its own evidence. None is cleared now.
- Permitted: review.
- Prohibited: deployment and rollback from this plan.
- Evidence: the blocker list.
- Pass: only if each blocker is cleared.
- Fail closed: any remaining blocker keeps deployment NO-GO and rollback NO-GO.
- Approval: a production decision that is not this document.
- Production: unchanged unless that separate decision says otherwise.
- Recovery: the running system stays as it is.

Gate B is not hidden between these stages. It would be its own approval. This plan does not grant it.
