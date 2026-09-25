# V2 shadow - second offline outcome checkpoint

RESEARCH / DESCRIPTIVE ONLY. V2 remains SKIP. No live trading change.
Scorer semantics unchanged: BUY ask->future bid_close; SELL bid->future ask_close;
horizons 5/15/30/60/120/240; direction_correct = forward_pips > 0; no mid fallback.

PREFLIGHT:
observations=2941
unique_decision_ids=2941
observation_range=2026-09-24T10:26:54.809816+00:00 -> 2026-09-25T20:03:24.226553+00:00
malformed_observations=0
malformed_market_rows=0
market_duplicates=0
existing_outcome_rows=1267
existing_logical_keys=14020
malformed_outcomes=0
store_safe=True
historical_duplicates=0
historical_conflicts=0
market_by_symbol:
  EUR_USD: rows=688 usable=688 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00
  GBP_USD: rows=688 usable=688 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00
  USD_JPY: rows=688 usable=688 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00
  AUD_USD: rows=688 usable=688 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00
  USD_CAD: rows=688 usable=688 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00
  USD_CHF: rows=687 usable=687 first=2026-09-23T11:40:00+00:00 last=2026-09-25T20:55:00+00:00

CURRENT OBSERVATIONS: 2941
CURRENT UNIQUE OPPORTUNITIES: 671
STRICTLY POST-CHECKPOINT OPPORTUNITIES: 381
OUTCOME STORE BEFORE: 1267 rows / 14020 logical keys

FIRST SCORING PASS:
new outcome rows: 2018
existing/skipped: already_exists=923 no_mature=0 no_market=0 bad_decision=0
conflicts: 0
logical_labels_written: 21014

SECOND IDENTICAL PASS:
new writes: 0
skipped: already_exists=2941 no_mature=0
conflicts: 0

HORIZON COVERAGE (all observations):
Hz   eligible  scored  missing/not-yet-mature
5    2936      2936    5
15   2941      2941    0
30   2936      2936    5
60   2932      2932    9
120  2903      2903    38
240  2869      2869    72

UNIQUE-OPPORTUNITY COVERAGE:
Hz   eligible  scored  missing/not-yet-mature
5    670       670     1
15   671       671     0
30   670       670     1
60   669       669     2
120  663       663     8
240  654       654     17

FULL OBSERVATION-WEIGHTED LABEL HEALTH:
Hz   BUY n  BUY hit  BUY mean  BUY med   SELL n  SELL hit  SELL mean  SELL med  BUY+SELL mean
5    2936   0.277   -1.81    -1.40   2936   0.264    -1.39     -1.60    -3.20
15   2941   0.353   -1.86    -1.40   2941   0.333    -1.38     -1.60    -3.24
30   2936   0.413   -1.60    -1.00   2936   0.344    -1.60     -2.10    -3.20
60   2932   0.441   -1.17    -0.90   2932   0.357    -2.16     -2.50    -3.34
120  2903   0.485   -0.41    -0.20   2903   0.338    -2.88     -3.10    -3.29
240  2869   0.426   -2.62    -1.40   2869   0.409    -0.64     -1.90    -3.26

FULL DEDUPLICATED LABEL HEALTH:
Hz   BUY n  BUY hit  BUY mean  BUY med   SELL n  SELL hit  SELL mean  SELL med  BUY+SELL mean
5    670    0.321   -1.70    -1.30   670    0.279    -1.51     -1.80    -3.21
15   671    0.374   -1.72    -1.40   671    0.334    -1.53     -1.70    -3.25
30   670    0.409   -1.43    -0.90   670    0.339    -1.77     -2.20    -3.20
60   669    0.457   -1.05    -0.80   669    0.351    -2.27     -2.70    -3.32
120  663    0.481   -0.45    -0.20   663    0.345    -2.83     -3.00    -3.28
240  654    0.437   -2.26    -1.10   654    0.396    -1.02     -2.35    -3.28

POST-CHECKPOINT DEDUPLICATED LABEL HEALTH:
Hz   BUY n  BUY hit  BUY mean  BUY med   SELL n  SELL hit  SELL mean  SELL med  BUY+SELL mean
5    381    0.310   -1.85    -1.40   381    0.302    -1.15     -1.60    -3.00
15   381    0.367   -1.99    -1.40   381    0.346    -1.00     -1.50    -2.99
30   381    0.399   -1.77    -0.80   381    0.325    -1.22     -2.10    -2.99
60   380    0.445   -1.61    -0.90   380    0.371    -1.38     -2.20    -2.99
120  374    0.476   -1.08    -0.30   374    0.382    -1.89     -2.75    -2.97
240  364    0.462   -3.78    -0.70   364    0.398    +0.78     -2.45    -3.00

OLD VS NEW VS COMBINED:
OLD = first validated checkpoint (deduplicated).
NEW = strictly post-checkpoint unique opportunities.
COMBINED = current full unique-opportunity set.
Differences are NEW-OLD and COMBINED-OLD. Not optimized thresholds.

Hz   view       BUY n  BUY hit  d_hit    BUY mean  d_mean   SELL n  SELL hit  d_hit    SELL mean  d_mean
5    OLD        284    0.342   -        -1.36    -        284    0.254    -        -1.81     -
5    NEW        381    0.310   -0.032    -1.85    -0.49   381    0.302    +0.048    -1.15     +0.67
5    COMBINED   670    0.321   -0.021    -1.70    -0.34   670    0.279    +0.026    -1.51     +0.30
15   OLD        284    0.391   -        -1.22    -        284    0.324    -        -2.05     -
15   NEW        381    0.367   -0.023    -1.99    -0.77   381    0.346    +0.023    -1.00     +1.05
15   COMBINED   671    0.374   -0.017    -1.72    -0.50   671    0.334    +0.010    -1.53     +0.52
30   OLD        279    0.437   -        -0.86    -        279    0.369    -        -2.25     -
30   NEW        381    0.399   -0.038    -1.77    -0.91   381    0.325    -0.044    -1.22     +1.02
30   COMBINED   670    0.409   -0.028    -1.43    -0.57   670    0.339    -0.030    -1.77     +0.48
60   OLD        272    0.496   -        -0.08    -        272    0.342    -        -3.27     -
60   NEW        380    0.445   -0.052    -1.61    -1.53   380    0.371    +0.029    -1.38     +1.89
60   COMBINED   669    0.457   -0.039    -1.05    -0.97   669    0.351    +0.009    -2.27     +1.00
120  OLD        252    0.536   -        +0.95    -        252    0.294    -        -4.22     -
120  NEW        374    0.476   -0.060    -1.08    -2.03   374    0.382    +0.089    -1.89     +2.33
120  COMBINED   663    0.481   -0.055    -0.45    -1.40   663    0.345    +0.052    -2.83     +1.39
240  OLD        209    0.507   -        +0.96    -        209    0.335    -        -4.28     -
240  NEW        364    0.462   -0.046    -3.78    -4.74   364    0.398    +0.063    +0.78     +5.05
240  COMBINED   654    0.437   -0.070    -2.26    -3.21   654    0.396    +0.061    -1.02     +3.25

POST-CHECKPOINT SYMBOL BREAKDOWN:
EUR_USD: n=45
    5m  BUY hit=0.244 mean=-1.50 n=45   SELL hit=0.467 mean=-0.77 n=45
   15m  BUY hit=0.222 mean=-2.00 n=45   SELL hit=0.556 mean=-0.28 n=45
   30m  BUY hit=0.289 mean=-1.51 n=45   SELL hit=0.467 mean=-0.78 n=45
   60m  BUY hit=0.267 mean=-2.25 n=45   SELL hit=0.578 mean=-0.05 n=45
  120m  BUY hit=0.378 mean=-0.82 n=45   SELL hit=0.422 mean=-1.48 n=45
  240m  BUY hit=0.273 mean=-3.08 n=44   SELL hit=0.659 mean=+0.78 n=44
GBP_USD: n=56
    5m  BUY hit=0.429 mean=-0.86 n=56   SELL hit=0.232 mean=-2.29 n=56
   15m  BUY hit=0.446 mean=-1.00 n=56   SELL hit=0.393 mean=-2.15 n=56
   30m  BUY hit=0.357 mean=-0.78 n=56   SELL hit=0.304 mean=-2.37 n=56
   60m  BUY hit=0.518 mean=+0.90 n=56   SELL hit=0.286 mean=-4.03 n=56
  120m  BUY hit=0.696 mean=+4.46 n=56   SELL hit=0.214 mean=-7.56 n=56
  240m  BUY hit=0.554 mean=+6.72 n=56   SELL hit=0.214 mean=-9.91 n=56
USD_JPY: n=71
    5m  BUY hit=0.324 mean=-4.63 n=71   SELL hit=0.493 mean=+1.37 n=71
   15m  BUY hit=0.380 mean=-5.96 n=71   SELL hit=0.493 mean=+2.69 n=71
   30m  BUY hit=0.394 mean=-6.57 n=71   SELL hit=0.535 mean=+3.31 n=71
   60m  BUY hit=0.329 mean=-7.87 n=70   SELL hit=0.629 mean=+4.61 n=70
  120m  BUY hit=0.266 mean=-9.76 n=64   SELL hit=0.703 mean=+6.53 n=64
  240m  BUY hit=0.133 mean=-30.45 n=60   SELL hit=0.850 mean=+27.16 n=60
AUD_USD: n=79
    5m  BUY hit=0.266 mean=-0.87 n=79   SELL hit=0.190 mean=-1.72 n=79
   15m  BUY hit=0.304 mean=-0.88 n=79   SELL hit=0.203 mean=-1.71 n=79
   30m  BUY hit=0.380 mean=-0.70 n=79   SELL hit=0.253 mean=-1.90 n=79
   60m  BUY hit=0.443 mean=-0.62 n=79   SELL hit=0.329 mean=-1.99 n=79
  120m  BUY hit=0.608 mean=+0.39 n=79   SELL hit=0.304 mean=-2.99 n=79
  240m  BUY hit=0.731 mean=+3.26 n=78   SELL hit=0.167 mean=-5.87 n=78
USD_CAD: n=56
    5m  BUY hit=0.304 mean=-1.50 n=56   SELL hit=0.214 mean=-2.16 n=56
   15m  BUY hit=0.375 mean=-1.25 n=56   SELL hit=0.286 mean=-2.36 n=56
   30m  BUY hit=0.411 mean=-0.79 n=56   SELL hit=0.232 mean=-2.81 n=56
   60m  BUY hit=0.500 mean=-0.50 n=56   SELL hit=0.250 mean=-3.07 n=56
  120m  BUY hit=0.446 mean=+0.43 n=56   SELL hit=0.250 mean=-4.00 n=56
  240m  BUY hit=0.518 mean=+0.34 n=56   SELL hit=0.286 mean=-3.93 n=56
USD_CHF: n=74
    5m  BUY hit=0.297 mean=-1.46 n=74   SELL hit=0.257 mean=-1.54 n=74
   15m  BUY hit=0.446 mean=-0.68 n=74   SELL hit=0.243 mean=-2.30 n=74
   30m  BUY hit=0.514 mean=+0.06 n=74   SELL hit=0.203 mean=-3.05 n=74
   60m  BUY hit=0.568 mean=+0.92 n=74   SELL hit=0.203 mean=-3.91 n=74
  120m  BUY hit=0.432 mean=-0.64 n=74   SELL hit=0.392 mean=-2.34 n=74
  240m  BUY hit=0.443 mean=-0.90 n=70   SELL hit=0.343 mean=-2.11 n=70

UTC TIME BREAKDOWN:
UTC hour (completed-M5 start):
00: opportunities=12 scored=12  [SMALL SAMPLE]
    5m BUY hit=0.250 mean=-1.04 n=12  SELL hit=0.250 mean=-1.87 n=12  [SMALL SAMPLE]
   60m BUY hit=0.583 mean=+1.31 n=12  SELL hit=0.167 mean=-4.33 n=12  [SMALL SAMPLE]
  240m BUY hit=0.583 mean=+0.28 n=12  SELL hit=0.083 mean=-3.27 n=12  [SMALL SAMPLE]
01: opportunities=19 scored=19  [SMALL SAMPLE]
    5m BUY hit=0.263 mean=-1.21 n=19  SELL hit=0.263 mean=-1.82 n=19  [SMALL SAMPLE]
   60m BUY hit=0.316 mean=-1.19 n=19  SELL hit=0.263 mean=-1.81 n=19  [SMALL SAMPLE]
  240m BUY hit=0.684 mean=+3.24 n=19  SELL hit=0.053 mean=-6.26 n=19  [SMALL SAMPLE]
02: opportunities=10 scored=10  [SMALL SAMPLE]
    5m BUY hit=0.100 mean=-2.39 n=10  SELL hit=0.400 mean=-0.53 n=10  [SMALL SAMPLE]
   60m BUY hit=0.400 mean=-0.02 n=10  SELL hit=0.300 mean=-2.98 n=10  [SMALL SAMPLE]
  240m BUY hit=0.600 mean=-1.53 n=10  SELL hit=0.200 mean=-1.48 n=10  [SMALL SAMPLE]
03: opportunities=7 scored=7  [SMALL SAMPLE]
    5m BUY hit=0.286 mean=-0.49 n=7  SELL hit=0.000 mean=-2.11 n=7  [SMALL SAMPLE]
   60m BUY hit=0.571 mean=+0.36 n=7  SELL hit=0.000 mean=-2.96 n=7  [SMALL SAMPLE]
  240m BUY hit=1.000 mean=+6.73 n=7  SELL hit=0.000 mean=-9.31 n=7  [SMALL SAMPLE]
04: opportunities=5 scored=5  [SMALL SAMPLE]
    5m BUY hit=0.200 mean=-1.34 n=5  SELL hit=0.000 mean=-1.30 n=5  [SMALL SAMPLE]
   60m BUY hit=0.800 mean=+1.42 n=5  SELL hit=0.000 mean=-4.06 n=5  [SMALL SAMPLE]
  240m BUY hit=1.000 mean=+11.78 n=5  SELL hit=0.000 mean=-14.42 n=5  [SMALL SAMPLE]
05: opportunities=11 scored=11  [SMALL SAMPLE]
    5m BUY hit=0.455 mean=+0.08 n=11  SELL hit=0.091 mean=-3.06 n=11  [SMALL SAMPLE]
   60m BUY hit=0.273 mean=-7.44 n=11  SELL hit=0.545 mean=+4.47 n=11  [SMALL SAMPLE]
  240m BUY hit=0.364 mean=-9.34 n=11  SELL hit=0.636 mean=+6.26 n=11  [SMALL SAMPLE]
06: opportunities=27 scored=27  [SMALL SAMPLE]
    5m BUY hit=0.333 mean=-2.02 n=27  SELL hit=0.333 mean=-1.00 n=27  [SMALL SAMPLE]
   60m BUY hit=0.444 mean=-1.70 n=27  SELL hit=0.407 mean=-1.34 n=27  [SMALL SAMPLE]
  240m BUY hit=0.519 mean=-2.67 n=27  SELL hit=0.407 mean=-0.41 n=27  [SMALL SAMPLE]
07: opportunities=23 scored=23  [SMALL SAMPLE]
    5m BUY hit=0.478 mean=-0.61 n=23  SELL hit=0.217 mean=-2.27 n=23  [SMALL SAMPLE]
   60m BUY hit=0.739 mean=+3.75 n=23  SELL hit=0.217 mean=-6.63 n=23  [SMALL SAMPLE]
  240m BUY hit=0.696 mean=+11.15 n=23  SELL hit=0.261 mean=-14.03 n=23  [SMALL SAMPLE]
08: opportunities=26 scored=26  [SMALL SAMPLE]
    5m BUY hit=0.308 mean=-1.24 n=26  SELL hit=0.192 mean=-1.64 n=26  [SMALL SAMPLE]
   60m BUY hit=0.615 mean=+0.86 n=26  SELL hit=0.154 mean=-3.73 n=26  [SMALL SAMPLE]
  240m BUY hit=0.500 mean=+2.36 n=26  SELL hit=0.346 mean=-5.23 n=26  [SMALL SAMPLE]
09: opportunities=22 scored=22  [SMALL SAMPLE]
    5m BUY hit=0.455 mean=-1.07 n=22  SELL hit=0.227 mean=-1.96 n=22  [SMALL SAMPLE]
   60m BUY hit=0.500 mean=-3.13 n=22  SELL hit=0.318 mean=+0.08 n=22  [SMALL SAMPLE]
  240m BUY hit=0.273 mean=-27.52 n=22  SELL hit=0.591 mean=+24.37 n=22  [SMALL SAMPLE]
10: opportunities=52 scored=52
    5m BUY hit=0.308 mean=-1.66 n=52  SELL hit=0.231 mean=-1.34 n=52
   60m BUY hit=0.481 mean=-3.36 n=52  SELL hit=0.404 mean=+0.37 n=52
  240m BUY hit=0.404 mean=-9.42 n=52  SELL hit=0.538 mean=+6.46 n=52
11: opportunities=54 scored=54
    5m BUY hit=0.352 mean=-0.93 n=54  SELL hit=0.167 mean=-2.04 n=54
   60m BUY hit=0.296 mean=-2.60 n=54  SELL hit=0.556 mean=-0.41 n=54
  240m BUY hit=0.500 mean=+1.09 n=54  SELL hit=0.463 mean=-4.04 n=54
12: opportunities=55 scored=55
    5m BUY hit=0.345 mean=-1.52 n=55  SELL hit=0.291 mean=-1.44 n=55
   60m BUY hit=0.491 mean=+0.17 n=55  SELL hit=0.327 mean=-3.11 n=55
  240m BUY hit=0.491 mean=+0.53 n=55  SELL hit=0.255 mean=-3.43 n=55
13: opportunities=65 scored=65
    5m BUY hit=0.308 mean=-2.72 n=65  SELL hit=0.400 mean=-0.22 n=65
   60m BUY hit=0.615 mean=+2.43 n=65  SELL hit=0.308 mean=-5.33 n=65
  240m BUY hit=0.646 mean=+2.28 n=65  SELL hit=0.231 mean=-5.21 n=65
14: opportunities=49 scored=49
    5m BUY hit=0.388 mean=-1.64 n=49  SELL hit=0.429 mean=-1.19 n=49
   60m BUY hit=0.367 mean=-2.14 n=49  SELL hit=0.490 mean=-0.67 n=49
  240m BUY hit=0.347 mean=-4.73 n=49  SELL hit=0.510 mean=+1.90 n=49
15: opportunities=59 scored=59
    5m BUY hit=0.339 mean=-2.28 n=59  SELL hit=0.356 mean=-0.65 n=59
   60m BUY hit=0.542 mean=-1.21 n=59  SELL hit=0.424 mean=-1.77 n=59
  240m BUY hit=0.356 mean=-3.32 n=59  SELL hit=0.475 mean=+0.28 n=59
16: opportunities=54 scored=54
    5m BUY hit=0.407 mean=-1.35 n=54  SELL hit=0.315 mean=-1.55 n=54
   60m BUY hit=0.481 mean=-1.47 n=54  SELL hit=0.463 mean=-1.43 n=54
  240m BUY hit=0.358 mean=-2.81 n=53  SELL hit=0.491 mean=-0.38 n=53
17: opportunities=23 scored=23  [SMALL SAMPLE]
    5m BUY hit=0.348 mean=-0.76 n=23  SELL hit=0.304 mean=-2.10 n=23  [SMALL SAMPLE]
   60m BUY hit=0.522 mean=-0.87 n=23  SELL hit=0.391 mean=-2.02 n=23  [SMALL SAMPLE]
  240m BUY hit=0.235 mean=-5.09 n=17  SELL hit=0.412 mean=-3.28 n=17  [SMALL SAMPLE]
18: opportunities=28 scored=28  [SMALL SAMPLE]
    5m BUY hit=0.107 mean=-1.77 n=28  SELL hit=0.250 mean=-1.15 n=28  [SMALL SAMPLE]
   60m BUY hit=0.393 mean=+0.01 n=28  SELL hit=0.214 mean=-2.96 n=28  [SMALL SAMPLE]
  240m BUY hit=0.160 mean=-3.77 n=25  SELL hit=0.600 mean=+0.54 n=25  [SMALL SAMPLE]
19: opportunities=26 scored=26  [SMALL SAMPLE]
    5m BUY hit=0.308 mean=-1.30 n=26  SELL hit=0.231 mean=-1.80 n=26  [SMALL SAMPLE]
   60m BUY hit=0.320 mean=-0.93 n=25  SELL hit=0.280 mean=-2.97 n=25  [SMALL SAMPLE]
  240m BUY hit=0.053 mean=-5.07 n=19  SELL hit=0.737 mean=+2.05 n=19  [SMALL SAMPLE]
20: opportunities=20 scored=20  [SMALL SAMPLE]
    5m BUY hit=0.200 mean=-2.58 n=20  SELL hit=0.300 mean=-1.40 n=20  [SMALL SAMPLE]
   60m BUY hit=0.263 mean=-5.44 n=19  SELL hit=0.158 mean=-3.99 n=19  [SMALL SAMPLE]
  240m BUY hit=0.100 mean=-3.68 n=20  SELL hit=0.550 mean=+0.74 n=20  [SMALL SAMPLE]
21: opportunities=12 scored=12  [SMALL SAMPLE]
    5m BUY hit=0.000 mean=-7.64 n=11  SELL hit=0.000 mean=-9.45 n=11  [SMALL SAMPLE]
   60m BUY hit=0.000 mean=-3.47 n=12  SELL hit=0.000 mean=-8.02 n=12  [SMALL SAMPLE]
  240m BUY hit=0.333 mean=-0.82 n=12  SELL hit=0.000 mean=-10.44 n=12  [SMALL SAMPLE]
22: opportunities=5 scored=5  [SMALL SAMPLE]
    5m BUY hit=0.000 mean=-2.66 n=5  SELL hit=0.000 mean=-1.34 n=5  [SMALL SAMPLE]
   60m BUY hit=0.000 mean=-2.66 n=5  SELL hit=0.000 mean=-1.14 n=5  [SMALL SAMPLE]
  240m BUY hit=0.200 mean=-0.00 n=5  SELL hit=0.000 mean=-3.68 n=5  [SMALL SAMPLE]
23: opportunities=7 scored=7  [SMALL SAMPLE]
    5m BUY hit=0.286 mean=-1.94 n=7  SELL hit=0.286 mean=-1.17 n=7  [SMALL SAMPLE]
   60m BUY hit=0.286 mean=-1.46 n=7  SELL hit=0.571 mean=-1.71 n=7  [SMALL SAMPLE]
  240m BUY hit=0.714 mean=+3.09 n=7  SELL hit=0.143 mean=-6.10 n=7  [SMALL SAMPLE]

UTC blocks:
00-06: opportunities=64 scored=64
    5m BUY hit=0.266 mean=-1.07 n=64  SELL hit=0.203 mean=-1.83 n=64
   60m BUY hit=0.438 mean=-1.24 n=64  SELL hit=0.250 mean=-1.69 n=64
  240m BUY hit=0.656 mean=+0.83 n=64  SELL hit=0.172 mean=-3.77 n=64
06-12: opportunities=204 scored=204
    5m BUY hit=0.358 mean=-1.28 n=204  SELL hit=0.221 mean=-1.69 n=204
   60m BUY hit=0.475 mean=-1.58 n=204  SELL hit=0.382 mean=-1.41 n=204
  240m BUY hit=0.475 mean=-3.88 n=204  SELL hit=0.451 mean=+0.90 n=204
12-18: opportunities=305 scored=305
    5m BUY hit=0.354 mean=-1.85 n=305  SELL hit=0.354 mean=-1.06 n=305
   60m BUY hit=0.508 mean=-0.36 n=305  SELL hit=0.397 mean=-2.55 n=305
  240m BUY hit=0.436 mean=-1.63 n=298  SELL hit=0.386 mean=-1.66 n=298
18-24: opportunities=98 scored=98
    5m BUY hit=0.175 mean=-2.54 n=97  SELL hit=0.216 mean=-2.33 n=97
   60m BUY hit=0.271 mean=-1.99 n=96  SELL hit=0.208 mean=-3.61 n=96
  240m BUY hit=0.193 mean=-2.87 n=88  SELL hit=0.466 mean=-1.35 n=88

RL METADATA:
observations=2941
rl_state=2941/2941
rl_action=2941/2941
rl_q=2941/2941
rl_epsilon=2941/2941
rl_agree=2941/2941
rl_veto=2941/2941
rl_complete=2941/2941
q_values_all_zero=2941
q_values_nonzero=0
Q values remain zero-initialized observation metadata. This is not RL effectiveness.

REPEAT RATE: 2270 repeats / 2941 observations = 77.2%

CORRELATED/SIMULTANEOUS OPPORTUNITY NOTE:
unique completed-M5 timestamps=308
timestamps with 2+ symbols=206
symbols-per-timestamp counts: 1 symbols: 102, 2 symbols: 102, 3 symbols: 67, 4 symbols: 24, 5 symbols: 10, 6 symbols: 3
Do NOT treat 671 unique opportunities as 671 independent statistical trials.
Same-timestamp USD-pair opportunities share session, USD factor, and often the same macro impulse.

OANDA/API REQUESTS: 0
OBSERVATIONS MODIFIED: NO
MARKET DATA MODIFIED: NO
SCORER SEMANTICS CHANGED: NO
AUTOMATIC SCORING ENABLED: NO
V2 POLICY: SKIP ONLY
MODEL TRAINED: NO
PRODUCTION TRADING LOGIC CHANGED: NO
TEST RESULTS: 66 passed (tests/test_v2_shadow_live_score.py, tests/test_v2_shadow_outcomes.py, tests/test_v2_shadow.py, tests/test_v2_shadow_market.py)
FILES CHANGED:
- forex_bot/v2_shadow/score_offline.py (persist-path only: write newly matured keys without rewriting old matching keys)
- tests/test_v2_shadow_live_score.py (incremental-horizon persist test)
- reports/decision_quality/_v2_shadow_checkpoint_2.py
- reports/decision_quality/_v2_shadow_checkpoint_2_results.json
- reports/decision_quality/v2_shadow_checkpoint_2.md
- data/research/v2_shadow/outcomes.jsonl (append-only via existing helper)

DATA SUFFICIENT FOR CONFIDENCE MODEL: NO

FINAL INTERPRETATION:
descriptively similar at 5-60 minutes, with material numeric movement at 120-240 minutes.
Post-checkpoint vs old: max |hit-rate shift|=0.089; max |mean-pip shift|=5.05 on horizons with n>=30.
At 5/15/30/60, BUY hit stays in the 0.31-0.45 range (old 0.34-0.50), both executable sides have negative mean pips, and BUY mean + SELL mean stays near -3. That is the same spread-dominated structure as the first session, not a new directional edge.
At 120-240 the first-session BUY-positive / SELL-very-negative pattern does not persist: post-checkpoint BUY 120/240 means are -1.08 / -3.78 (old +0.95 / +0.96) and SELL 240 mean is +0.78 (old -4.28). Combined +240m n=654 vs old 209. That long-horizon swing is not a pair ranking and is not independent across the six USD pairs (206 of 308 completed-M5 timestamps have 2+ symbols).
No live trading change follows from this.

Do not treat these numbers as a live trading change. Two sessions, six correlated USD pairs,
no validated independent fundamental family, and no out-of-sample confirmation.
