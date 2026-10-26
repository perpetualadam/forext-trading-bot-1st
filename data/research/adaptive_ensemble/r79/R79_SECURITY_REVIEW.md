# R.79 Security Review

Evidence class: source review and the isolation probes. This is not a production penetration test.

| Control | Status |
| --- | --- |
| Source enablement gates | Still false. Four gate-file hashes unchanged. |
| Live permit | Not created. |
| Consumed marker | Hash unchanged. Contents not printed. |
| Credential reads | Isolation refuses `.env` and credential-named opens. Tests did not read them. |
| OANDA | No practice or live request. Synthetic adapter only. |
| PostgreSQL | Connect path raises `IsolationBreach` under the harness. |
| Production SQLite | Not opened. Temporary journals only. |
| Operational publication | Fails closed without a current epoch and an active or completed recovery session. |
| Broker writes | OrderCreate and PositionClose check recovery authority before consuming a one-shot permit. |
| Offline reconstruction | Cannot grant `live_management_permitted()`. |
| Stale owner | Cannot publish or manage. |
| Automatic retry | Not added for ambiguous entry or close. |
| Automatic takeover | Not added. No lease expiry. |

The residual risk is the time between the authority check and `api.request`. Isolation during tests is not a production network control. A process that imports the operational modules without the harness can still construct an API client if a token is present. This stage did not place a token in the environment.

Paper `open_position` can still put a non-broker row in memory without a fencing epoch. That row is not a broker position and does not pass the OrderCreate guard.
