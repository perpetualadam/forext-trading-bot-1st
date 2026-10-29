# V2.8B bounded EUR/USD acquisition preparation

PREPARATION_ONLY. No authenticated acquisition authorised. Baseline main 54801b719df2fff8ac4c4ad22666f75e2dc1d050. Production NO-GO.

Candidate, unchanged: [2024-09-01T00:00:00Z, 2025-09-01T00:00:00Z), 365 days. LIVE GET api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles; M5, MBA, smooth=false, includeFirst=true, count omitted. Original decimal text and completion flags preserved.

Existing Plan.batches supplies exactly 106 contiguous windows: 105 x 1,000 slots plus 120 final slots = 105,120 M5 calendar slots. V28B_REQUEST_WINDOWS.json records each exact spec/hash, deterministic unique planning ID, source-seal reference, destination, predecessor and PLANNED_NOT_AUTHORISED state. Calendar slots are not promised candles; no weekend/holiday pre-skipping or fabricated fills.

First request: 2024-09-01T00:00:00Z to 2024-09-04T11:19:59Z inclusive; half-open end 11:20:00Z. Planning ID 7fdca051b58a58749a4782a6d18d7383. Last request: 2025-08-31T14:00:00Z to 2025-08-31T23:59:59Z inclusive; half-open end 2025-09-01T00:00:00Z. Planning ID 71fe4b5e7f9b5422b035e337a5cae190.

Maximum proposed future attempts: 106, one per independently approved request; currently authorised attempts ZERO. No retries, redirects, proxies, pagination, fallback, account endpoint or trading paths. A refused, corrupt, pending, timed-out or ambiguous session stops progression; never reset/retry a consumed or uncertain grant.

Approximate data: 74,880 weekday-grid candles, up to 105,120 calendar slots; actual hours, DST, weekends, holidays and outages require evidence. Pilot measured raw+validated size 695,691 bytes / 1,440 candles = 483.11875 bytes/candle. Extrapolation: 34.50 MiB expected, 48.43 MiB calendar upper estimate, before metadata and price-format variation. Proposed 256 MiB total budget/free-space review, not an already enforced new LIVE quota. Retain the existing 8 MiB response limit and protected atomic writes. Refuse acquisition if its reviewed disk budget cannot be enforced.

Assuming 1-15 seconds service time and proposed conservative one-second spacing, serial machine transfer estimate is 3.5-28.3 minutes. This excludes terminal confirmations, human token entry, validation/publication and review pauses; not a completion SLA. The sum of 106 x 15/120/15 timed phases is 4h25m, but pre-admission confirmation/waiting is unbounded. Do not lengthen any stage deadline to meet this plan.

## Existing-mechanism compatibility

Existing HTTP client, validator, Archive and batching logic are reusable. The published LIVE catalogue supports only the September connectivity request and three August pilot windows. It CANNOT execute this year plan. Reference source seal 34939a3db7ccd4dbb1b851ac6fb96c0ceba0b054b60dc65bd58f3248f2fd68d6 is not a year-scope permit. No LIVE source, seal, credential path or network activation changed here; no new native namespaces/grants/journals created.

Smallest justified future authority change: bind the existing per-process selector and parent/worker checks to one immutable reviewed 106-window catalogue, with exact session/spec/source hashes, separate per-window terminal approval and durable state. Keep one active global lock, one attempt, no automatic request progression, all-predecessor successful consumed evidence and 15/120/15 timing. Review predecessor verification cost as the chain grows; fail closed on deadline exhaustion. No generic arbitrary-date selector, reusable bulk permit, second downloader or automatic credential reuse. This LIVE-scope change requires local security verification and separate publication approval before use; it is not implemented by this offline plan. Planning IDs/source bindings need renewed exact review if the future LIVE source seal changes.

Before real acquisition: approve exact catalogue/hash and attempt/disk/rate bounds, extend applicable private research/retention rights evidence to this scope, complete exposure/first-access review, approve and publish any authority extension, verify its CI/source seal, then approve each individual GET. V2.8A approval does not apply. No executable command is provided for unsupported LIVE scope.
