# R.65 duplication audit

No duplicate is reachable from `main.py` at the same time as another copy. No operational merge was made.

## Findings

| Candidate | Class | Evidence | Action |
| --- | --- | --- | --- |
| R.59, R.60, and R.61 `diagnostic_supervisor.py` | `HISTORICAL_RESEARCH_COPY` | Same role, three directories, three test modules. R.61 adds the pre-`Popen` deadline check and untracked-process retention. Call sites are each directory's own tests. `forex_bot` has no import | `NO_CHANGE_REQUIRED` |
| R.59–R.61 worker, gate, transport, IPC, metadata | `HISTORICAL_RESEARCH_COPY` | Parallel files. Hashes differ. Each suite loads its neighbour by path | `HISTORICAL_DUPLICATION` |
| R.62 Windows job versus R.63 creation-time job | `HISTORICAL_RESEARCH_COPY` | R.63 replaces assign-after-create for the experiment. R.62 remains the evidence of the older gap. Neither is imported by the bot | `NO_CHANGE_REQUIRED` |
| R.62 and R.63 Linux park/pidfd | `FUNCTIONAL_OVERLAP` | Both park on a pipe and use pidfd. R.63 adds an explicit strict-policy refusal and parent-death signal. Separate packages | `NO_CHANGE_REQUIRED` |
| R.63 Windows and Linux backends | `INTENTIONAL_PLATFORM_BACKEND` | `lifecycle_contract._backend` imports one module. Policy fields are shared. Mechanisms are not | `NO_CHANGE_REQUIRED` |
| R.63 `ProcessLifecycleManager` and R.64 `strict_open` | `FUNCTIONAL_OVERLAP` | Both refuse strict Linux containment when no private cgroup exists. R.64 does not import R.63. R.64's host test also requires errno 13 | `REQUIRED_CORRECTION` in new R.65 code only. Do not merge the backends |
| R.64 `test_this_host_denies_a_private_child_cgroup` expects `MKDIR_ERRNO_13` | `POTENTIAL_CONFLICT` | This WSL2 host returns errno 13, so the archived test passes here. An independent run returned errno 30 (`EROFS`). Both are creation failures. The archived assertion treats them as different test results | Portable classifier in R.65. The R.64 test stays as the historical host record |
| `forex_bot` thread locks and the diagnostic supervisor's IPC threads | `NOT_DUPLICATE` | Locks and alert threads are in-process. The supervisor's threads belong to the research parent. No shared call site | `NO_CHANGE_REQUIRED` |
| `g4_integrity` git subprocess and diagnostic `Popen` | `NOT_DUPLICATE` | One reads a git revision for research. The other starts a diagnostic worker in a research test | `NO_CHANGE_REQUIRED` |

## Policy disagreement, not a live conflict

R.61 will `Popen` a worker with no descendant domain. R.63 and R.64 default to refusing a worker when descendant containment cannot be armed. Those policies are not installed together. The live bot uses neither. Class: `POTENTIAL_CONFLICT` if a later stage imports both into one process. It is not `CONFIRMED_RUNTIME_CONFLICT`.

Exit verification also differs on paper. R.61 uses `poll` and `wait`. R.63 uses a process handle or `waitpid` and will not treat the kill call itself as success. R.64's simulated table says the same. No operational function consults both.

## Not done

No function was deleted or merged. Optional cleanup of the historical copies is `OPTIONAL_REFACTOR` and was not implemented.

`R65_DUPLICATION_CLASSIFIED`
