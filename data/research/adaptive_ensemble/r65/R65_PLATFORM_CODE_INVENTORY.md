# R.65 platform code inventory

The operational trading process and the research process experiments are separate trees. Nothing in `main.py` or `forex_bot` imports R.62, R.63, or R.64.

`RESEARCH_IMPLEMENTATIONS_NOT_INTEGRATED`

## Operational entry

| Path | Role | Platform process APIs | Reachable from `main.py` |
| --- | --- | --- | --- |
| `main.py` | Starts uvicorn on `forex_bot.app:app` | None | Yes |
| `forex_bot/app.py` | HTTP app. Imports `run_bot` from `bot_loop` | None in the import scan | Yes |
| `forex_bot/bot_loop.py` | Trading loop. Record-only calls into `v2_shadow` | No `Popen`, `fork`, or `sys.platform` | Yes |
| `forex_bot/execution_risk.py`, `live_safety.py`, `decision_repair/*.py`, `database.py`, `oanda_rate_limit.py`, `telegram_*.py`, `alerts.py` | Locks and, for alerts and Telegram, in-process threads | `threading`. No child-process containment | Yes, through the app and loop |
| `forex_bot/v2_shadow/market.py`, `store.py` | File locks for shadow records | `threading.Lock` | Yes, from `bot_loop`, as record-only |
| `forex_bot/shadow/manifest.py` | Reads `git rev-parse` | `subprocess.check_output` | Not referenced by `bot_loop` in this scan |
| `forex_bot/research/adaptive_ensemble/g4_integrity.py` | Git baseline for research audits | `subprocess.check_output(["git", ...])` | No. Used by the `g4`–`g10` research scripts |
| `forex_bot/research/adaptive_ensemble/g10_audit.py` | On Windows, `GetFileAttributesW` to detect a reparse point. Other platforms return false | `os.name != "nt"` guards `ctypes.windll` | No |

Trading logic was not found to branch on job objects, cgroups, pidfd, or POSIX kill. The Windows reparse check is inside a research scanner and is not on the order path. Whether every future helper stays off that path is `NOT_VERIFIED` beyond this import scan.

## Diagnostic research copies

These are successive offline copies. Each test loads its own directory by path. They are not imported by `forex_bot`.

| Path | Main operations | OS | Runtime |
| --- | --- | --- | --- |
| `r59/diagnostic_supervisor.py` | `Popen`, pipe IPC, deadline, cleanup | Windows and Linux, with the known Linux `communicate` flush defect left in this copy | Research tests only |
| `r60/diagnostic_supervisor.py` | Same contract. Stdin is closed only after exit. Cleanup closes the read ends | Both | Research tests only |
| `r61/diagnostic_supervisor.py` | Deadline re-checked immediately before `Popen`. Untracked `Popen` is retained for cleanup | Both. No job and no cgroup | Research tests only |
| `r61/diagnostic_worker.py` | One metadata exchange. Literal `importlib` loads of four siblings | Both | Started only by the R.61 supervisor in tests |
| `r56/phase6_connection_enablement/diagnostic_supervisor.py` and `diagnostic_worker.py` | Earlier phase-6 copies | Both | Research tests only |
| `r56/phase5_connection/session_supervisor.py`, `isolated_worker.py` | Earlier isolated session experiment | Both | Research tests only |

R.59, R.60, and R.61 agree that the gate is false. They disagree on cleanup details because each stage fixed the previous copy and left the old files in place. That disagreement is historical, not two managers in one process.

## Containment experiments

| Path | Main types | Purpose | OS | Operational import |
| --- | --- | --- | --- | --- |
| `r62/poc/win_containment.py` | `launch`, `Session` | Suspended `CreateProcess`, assign, then resume, kill-on-close | Windows | No |
| `r62/poc/linux_containment.py` | `launch`, `cgroup_probe` | Park before exec, pidfd. Cgroup probe expected to fail | Linux | No |
| `r63/poc/lifecycle_contract.py` | `ProcessLifecycleManager` | Shared policy. Selects a backend with `sys.platform` inside the call | Both, one backend per process | No |
| `r63/poc/windows_backend.py` | `create`, `establish`, `start` | Creation-time `PROC_THREAD_ATTRIBUTE_JOB_LIST` | Windows. Import raises on other platforms | No |
| `r63/poc/linux_backend.py` | `create`, `probe` | Park, pidfd, parent-death signal. Refuses strict mode without a cgroup | Linux | No |
| `r63/poc/capability_probe.py` | `probe_capabilities` | Imports only the backend for the current platform | Both | No |
| `r64/poc/cgroup_probe.py` | `probe_host` | Read-only mkdir. Records errno. Does not write `cgroup.kill` | Linux probe. Other platforms return unavailable | No |
| `r64/poc/cgroup_lifecycle.py` | `strict_open`, `simulate`, `run_contained` | Strict open returns before `fork` when delegation is false. `run_contained` was not entered on the tested host | Linux for the kernel path | No |

Overlaps among R.62, R.63, and R.64 are intentional generations. They are not competing routers in the bot.

## What this inventory does not claim

`NOT_VERIFIED` for every file under the 728 Python paths beyond the entry graph, the `forex_bot` process-API scan, and the R.56–R.64 diagnostic and containment modules. A dynamic import whose module name is built from configuration outside those trees was not found on the worker path. The worker's `importlib` stems are literals.

`R65_REPOSITORY_AUDIT_COMPLETE` for the operational entry graph and the process-lifecycle research trees named above. It is not a claim that every unrelated research note was executed.
