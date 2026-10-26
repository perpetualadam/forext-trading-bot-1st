# Windows asyncio isolation

R.2's four failures came from `asyncio.run` on Windows. The loop class in that traceback was `ProactorEventLoop` (`asyncio/windows_events.py` and `proactor_events.py`). It builds a self-pipe with `socket.socketpair()`. On this Python, that falls back to `socket.socket(AF_INET, SOCK_STREAM)` in `socket.py`. The R.2 barrier raised before the operating system created the socket. The order function was never called.

That pipe is local. It is still an AF_INET socket. Allowing AF_INET, AF_INET6, or every localhost connection would also allow a later test to reuse the same hole. That exception was not added.

The order classification, reservation, direction lines, and strategy setter do not need an event loop. They were tested synchronously. The async paper-order tests were not run.

Verdict: `ASYNC_ISOLATION_NOT_PROVEN` for running those async tests. A blocked test is the result that was kept.

During the R.3 import of the order module, urllib3 tried `socket.socket(AF_INET6)` to see if IPv6 exists (`urllib3/util/connection.py`, `_has_ipv6("::1")`). The barrier raised inside the socket constructor. urllib3 caught that error and continued. No operating-system socket was created and no host was contacted.
