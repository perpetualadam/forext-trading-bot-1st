# D.7 test isolation review

`tests/d7_resource_cleanup_runner.py` is a separate harness. It does not import or modify the D.5 or D.6 runners.

Before `forex_bot.app` or `forex_bot.database` is imported, the child installs:

- a fake `dotenv.load_dotenv` that does not open a file
- a fake `requests` that records and raises
- a fake `psycopg2.connect`
- denial of `socket.connect`, `socket.connect_ex`, `socket.create_connection`, `socket.getaddrinfo`, `urllib.request.urlopen`, and `asyncio.open_connection`
- a `socket.socketpair` replacement that binds `127.0.0.1` or `::1` port 0 and uses the original connect only for that just-bound address
- denial of `open`, `os.open`, `os.replace`, `os.rename`, `os.remove`, `os.unlink`, `shutil.move`, `shutil.copy2`, and `shutil.rmtree` for `.env`, `credential`, `data/ops`, and `v2_shadow`

The self-check confirmed localhost port 5432, an external address, DNS for `api-fxpractice.oanda.com`, the self-pipe port, and the filesystem probes are denied. Those probe denials were cleared before lifespan. Later network and filesystem denial lists were empty.

The child environment is synthetic. `PYTHONPATH` is the repository only. The foreign project path is removed. The working directory is a temporary directory. `LIVE_SAFETY_STATE_PATH` points at a temporary file.

Lifespan mode leaves the real `get_connection` in place and replaces broker, order-loading, reconciliation, alert, and the four background coroutines. Order-routing callables on `oanda_exec` raise if reached. Repair mode does not wrap those callables, so the existing live-order gate tests still reach the real authorisation check.

Snapshots of connection close counts, held globals, pending tasks, and cleanup errors are taken before the harness cancels leftover tasks or closes leftover fakes. Fatal startup cases observed application close counts of 1 and harness close counts of 0. The successful baseline observed an application close count of 0 and a harness close count of 1, matching the decision to keep the published connection open.
