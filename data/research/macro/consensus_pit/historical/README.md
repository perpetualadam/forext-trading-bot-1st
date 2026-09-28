# Historical consensus PIT reconstruction

Research-only. Extends the 9-event pilot across the remaining 20 of 29 Stage-3 eligible events.

- `manifest/remaining_events.json` was frozen before remaining-event search. FX outcomes were not used.
- `raw/` holds short hashed excerpts, not full-page WARC.
- `evidence/remaining_evidence.json` is new reconstruction only.
- `normalized/all_records.json` concatenates pilot records (read, not rewritten) with remaining records.
- `gold/` is PIT_SAFE only. `silver/` is PIT_SAFE_WITH_LIMITATION only. They are not mixed.

Do not modify `data/research/macro/us_pit/` or `data/research/macro/consensus_pit/pilot/consensus_evidence.json` from this tree.
