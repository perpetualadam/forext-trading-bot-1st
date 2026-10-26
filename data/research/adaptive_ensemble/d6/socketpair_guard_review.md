# Stage D.6 socketpair guard review

Both the D.5 runner and the D.6 runner replace `socket.socketpair`. `socket.socket.connect` has no allow-list. Every `connect`, including `127.0.0.1`, raises.

The replacement `socketpair` binds `127.0.0.1` or `::1` on port 0 and calls the original `connect` only for that just-bound address. The listening socket is closed before the function returns. A later `connect` to the same port still goes through the denied `connect` wrapper. The D.6 self-check did that and received `RuntimeError`.

Checked in the D.6 child, before lifespan:

- `connect(("127.0.0.1", 5432))` denied.
- `connect(("203.0.113.1", 9))` denied.
- `getaddrinfo("api-fxpractice.oanda.com", 443)` denied. The D.6 runner adds this DNS denial. The D.5 runner does not wrap `getaddrinfo`. That does not make the D.5 socketpair exception broader. It is a separate D.5 gap, closed in the D.6 harness rather than by editing D.5.
- A connect to the port created by `socketpair` was denied.
- External HTTP verbs on the fake `requests` module raise.
- `urlopen` and `asyncio.open_connection` raise.
- Broker and database clients in the lifespan run were fakes. `psycopg2.connect` did not open a TCP socket.

The wrapper exists only in the child process. The parent test asserts that its own `socket.socket.connect` is not `blocked_connect`.

The socketpair exception is not broader than the event-loop self-pipe. `D6_NETWORK_ISOLATION_BLOCKED` was not used.
