# Historical coverage

Six original instruments: verified local G3 archive, September 1–October 9 2026, 29 trading days. Every normalized candle matches its raw archived complete candle, and all 36 raw-page SHA256 values match the acquisition manifest. This proves archive-chain consistency, not independent provenance attestation. The September 2025–August 2026 archive exists and is quality-checked by acquire, but was previously examined and its acquisition chain is unverified here; it is excluded from performance comparisons. No new data downloads or invented market prices.

- AUD_USD M5: 8146 complete bars; 2883 unavailable buckets; warmed 50/100 observations=7750/7350.
- AUD_USD M15: 2713 complete bars; 964 unavailable buckets; warmed 50/100 observations=2517/2317.
- AUD_USD H1: 676 complete bars; 244 unavailable buckets; warmed 50/100 observations=545/445.
- AUD_USD H4: 162 complete bars; 68 unavailable buckets; warmed 50/100 observations=79/29.
- AUD_USD D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.
- EUR_USD M5: 8148 complete bars; 2881 unavailable buckets; warmed 50/100 observations=7848/7548.
- EUR_USD M15: 2715 complete bars; 962 unavailable buckets; warmed 50/100 observations=2617/2517.
- EUR_USD H1: 678 complete bars; 242 unavailable buckets; warmed 50/100 observations=629/579.
- EUR_USD H4: 164 complete bars; 66 unavailable buckets; warmed 50/100 observations=115/65.
- EUR_USD D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.
- GBP_USD M5: 8148 complete bars; 2881 unavailable buckets; warmed 50/100 observations=7805/7455.
- GBP_USD M15: 2715 complete bars; 962 unavailable buckets; warmed 50/100 observations=2617/2517.
- GBP_USD H1: 678 complete bars; 242 unavailable buckets; warmed 50/100 observations=580/522.
- GBP_USD H4: 163 complete bars; 67 unavailable buckets; warmed 50/100 observations=101/51.
- GBP_USD D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.
- USD_CAD M5: 8147 complete bars; 2882 unavailable buckets; warmed 50/100 observations=7772/7422.
- USD_CAD M15: 2714 complete bars; 963 unavailable buckets; warmed 50/100 observations=2606/2506.
- USD_CAD H1: 677 complete bars; 243 unavailable buckets; warmed 50/100 observations=577/477.
- USD_CAD H4: 162 complete bars; 68 unavailable buckets; warmed 50/100 observations=86/36.
- USD_CAD D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.
- USD_CHF M5: 8123 complete bars; 2906 unavailable buckets; warmed 50/100 observations=7465/6815.
- USD_CHF M15: 2696 complete bars; 981 unavailable buckets; warmed 50/100 observations=2206/1716.
- USD_CHF H1: 668 complete bars; 252 unavailable buckets; warmed 50/100 observations=328/130.
- USD_CHF H4: 157 complete bars; 73 unavailable buckets; warmed 50/100 observations=2/0.
- USD_CHF D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.
- USD_JPY M5: 8141 complete bars; 2888 unavailable buckets; warmed 50/100 observations=7790/7440.
- USD_JPY M15: 2709 complete bars; 968 unavailable buckets; warmed 50/100 observations=2611/2511.
- USD_JPY H1: 675 complete bars; 245 unavailable buckets; warmed 50/100 observations=577/477.
- USD_JPY H4: 163 complete bars; 67 unavailable buckets; warmed 50/100 observations=80/30.
- USD_JPY D1: INSUFFICIENT_DATA; No independently validated session calendar; only 29 days < 50/100 candle warm-up.

Exact normalized, raw-page manifest and older archive hashes/ranges are preserved in outputs/mtf/frozen_inputs.json and data_quality.json. Dataset hashes are also included in MTF_SOURCE_HASHES.txt. Gaps are never interpolated; every excluded bucket and reason is recorded. H4/D1 evidence is explicitly data-limited; zero trades following warm-up refusal is not a successful strategy result.

Classification: TIV22_MTF_RESEARCH_PARTIALLY_VERIFIED. Production NO-GO. Archived-market replay, not broker fills. This 29-day archive was already examined during TIV2; these are chronologically out-of-fit comparisons, not a fresh independently untouched dataset. No reliable profitability or operational advantage is established.
