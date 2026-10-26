# R.51 hash verification

The R.51 adapter was read and hashed before any R.52 behaviour ran.

- File: `data/research/adaptive_ensemble/r51/https_adapter.py`
- Expected SHA-256: `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`
- Actual SHA-256: `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`
- Result: match

The file was not edited. R.48, R.49, and R.50 were not edited. The R.52 entry point loads the R.51 adapter by path and stops with `R52_R51_HASH_MISMATCH` if that pin changes.
