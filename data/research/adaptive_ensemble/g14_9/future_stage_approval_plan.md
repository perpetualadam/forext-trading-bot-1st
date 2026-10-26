# Future stage and approval plan

No stage below is authorised by G.14.9. No approval carries into the next stage. No stage authorises live trading, a strategy change, or a change to `operator_preflight_blocked`.

The next stage is not environment creation. It is not a download. It is not Docker.

## Stage 1 — architecture and threat model

- Objective: compare trust anchors. Completed by G.14.9.
- Allowed: read-only inspection and research documents.
- Prohibited: implementation, Docker, network, environment creation.
- Evidence: the G.14.9 artifacts.
- Pass: the three options compared and the G.14.8 finding preserved.
- Fail closed: baseline or staging mismatch stops the review.
- Approval: this stage's prompt. It does not approve Stage 2.
- Dependencies: G.14.8 report.
- Recovery: none. No system state was changed.

## Stage 2 — evidence sufficient to select a boundary

- Objective: determine whether any isolation boundary exists that this user cannot replace, or confirm that none is known.
- Allowed only under a new approval: read-only inspection that cannot start, stop, create, or modify a container, VM, WSL distro, user, or ACL. Docker commands remain prohibited unless that new approval says otherwise, and even then the running production container is out of scope.
- Prohibited: creating an environment, mounting the repository, network, downloads, production changes.
- Evidence required: the principal that owns the boundary, this user's actual access to it, mount list, and whether export avoids a user-writable `CreateFileW`.
- Pass: one subtype meets the mandatory condition with evidence, or the result is still `ENVIRONMENT_SELECTION_REQUIRES_FURTHER_EVIDENCE`.
- Fail closed: if the only way to answer is to create the boundary, stop and ask for a creation approval. Do not create it inside the evidence stage.
- Approval: a new prompt. G.14.9 does not grant it.
- Dependencies: Stage 1.
- Recovery: inspection must not leave a new guest or a changed ACL. If it would, it is the wrong stage.

## Stage 3 — implementation design

- Objective: specify code changes against a boundary Stage 2 actually selected.
- Allowed: documents, and only after Stage 2 passes.
- Prohibited: editing `tests/g14_7_fs.py` or production files until a still later implementation approval.
- Evidence: interface changes, threat coverage, and the tests that would show same-user substitution failing closed.
- Pass: a design that does not call path open on an attacker-writable directory.
- Fail closed: if Stage 2 did not select a boundary, this stage does not invent one.
- Approval: separate from Stage 2.
- Dependencies: Stage 2 pass with a real subtype.
- Recovery: design documents only.

## Stage 4 — isolated environment creation

- Objective: create the one approved environment.
- Allowed: only the approved subtype, with no production mounts and no network.
- Prohibited: Docker against the running bot, WSL or VM creation if that was not the approved subtype, ACL changes on the host profile, package installs.
- Evidence: identity of the environment, mount list, network default deny, and a same-user swap attempt from outside.
- Pass: the outside swap cannot redirect writes.
- Fail closed: any production mount, credential, or failed swap test destroys the claim. Do not continue into downloads.
- Approval: explicit creation approval.
- Dependencies: Stages 2 and 3.
- Recovery: discard the new environment without deleting host staging, probe directories, or production files.

## Stage 5 — offline synthetic validation

- Objective: run the synthetic acquisition inside the environment.
- Allowed: injected transport only.
- Prohibited: DNS, pip, real indexes, hooks.
- Evidence: `COMPLETE_SYNTHETIC`, `SYNTHETIC_TEST_ONLY`, and the outside swap still failing.
- Pass: synthetic success on the intended object and failure on a substitution attempt.
- Fail closed: a synthetic success on a substitute stops the sequence.
- Approval: separate, even after creation.
- Dependencies: Stage 4.
- Recovery: keep the failed environment for evidence. Do not broaden cleanup.

## Stage 6 — package-source metadata

- Objective: fetch approved metadata only.
- Allowed: the one approved index, if this stage's approval names it.
- Prohibited: wheel bodies, other hosts, broker, database.
- Evidence: request log, certificate result, redirect rejections, size bounds.
- Pass: metadata matches the policy and no unapproved host was contacted.
- Fail closed: any unexpected host or redirect aborts before downloads.
- Approval: source approval plus a metadata-access approval. The proposed PyPI host is not pre-approved.
- Dependencies: Stage 5.
- Recovery: discard partial metadata. Do not install it.

## Stage 7 — real wheel downloads

- Objective: download wheels from the approved artifact host.
- Allowed: that host only, wheels only.
- Prohibited: source distributions, setup.py, PEP 517, installation, extra indexes.
- Evidence: per-file hashes from handles, size bounds, no unapproved requests.
- Pass: every selected wheel verifies.
- Fail closed: one failure publishes nothing.
- Approval: a download approval distinct from metadata approval.
- Dependencies: Stage 6.
- Recovery: do not promote a partial wheelhouse.

## Stage 8 — lock and artifact verification

- Objective: independent verification of the set and the lock.
- Allowed: local reads of the acquired bytes.
- Prohibited: treating the producer manifest as the receiver's measurement.
- Evidence: receiver-built inventory, graph limits still labelled if the target profile is incomplete.
- Pass: receiver and producer agree, and the lock does not claim a broader provenance than the approval.
- Fail closed: mismatch or an incomplete target profile stops packaging.
- Approval: separate verification approval.
- Dependencies: Stage 7 and a complete target profile. The profile is not complete now.
- Recovery: keep the bytes unpublished.

## Stage 9 — export and import

- Objective: move bytes across the boundary and verify again on the far side.
- Allowed: the single approved exit.
- Prohibited: bind mounts of the repository, OneDrive, staging, or production.
- Evidence: the far side's own hashes and a failed attempt to swap the exit.
- Pass: swap is detected or impossible, and hashes match.
- Fail closed: a path open the same user can race is not a pass.
- Approval: separate export approval.
- Dependencies: Stage 8.
- Recovery: do not delete the source copy as a substitute for a failed import.

## Stage 10 — candidate packaging

- Objective: assemble a candidate context that is not the running image and not the 63-file staging tree.
- Allowed: copy of verified wheels into a new candidate context under the import rule.
- Prohibited: editing the production Dockerfile, requirements, dockerignore, or Compose.
- Evidence: candidate file list and hashes.
- Pass: the candidate contains only verified inputs.
- Fail closed: any extra file or packaging edit stops the stage.
- Approval: separate packaging approval.
- Dependencies: Stage 9.
- Recovery: leave the production packaging bytes unchanged.

## Stage 11 — candidate build

- Objective: build a candidate image.
- Allowed: only a Docker build a future prompt explicitly grants, aimed at the candidate, not the running container.
- Prohibited: pull or build against unapproved bases presented as if the digest were known. The registry digest is unknown.
- Evidence: image id and the digest it was built from, recorded by that stage, not invented now.
- Pass: the build uses the verified candidate and a pinned base.
- Fail closed: daemon context still unverified, or any risk to the running container, aborts.
- Approval: Docker build approval. Not granted here.
- Dependencies: Stage 10 and `BASE_IMAGE_DIGEST_UNVERIFIED` cleared by evidence.
- Recovery: do not tag, replace, or delete the running image. `NO_VERIFIED_ROLLBACK_TARGET` still applies.

## Stage 12 — isolated runtime verification

- Objective: start the candidate only in an isolated test that cannot reach OANDA or the live database.
- Allowed: whatever that future prompt narrowly allows.
- Prohibited: the production container, live orders, strategy activation.
- Evidence: no broker route, no live database route, tests of the candidate only.
- Pass: those absences are observed.
- Fail closed: any broker or database reachability stops the stage.
- Approval: separate runtime approval.
- Dependencies: Stage 11.
- Recovery: stop only the candidate, under that approval. Do not restart or stop the production container from this plan.

## Stage 13 — production readiness and rollback

- Objective: decide deployment and rollback with the safety-state, database, and shadow-mount questions still explicit.
- Allowed: a review.
- Prohibited: deployment or rollback from this plan.
- Evidence: cleared or still-open blockers.
- Pass: only if every preserved blocker is cleared by its own evidence. None is cleared now.
- Fail closed: any remaining blocker keeps deployment NO-GO and rollback NO-GO.
- Approval: a production decision that is not this document.
- Dependencies: all earlier stages and the blocker list.
- Recovery: the running system stays as it is.

Gate B is not a hidden stage between these. A Gate B request would be its own approval, and this plan does not grant it.
