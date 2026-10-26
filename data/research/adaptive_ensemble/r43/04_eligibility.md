# R.43 fresh-data eligibility

The research year is `2025-09-01` 00:00 UTC through `2026-08-31` 23:50 UTC. R.29–R.42 examined that period. Its classification is `RESEARCH_EXPOSED`. A later file timestamp does not make a row independent if the same market period was already used to design or select a strategy.

The stage date is 21 October 2026. Nothing in the approved candle directories is labelled `INDEPENDENTLY_VALIDATED`. Nothing local is a `PROTECTED_HOLDOUT_CANDIDATE`.

## Approved M5 year

`data/historical/{AUD_USD,EUR_USD,GBP_USD,USD_CAD,USD_CHF,USD_JPY}_M5.csv`

Classification: `RESEARCH_EXPOSED`.

These files have bid and ask OHLC, a completeness flag, and the hashes recorded again in `03_inventory.json`. R.30–R.42 used them for signals, costs, regimes, swings, and range lifecycle. They are development history. They are not a final test of a rule designed on them.

## Matching M1 files

`data/historical/m1/{same six}_M1.csv`

Classification: `RESEARCH_EXPOSED`.

The M1 files cover the same calendar span and the same six instruments. R.29 inventoried them and did not replay them. The calendar itself was then used through the M5 files. An M1 study of this span would still be a study of the exposed year. The files do contain bid and ask and can be aligned to H1 and H4 only as a finer description of that same year.

## G.3 normalised extract

`data/research/adaptive_ensemble/g3/normalized/{same six}_M5.csv`

Classification: `INSUFFICIENT_COVERAGE`.

The extract starts at 2026-09-01 00:00 UTC and ends on 2026-10-09, after the exposed year and before 21 October 2026. The local request plan names a candle endpoint, granularity M5, price `MBA`, and the six instruments. It does not prove account product type. The normalised files contain bid and ask. Prior G.3 readiness called the duration insufficient, recorded 29 complete trading days, and set validation to not started. R.2 used the same files for a session recount and recorded that profitability was not run. R.29 kept the extract out of the strategy ranking.

This segment is therefore newer than the exposed year, already opened, and too short to establish an edge. It is not a protected holdout. The old manifest phrase `POTENTIALLY_INDEPENDENT` is not reused. About twelve days from 2026-10-09 to 2026-10-21 are not in this extract.

## 2024 sample

`data/eurusd_m5_2024_sample.csv`

Classification: `INSUFFICIENT_PROVENANCE` and `INSUFFICIENT_COVERAGE`.

`data/README.txt` describes it as a short synthetic sample with time, open, high, low, and close. It has no bid or ask. It is one instrument and a fragment of 2024. It is not fresh data and it is not a holdout.

## Absent material

No stored H1 or H4 candle files were found. Higher-timeframe candles in R.40–R.42 were derived in memory from M5. No candle file was found for NZD_USD, EUR_GBP, EUR_JPY, GBP_JPY, AUD_JPY, or EUR_AUD. Those names are `INSUFFICIENT_COVERAGE` until a later authorised acquisition. `data/ops` and `data/research/v2_shadow` were left unopened, consistent with the R.2 boundary around operational and shadow state.

## Partitions for a later programme

| Partition | What qualifies | What exists now |
| --- | --- | --- |
| Development | The exposed year, including M1 of that year | Present |
| Previously inspected later segment | G.3 extract, 2026-09-01 through 2026-10-09 | Present, short, already read |
| Future acquisition | Data after a newly frozen protocol, not yet read by a strategy stage | Not present |
| Protected final holdout | A reserved slice of that future acquisition, unread until the protocol hash is frozen | Not present |

`POTENTIAL_NEW_DATA` is not applied to any current file. The only post-year candles have already been inspected and do not cover a long enough interval.
