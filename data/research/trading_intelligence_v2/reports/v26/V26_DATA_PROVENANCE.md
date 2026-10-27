# V2.6 Data Provenance

Actual acquisition NOT_EXECUTED; new market candles0. Small tracked
acquisition_plan.json and synthetic_verification.json distinguish plans/fixtures
from real provenance. Full invented archives stay in ignored outputs/v26.

Real schema records provider, transport mode, environment, public endpoint,
instrument, granularity, MBA, ranges, retrieval time, returned/valid/incomplete
counts, first/last candles, missing-run references, raw/envelope/normalized/commit
SHA256 and limitations. Per-batch commit files contain exact validation reports;
the small final manifest references and hashes them. No token, account ID, HTTP
headers or private URL is serialized. TLS/source assertions and local hashes
are not independent provider attestations or signatures against local tampering.

Large raw and normalized data are excluded from Git. Store confines writes to
research outputs/v26, rejects path escapes and links/junctions, limits logical
disk bytes and uses immutable data publication. Concurrent malicious filesystem
replacement, ACL security, OneDrive/cloud replication and media-failure integrity
are not proven. A protected location/usage review is required before Permission B.

Production remains NO-GO.
