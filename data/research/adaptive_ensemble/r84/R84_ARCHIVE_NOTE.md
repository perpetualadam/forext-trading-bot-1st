# R.84 archive note

This note is outside `R84_SOURCE_REVIEW.zip`.

| Check | Result |
| --- | --- |
| Path | `data/research/adaptive_ensemble/r84/R84_SOURCE_REVIEW.zip` |
| Size | 118,712 bytes |
| SHA-256 | `f259b60689045ea1a6b7d7d3b8785a3201f7c789d03ff56cd57594c94e4ff951` |
| Members | 44 |
| Manifest entries | 43 |
| CRC | `ZipFile.testzip()` returned no failing member |
| Read-back | Every manifest digest matched the member bytes |

The archive contains the operational close and recovery modules, the R.84 tests, the synthetic OANDA-shaped fixtures, the worker, the isolation harness, the reports, the regression logs, and `SHA256SUMS.txt`. It does not contain `.env`, permits, the consumed-marker body, or production journals.

The operational change inside the archive is `forex_bot/broker_close_evidence.py`.
