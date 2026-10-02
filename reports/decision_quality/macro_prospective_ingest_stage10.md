# MACRO RESEARCH — STAGE 10
# REAL T−12H PROSPECTIVE EMPLOYMENT CONSENSUS OBSERVATION

Manual screen observation of the Trading Economics Economic Calendar
for `usd_empsit_2026-10-02` at T−12h. No API call. No HTML scrape.
`FORWARD_CONSENSUS_COLLECTION_ENABLED` remains false.
T−48h and T−24h were not modified. T−36h was not backfilled.

EVENT
-----
`usd_empsit_2026-10-02`
T0 = `2026-10-02T12:30:00Z`
Checkpoint `T0-12h` scheduled `2026-10-02T00:30:00Z`

EVIDENCE
--------
Upload name `20261002-0030-19.7514577.mp4` was not assumed to exist
and was not used.

Canonical source:
`C:\Users\Brian\Videos\Screen Recordings\Screen Recording 2026-10-02 013036.mp4`
SHA-256: `73999531537053a2fe16fa7cc0bb4244fdad3ebcb5bc40324c818a1f8efff595`
CreationTimeUtc `2026-10-02T00:30:36.444Z` → truncated `2026-10-02T00:30:36Z`

A later byte-identical copy
`C:\Users\Brian\Videos\Recording 2026-10-02 013041.mp4`
(`2026-10-02T00:30:43Z`) was left in Videos and not archived.

Imported unchanged to:
`data/research/macro/consensus_pit/prospective/evidence/Screen Recording 2026-10-02 013036.mp4`

TIMESTAMP
---------
`observed_at_utc=2026-10-02T00:30:36Z`

Basis: Windows filesystem creation time truncated to UTC seconds, same
Stage 8/9 rule. Ingest clock
(`retrieval_utc=2026-10-02T00:37:02Z`) was not used as observed_at.
Associates to `T0-12h`. Capture delay from schedule: 36 seconds.

VALUES
------
Consensus is the displayed Consensus column. TE Forecast is metadata.

| series | previous | consensus | TE Forecast |
|---|---|---|---|
| NFP | 162K → 162000 persons | 90K → 90000 persons | 90.0K |
| Unemployment | 4.1% | 4.1% | 4.1% |
| AHE MoM | 0.3% | 0.3% | 0.2% |
| AHE YoY | 3.1% | 3.2% | 3.1% (not used as consensus) |

VINTAGES
--------
T−48h AHE YoY = MISSING
T−24h AHE YoY = MISSING
T−12h AHE YoY = 3.2%
Transition: CONSENSUS BECAME AVAILABLE AT T−12H.
No interpolation of the unobserved update time between T−24h and T−12h.

STATUS
------
CLI: T0-48h CAPTURED. T0-36h MISSED_NOT_OBSERVED. T0-24h CAPTURED.
T0-12h CAPTURED. Next checkpoint T0-6h at 2026-10-02T06:30:00Z
(07:30 BST). Autonomous collection OFF. Windows task unchanged.

OBSERVATION
-----------
observation_id `f9005e2c-da26-4b09-b804-bcc5fb6f01a3`
Duplicate re-ingest raises IngestClosed and does not overwrite.
