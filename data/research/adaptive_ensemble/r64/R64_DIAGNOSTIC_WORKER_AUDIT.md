# R.64 diagnostic worker audit

The question is the R.61 diagnostic worker and the modules it loads. It is not a finding about the rest of the trading application. The worker source was not modified.

## Entry

`diagnostic_worker.main` accepts only `--authenticated-worker` or `--authenticated-worker --harness-transport`. Any other argument returns 2. The supervisor builds that argument vector and starts it with one `subprocess.Popen`. The worker does not start that `Popen`.

## Direct loads

`_load` uses `importlib` with a literal stem and reads `HERE / f"{stem}.py"`. The stems used by the worker are:

| Module | Role | Process or thread creation |
| --- | --- | --- |
| `credential_ipc` | Parse one stdin frame. Imports `json` and `re` | None in the module |
| `live_session_gate` | Gate is `REAL_SESSION_SOURCE_ENABLEMENT = False`. Imports `hashlib`, `hmac`, `secrets`, `time` | None in the module |
| `restricted_live_transport` | One logical GET. Imports `json`, `re`, `time` | No `subprocess`. The harness object is an injected document. `http.client` is imported only inside the branch where `connection is None` |
| `metadata_extract` | Parse a document. Imports `re` | None |

`one_session_activation` and `real_session_entry` are not loaded by the worker.

## Execution path

Harness mode replaces `http.client.HTTPSConnection` and `HTTPConnection` with a function that raises. It then reads one frame, writes one ready line, reads `CAP_OK`, and calls `RestrictedLiveTransport.get_instruments` with a `HarnessConnection`. That path does not open a socket and does not create a process.

Non-harness mode calls `assert_real_session()` first. With the gate false, that raises `REAL_OANDA_SESSION_NOT_AUTHORISED` and the worker emits a failure and returns 2. The `connection is None` branch, which constructs `HTTPSConnection`, is not reached.

Stall names in the worker are `time.sleep` or `os._exit`. They do not spawn.

The worker writes one result to stdout and closes stdin. Those are the pipes the supervisor created. They are not extra processes.

The supervisor's daemon threads for the IPC write and the ready read run in the parent. They are not children of the worker. `threading` does not appear in the worker.

Searches of the worker and the four loaded modules found no `subprocess`, `multiprocessing`, `os.fork`, `os.system`, `Popen`, or `Thread(`. The existing R.61 test also asserts the worker source does not contain `Popen`. That assertion was not changed.

## Classifications

| Finding | Class |
| --- | --- |
| Worker source has no process or thread spawn | `DIRECTLY_VERIFIED` |
| The four loaded modules' source has no process spawn | `DIRECTLY_VERIFIED` |
| Harness transport uses an injected document | `DIRECTLY_VERIFIED` |
| Real HTTPS branch is behind the disabled gate | `STATICALLY_SUPPORTED` |
| A future edit, or a library imported later, could spawn | `POTENTIAL_DYNAMIC_BEHAVIOUR` |
| Runtime trace of a worker under a delegated cgroup | `NOT_VERIFIED` |
| The production trading bot's process tree | `NOT_VERIFIED` |

`HTTPSConnection` is an in-process socket when that branch runs. It is not a child process. This stage did not execute it. `REAL_NETWORK_EXECUTION_NOT_TESTED`.

## Decision

`DIRECT_CHILD_CONTAINMENT_SUFFICIENT_FOR_CURRENT_VERIFIED_WORKER`

The supervisor needs to own the one process it creates. Nothing in the current worker path creates a grandchild that direct-child termination would leave behind.

Assumptions:

- The worker keeps loading only those literal module names.
- Those modules, and the standard-library calls they contain, do not grow a `subprocess`, `multiprocessing`, `fork`, or shell invocation.
- The real gate stays off, or a future authorised real path still uses in-process HTTP rather than an external binary.
- "Current verified worker" means this R.61 file set, not a later strategy runner.

The conclusion becomes false if any of those change, if the IPC frame can choose a module path, or if this worker is reused as a host for trading code. It says nothing about other bot components.

The default lifecycle policy remains strict descendant containment. This audit is the documented reason a caller may explicitly select the reduced policy for this worker. It is not a silent downgrade.

`R64_WORKER_REQUIREMENTS_ASSESSED`
