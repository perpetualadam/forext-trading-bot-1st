# Spread and quote freshness

Quote structure still blocks a missing, non-finite, non-positive, or crossed bid/ask. A non-finite or negative spread value blocks. Spread units are price units: ask minus bid.

A missing quote timestamp now returns `quote_timestamp_missing` and the freshness gate is `MISSING_EVIDENCE`. An invalid timestamp, a future timestamp, and a timestamp older than the existing `MANAGE_PRICE_STALE_SEC` of 90 seconds block. A synthetic timestamp inside that window can make the freshness gate `PASS` for the harness rule. `production_quote_provenance` stays `MISSING_EVIDENCE`, so that pass is not production freshness.

No numeric spread threshold was added. `numeric_spread` is `POLICY_UNAPPROVED`. That status is not a spread pass, and it keeps `production_eligible` false. The isolated contract can still reach the inert adapter after the structural quote checks pass.
