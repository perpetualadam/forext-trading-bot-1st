# MACRO RESEARCH — STAGE 9
# REAL T−24H PROSPECTIVE EMPLOYMENT CONSENSUS OBSERVATION

Manual screen observation of the Trading Economics Economic Calendar
for `usd_empsit_2026-10-02` at T−24h. No API call. No HTML scrape.
`FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
T−48h was not modified. T−36h was not backfilled.

EVENT
-----
`usd_empsit_2026-10-02`
T0 = `2026-10-02T12:30:00Z`
Checkpoint `T0-24h` scheduled `2026-10-01T12:30:00Z`

EVIDENCE
--------
Upload names `20261001-1230-38.6201347.mp4` / `(1).mp4` were not assumed
to exist and were not used.

Candidate 1 (canonical):
`C:\Users\Brian\Videos\Screen Recordings\Screen Recording 2026-10-01 133043.mp4`
SHA-256: `443aeb9614102cd134bee8659459e4ce97880ff64fca85a1ec3ace658c719adb`
CreationTimeUtc `2026-10-01T12:30:43.797Z` → truncated `2026-10-01T12:30:43Z`
Valid for T−24h: YES (earliest at-or-after 12:30:00Z)

Candidate 2 (non-canonical; original left in Videos):
`C:\Users\Brian\Videos\Recording 2026-10-01 133049.mp4`
SHA-256: `443aeb9614102cd134bee8659459e4ce97880ff64fca85a1ec3ace658c719adb`
CreationTimeUtc `2026-10-01T12:30:54.078Z` → truncated `2026-10-01T12:30:54Z`
Valid for T−24h: YES but later. Byte-identical copy of candidate 1.
Not copied into the research archive.

Canonical imported unchanged to:
`data/research/macro/consensus_pit/prospective/evidence/Screen Recording 2026-10-01 133043.mp4`
Copied bytes SHA-256 matches the source.

TIMESTAMP
---------
`observed_at_utc=2026-10-01T12:30:43Z`

Basis: Windows filesystem creation time (st_ctime) truncated to UTC
seconds, same Stage 8 provenance rule. Filename 13:30:43 BST is
corroboration only. Ingest clock
(`retrieval_utc=2026-10-01T12:39:17Z`) was not used as observed_at.

Associates to checkpoint `T0-24h` under latest-checkpoint-at-or-before
observed_at. Pre-T0. Capture delay from schedule: 43 seconds.

VALUES
------
Consensus is the displayed Consensus column (survey average among
economists). TE Forecast is stored only as provider metadata.

| series | previous | consensus | TE Forecast |
|---|---|---|---|
| NFP | 162K → 162000 persons | 90K → 90000 persons | 90.0K |
| Unemployment | 4.1% | 4.1% | 4.1% |
| AHE MoM | 0.3% | 0.3% | 0.2% |
| AHE YoY | 3.1% | MISSING / NOT_AVAILABLE | 3.1% (not used as consensus) |

T−48h → T−24h consensus: NFP NO CHANGE, Unemployment NO CHANGE,
AHE MoM NO CHANGE, AHE YoY STILL MISSING.

STATUS
------
CLI status: T0-48h CAPTURED. T0-36h MISSED_NOT_OBSERVED. T0-24h CAPTURED.
Next checkpoint T0-12h at 2026-10-02T00:30:00Z (01:30 BST).
Autonomous collection OFF. 0 enabled sources. Windows task unchanged.

OBSERVATION
-----------
observation_id `00a6ca6c-3598-47b0-8d4e-c9a2268a584d`
Duplicate re-ingest raises IngestClosed and does not overwrite.

TESTS
-----
Stage 9 fixture tests plus Stage 8. No test network calls.
Older empty-archive assertions were narrowed so genuine T−48h/T−24h
rows are allowed and T−36h remains un-backfilled.
