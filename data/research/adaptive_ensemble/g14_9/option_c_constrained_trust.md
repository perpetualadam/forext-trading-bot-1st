# Option C — explicitly constrained trust model

Classification: `TRUST_ANCHOR_ASSUMPTION_ONLY`

This option does not fix the G.14.8 result. It would state that the result is outside the accepted model. That is a risk acceptance, not a boundary.

## The model, stated without softening

Trusted actors would be this Windows user and every process that can act as this user, including any process that can rename a directory the user owns.

Untrusted actors would be other local users, remote network clients, and package authors. Elevated administrators and a fully compromised host would stay outside the claim, as they do for every option.

Trusted paths would be whatever directory the operator passed, for the interval between the operator's choice and `CreateFileW`, plus every parent component of that path.

Untrusted paths would be the repository, OneDrive, the Consensus Forecast tree, the 63-file staging directory, Docker volume paths, shadow and operational state paths, and the two sensitive backup filenames. The existing `assert_destination_boundary` denylist already names those. A denylist is not a lock against a same-user rename.

## Comparison with the demonstration

G.14.8 cases 1, 2, and 3 used a same-user rename. The open returned the substitute. The child was created there. No administrator was involved.

Option C excludes that actor by defining the user as trusted. The demonstrated vulnerability remains in the code. A real download under this model could complete on a directory another process of the same user substituted, and the synthetic success state shows the workflow does not notice.

Calling that exclusion a verified filesystem boundary would be false. `FILESYSTEM_TRUST_BOUNDARY_UNVERIFIED` remains.

## Why exclusion is not acceptable for later downloads

The attacker does not need malware in another account. Any process running as this user can perform the swap the test performed. That includes a compromised user-mode program, a raced cleanup, or a second copy of the tool. During a real download the window includes the time spent on network reads, which is longer than the offline test.

ACLs were not shown to stop this. G.14.8 recorded `ACL_RESTRICTION_NOT_APPLICABLE` for the same user, because that user can change a discretionary ACL on an object the user owns. The DACL bytes themselves were not read (`ACL_RESTRICTION_UNVERIFIED`).

There is no independent evidence that the user is the only actor in the session. The assumption would have to be re-accepted for every real download. It would not become true because a download is authorised.

## Residual risk the operator would have to accept

- Pre-open substitution of the parent.
- Creation of the wheelhouse and lock in the substitute.
- A success marker that refers to the opened object, not the intended path.
- Junctions are rejected when they are the opened object. Symlinks were not executed. Other reparse tags were not enumerated.
- Package contents would still need the existing verifier, which does not repair the directory choice.
- Host compromise and administrators remain out of scope, in addition to the same-user attacker this model would drop.

## Operator acceptance

Acceptance would have to be an explicit statement that same-user path substitution is an accepted residual risk, that the G.14.8 test is not considered fixed, and that a later success result is not evidence of directory identity. This stage does not record that acceptance. It does not recommend that the operator sign it in order to avoid building an isolated environment.

## What this option would preserve

The G.14.7 verifier and the G.14.1 staging tree could stay unchanged. No Docker, network, or production packaging change is required. That smaller scope is not a security advantage. The mandatory condition is containment of the demonstrated substitution. This option fails it by definition.

## Classification

`TRUST_ANCHOR_ASSUMPTION_ONLY`

The option is ineligible as a filesystem trust boundary.
