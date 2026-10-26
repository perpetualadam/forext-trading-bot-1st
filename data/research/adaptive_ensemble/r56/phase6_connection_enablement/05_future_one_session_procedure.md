# Future one-session procedure

This is not authorised now. Do not treat the synthetic screen, the harness connection, or schema `r56.phase6.ipc.2` as permission to connect.

A later written instruction would have to name OANDA Live and only these two reads:

1. `GET https://api-fxtrade.oanda.com/v3/accounts/{accountID}/summary`
2. `GET https://api-fxtrade.oanda.com/v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`

Only after that instruction would `REAL_SESSION_SOURCE_ENABLEMENT` be changed in source, and only after a separate instruction would `prepare_one_session.py` be run once to create the permit. The operator command from the project root is `python -B data\research\adaptive_ensemble\r56\phase6_connection_enablement\real_session_entry.py` with no arguments. It calls `run_real_session`, shows the host and the two GET paths, accepts one fresh confirmation receipt, consumes the permit, and only then prompts for the account id and the hidden token. The permit is spent even if the process is then interrupted. A second launch fails. The local file does not stop someone who can write the directory. The parent then launches `diagnostic_worker.py --authenticated-worker` with no harness flag, sends IPC mode `REAL_SESSION`, and issues one `REAL_SESSION` capability per step. The worker accepts the connection only after the parent redeems that capability. A phrase inside the worker cannot mint it. `--harness-transport` cannot mint it either. Neither an environment variable nor a hidden command-line flag can turn the source switch on. A parent capability does not replace process isolation or OANDA authentication.

The account id would have to match `^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$` and would be carried with the token on one stdin frame. The offline worker would not be the process that opens the socket, because that worker seals the network. The authenticated worker would have to omit the seal and still refuse every URL, host, method, and endpoint outside the two GETs. Those prompts and that worker are not enabled here.

The parent would keep the 5 second and 15 second deadlines and kill a child that ignores them. Raw responses would be reduced, then scanned for the exact account id and token, and not stored. The production bot would stay stopped.

Practice orders, live orders, and production deployment are outside that instruction as well. Stopping the child cannot retract a GET OANDA has already received. Application allowlisting does not stop a compromised child that ignores the transport and opens its own socket.
