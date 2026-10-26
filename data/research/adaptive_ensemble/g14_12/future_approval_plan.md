# Future approval plan

No row below is authorised. Nothing carries forward. Nothing authorises live trading.

## A. Contract defect remediation

Objective: write any remaining design holes. This stage already wrote the ancestor, executable, pipe-order, fail-closed maximum, and publication-handle rules.
Preconditions: baseline and staging still match.
Permitted: research documents under a new stage directory.
Prohibited: code, accounts, ACLs, pipes, Docker, network.
Evidence: a matrix with no DESIGN_UNSATISFIED criterion.
Pass: the text states the rule. Fail closed: an unstated critical hole.
Approval: a later prompt. Production: none. Recovery: do not delete prior artifacts.

## B. Operator acceptance of the security contract

Objective: an explicit human acceptance of the design text, including the limit to threats A and B.
Preconditions: A complete.
Permitted: a recorded decision.
Prohibited: treating acceptance as implementation approval.
Evidence: the decision text.
Pass: acceptance names the limits. Fail closed: silence.
Approval: operator. Production: none.

## C. Read-only inspection of one named existing principal or path

Objective: only if a later prompt names one non-secret account or path.
Preconditions: B, and a single named target.
Permitted: read-only owner and DACL of that target.
Prohibited: user-database dumps, credential paths, production mounts, ACL writes.
Evidence: effective access of the interactive medium token.
Pass: the token lacks the denied rights, or the target is rejected.
Fail closed: unknown access.
Approval: separate. Production: none.
This stage found no target, so C has nothing to inspect until a prompt names one.

## D. Account and ACL creation

Objective: create the dedicated non-administrator principal and the directory chain only if C found no existing fit and the operator explicitly approves creation.
Preconditions: C complete or explicitly skipped because no candidate exists, plus a written creation approval.
Permitted: the named account and the named directory ACLs.
Prohibited: Administrators membership, LocalSystem, production paths, this user's temp.
Evidence: SID, owner, effective access, failed medium-integrity rename.
Pass: the rename fails and no file appears in a substitute. Fail closed: any success of the swap.
Approval: separate and explicit. Production: none.
Recovery: do not delete production. Account removal is a later decision, not an automatic cleanup.

## E. Synthetic receiver implementation

Objective: a receiver that has no path parameter.
Preconditions: D passed.
Permitted: code that reads bytes and writes only under the receiver handle.
Prohibited: production edits, staging edits, Docker.
Evidence: code review plus the tests in F through J.
Pass: no path fallback. Fail closed: any path open of a sender directory.
Approval: separate. Production: none.

## F. Same-user substitution tests

Objective: rerun the G.14.8 swap against the receiver chain on nonproduction resources.
Preconditions: E.
Permitted: nonproduction directories the approval names.
Prohibited: production, staging deletion, the two backup files.
Evidence: swap fails.
Pass: substitute receives nothing. Fail closed: workflow completes on the substitute.
Approval: separate. Production: none.

## G. IPC authentication tests

Objective: squatting, wrong client, wrong server, impersonation absent.
Preconditions: E and a pipe approval.
Permitted: a local pipe in the approved test.
Prohibited: listening on a production name or a network port.
Evidence: scenarios O through S.
Pass: no file on failure. Fail closed: bytes stored before SID checks.
Approval: separate. Production: none.

## H. Transfer limits and crash tests

Objective: unconfigured maximum refuses; partial frames leave no commit.
Preconditions: G.
Permitted: synthetic bytes.
Prohibited: downloads.
Evidence: scenarios T through AE.
Pass: no commit. Fail closed: a commit after a short read.
Approval: separate. Production: none.

## I. Publication and mutation tests

Objective: re-read mismatch and path reopen fail.
Preconditions: H.
Permitted: synthetic files under the receiver handle.
Prohibited: publishing into the repository.
Evidence: scenarios AK through AN.
Pass: consumer receives nothing on mismatch. Fail closed: a path reopen counted as success.
Approval: separate. Production: none.

## J. Consumer verification tests

Objective: consumer re-hashes and rejects a synthetic lock.
Preconditions: I.
Permitted: a consumer that reads the pipe.
Prohibited: Docker, staging modification.
Evidence: scenarios AP through AR.
Pass: mismatch fails. Fail closed: consumer trusts the sender manifest alone.
Approval: separate. Production: none.

## K through T

K acquisition environment design, L its creation, M offline synthetic acquisition, N package-source metadata, O wheel downloads, P lock verification, Q candidate packaging, R candidate Docker build, S isolated runtime, T production safety and rollback review.

Each keeps its own approval. None is granted here. N and O need network approval, which is not granted. R needs Docker approval, which is not granted. T does not change live-order authorisation.

Next recommended stage is not D and not E. It is B only if an operator wants to accept this text. Until then, no account and no receiver.
