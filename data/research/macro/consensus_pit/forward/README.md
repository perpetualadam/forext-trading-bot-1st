# Forward consensus snapshot architecture

Research-only. Collection is disabled.

- `observed_at_utc` is OUR collector clock and is never replaced by `source_publication_utc`.
- Snapshots are append-only. Identical bytes reuse the content snapshot and log a new observation. Changed bytes create a new vintage.
- SHA-256 is over the artifact bytes actually observed.
- `final_pre_release_snapshot` is the latest snapshot with `observed_at_utc < official_release_utc`.
- Providers are stored separately and must not be averaged.
- Cadence T0-48h / -24h / -12h / -4h / -1h is a design note, not a trading rule.

`FORWARD_CONSENSUS_COLLECTION_ENABLED=false`
Every source in `source_registry.json` has `enabled=false`.
