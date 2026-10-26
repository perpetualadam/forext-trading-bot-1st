# Stage D.6 subprocess isolation review

The child environment is constructed. It is not a copy of the parent environment. Token and password variables are empty strings. `POSTGRES_HOST` is `d6-invalid-host`. `LIVE_SAFETY_STATE_PATH` and `D6_WORK_DIR` are under the pytest temporary directory.

The child removes the foreign project path before importing `forex_bot`. The working directory is the temporary directory. `subprocess.run` uses `timeout=180`. On timeout, Python kills that child. The child is not a production process.

Guards are installed inside the child only. The parent assertion checks that the parent's `socket.socket.connect` was not replaced.

A subprocess alone is not the boundary. The boundary is the combination of the synthetic environment, the pre-import fakes, the socket and DNS denials, and the path denials. Those checks passed in the child before fault injection. The passing runs recorded an empty network list and an empty filesystem-denial list after the intentional probes were cleared.

`D6_SUBPROCESS_ISOLATION_BLOCKED` was not used.
