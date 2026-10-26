# Authoritative dependency hashes

The R.52 value is the authoritative pin. The differing value from the blocked B1 attempt was not used.

| File | SHA-256 | On disk |
| --- | --- | --- |
| R.51 `https_adapter.py` | `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` | match |
| R.52 `session_entry.py` | `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` | match |
| R.53 `connector.py` | `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4` | match |
| R.54 `session_main.py` | `50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280` | match |
| R.55 Boundary A `session_main.py` | `5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8` | match |

Imported by the B1 session, and also checked:

| File | SHA-256 |
| --- | --- |
| R.48 `readonly_transport.py` | `3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844` |
| R.50 `connector.py` | `4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8` |
| R.50 `fixtures.py` | `bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee` |

R.51, R.52, R.54, and the R.55 Boundary A session are hash-checked and are not imported. A mismatch stops the program with `R55B1_PRIOR_HASH_MISMATCH`.
