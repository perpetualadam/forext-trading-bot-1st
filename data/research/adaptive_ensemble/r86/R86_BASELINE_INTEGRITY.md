# R.86 Baseline Integrity

Evidence: hash and archive inspection before the reporting module was added, plus `test_01` and `test_02`.

HEAD `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The working tree was already dirty. It was not cleaned or committed.

R.85 archive:

| Property | Observed |
| --- | --- |
| Size | 153,847 bytes |
| Members | 43 |
| Manifest entries | 42 |
| Mismatches | 0 |
| CRC | clean |
| SHA-256 | `766e0bc37f1ba3b2d1f0d58c216cc5d9c7f467aa9630954cfe0ed2d283102864` |

Working-tree hashes matched the R.85 operational set, including `recovery_owner_lock.py` `6a60e2264f703bbc9192658f0c82e54f3cd65a773b72a0afe916dae4163a9361`. Isolation and the consumed-marker digest matched. `one_session.permit` was absent.

No unexpected mismatch appeared. The new file `forex_bot/exposure_report.py` is the R.86 addition and was not part of the R.85 archive.
