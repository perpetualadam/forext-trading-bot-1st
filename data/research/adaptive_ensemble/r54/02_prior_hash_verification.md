# Prior hash verification

Checked before any R.54 file was added, and again by `00_preflight.py` and by `session_main.py` at launch.

| File | SHA-256 | Result |
| --- | --- | --- |
| `data/research/adaptive_ensemble/r51/https_adapter.py` | `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` | match |
| `data/research/adaptive_ensemble/r52/session_entry.py` | `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` | match |
| `data/research/adaptive_ensemble/r53/connector.py` | `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4` | match |

R.51, R.52, and R.53 were not modified. A mismatch stops the session with `R54_PRIOR_HASH_MISMATCH`.
