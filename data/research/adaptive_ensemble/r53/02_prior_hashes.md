# Prior hash verification

Both pinned files were hashed before the R.53 connector was used.

- R.51 `https_adapter.py`: `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` — match
- R.52 `session_entry.py`: `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` — match

Neither file was edited. A mismatch stops the R.53 program with `R53_PRIOR_HASH_MISMATCH`.
