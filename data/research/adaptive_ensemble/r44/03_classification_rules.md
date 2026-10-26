# R.44 evidence classification rules

Each claim uses one label:

| Label | Meaning |
| --- | --- |
| `LOCALLY_VERIFIED_IMPLEMENTATION` | The current source or a prior offline test shows what this repository does. |
| `DOCUMENTED_BUT_ACCOUNT_UNVERIFIED` | A library example, code comment, or past research note describes a broker concept. It was not checked against this account. |
| `SYNTHETIC_TEST_ONLY` | A fixture exercised the code. The fixture is not this account. |
| `ASSUMPTION_ONLY` | A default, fallback, or paper table. It is not a broker term. |
| `UNKNOWN` | No approved local evidence answers the claim. |
| `CONFLICTING_EVIDENCE` | Approved local sources disagree. The disagreement is left visible. |

`ACCOUNT_VERIFIED` is not used. No authorised non-secret account record was in scope.

A code default is not a confirmed contract term. A synthetic account id, currency, or balance is not this account. A public or library description of a field does not prove this account returns that field.
