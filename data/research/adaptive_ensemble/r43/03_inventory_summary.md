# R.43 local dataset inventory

Source files were hashed and read. They were not modified. Filesystem modification time is stored in `03_inventory.json` and is not the market timestamp. `data/ops` and `data/research/v2_shadow` were not opened.

No stored H1 or H4 candle file exists. No file exists for NZD_USD, EUR_GBP, EUR_JPY, GBP_JPY, AUD_JPY, or EUR_AUD.

## Research-exposed M5 year

Bid and ask OHLC are present. Duplicate timestamps, null rows, negative close spreads, and `complete=false` rows are zero. The largest gap on every file is 2 days 1 hour 5 minutes.

| File | Rows | Earliest UTC | Latest UTC | Gaps longer than 5 minutes | SHA-256 matches R.41 |
| --- | ---: | --- | --- | ---: | --- |
| AUD_USD_M5 | 74563 | 2025-09-01 00:00 | 2026-08-31 23:50 | 81 | yes |
| EUR_USD_M5 | 74572 | 2025-09-01 00:00 | 2026-08-31 23:50 | 73 | yes |
| GBP_USD_M5 | 74555 | 2025-09-01 00:00 | 2026-08-31 23:50 | 87 | yes |
| USD_CAD_M5 | 74560 | 2025-09-01 00:00 | 2026-08-31 23:50 | 82 | yes |
| USD_CHF_M5 | 74514 | 2025-09-01 00:00 | 2026-08-31 23:50 | 116 | yes |
| USD_JPY_M5 | 74557 | 2025-09-01 00:00 | 2026-08-31 23:50 | 85 | yes |

## M1 files for the same calendar

Bid and ask are present. Duplicates, nulls, negative close spreads, and incomplete flags are zero. A gap count here includes every missing minute, not only weekends. The largest gap is again 2 days 1 hour 5 minutes.

| File | Rows | Latest UTC | Gaps longer than 1 minute |
| --- | ---: | --- | ---: |
| AUD_USD_M1 | 369295 | 2026-08-31 23:58 | 2345 |
| EUR_USD_M1 | 370729 | 2026-08-31 23:59 | 1178 |
| GBP_USD_M1 | 370998 | 2026-08-31 23:59 | 851 |
| USD_CAD_M1 | 370249 | 2026-08-31 23:58 | 1490 |
| USD_CHF_M1 | 368404 | 2026-08-31 23:58 | 2705 |
| USD_JPY_M1 | 370450 | 2026-08-31 23:59 | 1236 |

## G.3 later M5 extract

Hashes match the R.2 record. Bid and ask are present. Duplicates, nulls, negative spreads, and incomplete flags are zero. The extract ends 2026-10-09 07:00 UTC. Nothing later is on disk.

| File | Rows | Gaps longer than 5 minutes |
| --- | ---: | ---: |
| AUD_USD | 8146 | 8 |
| EUR_USD | 8148 | 6 |
| GBP_USD | 8148 | 6 |
| USD_CAD | 8147 | 7 |
| USD_CHF | 8123 | 22 |
| USD_JPY | 8141 | 11 |

## 2024 sample

`data/eurusd_m5_2024_sample.csv` has 450 rows from 2024-01-02 08:00 UTC through 2024-01-03 21:25 UTC. Columns are time, open, high, low, and close. Bid and ask are absent.

Provenance and eligibility are in `04_eligibility.md`. Full hashes are in `03_inventory.json`.
