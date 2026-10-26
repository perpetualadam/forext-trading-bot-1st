# R.79 Isolation Harness Validation

Evidence class: executed probes inside `test_09_schema_and_isolation_probes` and the harness setup. The same test passed on Windows and Linux.

The harness imports `data/research/adaptive_ensemble/r69/poc/isolation.py` before `forex_bot`. That module scrubs environment names containing credential markers, stubs `load_dotenv`, installs a synthetic config, blocks non-loopback sockets, blocks `urllib.request.urlopen`, blocks `.env` and permit opens, and replaces `psycopg2.connect`.

| Probe | Result |
| --- | --- |
| `socket.create_connection(("203.0.113.5", 9))` | `IsolationBreach`. Address is documentation TEST-NET, not an OANDA host. |
| OrderCreate after recovery authority | Intercepted. The synthetic `request` raises. The test expects the exception. No write succeeds. |
| PositionClose without recovery authority | `CloseGuardRefusal` before `request`. |
| PositionClose with recovery authority | One synthetic PositionClose, then a stale permit is refused. |
| PostgreSQL | `psycopg2.connect` is replaced and raises `IsolationBreach`. No test called a real server. |
| Credential and `.env` reads | The open guard refuses those names. Tests did not read them. |
| Permit creation | `one_session.permit` remained absent after the suite. |
| Production journal | Every test journal is a `TemporaryDirectory` file. Linux used `/tmp`. |
| Unrestricted loop | The harness calls `run_startup_and_one_iteration`. It does not call `run_bot` or `main.py`. |

The cycle wrapper increments a counter and then awaits the original `_execute_bot_cycle`. It does not replace the function body. `state_dict["last_bot_cycle_utc"]` is set only by the original function.

Account summary reads returned a synthetic body that the operational parser rejected as `broker_unrealised_missing`. That is a read of the fixture, not a broker write. Candle acquisition then skipped with `decision_candles_missing`.
