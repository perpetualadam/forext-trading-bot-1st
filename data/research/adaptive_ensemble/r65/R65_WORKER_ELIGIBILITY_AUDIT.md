# R.65 worker eligibility audit

The R.61 worker conclusion stands, and only for these bytes. R.61 was not modified. There is no global bypass.

## Manifest

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `diagnostic_worker.py` | 6343 | `0f70dcf2a9d6a1d7cd12f285bb6396c4aa0163148dc4943bc419d6743ab1020e` |
| `credential_ipc.py` | 8287 | `b4630c5b74dd0d9f73bce1f707f3b2391bffd0fe746d5b74447e728a4ced4d1b` |
| `live_session_gate.py` | 10271 | `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0` |
| `restricted_live_transport.py` | 9236 | `b56d94edaf8d4d7ed2ae366efc6587aab9c49d7841aeef9bc5fdc7429f6d6f10` |
| `metadata_extract.py` | 6183 | `06561e7e8fd5fb5278929f2edfad0b18ce8c7ec5d7f4a4f13bb2c1b647bbafd3` |

`evaluate` hashes those five names in a directory and compares them with the manifest. All five must match. The worker's `importlib` loads are literals for four of them, so a new load changes `diagnostic_worker.py` and drops eligibility. A spawn added inside one of the four modules changes that module's hash.

When eligible, the only policy named is `DIRECT_CHILD_ONLY_EXPLICIT`, and the record says it is not descendant containment. `default_policy` stays `REQUIRE_DESCENDANT_CONTAINMENT`. `global_bypass` is false. Nothing in the operational bot calls `evaluate`.

## Tests

The current R.61 directory matches. Appending a comment that mentions `subprocess.Popen` to a copy of the worker makes `eligible` false and the policy `NOT_ELIGIBLE`. Omitting `credential_ipc.py` does the same. Both ran on Windows and on WSL2.

`DIRECT_CHILD_CONTAINMENT_SUFFICIENT_FOR_CURRENT_VERIFIED_WORKER` remains the R.64 statement for this manifest. It is not enabled as a process-wide setting.

`R65_WORKER_ELIGIBILITY_ASSESSED`
