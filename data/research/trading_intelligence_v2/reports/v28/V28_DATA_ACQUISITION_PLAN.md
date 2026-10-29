# V2.8 bounded acquisition preparation

Status: PREPARATION_ONLY; no new authenticated request authorised or attempted.
Baseline: c93aea60136c8e3906e0dc1a9a22e224e2fa911f. Production NO-GO.

## Scope and arithmetic

Six instruments: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF. M5, MBA, UTC start timestamps, complete flags and original decimal text preserved. Existing protected archive only: C:\TradingResearchData\OANDA. No new downloader or credential system.

Candidate minimum interval: [2024-09-01, 2025-09-01) UTC, 365 days. Calendar grid: 105,120 candles/pair; six-pair upper bound 630,720. Approximate weekday expectation: 74,880/pair, 449,280 total (260 weekdays). Candidate preferred interval: [2023-09-01, 2025-09-01), 731 days: 210,528/pair, 1,263,168 upper bound; approximate 150,048/pair, 900,288 total (521 weekdays). These are planning estimates, not exchange-session completeness guarantees; Sunday openings, Friday closes, DST and holidays require evidence.

Reuse existing Plan.batches at 1,000 grid slots/request (83h20m); do not use the 5,000 maximum for the pilot. Minimum: ceil(105120/1000)*6 = 636 requests, 106/pair. Preferred: ceil(210528/1000)*6 = 1,266 requests, 211/pair. Count omitted with from/to. Inclusive API `to` is exclusive batch end minus one second; no overlapping windows or pagination.

At a proposed conservative one-second spacing and assumed 1-15 seconds service time, serial transfer estimates are 21-170 minutes minimum and 42-338 minutes preferred. Human entry, approval, validation, persistence and safety checks add unbounded scheduling time; this is not an automatic session schedule or hard total completion promise. Existing one-second rate controls are below published 120 requests/second and two new connections/second; no rate increase proposed.

Observed ten-candle sample: 2,685 raw + 2,202 validated bytes, 488.7 bytes/candle combined. Calendar-grid extrapolation: approximately 294 MiB (12 months) or 589 MiB (24 months), before envelope/manifest/decimal-length variation. Reserve 2 GiB free budget, halt before exceeding the existing cap; this is an estimate, not preallocated disk or authorisation.

## Stages requiring separate approval

1. EUR_USD [2024-08-05T00:00:00Z, 2024-08-12T00:00:00Z): 2,016 grid slots, about 1,440 weekday candles, three 1,000-slot-or-smaller windows. Review bid/ask/mid, timestamps, hashes, unexpected gaps, holiday/session evidence and measured request duration. No automatic continuation.
2. EUR_USD minimum interval: 106 windows; then optional 24-month coverage: 211 windows total, never redownload committed batches implicitly.
3. Same approved dates for other five instruments only after stage review: 530 windows for 12 months, 1,055 for 24 months. Reconcile cross-pair coverage and conversion rates.

Existing generic offline batch planning/rate controls are reusable. The working V2.7 LIVE authority is deliberately pinned to one September EUR_USD request; it cannot authorise any stage above. Bulk activation is BLOCKED pending separately approved exact request budgets, ranges, applicable account retention/derived-result rights and reviewed admission compatibility. Do not run the generic downloader with real credentials, substitute an account endpoint, reuse consumed grants, or widen the source seal to bypass this boundary. No API infrastructure changes were made.

Official references reviewed: https://github.com/oanda/v20-openapi/blob/master/yaml/separate/v20_instrument.yaml ; https://developer.oanda.com/rest-live-v20/development-guide/ ; https://developer.oanda.com/rest-live-v20/pricing-ep/ . The latter documents an account-specific endpoint; it is not permission to substitute it. The successful non-account ten-candle request demonstrates only that call's acceptance. No account terms or broad retention rights inferred.
