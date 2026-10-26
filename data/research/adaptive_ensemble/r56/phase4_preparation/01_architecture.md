# R.56 Phase 4 architecture

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

The fixed host constant is `api-fxtrade.oanda.com` port `443`. That name is the OANDA live environment. This phase does not resolve it and does not connect to it. The host cannot be replaced by a caller, and the practice host is rejected by the Phase 3 gate.

## Modules

All new code is under `data/research/adaptive_ensemble/r56/phase4_preparation/`.

| Module | Role |
| --- | --- |
| `https_transport_candidate.py` | Offline transport. Accepts only an `OfflineDouble`. GET, HTTPS, fixed host and port, Phase 3 path and query shape, no body, no redirect, no retry, no stream. At most one summary and then one pricing call. |
| `synthetic_transport.py` | Test double. Cooperative phases advance an injected clock. `ignore_timeout` sleeps and is not preempted. |
| `credential_boundary.py` | `SyntheticCredential` only. `read_real_credential()` raises `REAL_CREDENTIAL_INPUT_NOT_AUTHORISED`. |
| `diagnostic_session.py` | Loads the Phase 3 gate and plan, and the Phase 2 account and pricing adapters, by file path. Writes one sanitised log. |
| `offline_entry.py` | Accepts only `--offline`. |
| `test_phase4_offline.py` | Offline security tests. Socket and DNS calls are replaced before imports. |

## Session order

1. Confirm `mode == OFFLINE_TEST`.
2. Accept only `SyntheticCredential`. The token is not returned.
3. Phase 3 `summary_candidate()` then `approve(..., step=1, prior=[])`.
4. Synthetic summary through the double. Non-200 stops before the body is read.
5. JSON decode. A copy is passed to Phase 2 `account_diagnostics.build` and `diagnostic_writer.stamp`.
6. Pricing runs only when the account outcome is `DIAGNOSTIC_RECORDED`.
7. Phase 3 `pricing_candidate()` then `approve(..., step=2, prior=["summary"])`.
8. A copy is passed to Phase 2 `pricing_diagnostics.build` and `stamp`.
9. One JSON file under `synthetic_logs/`.
10. The double is closed.

Phase 2 `write_record` is path-locked to the Phase 2 log directory, so it is not called. The calculations stay in Phase 2. The Phase 4 writer only stores the stamped records.

## Allowlist

- Request 1: `GET /v3/accounts/{accountID}/summary`, empty query.
- Request 2: `GET /v3/accounts/{accountID}/pricing` with query key `instruments` and value `EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`.
- No third request. A second summary is `SUMMARY_DUPLICATE_REJECTED`. Pricing before summary is `SEQUENCE_REJECTED`.
- Excluded: `includeHomeConversions`, instrument metadata, candles, financing, orders, trades, positions, transactions, and account changes.

The logged endpoint uses `{accountID}`. The synthetic account identifier is removed by the Phase 3 gate before the transport sees the path.
