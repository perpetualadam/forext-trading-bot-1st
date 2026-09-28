# MACRO RESEARCH — STAGE 4
# EARLY USD SYNCHRONIZATION → NON-OVERLAPPING FORWARD MOVEMENT

Research only. Stage-3 H1/H2 definitions were not altered.
Primary independent unit = **macro event**. Six pairs are correlated responses to one release.
Helpers/tests/report only. `data/research/macro/us_pit/` and `data/historical/*_M5.csv` were read, not modified.
No OANDA requests. No model. No live rule.

LOOKAHEAD
---------
T0 = official scheduled_release_utc (all 29 eligible T0s fall on M5 boundaries).
D = T0 + 5 minutes = close of the T0 M5 bar, the first completed post-release candle.
Features at D use only that T0 bar: open to close. The bar that starts at D is unknown at D and is not a feature.
Targets are strictly non-overlapping with the feature candle: remaining movement from T0-bar close to the close of the bar completing at T0+H.
H in {15, 30, 60, 120, 240} minutes. Exit bar start = T0+H-5m, which is >= D for every listed H.
These are not Stage-3 cumulative T0 to future returns. Stage-3 overlapping 5m to 60m continuation is not reused as a prediction target.

DATASET:
eligible events: 29
CPI: 10
Employment: 11
FOMC: 8
controls: 458 (Stage-3 matched weekday+UTC HH:MM, window padding 240m, outside +/-240m of eligible T0; T0 bar and +60m exit bar required on all six pairs)
excluded: unpublished Oct-2025 CPI, unpublished Oct-2025 Employment, retrieval-blocked 2026-08-12 CPI

FIRST-5M AGREEMENT:
3/6: 0
4/6: 0
5/6: 7
6/6: 22
Zeros do not count as agreement. No weighted voting. Natural categories were not recombined after seeing results.

PRIMARY 6/6 TEST:
n: 22
+5->+15 continuation: 12/22 (54.5%, event bootstrap 95% CI 31.8%-77.3%); reversals 10; flats 0
+5->+30 continuation: 10/22 (45.5%, CI 27.3%-68.2%); reversals 12; flats 0
+5->+60 continuation: 12/22 (54.5%, CI 36.4%-77.3%); reversals 10; flats 0
Bootstrap resamples events, not pair-rows. All three primary CIs include 50%.

SECONDARY AGREEMENT (descriptive; not a threshold search):
5/6 n=7; +5->+15 4/7 cont, 3 rev, 0 flat; +5->+30 3/7 cont, 4 rev, 0 flat; +5->+60 4/7 cont, 3 rev, 0 flat
4/6 n=0 (no events in this sample)
3/6 n=0 (no events in this sample)

REMAINING MOVEMENT:
6/6 first-5m median |USD| mid pips (already realized by D): 17.10
6/6 subsequent median signed / |USD| mid pips:
+5->+15: -1.70 / 5.09
+5->+30: 3.82 / 4.27
+5->+60: 0.34 / 6.90
+5->+120: 3.78 / 11.11
+5->+240: 6.66 / 17.03
5/6 subsequent signed / |USD|:
+5->+15 1.53 / 3.02; +5->+30 3.95 / 4.82; +5->+60 1.52 / 6.87; +5->+120 3.78 / 9.92; +5->+240 6.85 / 8.98
4/6 and 3/6: n=0, remaining movement NA.
Median M5 spread at D across event-pair closes: 1.70 pips (M5 bid/ask; not tick-level).

EXECUTABLE AFTER-COST OUTCOMES:
Hypothetical USD-direction expression at D. USD-strength: SELL EUR_USD, GBP_USD, AUD_USD; BUY USD_JPY, USD_CAD, USD_CHF. Reverse for USD-weakness.
Entry uses completed T0 close available at D: BUY ask_close, SELL bid_close. Exit later: BUY bid_close, SELL ask_close.
No sizing. No production SL/TP. No exit optimization. Event-level statistic = median of six pair executable pips.
6/6 +5->+15: 0.07 event-median; -0.20 per-pair-median; pos 11 / neg 11 / flat 0 (n=22)
6/6 +5->+30: -2.60 event-median; -2.25 per-pair-median; pos 8 / neg 14 / flat 0 (n=22)
6/6 +5->+60: -1.00 event-median; -2.30 per-pair-median; pos 8 / neg 14 / flat 0 (n=22)
6/6 +5->+120: -4.95 event-median; -4.30 per-pair-median; pos 7 / neg 15 / flat 0 (n=22)
6/6 +5->+240: -1.37 event-median; -2.80 per-pair-median; pos 9 / neg 13 / flat 0 (n=22)

FAMILY BREAKDOWN:
Descriptive case-study only. CPI n~10, Employment n~11, FOMC n=8. Do not select a family for deployment.
CPI n=10, 6/6 n=7; +5->+15 3/7 cont, 4 rev, 0 flat; +5->+60 5/7 cont, 2 rev, 0 flat; remaining |USD| 5->60 -0.65 / 2.62; exec 5->60 -0.70 event-median; -1.60 per-pair-median; pos 2 / neg 5 / flat 0 (n=7)
Employment n=11, 6/6 n=8; +5->+15 4/8 cont, 4 rev, 0 flat; +5->+60 2/8 cont, 6 rev, 0 flat; remaining |USD| 5->60 1.45 / 6.63; exec 5->60 -6.07 event-median; -7.50 per-pair-median; pos 1 / neg 7 / flat 0 (n=8)
FOMC n=8, 6/6 n=7; +5->+15 5/7 cont, 2 rev, 0 flat; +5->+60 5/7 cont, 2 rev, 0 flat; remaining |USD| 5->60 6.45 / 26.88; exec 5->60 9.40 event-median; 6.85 per-pair-median; pos 5 / neg 2 / flat 0 (n=7)
FOMC 6/6 remaining |move| and after-cost median look larger, but n=7. Not a frozen family rule.

MATCHED CONTROL COMPARISON:
Same T0 to +5 observation and non-overlapping remaining windows on Stage-3 matched non-event clocks.
Control first-5m agreement: 6/6 197; 5/6 120; 4/6 91; 3/6 49 of 458
Control 6/6 n=197 of 458 (43.0%) vs events 22/29 (75.9%). Early 6/6 is more common after releases (environment), consistent with Stage-3 H2 being about synchronization frequency, not remaining-direction prediction.
+5->+15 continuation: events 54.5% vs controls 45.7% (CI 38.6%-52.3%)
+5->+30 continuation: events 45.5% vs controls 53.3% (CI 46.2%-59.9%)
+5->+60 continuation: events 54.5% vs controls 45.2% (CI 38.6%-52.3%)
Control 6/6 remaining |USD| 5->60 median 5.35 vs event 6/6 6.90. Control 6/6 exec 5->60 -2.45 event-median; -2.30 per-pair-median; pos 71 / neg 126 / flat 0 (n=197).
Early sync is more frequent around events. Subsequent direction after D is not distinguishable from matched clocks.

CONDITIONAL MAGNITUDE (exploratory tertiles of |first-5m|; not a threshold search; not a trading rule):
low n=10 median remaining |5->60| 9.60
mid n=9 median remaining |5->60| 5.23
high n=10 median remaining |5->60| 6.89
Larger first-5m |USD| is not associated with larger remaining |5->60| in this sample (low tertile remaining is largest). Secondary only.

EVENT-LEVEL ROBUSTNESS:
Pooled 6/6 continuation is not a handful of identical rows: CPI and Employment 6/6 at +5->+60 are mixed continuation/reversal; FOMC 5/7 continuation. See table.

| event | family | T0 | 5m USD dir | agree | 5m med pips | 5->15 | 5->30 | 5->60 | 5->120 | 5->240 | 5->15 c | 5->30 c | 5->60 c | exec 5->60 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| usd_cpi_2025-09-11 | CPI | 2025-09-11T12:30:00Z | USD- | 6/6 | -19.70 | 7.80 | -0.58 | -1.60 | -18.58 | -34.10 | reversal | continuation | continuation | -0.25 |
| usd_cpi_2025-10-24 | CPI | 2025-10-24T12:30:00Z | USD- | 6/6 | -25.52 | -2.10 | 6.57 | 7.87 | 23.93 | 17.25 | continuation | reversal | reversal | -9.45 |
| usd_cpi_2025-12-18 | CPI | 2025-12-18T13:30:00Z | USD- | 6/6 | -7.37 | -2.85 | -5.68 | -2.62 | 4.93 | 8.15 | continuation | continuation | continuation | 1.20 |
| usd_cpi_2026-01-13 | CPI | 2026-01-13T13:30:00Z | USD- | 6/6 | -17.07 | 2.82 | 4.78 | 4.77 | 27.63 | 33.57 | reversal | reversal | reversal | -6.40 |
| usd_cpi_2026-02-13 | CPI | 2026-02-13T13:30:00Z | USD- | 6/6 | -17.12 | 9.65 | -0.85 | -5.23 | 1.08 | -7.80 | reversal | continuation | continuation | 3.55 |
| usd_cpi_2026-03-11 | CPI | 2026-03-11T12:30:00Z | USD+ | 6/6 | 11.30 | -0.15 | 8.95 | 1.03 | -2.15 | 16.80 | reversal | continuation | continuation | -0.70 |
| usd_cpi_2026-04-10 | CPI | 2026-04-10T12:30:00Z | USD- | 5/6 | -4.15 | 1.58 | 1.17 | -12.33 | -15.13 | 8.98 | reversal | reversal | continuation | 10.70 |
| usd_cpi_2026-05-12 | CPI | 2026-05-12T12:30:00Z | USD- | 5/6 | -1.60 | -3.02 | -4.82 | 4.38 | 3.78 | 6.85 | continuation | continuation | reversal | -5.95 |
| usd_cpi_2026-06-10 | CPI | 2026-06-10T12:30:00Z | USD- | 5/6 | -2.93 | -6.07 | 3.95 | -6.87 | -6.70 | -1.28 | continuation | reversal | continuation | 5.30 |
| usd_cpi_2026-07-14 | CPI | 2026-07-14T12:30:00Z | USD- | 6/6 | -34.60 | -7.53 | 6.85 | -0.65 | 3.95 | 15.60 | continuation | reversal | continuation | -0.90 |
| usd_empsit_2025-09-05 | EMPLOYMENT_SITUATION | 2025-09-05T12:30:00Z | USD- | 5/6 | -27.55 | -1.87 | -4.40 | -4.75 | 0.22 | -16.05 | continuation | continuation | continuation | 2.95 |
| usd_empsit_2025-11-20 | EMPLOYMENT_SITUATION | 2025-11-20T13:30:00Z | USD- | 6/6 | -9.73 | -5.02 | -3.28 | -7.35 | 2.47 | -1.32 | continuation | continuation | continuation | 5.80 |
| usd_empsit_2025-12-16 | EMPLOYMENT_SITUATION | 2025-12-16T13:30:00Z | USD- | 6/6 | -5.07 | 11.82 | 5.50 | -0.35 | 5.50 | -0.50 | reversal | reversal | continuation | -1.10 |
| usd_empsit_2026-01-09 | EMPLOYMENT_SITUATION | 2026-01-09T13:30:00Z | USD- | 6/6 | -8.97 | -6.97 | 2.00 | 13.00 | 22.05 | 22.30 | continuation | reversal | reversal | -14.65 |
| usd_empsit_2026-02-11 | EMPLOYMENT_SITUATION | 2026-02-11T13:30:00Z | USD+ | 6/6 | 47.88 | -16.47 | -16.00 | -22.55 | -10.15 | -42.18 | reversal | reversal | reversal | -24.40 |
| usd_empsit_2026-03-06 | EMPLOYMENT_SITUATION | 2026-03-06T13:30:00Z | USD- | 6/6 | -18.77 | 0.08 | 35.58 | 30.95 | 12.07 | -9.27 | reversal | reversal | reversal | -32.45 |
| usd_empsit_2026-04-03 | EMPLOYMENT_SITUATION | 2026-04-03T12:30:00Z | USD+ | 6/6 | 9.92 | -4.78 | -2.10 | -1.97 | 2.30 | 7.20 | reversal | reversal | reversal | -4.05 |
| usd_empsit_2026-05-08 | EMPLOYMENT_SITUATION | 2026-05-08T12:30:00Z | USD- | 5/6 | -11.15 | 1.53 | 8.32 | 1.52 | 9.92 | 1.35 | reversal | reversal | reversal | -3.35 |
| usd_empsit_2026-06-05 | EMPLOYMENT_SITUATION | 2026-06-05T12:30:00Z | USD+ | 5/6 | 15.80 | 7.17 | 24.35 | 25.82 | 50.33 | 70.03 | continuation | continuation | continuation | 24.40 |
| usd_empsit_2026-07-02 | EMPLOYMENT_SITUATION | 2026-07-02T12:30:00Z | USD- | 6/6 | -46.35 | -17.68 | 1.22 | 5.90 | 2.70 | 8.75 | continuation | reversal | reversal | -7.35 |
| usd_empsit_2026-08-07 | EMPLOYMENT_SITUATION | 2026-08-07T12:30:00Z | USD- | 6/6 | -46.40 | -1.30 | 0.83 | 3.25 | 6.15 | 6.13 | continuation | reversal | reversal | -4.80 |
| usd_fomc_statement_2025-09-17 | FOMC | 2025-09-17T18:00:00Z | USD- | 6/6 | -33.82 | 1.83 | 5.98 | 50.47 | 53.92 | 60.88 | reversal | reversal | reversal | -52.00 |
| usd_fomc_statement_2025-10-29 | FOMC | 2025-10-29T18:00:00Z | USD+ | 6/6 | 7.47 | 6.43 | 4.25 | 39.75 | 36.83 | 30.62 | continuation | continuation | continuation | 38.10 |
| usd_fomc_statement_2025-12-10 | FOMC | 2025-12-10T19:00:00Z | USD- | 6/6 | -11.35 | -2.35 | 4.30 | -11.10 | -27.80 | -25.70 | continuation | reversal | continuation | 9.40 |
| usd_fomc_statement_2026-01-28 | FOMC | 2026-01-28T19:00:00Z | USD+ | 6/6 | 6.87 | -3.17 | 4.10 | -26.88 | -35.30 | -39.63 | reversal | continuation | reversal | -28.70 |
| usd_fomc_statement_2026-03-18 | FOMC | 2026-03-18T18:00:00Z | USD- | 5/6 | -3.62 | 4.65 | 6.90 | 36.58 | 49.10 | 44.78 | reversal | reversal | reversal | -38.15 |
| usd_fomc_statement_2026-04-29 | FOMC | 2026-04-29T18:00:00Z | USD+ | 6/6 | 8.93 | 6.15 | 4.70 | 6.45 | 3.60 | 3.80 | continuation | continuation | continuation | 4.75 |
| usd_fomc_statement_2026-06-17 | FOMC | 2026-06-17T18:00:00Z | USD+ | 6/6 | 31.20 | 5.15 | 3.55 | 13.48 | 52.97 | 40.50 | continuation | continuation | continuation | 11.75 |
| usd_fomc_statement_2026-07-29 | FOMC | 2026-07-29T18:00:00Z | USD- | 6/6 | -18.85 | -8.85 | -3.48 | -33.38 | -15.97 | -31.70 | continuation | continuation | continuation | 31.70 |

MULTIPLE TESTING:
primary comparisons: 3
secondary comparisons: 3 remaining agreement categories x 5 horizons x (continuation, signed, abs, exec pos/neg) + 3 families + control comparisons + tertiles (~80 descriptive cells)
Do not convert secondary findings into validated alpha.

ANSWERS:
A: YES as a description — 22/29 eligible events (75.9%) have 6/6 first-5m USD agreement, vs 197/458 (43.0%) matched controls. Frequent enough to study. Not frequent-and-stable enough to train.
B: NO clear persistence. 6/6 continuation after D is 12/22 (54.5%) at +5->+15, 10/22 (45.5%) at +5->+30, 12/22 (54.5%) at +5->+60. Event-bootstrap CIs all include 50%.
C: SOME remaining |USD| exists (6/6 median |remaining| 5.09 / 4.27 / 6.90 / 11.11 / 17.03 pips at the five horizons) but it is smaller than the first-5m move already observed (6/6 median |first-5m| 17.10 pips) and signed remaining is near zero because continuations and reversals mix.
D: NO at the event-median. After genuine bid/ask, 6/6 median executable pips are +0.07 (11 pos / 11 neg) at +5->+15, -2.60 (8/14) at +5->+30, -1.00 (8/14) at +5->+60. Gross remaining movement does not survive costs as an event-level median.
E: Early 6/6 is more common on event clocks than controls (75.9% vs 43.0%), which is an environment fact. Subsequent directional continuation after D is not stronger than matched non-event 6/6 clocks (control 45.7% / 53.3% / 45.2% at the three primary horizons).
F: NO — INSUFFICIENT / UNSTABLE. n=22 primary rows; rates straddle 50% across the three pre-registered horizons; family split is unstable (Employment 6/6 +5->+60 is 2/8 continuation; FOMC 5/7). Do not freeze a prospective directional hypothesis.

PROSPECTIVE DIRECTIONAL HYPOTHESIS FROZEN:
NONE

DATA SUFFICIENT FOR MODEL TRAINING:
NO
DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM:
NO
SURPRISE DATA AVAILABLE:
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
