# R.83 archive note

This note is outside `R83_SOURCE_REVIEW.zip`.

| Check | Result |
| --- | --- |
| Path | `data/research/adaptive_ensemble/r83/R83_SOURCE_REVIEW.zip` |
| Size | 131,780 bytes |
| SHA-256 | `b01b060d90ead2a5ddaa50c85e5a8fa25613957659adaf79753d7a1bd78257d7` |
| Members | 47 |
| Manifest entries | 46 |
| CRC | `ZipFile.testzip()` returned no failing member |
| Read-back | Every manifest digest matched the member bytes read back from the ZIP |

The archive contains the operational modules, the R.83 test and worker, the isolation harness, the R.83 reports, the source-hash file, the regression logs, and `SHA256SUMS.txt`. It does not contain `.env`, permits, the consumed-marker body, production journals, or database files.

The two operational changes inside the archive are `forex_bot/entry_journal.py` and `forex_bot/positions.py`.
