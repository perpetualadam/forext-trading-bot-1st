# SUPERVISOR AND DISPOSABLE WORKER

The supervisor owns the stage clock, the operation clock, request and byte counters, worker start, graceful stop request, forced termination, exit confirmation, and the sanitised ledger.

The worker runs one allowlisted synthetic mode. It can sleep, exit, raise, or write bounded fixture data. It cannot resolve a name, open a socket, or import the trading application.

A timed wait is not treated as cancellation. After the deadline, the supervisor writes a stop file, waits briefly, and then calls terminate if the worker is still alive. Exit is confirmed only when poll reports an exit code.

On Windows, terminate ends that process. It does not by itself end descendants. This stage does not spawn descendants and does not claim process-tree containment.
