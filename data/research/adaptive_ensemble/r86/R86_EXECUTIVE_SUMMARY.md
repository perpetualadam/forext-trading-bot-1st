# R.86 Executive Summary

Classification: `R86_SNAPSHOT_PROVENANCE_AND_REPORTING_PARTIALLY_VERIFIED`

Production trading remains NO-GO. R.87 was not started. Quarantine was not released.

The R.85 baseline matched before this stage, including the archive `766e0bc37f1ba3b2d1f0d58c216cc5d9c7f467aa9630954cfe0ed2d283102864`. The only new operational file is `forex_bot/exposure_report.py`. It does not write journals, mutate the position book, or submit broker requests. `portfolio_exposure.py` was left unchanged so its existing managed-book metric is not silently redefined.

OpenPositions in this repository is one request. The parser has no page token and no transaction watermark. A body that parses, including an empty `positions` list, is `UNKNOWN_COMPLETENESS`. It is not `COMPLETE_VERIFIED` and it is not a verified flat account. Stale, failed, and incomplete observations are not current recovery evidence.

The report shows active manageable units, the journal remainder, and unverified broker observations as separate lines. Unknown exposure has null units, not zero. Instruments are not added together as raw units. A 1,000 / 400 / 600 partial close stays quarantined with manageable units at zero.

The live adapter still cannot prove snapshot completeness or broker-side chronology. That limitation is why the classification is partial.

## Explicit answers

The bot can report active, quarantined, broker-observed, and unknown exposure without treating the journal remainder as verified broker exposure. That was executed in the read-only report.

The bot cannot demonstrate that a broker snapshot is complete and fresh enough for a recovery decision. That remains unverified.

Reporting can run without changing trading authority, journal state, position state, or broker requests. The operational cycle was executed separately and did not call the report from inside the trading path.
