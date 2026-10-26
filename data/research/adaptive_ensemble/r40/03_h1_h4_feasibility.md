# R.40 H1 and H4 feasibility

## Source inventory

`data/historical/` contains six M5 files and no H1 or H4 files:

| Instrument | Rows | SHA-256 | Median close spread | Local pip |
| --- | ---: | --- | ---: | ---: |
| AUD_USD | 74,563 | `e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0` | 0.00013 | 0.0001 |
| EUR_USD | 74,572 | `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091` | 0.00016 | 0.0001 |
| GBP_USD | 74,555 | `ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58` | 0.00019 | 0.0001 |
| USD_CAD | 74,560 | `a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60` | 0.00018 | 0.0001 |
| USD_CHF | 74,514 | `3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc` | 0.00015 | 0.0001 |
| USD_JPY | 74,557 | `e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c` | 0.016 | 0.01 |

Every file starts at 2025-09-01 00:00 UTC and ends at 2026-08-31 23:50 UTC. Duplicate timestamps, negative spreads, and source rows flagged incomplete were zero. Bid and ask open, high, low, and close are present. The pip column is the local quote-currency rule in `research_pip_size`. USD_JPY uses 0.01. The other five use 0.0001.

## Alignment rule

An H1 candle opens on a UTC hour and contains the twelve M5 bars at `open`, `open+5min`, through `open+55min`. An H4 candle opens at 00:00, 04:00, 08:00, 12:00, 16:00, or 20:00 UTC and contains the forty-eight M5 bars through `open+235min`. Unix time divides evenly into these boundaries, so the bucket is `floor(timestamp / period)`.

A higher-timeframe candle is complete only when every constituent exists, each step is exactly 300 seconds, and no constituent is flagged incomplete. Open is the first constituent open. High is the maximum constituent high. Low is the minimum constituent low. Close is the last constituent close. Volume is the sum of constituent M5 volume. Bid and ask are aggregated separately. Missing prices stay missing.

The candle is labelled by its UTC open. Its close is known at `open + period` (`available_at`). The file ends at 23:50 UTC, so the final H1 hour and the 20:00 H4 block are unfinished and were rejected. The last complete H1 opens at 2026-08-31 22:00 UTC. The last complete H4 opens at 2026-08-31 16:00 UTC.

## Complete-candle counts

| Instrument | Complete H1 | Incomplete H1 buckets | Complete H4 | Incomplete H4 buckets | M5 gaps > 5 min | Gaps > 48 h |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AUD_USD | 6,189 | 27 | 1,478 | 130 | 81 | 51 |
| EUR_USD | 6,196 | 20 | 1,483 | 125 | 73 | 51 |
| GBP_USD | 6,184 | 32 | 1,478 | 130 | 87 | 51 |
| USD_CAD | 6,188 | 28 | 1,483 | 125 | 82 | 51 |
| USD_CHF | 6,163 | 53 | 1,460 | 148 | 116 | 51 |
| USD_JPY | 6,185 | 31 | 1,476 | 132 | 85 | 51 |

Each file has 51 gaps longer than 48 hours. The largest gap is 49.08 hours, which matches a weekend close rather than a deleted trading week. Each file also has 3 gaps between 1 hour and 48 hours. This stage does not name those gaps as particular holidays. USD_CHF has more short gaps and more incomplete higher-timeframe buckets than the other five. Those buckets stay out of the complete series.

Derived candles were counted for integrity only. No strategy signal, entry, or profit figure was produced. The historical files were not copied.
