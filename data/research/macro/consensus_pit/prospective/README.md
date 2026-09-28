# Prospective US macro recorder (research-only)

48-hour pre-release consensus + economic-calendar + official first-print capture.

- `FORWARD_CONSENSUS_COLLECTION_ENABLED=false`
- Manual ingest is supported. Autonomous external collection is not enabled.
- `observed_at_utc` is OUR clock and is never replaced by source publication time.
- Do not rewrite `historical/` or `pilot/` evidence from this tree.
- Do not import this module from production trading code.
