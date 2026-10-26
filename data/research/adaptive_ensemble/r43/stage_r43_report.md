# STAGE R.43 — FRESH MARKET DATA AND BROKER CONTRACT FEASIBILITY REPORT

Classification: `R43_FRESH_DATA_CONTRACT_FEASIBILITY_COMPLETED`

## Preservation

Project root `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`, branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty. R.24–R.42 evidence is intact. All six strategies remain inactive and unauthorised. The quant stub remains `quant_stub_removed` and fail-closed. Reinforcement learning remains `UNAVAILABLE`. Research lifecycle code is not imported by `bot_loop.py` or `ai_ensemble.py`. No acquisition client exists. No broker was contacted, no market data was downloaded, and no backtest was run.

## Local data inventory

The approved M5 year is still `2025-09-01` 00:00 UTC through `2026-08-31` 23:50 UTC for AUD_USD, EUR_USD, GBP_USD, USD_CAD, USD_CHF, and USD_JPY. Row counts are 74,514 to 74,572. Bid and ask are present. Duplicates, nulls, negative close spreads, and incomplete flags are zero. Gaps longer than five minutes number 73 to 116, and the largest gap is 2 days 1 hour 5 minutes. SHA-256 values match the prior research record.

Matching M1 files cover the same calendar, 368,404 to 370,998 rows, also with bid and ask and no duplicate timestamps. Gaps longer than one minute are more numerous, from 851 on GBP_USD to 2,705 on USD_CHF. That count includes every missing minute. The largest gap is the same weekend length.

The G.3 normalised M5 extract is `2026-09-01` 00:00 UTC through `2026-10-09` 07:00 UTC, 8,123 to 8,148 rows, bid and ask present, hashes unchanged from R.2. No candle after 2026-10-09 is on disk. No stored H1 or H4 file exists. No file exists for NZD_USD, EUR_GBP, EUR_JPY, GBP_JPY, AUD_JPY, or EUR_AUD. `data/eurusd_m5_2024_sample.csv` has 450 midpoint rows from 2024-01-02 through 2024-01-03 and no bid or ask. `data/ops` and `v2_shadow` were left unopened.

## Fresh-data eligibility

The M5 year and the matching M1 files are `RESEARCH_EXPOSED`. The G.3 extract is outside that year, already inspected by G.3 and G.4, and `INSUFFICIENT_COVERAGE`. Its old label `POTENTIALLY_INDEPENDENT` is not reused. The 2024 sample is `INSUFFICIENT_PROVENANCE` and `INSUFFICIENT_COVERAGE`. No file is a `PROTECTED_HOLDOUT_CANDIDATE`, and none is `INDEPENDENTLY_VALIDATED`.

## Additional-pair shortlist

Verification priority, not expected profit: NZD_USD, EUR_GBP, EUR_JPY, GBP_JPY, AUD_JPY, EUR_AUD. NZD_USD is first because it is the only name that adds a currency absent from the six files. Local pip sizes are a code convention: 0.01 for a JPY quote and 0.0001 otherwise. Spreads, margin, financing, and account eligibility were not invented. Cross prices were not synthesised.

## OANDA GBP spread-betting unknowns

The account product, jurisdiction, GBP stake convention, pip value, margin, closeout, guaranteed stops, financing, weekend charges, and conversion fees are unknown. A public page would not prove this account has the product. The brief's figure of about £97.15 was not read from operational state and is not a spread. R.27 still requires NAV and balance to stay separate. These unknowns block a later trade and a GBP performance claim.

## Future acquisition

The design allows an explicit instrument list and UTC range, candle-only access, throttling, pagination, two retries, raw immutable files, hashes, gap and duplicate checks, and a holdout partition. It does not evaluate a strategy after download. It is not implemented.

## Protected holdout

Development data is the exposed year. The G.3 extract is previously inspected and too short to reserve. A final holdout would be a later slice of a new acquisition, named before the first development read, and opened once. A repeated look is a repeated test. Changing the protocol after the hash invalidates an independence claim. The R.42 range rule stays frozen.

## Independent validation

A later test needs completed-candle clocks, the `k = 2` swing delay, R.42 line and range lifecycle, next-bar bid/ask, conservative gaps, financing, and dependence-aware intervals. One confirmed range in the exposed year is a warning that the current range rule may not supply enough events. `INSUFFICIENT_EVENTS` is an acceptable stop. The evaluation was not run.

## AI roadmap

Descriptive structure, economic evaluation, supervised learning, independent validation, contract verification, and deployment stay separate. No model was trained. Research records do not enter the production journal.

## Ranked R.44 options

The practical next stage is read-only contract verification for the existing six instruments. Fresh bid/ask acquisition for those six follows, and it stops at a quality manifest. Independent evaluation waits for both. Additional pairs wait, with NZD_USD first if a later stage is limited to one new name. These are not one combined stage.

## Tests

The offline R.8–R.42 suites passed on the first run except R.10. R.10 attempt 1 failed when Windows returned `WinError 5` replacing the R.10 synthetic safety file: 1 failed, 68 passed, 5 skipped. The separate retry passed: 69 passed, 5 skipped. `live_safety.py` was not changed.

## Remaining blockers

Account product and stake rules, financing, fresh candles after 2026-10-09, and the absence of a reserved holdout. None of these were collected in this stage.

R.44 was not started.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
