# V2.8D partial archive

The 39 original completed batches were independently revalidated against their exact request/index, session/identity, original source seal and catalogue, LIVE claimed grant, durable one-attempt completion, raw/validated/manifest hashes, strict candle validation and previously captured file hashes/modification times. Original files were not rewritten. Window 40 and overall parent remain OUTCOME_UNKNOWN and consumed; no new diagnostic was retrofitted to them.

Saved private derivative: `C:\TradingResearchData\OANDA\research_outputs\v28d_partial_eurusd_5461c06197674665a4aa6f84ffebc718\candles.json.gz`.
Manifest: `C:\TradingResearchData\OANDA\research_outputs\v28d_partial_eurusd_5461c06197674665a4aa6f84ffebc718\manifest.json`.
Count: **27,213** completed EUR_USD M5 candles; full original bid/ask/mid OHLC strings, no duplicates or overlaps.
Observed coverage: 2024-09-01T21:00:00Z through 2025-01-14T09:55:00Z.
Canonical uncompressed records SHA-256: `81b006a153237ac42dabbbd817a5e56b80493cb82b89bd0db4705a207a64a8a9`.
Stored gzip file SHA-256: `007d85b7c95176a830ddeddf799c58f29401960773c924754f25a2a1bc174ab0`.
Manifest SHA-256: `54782a07b77b340180f1dd6bf37ac8c1a99a6f06ee94a3ebd05ec9ea37bb2c12`.

The existing importer is used for each independently reviewed manifest; the original pilot merger's ordered-record/gap accumulator is shared without relaxing its existing complete-session checks. A separate bounded-prefix adapter validates the actual OUTCOME_UNKNOWN parent and its completed windows; it never fabricates DONE records or grants. Exactly 39 manifests are admitted; incomplete/unknown windows are refused.

Publication uses existing protected Archive.put pending-file/write-through publication, a fresh exclusive output directory and a manifest committed last. Gzip is deterministic (mtime=0); records remain the existing research-import schema. A fresh process reopened the derivative, revalidated/remerged all 39 source batches, and compared identical canonical records and hashes. No original archive relocation or fallback occurred.

The derivative manifest records all 39 batch identities/specifications/hashes, original request/grant/journal/result/rights hashes, preserved rights conditions, missing-period reports, explicitly unresolved window 40 and unattempted tail. Status is PARTIAL_OUTCOME_UNKNOWN; complete_12_month_history=false. Weekend-containing gaps remain unverified; no independent holiday/session calendar was introduced and no candle was invented. Within the 39-window planned prefix there are 39,000 calendar slots and 27,213 observed completed candles; missing slots are retained as unknown closure/missing evidence, not declared verified closures.

Rights remain private local research only under the previously reviewed catalogue-specific evidence and conditions, with per-manifest provenance/hash checks. Raw and merged market data stay outside OneDrive/Git. No external publication/redistribution or perpetual post-termination retention is inferred. Independence is PREVIOUSLY_EXAMINED_INDEPENDENCE_UNVERIFIED. Frozen V2.5 policy/cost/evaluation gates remain; no optimisation or strategy tournament was run.
