# MACRO RESEARCH — STAGE 3
# US PIT MACRO × HISTORICAL FX EVENT MINING

Research only. No surprise. No trading-rule optimization. No production change.
Helpers/tests/report only. Stage-2 `data/research/macro/us_pit/` was read, not modified.
Historical FX CSVs were read, not modified.

Primary independent unit = **macro event** (n=29). Six pair responses to one release are correlated.

DATASET
-------
macro inventory: 32
eligible archived events: 29
excluded: [{"macro_event_id": "usd_cpi_unpublished_2025-10", "reasons": ["archive_status=OFFICIALLY_UNPUBLISHED", "no_hash", "no_timestamp", "officially_unpublished", "pit_status=UNKNOWN"]}, {"macro_event_id": "usd_cpi_2026-08-12", "reasons": ["archive_status=RETRIEVAL_BLOCKED", "no_hash", "pit_status=UNKNOWN", "retrieval_blocked"]}, {"macro_event_id": "usd_empsit_unpublished_2025-10", "reasons": ["archive_status=OFFICIALLY_UNPUBLISHED", "no_hash", "no_timestamp", "officially_unpublished", "pit_status=UNKNOWN"]}]
CPI n: 10
Employment n: 11
FOMC n: 8
FX pairs: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF
FX window: 2025-09-01T00:00:00Z through 2026-08-31T23:50:00Z

LOOKAHEAD AUDIT
---------------
All 29 eligible T0 timestamps fall on M5 boundaries.
T0 = official scheduled_release_utc.
Last completed pre bar = floor_m5(T0) − 5m (bar_start + 5m <= T0).
Containing bar starts at T0. Its **open** is the first M5 snapshot at T0 (not known before T0).
+5m uses that bar's **close** (first completed post-T0 bar). Later horizons use the close of the bar that completes at T0+h.
Pre-release windows use only completed closes at or before last completed bar.
No future-containing-bar close enters pre-release features.

EVENT-CONDITIONED VOLATILITY
----------------------------
Question: do major US releases create measurably different movement magnitude from ordinary comparable periods?

Control (frozen before seeing magnitudes): same UTC weekday and HH:MM as an eligible T0; inside the FX window with 240m padding; **not** within ±240m of any eligible T0; median USD-normalized mid pips across six pairs; compare **absolute** median. All matches kept (n_control=458).

| horizon | event n | event median |abs USD pips| | event bootstrap 95% CI | control median |abs| at 60m |
| ---: | ---: | ---: | --- | ---: |
| 5 | 29 | 11.35 | 8.97–18.85 |  |
| 15 | 29 | 14.05 | 10.80–22.32 |  |
| 30 | 29 | 13.30 | 9.15–23.33 |  |
| 60 | 29 | 17.67 | 12.32–27.37 | 4.94 (n=458) |
| 120 | 29 | 20.15 | 11.20–37.88 |  |
| 240 | 29 | 26.77 | 11.67–38.40 |  |

Event-level 60m |median USD pips| 17.67 vs matched-control 4.94. Event bootstrap CI does not include the control median. This is **magnitude**, not direction. Classification: DESCRIPTIVE CANDIDATE — REPEATED ACROSS EVENTS (environment), **not** validated alpha.

Family 60m cumulative |median USD pips| (event-level bootstrap):
CPI n=10 median 14.06 CI 10.95–19.55
Employment n=11 median 15.93 CI 8.48–40.77
FOMC n=8 median 26.86 CI 17.67–46.20

MOVEMENT TIMING
---------------
Event-level |incremental| median USD pips (ALL n=29):
0–5m 11.35; 5–15m 4.95; 15–30m 4.35; 30–60m 5.23; 60–120m 8.42; 120–240m 6.45

Largest increment is the first completed post-T0 5-minute bar. Meaningful additional |move| continues after that, especially 60–120m. Not a trading rule.

USD CROSS-PAIR SYNCHRONIZATION
------------------------------
Max agreement among six USD-normalized pair signs at +60m: event median 6/6; 6/6 on 20/29 events (69.0%).
Matched controls: median max-agree 5/6; 6/6 fraction 39.3% (n=458).
Horizon max-agree counts (events): 5m {'6': 22, '5': 7}; 15m {'6': 18, '5': 9, '4': 2}; 30m {'6': 19, '4': 2, '5': 6, '3': 2}; 60m {'6': 20, '4': 1, '5': 8}; 120m {'6': 17, '4': 3, '3': 2, '5': 7}; 240m {'6': 18, '5': 6, '4': 4, '3': 1}.
Genuine US releases in this sample often produce coherent USD-wide M5 moves. Six pairs remain **one** event.

INITIAL MOVE CONTINUATION / REVERSAL
------------------------------------
Initial move = event-level median USD-normalized mid pips over the first completed post-T0 5m bar. Compared with later cumulative horizons. n visible. Not optimized.

ALL n=29: 15m {'continuation': 27, 'reversal': 2, 'n': 29}; 30m {'continuation': 26, 'reversal': 3, 'n': 29}; 60m {'continuation': 23, 'reversal': 6, 'n': 29}; 120m {'continuation': 22, 'reversal': 7, 'n': 29}; 240m {'continuation': 21, 'reversal': 8, 'n': 29}
CPI n=10: 60m {'continuation': 9, 'reversal': 1, 'n': 10}
Employment n=11: 60m {'continuation': 9, 'reversal': 2, 'n': 11}
FOMC n=8: 60m {'reversal': 3, 'continuation': 5, 'n': 8}

5m→15m continuation is common (27/29) but later horizons overlap the initial window, so this is **not** independent evidence of an edge. Classification: DESCRIPTIVE CANDIDATE — UNSTABLE (no control comparison; overlapping windows).

PRE-RELEASE VS POST-RELEASE
---------------------------
Pre −60m completed USD median sign vs post +60m (event-level).
ALL {'continuation': 16, 'reversal': 13, 'n': 29}; CPI {'continuation': 8, 'reversal': 2, 'n': 10}; Employment {'continuation': 6, 'reversal': 5, 'n': 11}; FOMC {'reversal': 6, 'continuation': 2, 'n': 8}
No stable continue-or-reverse rule. FOMC 6/8 pre-move reversals is case-study scale. Classification: NO APPARENT INFORMATION / INSUFFICIENT EVENTS.

FIRST-PRINT VALUE ANALYSIS
--------------------------
Not surprise. published_change = headline_mom − previous_as_reported only when both are 1-month SA prints. Nov 2025 2-month CPI excluded from accel/decel.

CPI accel vs 60m median USD pips: {'accel': {'n': 2, 'median_usd_pips_60': -3.762500000000336, 'events': ['usd_cpi_2025-09-11', 'usd_cpi_2026-03-11']}, 'decel': {'n': 1, 'median_usd_pips_60': -16.200000000000102, 'events': ['usd_cpi_2025-10-24']}}
NFP sign vs 60m: {'nfp_positive': {'n': 9, 'median_usd_pips_60': -8.47500000000001, 'events': ['usd_empsit_2025-09-05', 'usd_empsit_2025-11-20', 'usd_empsit_2025-12-16', 'usd_empsit_2026-01-09', 'usd_empsit_2026-02-11', 'usd_empsit_2026-04-03', 'usd_empsit_2026-05-08', 'usd_empsit_2026-06-05', 'usd_empsit_2026-07-02']}, 'nfp_negative': {'n': 2, 'median_usd_pips_60': -18.850000000001767, 'events': ['usd_empsit_2026-03-06', 'usd_empsit_2026-08-07']}}
FOMC cut vs hold vs 60m: {'cut': {'n': 3, 'median_usd_pips_60': 18.700000000000937, 'events': ['usd_fomc_statement_2025-09-17', 'usd_fomc_statement_2025-10-29', 'usd_fomc_statement_2025-12-10']}, 'hold': {'n': 5, 'median_usd_pips_60': 14.47500000000046, 'events': ['usd_fomc_statement_2026-01-28', 'usd_fomc_statement_2026-03-18', 'usd_fomc_statement_2026-04-29', 'usd_fomc_statement_2026-06-17', 'usd_fomc_statement_2026-07-29']}}

CPI accel n=2 / decel n=1. NFP negative n=2. FOMC cuts n=3 and holds n=5 both show positive median USD pips in this sample — **not** a cut=USD-down rule. Classification: INSUFFICIENT EVENTS.

CPI EVENT TABLE
---------------
USD pips = event-level median of six pair USD-normalized **mid** moves (not executable P&L).
| event | T0 UTC | ref | first-print | 5m | 15m | 30m | 60m | 120m | 240m | 60m USD agree |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| usd_cpi_2025-09-11 | 2025-09-11T12:30:00Z | 2025-08 | MoM 0.4; YoY 2.9; core 0.3/3.1 | -19.70 | -12.62 | -23.33 | -19.55 | -38.88 | -52.50 | 6/6 USD- 0up/6dn |
| usd_cpi_2025-10-24 | 2025-10-24T12:30:00Z | 2025-09 | MoM 0.3; YoY 3.0; core 0.2/3.0 | -25.52 | -26.62 | -18.15 | -16.20 | -8.27 | -5.60 | 6/6 USD- 0up/6dn |
| usd_cpi_2025-12-18 | 2025-12-18T13:30:00Z | 2025-11 | MoM None; YoY 2.7; core None/2.6; 2m 0.2 | -7.37 | -10.75 | -13.30 | -11.03 | -1.25 | 1.98 | 6/6 USD- 0up/6dn |
| usd_cpi_2026-01-13 | 2026-01-13T13:30:00Z | 2025-12 | MoM 0.3; YoY 2.7; core 0.2/2.6 | -17.07 | -13.53 | -9.65 | -12.32 | 10.18 | 17.92 | 6/6 USD- 0up/6dn |
| usd_cpi_2026-02-13 | 2026-02-13T13:30:00Z | 2026-01 | MoM 0.2; YoY 2.4; core 0.3/2.5 | -17.12 | -5.57 | -21.27 | -22.18 | -17.70 | -26.77 | 6/6 USD- 0up/6dn |
| usd_cpi_2026-03-11 | 2026-03-11T12:30:00Z | 2026-02 | MoM 0.3; YoY 2.4; core 0.2/2.5 | 11.30 | 10.80 | 19.72 | 12.02 | 6.70 | 28.57 | 6/6 USD+ 6up/0dn |
| usd_cpi_2026-04-10 | 2026-04-10T12:30:00Z | 2026-03 | MoM 0.9; YoY 3.3; core 0.2/2.6 | -4.15 | -2.35 | -1.53 | -15.80 | -20.15 | 5.22 | 6/6 USD- 0up/6dn |
| usd_cpi_2026-05-12 | 2026-05-12T12:30:00Z | 2026-04 | MoM 0.6; YoY 3.8; core 0.4/2.8 | -1.60 | -5.10 | -6.65 | 1.60 | 4.05 | 5.75 | 4/6 USD+ 4up/2dn |
| usd_cpi_2026-06-10 | 2026-06-10T12:30:00Z | 2026-05 | MoM 0.5; YoY 4.2; core 0.2/2.9 | -2.93 | -9.43 | 1.17 | -9.88 | -10.63 | -4.18 | 6/6 USD- 0up/6dn |
| usd_cpi_2026-07-14 | 2026-07-14T12:30:00Z | 2026-06 | MoM -0.4; YoY 3.5; core 0.0/2.6 | -34.60 | -41.10 | -23.90 | -32.87 | -30.68 | -19.70 | 6/6 USD- 0up/6dn |

EMPLOYMENT EVENT TABLE
----------------------
| event | T0 UTC | ref | first-print | 5m | 15m | 30m | 60m | 120m | 240m | 60m USD agree |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| usd_empsit_2025-09-05 | 2025-09-05T12:30:00Z | 2025-08 | NFP 22000; u 4.3; AHE 0.3 | -27.55 | -29.42 | -32.12 | -27.37 | -35.12 | -53.72 | 5/6 USD- 1up/5dn |
| usd_empsit_2025-11-20 | 2025-11-20T13:30:00Z | 2025-09 | NFP 119000; u 4.4; AHE 0.2 | -9.73 | -15.07 | -13.33 | -15.93 | -6.75 | -11.38 | 5/6 USD- 1up/5dn |
| usd_empsit_2025-12-16 | 2025-12-16T13:30:00Z | 2025-11 | NFP 64000; u 4.6; AHE 0.1 | -5.07 | 5.65 | -2.00 | -8.48 | 0.13 | -5.17 | 5/6 USD- 1up/5dn |
| usd_empsit_2026-01-09 | 2026-01-09T13:30:00Z | 2025-12 | NFP 50000; u 4.4; AHE 0.3 | -8.97 | -16.33 | -7.48 | 5.65 | 15.03 | 17.75 | 5/6 USD+ 5up/1dn |
| usd_empsit_2026-02-11 | 2026-02-11T13:30:00Z | 2026-01 | NFP 130000; u 4.3; AHE 0.4 | 47.88 | 25.13 | 33.58 | 33.63 | 40.20 | 1.02 | 5/6 USD+ 5up/1dn |
| usd_empsit_2026-03-06 | 2026-03-06T13:30:00Z | 2026-02 | NFP -92000; u 4.4; AHE 0.4 | -18.77 | -22.32 | 4.15 | 9.32 | -11.85 | -33.10 | 5/6 USD+ 5up/1dn |
| usd_empsit_2026-04-03 | 2026-04-03T12:30:00Z | 2026-03 | NFP 178000; u 4.3; AHE 0.2 | 9.92 | 7.95 | 9.15 | 7.52 | 15.02 | 17.32 | 5/6 USD+ 5up/1dn |
| usd_empsit_2026-05-08 | 2026-05-08T12:30:00Z | 2026-04 | NFP 115000; u 4.3; AHE 0.2 | -11.15 | -11.00 | -7.02 | -10.75 | -2.33 | -11.67 | 5/6 USD- 1up/5dn |
| usd_empsit_2026-06-05 | 2026-06-05T12:30:00Z | 2026-05 | NFP 172000; u 4.3; AHE 0.3 | 15.80 | 21.63 | 40.42 | 41.90 | 64.70 | 79.02 | 6/6 USD+ 6up/0dn |
| usd_empsit_2026-07-02 | 2026-07-02T12:30:00Z | 2026-06 | NFP 57000; u 4.2; AHE 0.3 | -46.35 | -68.27 | -46.00 | -40.77 | -43.58 | -40.37 | 6/6 USD- 0up/6dn |
| usd_empsit_2026-08-07 | 2026-08-07T12:30:00Z | 2026-07 | NFP -23000; u 4.1; AHE None | -46.40 | -45.13 | -48.43 | -47.03 | -38.45 | -42.98 | 6/6 USD- 0up/6dn |

FOMC EVENT TABLE
----------------
Case-study only (n=8). Three cuts, five holds. No high-confidence FOMC trading rule.
| event | T0 UTC | ref | first-print | 5m | 15m | 30m | 60m | 120m | 240m | 60m USD agree |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| usd_fomc_statement_2025-09-17 | 2025-09-17T18:00:00Z | 2025-09-16/17 | cut -25bp 4.0-4.25 | -33.82 | -29.67 | -25.32 | 18.70 | 22.95 | 29.70 | 6/6 USD+ 6up/0dn |
| usd_fomc_statement_2025-10-29 | 2025-10-29T18:00:00Z | 2025-10-28/29 | cut -25bp 3.75-4.0 | 7.47 | 14.05 | 11.13 | 46.20 | 42.50 | 40.05 | 6/6 USD+ 6up/0dn |
| usd_fomc_statement_2025-12-10 | 2025-12-10T19:00:00Z | 2025-12-09/10 | cut -25bp 3.5-3.75 | -11.35 | -13.57 | -7.95 | -22.27 | -37.88 | -38.40 | 6/6 USD- 0up/6dn |
| usd_fomc_statement_2026-01-28 | 2026-01-28T19:00:00Z | 2026-01-27/28 | hold 0bp 3.5-3.75 | 6.87 | 4.10 | 10.97 | -17.67 | -28.45 | -31.67 | 6/6 USD- 0up/6dn |
| usd_fomc_statement_2026-03-18 | 2026-03-18T18:00:00Z | 2026-03-17/18 | hold 0bp 3.5-3.75 | -3.62 | 1.32 | 5.33 | 31.45 | 43.97 | 39.65 | 6/6 USD+ 6up/0dn |
| usd_fomc_statement_2026-04-29 | 2026-04-29T18:00:00Z | 2026-04-28/29 | hold 0bp 3.5-3.75 | 8.93 | 15.20 | 12.35 | 14.48 | 11.20 | 11.40 | 6/6 USD+ 6up/0dn |
| usd_fomc_statement_2026-06-17 | 2026-06-17T18:00:00Z | 2026-06-16/17 | hold 0bp 3.5-3.75 | 31.20 | 36.92 | 34.25 | 42.90 | 83.05 | 69.92 | 6/6 USD+ 6up/0dn |
| usd_fomc_statement_2026-07-29 | 2026-07-29T18:00:00Z | 2026-07-28/29 | hold 0bp 3.5-3.75 | -18.85 | -28.82 | -25.50 | -50.58 | -37.97 | -50.53 | 6/6 USD- 0up/6dn |

MFE / MAE
---------
Hypothetical USD-long / USD-short using genuine bid/ask after T0, M5 OHLC path to each fixed horizon. Event-level = median across pairs. **Not** tick-level. Stops/targets not optimized.
USD-long 5m MFE/MAE 0.70/19.10; 60m 6.75/28.65
USD-short 5m 14.00/12.55; 60m 21.00/15.90
Pooled long vs short MAE/MFE is dominated by whichever USD direction the event realized. Distributional only.

SPREAD BEHAVIOR
---------------
M5 OHLC cannot reconstruct tick-level max spread inside the release candle. Pair pip sizes differ (JPY 0.01).
Median pair pips, last completed pre close vs T0 bar open vs +60m close:
{
  "EUR_USD": {
    "median_pre_close_pips": 3.8000000000004697,
    "median_t0_open_pips": 3.8000000000004697,
    "median_60m_close_pips": 1.5999999999993797
  },
  "GBP_USD": {
    "median_pre_close_pips": 6.200000000000649,
    "median_t0_open_pips": 7.299999999998974,
    "median_60m_close_pips": 1.900000000001345
  },
  "USD_JPY": {
    "median_pre_close_pips": 6.299999999998818,
    "median_t0_open_pips": 6.099999999997863,
    "median_60m_close_pips": 1.6999999999995907
  },
  "AUD_USD": {
    "median_pre_close_pips": 3.1000000000003247,
    "median_t0_open_pips": 3.3000000000005247,
    "median_60m_close_pips": 1.2999999999996348
  },
  "USD_CAD": {
    "median_pre_close_pips": 4.999999999999449,
    "median_t0_open_pips": 4.899999999998794,
    "median_60m_close_pips": 1.7999999999984695
  },
  "USD_CHF": {
    "median_pre_close_pips": 4.8000000000003595,
    "median_t0_open_pips": 5.5000000000005045,
    "median_60m_close_pips": 1.4999999999998348
  }
}
No tick-level execution-quality claim.

MATCHED NON-EVENT CONTROLS
--------------------------
Definition above. Questions answered: 60m |USD median pips| is larger on events than controls; 6/6 USD-sign agreement is more frequent on events (69.0% vs 39.3%). MFE/MAE was not re-optimized as a strategy grid.

MULTIPLE TESTING
----------------
independent macro events: 29
analyses/comparisons: ~48 (eligibility; |move| at 6 horizons; family cumulatives; 6 increment buckets × 4 groups; sync at 6 horizons + vs control; continuation at 5 horizons × 4 groups; pre/post × 4 groups; CPI accel; NFP sign; FOMC cut/hold; MFE/MAE 6h × 2 sides; spread)
Pair-row n is **not** the sample size. Bootstrap CIs resample **events**.
No finding is an edge because one cell looked good.

WHAT WE STILL CANNOT TEST
-------------------------
actual − market consensus
standardized economic surprise
beat/miss versus expectation
pre-release expected policy probability (e.g. OIS/futures implied cut odds)
Do not infer consensus from the post-release price path.

PROSPECTIVE HYPOTHESES WORTH FREEZING
-------------------------------------
1. **Event-conditioned USD |move| at +60m.** At official CPI / Employment Situation / FOMC statement T0, the absolute event-level median USD-normalized M5 mid move from T0-bar open to the close of the bar completing at T0+60m is larger than the same statistic on matched non-event weekday+UTC-clock times outside ±240m of any eligible T0. Direction: magnitude only (no USD long/short). Information at decision time: official release timestamp and event family membership (not first-print value, not consensus). Scope: the three US families jointly. Survived because event median 17.67 pips vs control 4.94 with event bootstrap CI excluding the control median. Still **not** validated alpha.
2. **Cross-pair USD agreement at +60m.** Eligible US releases produce 6/6 USD-direction agreement more often than the same matched controls. Information at T0: release timestamp/family. Scope: all three families jointly. Survived as a repeated descriptive pattern in this window (69.0% vs 39.3%). Not a trade.

No third hypothesis: first-print sign, FOMC cut vs hold, and pre-release continuation/reversal did not survive as stable, pre-specifiable directional relationships.

DATA SUFFICIENT FOR MACRO MODEL TRAINING:
NO
DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM:
NO
SURPRISE BACKTEST POSSIBLE:
NO
PRODUCTION CHANGE JUSTIFIED:
NO
V2 POLICY CHANGE:
NO
MODEL TRAINED:
NO
OANDA/API REQUESTS:
0
SOURCE DATA MODIFIED:
NO
FILES CHANGED:
research helpers/tests/report only
STOP.
