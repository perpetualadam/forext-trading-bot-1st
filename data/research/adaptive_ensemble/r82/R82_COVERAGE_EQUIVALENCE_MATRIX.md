# R.82 coverage equivalence

| Older failing area | R.82 coverage | Class |
| --- | --- | --- |
| R.77 fencing-era publication failures | `test_14` restarts ambiguous entry and close under a real startup. It does not rewrite the old assertions | `STRONGER_COVERAGE` for restart ambiguity. The old tests remain failed |
| R.76 entry identity failures | Not re-implemented. R.81 entry finalisation still passes inside the 16-test suite | `PARTIAL_COVERAGE` |
| R.75 guard failures | Current sinks still refuse without a permit. Covered by `test_02` and `test_03` | `PARTIAL_COVERAGE` |
| R.74 operational closes without authority | `test_03` and `test_05` refuse the close. Old tests remain failed | `STRONGER_COVERAGE` for the authority check. Old expectations remain obsolete |
| R.73 close-evidence shape failures | `test_16` and `test_18` cover partial, full, reject, zero, overfill, and identity mismatch on the current classifier | `STRONGER_COVERAGE` for the current function. Old tests remain failed |
| R.72 single failure | Not changed. Profit-protection file hash is unchanged | `PARTIAL_COVERAGE` |
| R.70 snapshot failure | `test_17` covers remaining, original, empty, wrong identity, missing, and incomplete snapshots for a partial close | `STRONGER_COVERAGE` for that restart. The old failure remains |
| R.69 and R.68 failures | Not rewritten. Isolation is still imported first | `PARTIAL_COVERAGE` |
| One-shot permits, client-id retention, ambiguous blocking, owner liveness | Preserved by the passing R.81 suite plus `test_08`, `test_12`, `test_14`, and `test_18` | `EQUIVALENT_COVERAGE` where R.81 already passed; `STRONGER_COVERAGE` for journal loss after the rate-limit slot |

`MISSING_COVERAGE`: a fault injected only after a successful durable entry or close commit and before the memory publication step. `test_13` covers the opposite order, where the confirmation commit fails and memory is not allowed to remove the position.
