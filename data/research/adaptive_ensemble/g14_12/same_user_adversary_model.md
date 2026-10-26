# Same-user adversary model

The adversary retained from G.14.8 may run a medium-integrity process as `nucbox_m5plus\brian` (`S-1-5-21-1451533663-3497457457-3930589332-1001`). This stage observed that token. It is not elevated. Administrators is present as deny-only. Whether the account can elevate is unknown and was not tested.

That adversary may create, rename, and replace objects where the token has permission, create reparse points where it has permission, attempt ACL and owner changes, substitute programs and configuration where it can write, create a competing pipe, and race checks against opens. G.14.8 showed the rename works against a directory this user owns, without elevation.

## Boundaries

A. Observed medium-integrity same-user attacker. The contract is written to stop this attacker by denying write and control on the receiver chain and by refusing sender paths. That denial is not measured. This is the only class the design tries to cover with a future test.

B. Other unprivileged users. They are stopped only if the effective DACL denies them the same rights. No other account was enumerated. No DACL was read. Coverage is a requirement, not a result.

C. Elevated administrators. Not claimed. This includes this account if it elevates later. No evidence says elevation is impossible.

D. A compromised host. Not claimed.

E. A compromised receiving principal. Not claimed. The owner of the directory can change its DACL. The contract does not pretend otherwise.

Protected paths do not stay protected if any ancestor is replaceable. The ancestor contract exists so that case fails closed instead of being assumed away. A different SID is not, by itself, isolation.
