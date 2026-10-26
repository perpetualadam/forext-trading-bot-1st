# R.83 coverage equivalence

| Area | Class | Basis |
| --- | --- | --- |
| Entry commit then publication failure | STRONGER_COVERAGE | Exception and process kill are separate tests, plus a real successor |
| Close commit then removal failure | STRONGER_COVERAGE | Exception, process kill, stale owner, and conflicting snapshot are separate |
| Partial 400/1000 restart | EQUIVALENT_COVERAGE | Same remainder and quarantine as R.82, now also after a kill |
| Production WAL `SQLITE_BUSY` on the authority SELECT | MISSING_COVERAGE | Not reproduced. Rollback-mode SELECT is a different journal mode |
| `SQLITE_LOCKED` on the authority SELECT | MISSING_COVERAGE | Reproduced only on shared-cache `BEGIN IMMEDIATE` |
| Injected authority-read faults | EQUIVALENT_COVERAGE | Both sinks, both injected messages, zero writes |
| Negative closed units | EQUIVALENT_COVERAGE | R.82 rejection re-audited and retested. Not reversed |
| Positive closed units | EQUIVALENT_COVERAGE | 400, 999, 1000, zero, overfill, decimal, SELL, USD_JPY |
| R.82–R.78 suites | EQUIVALENT_COVERAGE | Same pass counts |
| R.77–R.68 historical failures | EQUIVALENT_COVERAGE | Same fail, error, and skip counts |
| Kill after a completed memory publication or completed removal | PARTIAL_COVERAGE | The durable row is already committed. A separate kill after the memory step finished was not added |
| Broker idempotency | MISSING_COVERAGE | Synthetic requests cannot prove it |
| Power loss | MISSING_COVERAGE | Process kill is not a power cut |
