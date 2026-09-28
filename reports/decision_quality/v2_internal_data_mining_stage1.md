# V2 internal data mining - stage 1 discovery

RESEARCH / DESCRIPTIVE ONLY. V2 remains SKIP. No live trading change.
Unique opportunity = (symbol, last completed M5 start), earliest observation representative.
Quartile cuts are computed from the earlier labeled session (scored unique opportunities) only.
Repeated ~60s bot-loop rows are not treated as independent samples.

DATASET:
raw observations: 4001
unique opportunities: 929
joined unique opportunities with at least one mature label: 671
time range: 2026-09-24T10:26:54.809816+00:00 -> 2026-09-28T10:43:55.896197+00:00
repeat rate: 76.8%
malformed observations: 0
malformed outcomes: 0
mature labels (unique opportunities with BUY forward_pips AVAILABLE):
  5m: 670
  15m: 671
  30m: 670
  60m: 669
  120m: 663
  240m: 654
symbol counts (unique opportunities):
  AUD_USD: 173
  EUR_USD: 130
  GBP_USD: 138
  USD_CAD: 149
  USD_CHF: 204
  USD_JPY: 135
UTC date of completed-M5 start (all unique / scored):
  2026-09-24: unique=304 scored=304
  2026-09-25: unique=367 scored=367
  2026-09-27: unique=71 scored=0
  2026-09-28: unique=187 scored=0
unscored unique opportunities (no mature outcome yet): 258
Outcome/stability tables use scored unique opportunities only, split by labeled session date 2026-09-24 vs 2026-09-25. Unscored later dates are not treated as a later outcome block.
earlier labeled n=304  later labeled n=367

FEATURE QUALITY:
name  avail  miss  not_computed  unique  min  median  mean  max  flag
production_stub_side: avail=4001 miss=0 nc=0 unique=2 min=n/a med=n/a mean=n/a max=n/a 
strategy_label: avail=4001 miss=0 nc=0 unique=6 min=n/a med=n/a mean=n/a max=n/a 
bid: avail=4001 miss=0 nc=0 unique=1925 min=0.700380 med=1.138520 mean=22.822061 max=159.022000 
ask: avail=4001 miss=0 nc=0 unique=1930 min=0.700520 med=1.138600 mean=22.824653 max=159.037000 
mid: avail=4001 miss=0 nc=0 unique=737 min=0.700430 med=1.138570 mean=22.823916 max=158.992000 
spread: avail=4001 miss=0 nc=0 unique=151 min=0.000060 med=0.000140 mean=0.002592 max=0.080000 
pip_size: avail=4001 miss=0 nc=0 unique=2 min=0.000100 med=0.000100 mean=0.001476 max=0.010000 
atr: avail=4001 miss=0 nc=0 unique=889 min=0.000110 med=0.000335 mean=0.011864 max=0.169100 
atr_over_price: avail=4001 miss=0 nc=0 unique=920 min=0.000084 med=0.000329 mean=0.000346 max=0.001079 
sma_fast: avail=4001 miss=0 nc=0 unique=914 min=0.700777 med=1.138588 mean=22.826551 max=158.933600 
sma_slow: avail=4001 miss=0 nc=0 unique=918 min=0.701131 med=1.138747 mean=22.829817 max=158.893000 
sma_difference: avail=4001 miss=0 nc=0 unique=921 min=-0.419320 med=0.000094 mean=-0.003265 max=0.217480 
sma_difference_over_atr: avail=4001 miss=0 nc=0 unique=924 min=-6.518016 med=0.319715 mean=0.431740 max=6.477206 
rsi: avail=4001 miss=0 nc=0 unique=915 min=2.400000 med=50.340112 mean=50.483259 max=95.939018 
macd: avail=4001 miss=0 nc=0 unique=932 min=-0.206987 med=0.000009 mean=-0.003137 max=0.111666 
macd_signal: avail=0 miss=0 nc=4001 unique=0 min=n/a med=n/a mean=n/a max=n/a NOT_COMPUTED
adx: avail=0 miss=0 nc=4001 unique=0 min=n/a med=n/a mean=n/a max=n/a NOT_COMPUTED
bollinger_position: avail=4001 miss=0 nc=0 unique=933 min=-0.499493 med=0.555894 mean=0.534177 max=1.583572 
ret_1: avail=4001 miss=0 nc=0 unique=909 min=-0.003441 med=0.000113 mean=-0.000000 max=0.001896 SEE_RET_DUP
ret_5: avail=4001 miss=0 nc=0 unique=909 min=-0.003441 med=0.000113 mean=-0.000000 max=0.001896 SEE_RET_DUP
ret_15: avail=4001 miss=0 nc=0 unique=910 min=-0.005250 med=0.000000 mean=-0.000019 max=0.002481 
ret_30: avail=4001 miss=0 nc=0 unique=911 min=-0.004897 med=-0.000014 mean=-0.000016 max=0.002675 
hour_utc: avail=4001 miss=0 nc=0 unique=24 min=0.000000 med=12.000000 mean=11.534116 max=23.000000 
day_of_week: avail=4001 miss=0 nc=0 unique=4 min=0.000000 med=3.000000 mean=3.009248 max=6.000000 
usd_direction: avail=4001 miss=0 nc=0 unique=2 min=n/a med=n/a mean=n/a max=n/a 
broker_backed_position_count: avail=4001 miss=0 nc=0 unique=5 min=0.000000 med=3.000000 mean=2.708323 max=4.000000 
gross_portfolio_exposure: avail=4001 miss=0 nc=0 unique=281 min=97.178200 med=97.209700 mean=97.203543 max=97.213900 
same_usd_direction_count: avail=4001 miss=0 nc=0 unique=4 min=0.000000 med=2.000000 mean=1.773557 max=3.000000 

RET_1 VS RET_5:
n=929
exact equality rate=0.0000 (0/929)
abs(diff)<=1e-12 rate=1.0000
correlation=1.000000
diff mean=2.269209471610875e-19 median=-2.710505431213761e-18 min=-1.1039888621333649e-16 max=1.1034467610471221e-16
bot_loop ret_1 = close.pct_change()[-1]; ret_5 uses 1 M5 bar lookback
Do not treat ret_1 and ret_5 as independent signals. They are the same one-bar M5 return
up to floating-point noise (pct_change vs explicit 1-bar lookback).

SINGLE-FEATURE AUDIT:
Continuous features use earlier-half quartiles. Categorical features use natural categories.
Full 5/60/240 shown. 15/30/120 were computed and used for classification counts.
atr_over_price (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=242
      5m BUY hit=0.290 mean=-1.57 n=241  SELL hit=0.220 mean=-2.15 n=241
     60m BUY hit=0.483 mean=+0.16 n=242  SELL hit=0.248 mean=-3.94 n=242
    240m BUY hit=0.607 mean=+3.51 n=242  SELL hit=0.227 mean=-7.08 n=242
  Q2: n=169
      5m BUY hit=0.379 mean=-1.10 n=169  SELL hit=0.266 mean=-1.87 n=169
     60m BUY hit=0.467 mean=-0.80 n=167  SELL hit=0.359 mean=-2.41 n=167
    240m BUY hit=0.405 mean=-1.43 n=158  SELL hit=0.392 mean=-1.51 n=158
  Q3: n=91
      5m BUY hit=0.253 mean=-1.89 n=91  SELL hit=0.352 mean=-0.89 n=91
     60m BUY hit=0.473 mean=-0.10 n=91  SELL hit=0.385 mean=-2.91 n=91
    240m BUY hit=0.311 mean=-2.61 n=90  SELL hit=0.467 mean=-0.39 n=90
  Q4: n=169
      5m BUY hit=0.343 mean=-2.39 n=169  SELL hit=0.337 mean=-0.57 n=169
     60m BUY hit=0.402 mean=-3.54 n=169  SELL hit=0.473 mean=+0.59 n=169
    240m BUY hit=0.287 mean=-11.38 n=164  SELL hit=0.610 mean=+8.04 n=164
  earlier:
  Q1: n=76
      5m BUY hit=0.267 mean=-2.75 n=75  SELL hit=0.213 mean=-2.68 n=75
     60m BUY hit=0.421 mean=-0.10 n=76  SELL hit=0.184 mean=-5.45 n=76
    240m BUY hit=0.566 mean=+3.46 n=76  SELL hit=0.197 mean=-8.34 n=76
  Q2: n=76
      5m BUY hit=0.395 mean=-0.83 n=76  SELL hit=0.197 mean=-2.27 n=76
     60m BUY hit=0.453 mean=-1.33 n=75  SELL hit=0.387 mean=-2.30 n=75
    240m BUY hit=0.434 mean=+0.03 n=76  SELL hit=0.355 mean=-3.11 n=76
  Q3: n=76
      5m BUY hit=0.276 mean=-1.93 n=76  SELL hit=0.355 mean=-0.89 n=76
     60m BUY hit=0.513 mean=+0.22 n=76  SELL hit=0.342 mean=-3.30 n=76
    240m BUY hit=0.303 mean=-2.49 n=76  SELL hit=0.447 mean=-0.56 n=76
  Q4: n=76
      5m BUY hit=0.368 mean=-0.68 n=76  SELL hit=0.211 mean=-2.13 n=76
     60m BUY hit=0.447 mean=-0.41 n=76  SELL hit=0.382 mean=-2.42 n=76
    240m BUY hit=0.355 mean=-1.99 n=76  SELL hit=0.513 mean=-1.55 n=76
  later:
  Q1: n=166
      5m BUY hit=0.301 mean=-1.04 n=166  SELL hit=0.223 mean=-1.91 n=166
     60m BUY hit=0.512 mean=+0.29 n=166  SELL hit=0.277 mean=-3.25 n=166
    240m BUY hit=0.627 mean=+3.54 n=166  SELL hit=0.241 mean=-6.51 n=166
  Q2: n=93
      5m BUY hit=0.366 mean=-1.32 n=93  SELL hit=0.323 mean=-1.54 n=93
     60m BUY hit=0.478 mean=-0.37 n=92  SELL hit=0.337 mean=-2.51 n=92
    240m BUY hit=0.378 mean=-2.78 n=82  SELL hit=0.427 mean=-0.03 n=82
  Q3: n=15 [SMALL]
      5m BUY hit=0.133 mean=-1.69 n=15  SELL hit=0.333 mean=-0.89 n=15 [SMALL]
     60m BUY hit=0.267 mean=-1.71 n=15  SELL hit=0.600 mean=-0.93 n=15 [SMALL]
    240m BUY hit=0.357 mean=-3.26 n=14  SELL hit=0.571 mean=+0.56 n=14 [SMALL]
  Q4: n=93
      5m BUY hit=0.323 mean=-3.78 n=93  SELL hit=0.441 mean=+0.72 n=93
     60m BUY hit=0.366 mean=-6.10 n=93  SELL hit=0.548 mean=+3.05 n=93
    240m BUY hit=0.227 mean=-19.48 n=88  SELL hit=0.693 mean=+16.32 n=88

spread_pips (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=246
      5m BUY hit=0.325 mean=-1.08 n=246  SELL hit=0.313 mean=-1.55 n=246
     60m BUY hit=0.415 mean=-0.62 n=246  SELL hit=0.407 mean=-2.27 n=246
    240m BUY hit=0.461 mean=-0.27 n=243  SELL hit=0.412 mean=-2.58 n=243
  Q2: n=138
      5m BUY hit=0.341 mean=-1.36 n=138  SELL hit=0.232 mean=-1.51 n=138
     60m BUY hit=0.522 mean=-0.14 n=138  SELL hit=0.304 mean=-3.19 n=138
    240m BUY hit=0.426 mean=-0.07 n=136  SELL hit=0.368 mean=-2.94 n=136
  Q3: n=122
      5m BUY hit=0.270 mean=-1.91 n=122  SELL hit=0.254 mean=-1.28 n=122
     60m BUY hit=0.504 mean=-1.09 n=121  SELL hit=0.314 mean=-2.16 n=121
    240m BUY hit=0.414 mean=-3.26 n=116  SELL hit=0.414 mean=+0.05 n=116
  Q4: n=165
      5m BUY hit=0.335 mean=-2.78 n=164  SELL hit=0.287 mean=-1.60 n=164
     60m BUY hit=0.433 mean=-2.43 n=164  SELL hit=0.335 mean=-1.59 n=164
    240m BUY hit=0.428 mean=-6.43 n=159  SELL hit=0.384 mean=+2.22 n=159
  earlier:
  Q1: n=108
      5m BUY hit=0.343 mean=-0.95 n=108  SELL hit=0.306 mean=-1.72 n=108
     60m BUY hit=0.435 mean=-0.29 n=108  SELL hit=0.407 mean=-2.96 n=108
    240m BUY hit=0.352 mean=-2.31 n=108  SELL hit=0.481 mean=-0.80 n=108
  Q2: n=61
      5m BUY hit=0.361 mean=-0.94 n=61  SELL hit=0.180 mean=-1.96 n=61
     60m BUY hit=0.459 mean=-0.80 n=61  SELL hit=0.344 mean=-3.07 n=61
    240m BUY hit=0.328 mean=-1.82 n=61  SELL hit=0.459 mean=-1.34 n=61
  Q3: n=66
      5m BUY hit=0.258 mean=-2.24 n=66  SELL hit=0.258 mean=-1.02 n=66
     60m BUY hit=0.538 mean=+0.06 n=65  SELL hit=0.246 mean=-3.45 n=65
    240m BUY hit=0.455 mean=-0.02 n=66  SELL hit=0.364 mean=-3.27 n=66
  Q4: n=69
      5m BUY hit=0.338 mean=-2.37 n=68  SELL hit=0.191 mean=-3.38 n=68
     60m BUY hit=0.420 mean=-0.66 n=69  SELL hit=0.246 mean=-4.20 n=69
    240m BUY hit=0.551 mean=+4.15 n=69  SELL hit=0.159 mean=-9.38 n=69
  later:
  Q1: n=138
      5m BUY hit=0.312 mean=-1.18 n=138  SELL hit=0.319 mean=-1.42 n=138
     60m BUY hit=0.399 mean=-0.87 n=138  SELL hit=0.406 mean=-1.74 n=138
    240m BUY hit=0.548 mean=+1.36 n=135  SELL hit=0.356 mean=-4.01 n=135
  Q2: n=77
      5m BUY hit=0.325 mean=-1.69 n=77  SELL hit=0.273 mean=-1.16 n=77
     60m BUY hit=0.571 mean=+0.39 n=77  SELL hit=0.273 mean=-3.28 n=77
    240m BUY hit=0.507 mean=+1.35 n=75  SELL hit=0.293 mean=-4.24 n=75
  Q3: n=56
      5m BUY hit=0.286 mean=-1.53 n=56  SELL hit=0.250 mean=-1.59 n=56
     60m BUY hit=0.464 mean=-2.43 n=56  SELL hit=0.393 mean=-0.66 n=56
    240m BUY hit=0.360 mean=-7.53 n=50  SELL hit=0.480 mean=+4.42 n=50
  Q4: n=96
      5m BUY hit=0.333 mean=-3.06 n=96  SELL hit=0.354 mean=-0.34 n=96
     60m BUY hit=0.442 mean=-3.72 n=95  SELL hit=0.400 mean=+0.31 n=95
    240m BUY hit=0.333 mean=-14.54 n=90  SELL hit=0.556 mean=+11.12 n=90

spread_over_atr (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=177
      5m BUY hit=0.322 mean=-2.26 n=177  SELL hit=0.401 mean=-0.51 n=177
     60m BUY hit=0.356 mean=-3.62 n=177  SELL hit=0.548 mean=+0.84 n=177
    240m BUY hit=0.293 mean=-10.99 n=174  SELL hit=0.609 mean=+8.07 n=174
  Q2: n=152
      5m BUY hit=0.355 mean=-1.55 n=152  SELL hit=0.276 mean=-1.45 n=152
     60m BUY hit=0.510 mean=-0.63 n=151  SELL hit=0.325 mean=-2.66 n=151
    240m BUY hit=0.413 mean=-1.06 n=138  SELL hit=0.420 mean=-2.41 n=138
  Q3: n=107
      5m BUY hit=0.327 mean=-1.60 n=107  SELL hit=0.299 mean=-1.39 n=107
     60m BUY hit=0.570 mean=+1.24 n=107  SELL hit=0.290 mean=-4.27 n=107
    240m BUY hit=0.486 mean=+1.29 n=107  SELL hit=0.364 mean=-4.36 n=107
  Q4: n=235
      5m BUY hit=0.295 mean=-1.42 n=234  SELL hit=0.179 mean=-2.36 n=234
     60m BUY hit=0.449 mean=-0.41 n=234  SELL hit=0.248 mean=-3.47 n=234
    240m BUY hit=0.536 mean=+1.89 n=235  SELL hit=0.238 mean=-5.42 n=235
  earlier:
  Q1: n=76
      5m BUY hit=0.408 mean=-0.50 n=76  SELL hit=0.289 mean=-2.14 n=76
     60m BUY hit=0.513 mean=+0.25 n=76  SELL hit=0.408 mean=-2.93 n=76
    240m BUY hit=0.487 mean=-0.57 n=76  SELL hit=0.368 mean=-2.35 n=76
  Q2: n=76
      5m BUY hit=0.276 mean=-1.69 n=76  SELL hit=0.237 mean=-1.33 n=76
     60m BUY hit=0.355 mean=-2.29 n=76  SELL hit=0.395 mean=-1.29 n=76
    240m BUY hit=0.316 mean=-2.55 n=76  SELL hit=0.487 mean=-1.31 n=76
  Q3: n=76
      5m BUY hit=0.329 mean=-1.81 n=76  SELL hit=0.289 mean=-1.16 n=76
     60m BUY hit=0.553 mean=+0.88 n=76  SELL hit=0.303 mean=-3.90 n=76
    240m BUY hit=0.382 mean=-0.70 n=76  SELL hit=0.447 mean=-2.38 n=76
  Q4: n=76
      5m BUY hit=0.293 mean=-2.19 n=75  SELL hit=0.160 mean=-3.35 n=75
     60m BUY hit=0.413 mean=-0.43 n=75  SELL hit=0.187 mean=-5.38 n=75
    240m BUY hit=0.474 mean=+2.83 n=76  SELL hit=0.211 mean=-7.53 n=76
  later:
  Q1: n=101
      5m BUY hit=0.257 mean=-3.59 n=101  SELL hit=0.485 mean=+0.73 n=101
     60m BUY hit=0.238 mean=-6.53 n=101  SELL hit=0.653 mean=+3.68 n=101
    240m BUY hit=0.143 mean=-19.07 n=98  SELL hit=0.796 mean=+16.15 n=98
  Q2: n=76
      5m BUY hit=0.434 mean=-1.42 n=76  SELL hit=0.316 mean=-1.57 n=76
     60m BUY hit=0.667 mean=+1.05 n=75  SELL hit=0.253 mean=-4.04 n=75
    240m BUY hit=0.532 mean=+0.77 n=62  SELL hit=0.339 mean=-3.75 n=62
  Q3: n=31
      5m BUY hit=0.323 mean=-1.07 n=31  SELL hit=0.323 mean=-1.95 n=31
     60m BUY hit=0.613 mean=+2.14 n=31  SELL hit=0.258 mean=-5.17 n=31
    240m BUY hit=0.742 mean=+6.16 n=31  SELL hit=0.161 mean=-9.23 n=31
  Q4: n=159
      5m BUY hit=0.296 mean=-1.06 n=159  SELL hit=0.189 mean=-1.90 n=159
     60m BUY hit=0.465 mean=-0.41 n=159  SELL hit=0.277 mean=-2.56 n=159
    240m BUY hit=0.566 mean=+1.44 n=159  SELL hit=0.252 mean=-4.42 n=159

sma_difference_over_atr (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=103
      5m BUY hit=0.398 mean=-0.62 n=103  SELL hit=0.184 mean=-2.55 n=103
     60m BUY hit=0.485 mean=+1.89 n=103  SELL hit=0.320 mean=-5.15 n=103
    240m BUY hit=0.417 mean=-0.99 n=103  SELL hit=0.369 mean=-1.98 n=103
  Q2: n=187
      5m BUY hit=0.253 mean=-2.65 n=186  SELL hit=0.333 mean=-0.86 n=186
     60m BUY hit=0.353 mean=-3.57 n=187  SELL hit=0.422 mean=-0.05 n=187
    240m BUY hit=0.305 mean=-10.70 n=174  SELL hit=0.494 mean=+7.18 n=174
  Q3: n=227
      5m BUY hit=0.322 mean=-1.69 n=227  SELL hit=0.282 mean=-1.48 n=227
     60m BUY hit=0.458 mean=-1.33 n=225  SELL hit=0.342 mean=-2.03 n=225
    240m BUY hit=0.489 mean=+1.44 n=223  SELL hit=0.377 mean=-4.88 n=223
  Q4: n=154
      5m BUY hit=0.351 mean=-1.30 n=154  SELL hit=0.273 mean=-1.63 n=154
     60m BUY hit=0.565 mean=+0.47 n=154  SELL hit=0.299 mean=-3.41 n=154
    240m BUY hit=0.526 mean=+1.08 n=154  SELL hit=0.331 mean=-4.07 n=154
  earlier:
  Q1: n=76
      5m BUY hit=0.355 mean=-0.99 n=76  SELL hit=0.224 mean=-2.21 n=76
     60m BUY hit=0.474 mean=+0.72 n=76  SELL hit=0.355 mean=-4.05 n=76
    240m BUY hit=0.342 mean=-2.71 n=76  SELL hit=0.434 mean=-0.21 n=76
  Q2: n=76
      5m BUY hit=0.253 mean=-1.86 n=75  SELL hit=0.227 mean=-2.26 n=75
     60m BUY hit=0.276 mean=-1.82 n=76  SELL hit=0.342 mean=-2.53 n=76
    240m BUY hit=0.263 mean=-3.51 n=76  SELL hit=0.461 mean=-0.49 n=76
  Q3: n=76
      5m BUY hit=0.342 mean=-1.52 n=76  SELL hit=0.263 mean=-2.14 n=76
     60m BUY hit=0.413 mean=-1.45 n=75  SELL hit=0.347 mean=-2.79 n=75
    240m BUY hit=0.447 mean=+1.56 n=76  SELL hit=0.382 mean=-5.92 n=76
  Q4: n=76
      5m BUY hit=0.355 mean=-1.82 n=76  SELL hit=0.263 mean=-1.35 n=76
     60m BUY hit=0.671 mean=+0.94 n=76  SELL hit=0.250 mean=-4.10 n=76
    240m BUY hit=0.605 mean=+3.67 n=76  SELL hit=0.237 mean=-6.95 n=76
  later:
  Q1: n=27 [SMALL]
      5m BUY hit=0.519 mean=+0.42 n=27  SELL hit=0.074 mean=-3.52 n=27 [SMALL]
     60m BUY hit=0.519 mean=+5.17 n=27  SELL hit=0.222 mean=-8.23 n=27 [SMALL]
    240m BUY hit=0.630 mean=+3.88 n=27  SELL hit=0.185 mean=-6.94 n=27 [SMALL]
  Q2: n=111
      5m BUY hit=0.252 mean=-3.19 n=111  SELL hit=0.405 mean=+0.09 n=111
     60m BUY hit=0.405 mean=-4.76 n=111  SELL hit=0.477 mean=+1.65 n=111
    240m BUY hit=0.337 mean=-16.27 n=98  SELL hit=0.520 mean=+13.13 n=98
  Q3: n=151
      5m BUY hit=0.311 mean=-1.77 n=151  SELL hit=0.291 mean=-1.15 n=151
     60m BUY hit=0.480 mean=-1.27 n=150  SELL hit=0.340 mean=-1.65 n=150
    240m BUY hit=0.510 mean=+1.38 n=147  SELL hit=0.374 mean=-4.35 n=147
  Q4: n=78
      5m BUY hit=0.346 mean=-0.80 n=78  SELL hit=0.282 mean=-1.91 n=78
     60m BUY hit=0.462 mean=+0.01 n=78  SELL hit=0.346 mean=-2.73 n=78
    240m BUY hit=0.449 mean=-1.45 n=78  SELL hit=0.423 mean=-1.27 n=78

rsi (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=169
      5m BUY hit=0.440 mean=-1.12 n=168  SELL hit=0.232 mean=-2.28 n=168
     60m BUY hit=0.651 mean=+2.77 n=169  SELL hit=0.225 mean=-6.14 n=169
    240m BUY hit=0.578 mean=-2.26 n=161  SELL hit=0.267 mean=-1.26 n=161
  Q2: n=160
      5m BUY hit=0.338 mean=-1.44 n=160  SELL hit=0.269 mean=-1.81 n=160
     60m BUY hit=0.403 mean=-1.97 n=159  SELL hit=0.327 mean=-1.53 n=159
    240m BUY hit=0.392 mean=-3.86 n=158  SELL hit=0.430 mean=+0.62 n=158
  Q3: n=146
      5m BUY hit=0.240 mean=-1.86 n=146  SELL hit=0.274 mean=-1.39 n=146
     60m BUY hit=0.438 mean=-1.34 n=146  SELL hit=0.342 mean=-2.09 n=146
    240m BUY hit=0.368 mean=-0.82 n=144  SELL hit=0.410 mean=-2.28 n=144
  Q4: n=196
      5m BUY hit=0.265 mean=-2.29 n=196  SELL hit=0.332 mean=-0.69 n=196
     60m BUY hit=0.349 mean=-3.38 n=195  SELL hit=0.487 mean=+0.34 n=195
    240m BUY hit=0.408 mean=-2.01 n=191  SELL hit=0.466 mean=-1.24 n=191
  earlier:
  Q1: n=76
      5m BUY hit=0.467 mean=-0.76 n=75  SELL hit=0.213 mean=-3.10 n=75
     60m BUY hit=0.737 mean=+5.42 n=76  SELL hit=0.092 mean=-9.23 n=76
    240m BUY hit=0.632 mean=+3.87 n=76  SELL hit=0.118 mean=-7.96 n=76
  Q2: n=76
      5m BUY hit=0.316 mean=-1.11 n=76  SELL hit=0.197 mean=-2.48 n=76
     60m BUY hit=0.373 mean=-1.11 n=75  SELL hit=0.307 mean=-3.03 n=75
    240m BUY hit=0.342 mean=-0.56 n=76  SELL hit=0.447 mean=-2.96 n=76
  Q3: n=76
      5m BUY hit=0.250 mean=-1.97 n=76  SELL hit=0.263 mean=-1.57 n=76
     60m BUY hit=0.382 mean=-1.61 n=76  SELL hit=0.382 mean=-2.25 n=76
    240m BUY hit=0.289 mean=-1.71 n=76  SELL hit=0.474 mean=-1.46 n=76
  Q4: n=76
      5m BUY hit=0.276 mean=-2.32 n=76  SELL hit=0.303 mean=-0.82 n=76
     60m BUY hit=0.342 mean=-4.32 n=76  SELL hit=0.513 mean=+1.04 n=76
    240m BUY hit=0.395 mean=-2.59 n=76  SELL hit=0.474 mean=-1.19 n=76
  later:
  Q1: n=93
      5m BUY hit=0.419 mean=-1.41 n=93  SELL hit=0.247 mean=-1.62 n=93
     60m BUY hit=0.581 mean=+0.61 n=93  SELL hit=0.333 mean=-3.62 n=93
    240m BUY hit=0.529 mean=-7.75 n=85  SELL hit=0.400 mean=+4.73 n=85
  Q2: n=84
      5m BUY hit=0.357 mean=-1.74 n=84  SELL hit=0.333 mean=-1.20 n=84
     60m BUY hit=0.429 mean=-2.75 n=84  SELL hit=0.345 mean=-0.19 n=84
    240m BUY hit=0.439 mean=-6.93 n=82  SELL hit=0.415 mean=+3.95 n=82
  Q3: n=70
      5m BUY hit=0.229 mean=-1.75 n=70  SELL hit=0.286 mean=-1.20 n=70
     60m BUY hit=0.500 mean=-1.05 n=70  SELL hit=0.300 mean=-1.92 n=70
    240m BUY hit=0.456 mean=+0.18 n=68  SELL hit=0.338 mean=-3.20 n=68
  Q4: n=120
      5m BUY hit=0.258 mean=-2.27 n=120  SELL hit=0.350 mean=-0.61 n=120
     60m BUY hit=0.353 mean=-2.79 n=119  SELL hit=0.471 mean=-0.10 n=119
    240m BUY hit=0.417 mean=-1.62 n=115  SELL hit=0.461 mean=-1.27 n=115

macd_over_atr (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=152
      5m BUY hit=0.397 mean=-1.48 n=151  SELL hit=0.238 mean=-2.02 n=151
     60m BUY hit=0.539 mean=+0.75 n=152  SELL hit=0.329 mean=-4.10 n=152
    240m BUY hit=0.390 mean=-7.85 n=146  SELL hit=0.445 mean=+4.29 n=146
  Q2: n=161
      5m BUY hit=0.335 mean=-1.50 n=161  SELL hit=0.236 mean=-2.03 n=161
     60m BUY hit=0.450 mean=-1.47 n=160  SELL hit=0.294 mean=-2.30 n=160
    240m BUY hit=0.406 mean=-4.26 n=155  SELL hit=0.335 mean=+0.79 n=155
  Q3: n=171
      5m BUY hit=0.263 mean=-2.14 n=171  SELL hit=0.339 mean=-0.80 n=171
     60m BUY hit=0.376 mean=-2.17 n=170  SELL hit=0.388 mean=-1.11 n=170
    240m BUY hit=0.392 mean=-0.94 n=166  SELL hit=0.458 mean=-2.21 n=166
  Q4: n=187
      5m BUY hit=0.299 mean=-1.65 n=187  SELL hit=0.294 mean=-1.29 n=187
     60m BUY hit=0.471 mean=-1.12 n=187  SELL hit=0.385 mean=-1.82 n=187
    240m BUY hit=0.540 mean=+2.60 n=187  SELL hit=0.353 mean=-5.63 n=187
  earlier:
  Q1: n=76
      5m BUY hit=0.440 mean=-0.51 n=75  SELL hit=0.173 mean=-3.35 n=75
     60m BUY hit=0.566 mean=+2.88 n=76  SELL hit=0.237 mean=-6.44 n=76
    240m BUY hit=0.395 mean=-1.09 n=76  SELL hit=0.382 mean=-2.84 n=76
  Q2: n=76
      5m BUY hit=0.289 mean=-1.70 n=76  SELL hit=0.171 mean=-2.46 n=76
     60m BUY hit=0.387 mean=-0.57 n=75  SELL hit=0.293 mean=-4.04 n=75
    240m BUY hit=0.342 mean=-1.89 n=76  SELL hit=0.316 mean=-2.02 n=76
  Q3: n=76
      5m BUY hit=0.263 mean=-1.82 n=76  SELL hit=0.329 mean=-1.11 n=76
     60m BUY hit=0.395 mean=-1.22 n=76  SELL hit=0.316 mean=-2.49 n=76
    240m BUY hit=0.395 mean=+0.02 n=76  SELL hit=0.434 mean=-3.35 n=76
  Q4: n=76
      5m BUY hit=0.316 mean=-2.15 n=76  SELL hit=0.303 mean=-1.06 n=76
     60m BUY hit=0.487 mean=-2.68 n=76  SELL hit=0.447 mean=-0.51 n=76
    240m BUY hit=0.526 mean=+1.97 n=76  SELL hit=0.382 mean=-5.35 n=76
  later:
  Q1: n=76
      5m BUY hit=0.355 mean=-2.45 n=76  SELL hit=0.303 mean=-0.71 n=76
     60m BUY hit=0.513 mean=-1.38 n=76  SELL hit=0.421 mean=-1.75 n=76
    240m BUY hit=0.386 mean=-15.18 n=70  SELL hit=0.514 mean=+12.04 n=70
  Q2: n=85
      5m BUY hit=0.376 mean=-1.33 n=85  SELL hit=0.294 mean=-1.65 n=85
     60m BUY hit=0.506 mean=-2.27 n=85  SELL hit=0.294 mean=-0.77 n=85
    240m BUY hit=0.468 mean=-6.53 n=79  SELL hit=0.354 mean=+3.49 n=79
  Q3: n=95
      5m BUY hit=0.263 mean=-2.40 n=95  SELL hit=0.347 mean=-0.55 n=95
     60m BUY hit=0.362 mean=-2.94 n=94  SELL hit=0.447 mean=+0.01 n=94
    240m BUY hit=0.389 mean=-1.76 n=90  SELL hit=0.478 mean=-1.24 n=90
  Q4: n=111
      5m BUY hit=0.288 mean=-1.31 n=111  SELL hit=0.288 mean=-1.45 n=111
     60m BUY hit=0.459 mean=-0.05 n=111  SELL hit=0.342 mean=-2.72 n=111
    240m BUY hit=0.550 mean=+3.03 n=111  SELL hit=0.333 mean=-5.81 n=111

bollinger_position (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=145
      5m BUY hit=0.417 mean=-1.08 n=144  SELL hit=0.229 mean=-2.38 n=144
     60m BUY hit=0.559 mean=+1.88 n=145  SELL hit=0.283 mean=-5.30 n=145
    240m BUY hit=0.450 mean=-4.40 n=140  SELL hit=0.386 mean=+1.05 n=140
  Q2: n=141
      5m BUY hit=0.277 mean=-1.74 n=141  SELL hit=0.277 mean=-1.66 n=141
     60m BUY hit=0.440 mean=-1.31 n=141  SELL hit=0.319 mean=-2.33 n=141
    240m BUY hit=0.390 mean=-4.30 n=136  SELL hit=0.360 mean=+0.83 n=136
  Q3: n=172
      5m BUY hit=0.320 mean=-1.95 n=172  SELL hit=0.285 mean=-1.25 n=172
     60m BUY hit=0.392 mean=-2.25 n=171  SELL hit=0.368 mean=-1.21 n=171
    240m BUY hit=0.410 mean=-3.03 n=166  SELL hit=0.422 mean=-0.39 n=166
  Q4: n=213
      5m BUY hit=0.286 mean=-1.91 n=213  SELL hit=0.310 mean=-1.02 n=213
     60m BUY hit=0.453 mean=-1.91 n=212  SELL hit=0.406 mean=-1.02 n=212
    240m BUY hit=0.481 mean=+1.08 n=212  SELL hit=0.406 mean=-4.08 n=212
  earlier:
  Q1: n=76
      5m BUY hit=0.467 mean=-0.68 n=75  SELL hit=0.213 mean=-3.06 n=75
     60m BUY hit=0.566 mean=+2.47 n=76  SELL hit=0.250 mean=-6.17 n=76
    240m BUY hit=0.382 mean=-1.41 n=76  SELL hit=0.382 mean=-2.10 n=76
  Q2: n=76
      5m BUY hit=0.211 mean=-1.66 n=76  SELL hit=0.250 mean=-2.03 n=76
     60m BUY hit=0.368 mean=+0.01 n=76  SELL hit=0.276 mean=-4.12 n=76
    240m BUY hit=0.355 mean=-1.22 n=76  SELL hit=0.355 mean=-2.56 n=76
  Q3: n=76
      5m BUY hit=0.355 mean=-1.30 n=76  SELL hit=0.158 mean=-2.22 n=76
     60m BUY hit=0.440 mean=-0.82 n=75  SELL hit=0.320 mean=-3.29 n=75
    240m BUY hit=0.395 mean=-0.71 n=76  SELL hit=0.408 mean=-3.21 n=76
  Q4: n=76
      5m BUY hit=0.276 mean=-2.52 n=76  SELL hit=0.355 mean=-0.66 n=76
     60m BUY hit=0.461 mean=-3.27 n=76  SELL hit=0.447 mean=+0.11 n=76
    240m BUY hit=0.526 mean=+2.35 n=76  SELL hit=0.368 mean=-5.69 n=76
  later:
  Q1: n=69
      5m BUY hit=0.362 mean=-1.50 n=69  SELL hit=0.246 mean=-1.65 n=69
     60m BUY hit=0.551 mean=+1.24 n=69  SELL hit=0.319 mean=-4.35 n=69
    240m BUY hit=0.531 mean=-7.95 n=64  SELL hit=0.391 mean=+4.80 n=64
  Q2: n=65
      5m BUY hit=0.354 mean=-1.83 n=65  SELL hit=0.308 mean=-1.24 n=65
     60m BUY hit=0.523 mean=-2.85 n=65  SELL hit=0.369 mean=-0.25 n=65
    240m BUY hit=0.433 mean=-8.21 n=60  SELL hit=0.367 mean=+5.13 n=60
  Q3: n=96
      5m BUY hit=0.292 mean=-2.46 n=96  SELL hit=0.385 mean=-0.48 n=96
     60m BUY hit=0.354 mean=-3.37 n=96  SELL hit=0.406 mean=+0.42 n=96
    240m BUY hit=0.422 mean=-4.99 n=90  SELL hit=0.433 mean=+1.99 n=90
  Q4: n=137
      5m BUY hit=0.292 mean=-1.56 n=137  SELL hit=0.285 mean=-1.22 n=137
     60m BUY hit=0.449 mean=-1.15 n=136  SELL hit=0.382 mean=-1.65 n=136
    240m BUY hit=0.456 mean=+0.37 n=136  SELL hit=0.426 mean=-3.18 n=136

ret_1 (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=155
      5m BUY hit=0.370 mean=-1.25 n=154  SELL hit=0.247 mean=-1.71 n=154
     60m BUY hit=0.542 mean=+0.40 n=155  SELL hit=0.335 mean=-3.57 n=155
    240m BUY hit=0.464 mean=-2.85 n=151  SELL hit=0.404 mean=-0.35 n=151
  Q2: n=178
      5m BUY hit=0.315 mean=-1.98 n=178  SELL hit=0.320 mean=-1.40 n=178
     60m BUY hit=0.483 mean=-0.61 n=178  SELL hit=0.281 mean=-3.03 n=178
    240m BUY hit=0.439 mean=-0.38 n=173  SELL hit=0.405 mean=-2.98 n=173
  Q3: n=173
      5m BUY hit=0.324 mean=-1.63 n=173  SELL hit=0.277 mean=-1.81 n=173
     60m BUY hit=0.413 mean=-1.01 n=172  SELL hit=0.331 mean=-2.41 n=172
    240m BUY hit=0.476 mean=-0.42 n=170  SELL hit=0.324 mean=-3.04 n=170
  Q4: n=165
      5m BUY hit=0.279 mean=-1.90 n=165  SELL hit=0.267 mean=-1.12 n=165
     60m BUY hit=0.396 mean=-2.94 n=164  SELL hit=0.463 mean=-0.08 n=164
    240m BUY hit=0.369 mean=-5.68 n=160  SELL hit=0.456 mean=+2.59 n=160
  earlier:
  Q1: n=76
      5m BUY hit=0.413 mean=-0.46 n=75  SELL hit=0.213 mean=-2.43 n=75
     60m BUY hit=0.592 mean=+1.24 n=76  SELL hit=0.250 mean=-4.55 n=76
    240m BUY hit=0.447 mean=+0.14 n=76  SELL hit=0.382 mean=-3.49 n=76
  Q2: n=76
      5m BUY hit=0.303 mean=-2.20 n=76  SELL hit=0.289 mean=-1.85 n=76
     60m BUY hit=0.421 mean=-0.91 n=76  SELL hit=0.303 mean=-3.71 n=76
    240m BUY hit=0.382 mean=+0.55 n=76  SELL hit=0.434 mean=-4.47 n=76
  Q3: n=76
      5m BUY hit=0.342 mean=-1.38 n=76  SELL hit=0.211 mean=-2.74 n=76
     60m BUY hit=0.453 mean=+0.15 n=75  SELL hit=0.227 mean=-4.24 n=75
    240m BUY hit=0.461 mean=+1.00 n=76  SELL hit=0.250 mean=-5.12 n=76
  Q4: n=76
      5m BUY hit=0.250 mean=-2.13 n=76  SELL hit=0.263 mean=-0.94 n=76
     60m BUY hit=0.368 mean=-2.07 n=76  SELL hit=0.513 mean=-0.99 n=76
    240m BUY hit=0.368 mean=-2.68 n=76  SELL hit=0.447 mean=-0.48 n=76
  later:
  Q1: n=79
      5m BUY hit=0.329 mean=-2.01 n=79  SELL hit=0.278 mean=-1.03 n=79
     60m BUY hit=0.494 mean=-0.40 n=79  SELL hit=0.418 mean=-2.62 n=79
    240m BUY hit=0.480 mean=-5.87 n=75  SELL hit=0.427 mean=+2.83 n=75
  Q2: n=102
      5m BUY hit=0.324 mean=-1.83 n=102  SELL hit=0.343 mean=-1.06 n=102
     60m BUY hit=0.529 mean=-0.37 n=102  SELL hit=0.265 mean=-2.53 n=102
    240m BUY hit=0.485 mean=-1.12 n=97  SELL hit=0.381 mean=-1.81 n=97
  Q3: n=97
      5m BUY hit=0.309 mean=-1.82 n=97  SELL hit=0.330 mean=-1.08 n=97
     60m BUY hit=0.381 mean=-1.91 n=97  SELL hit=0.412 mean=-1.00 n=97
    240m BUY hit=0.489 mean=-1.57 n=94  SELL hit=0.383 mean=-1.36 n=94
  Q4: n=89
      5m BUY hit=0.303 mean=-1.70 n=89  SELL hit=0.270 mean=-1.28 n=89
     60m BUY hit=0.420 mean=-3.69 n=88  SELL hit=0.420 mean=+0.71 n=88
    240m BUY hit=0.369 mean=-8.38 n=84  SELL hit=0.464 mean=+5.38 n=84

ret_15 (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=176
      5m BUY hit=0.371 mean=-1.58 n=175  SELL hit=0.314 mean=-1.50 n=175
     60m BUY hit=0.523 mean=+0.27 n=176  SELL hit=0.335 mean=-3.67 n=176
    240m BUY hit=0.422 mean=-3.70 n=173  SELL hit=0.439 mean=+0.47 n=173
  Q2: n=161
      5m BUY hit=0.348 mean=-1.35 n=161  SELL hit=0.255 mean=-1.80 n=161
     60m BUY hit=0.534 mean=+0.51 n=161  SELL hit=0.242 mean=-3.65 n=161
    240m BUY hit=0.516 mean=+0.38 n=157  SELL hit=0.344 mean=-3.68 n=157
  Q3: n=152
      5m BUY hit=0.329 mean=-1.46 n=152  SELL hit=0.237 mean=-2.09 n=152
     60m BUY hit=0.421 mean=-0.82 n=152  SELL hit=0.329 mean=-2.77 n=152
    240m BUY hit=0.445 mean=+0.40 n=146  SELL hit=0.329 mean=-3.88 n=146
  Q4: n=182
      5m BUY hit=0.242 mean=-2.34 n=182  SELL hit=0.302 mean=-0.77 n=182
     60m BUY hit=0.356 mean=-3.92 n=180  SELL hit=0.483 mean=+0.75 n=180
    240m BUY hit=0.376 mean=-5.36 n=178  SELL hit=0.455 mean=+2.21 n=178
  earlier:
  Q1: n=76
      5m BUY hit=0.413 mean=-1.00 n=75  SELL hit=0.280 mean=-2.20 n=75
     60m BUY hit=0.592 mean=+2.05 n=76  SELL hit=0.237 mean=-6.02 n=76
    240m BUY hit=0.408 mean=-0.21 n=76  SELL hit=0.408 mean=-3.31 n=76
  Q2: n=76
      5m BUY hit=0.368 mean=-1.31 n=76  SELL hit=0.211 mean=-2.12 n=76
     60m BUY hit=0.566 mean=+1.17 n=76  SELL hit=0.211 mean=-4.57 n=76
    240m BUY hit=0.539 mean=+2.81 n=76  SELL hit=0.303 mean=-6.50 n=76
  Q3: n=76
      5m BUY hit=0.289 mean=-1.80 n=76  SELL hit=0.237 mean=-2.32 n=76
     60m BUY hit=0.342 mean=-1.43 n=76  SELL hit=0.382 mean=-2.74 n=76
    240m BUY hit=0.355 mean=-1.44 n=76  SELL hit=0.382 mean=-2.51 n=76
  Q4: n=76
      5m BUY hit=0.237 mean=-2.08 n=76  SELL hit=0.250 mean=-1.32 n=76
     60m BUY hit=0.333 mean=-3.43 n=75  SELL hit=0.467 mean=-0.10 n=75
    240m BUY hit=0.355 mean=-2.16 n=76  SELL hit=0.421 mean=-1.25 n=76
  later:
  Q1: n=100
      5m BUY hit=0.340 mean=-2.01 n=100  SELL hit=0.340 mean=-0.98 n=100
     60m BUY hit=0.470 mean=-1.09 n=100  SELL hit=0.410 mean=-1.89 n=100
    240m BUY hit=0.433 mean=-6.44 n=97  SELL hit=0.464 mean=+3.43 n=97
  Q2: n=85
      5m BUY hit=0.329 mean=-1.39 n=85  SELL hit=0.294 mean=-1.51 n=85
     60m BUY hit=0.506 mean=-0.07 n=85  SELL hit=0.271 mean=-2.83 n=85
    240m BUY hit=0.494 mean=-1.90 n=81  SELL hit=0.383 mean=-1.04 n=81
  Q3: n=76
      5m BUY hit=0.368 mean=-1.11 n=76  SELL hit=0.237 mean=-1.85 n=76
     60m BUY hit=0.500 mean=-0.21 n=76  SELL hit=0.276 mean=-2.80 n=76
    240m BUY hit=0.543 mean=+2.39 n=70  SELL hit=0.271 mean=-5.37 n=70
  Q4: n=106
      5m BUY hit=0.245 mean=-2.54 n=106  SELL hit=0.340 mean=-0.38 n=106
     60m BUY hit=0.371 mean=-4.27 n=105  SELL hit=0.495 mean=+1.36 n=105
    240m BUY hit=0.392 mean=-7.74 n=102  SELL hit=0.480 mean=+4.79 n=102

ret_30 (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=156
      5m BUY hit=0.368 mean=-1.38 n=155  SELL hit=0.265 mean=-1.86 n=155
     60m BUY hit=0.577 mean=+1.65 n=156  SELL hit=0.321 mean=-4.94 n=156
    240m BUY hit=0.461 mean=-2.89 n=152  SELL hit=0.382 mean=-0.47 n=152
  Q2: n=169
      5m BUY hit=0.325 mean=-1.39 n=169  SELL hit=0.266 mean=-1.85 n=169
     60m BUY hit=0.462 mean=-0.44 n=169  SELL hit=0.314 mean=-2.89 n=169
    240m BUY hit=0.467 mean=-0.42 n=165  SELL hit=0.364 mean=-2.78 n=165
  Q3: n=179
      5m BUY hit=0.346 mean=-1.70 n=179  SELL hit=0.263 mean=-1.48 n=179
     60m BUY hit=0.492 mean=-0.76 n=177  SELL hit=0.277 mean=-2.69 n=177
    240m BUY hit=0.457 mean=-0.76 n=173  SELL hit=0.364 mean=-2.59 n=173
  Q4: n=167
      5m BUY hit=0.246 mean=-2.31 n=167  SELL hit=0.323 mean=-0.87 n=167
     60m BUY hit=0.305 mean=-4.49 n=167  SELL hit=0.497 mean=+1.29 n=167
    240m BUY hit=0.366 mean=-5.10 n=164  SELL hit=0.476 mean=+1.88 n=164
  earlier:
  Q1: n=76
      5m BUY hit=0.373 mean=-1.45 n=75  SELL hit=0.280 mean=-2.02 n=75
     60m BUY hit=0.645 mean=+3.02 n=76  SELL hit=0.224 mean=-6.59 n=76
    240m BUY hit=0.474 mean=+0.91 n=76  SELL hit=0.303 mean=-4.56 n=76
  Q2: n=76
      5m BUY hit=0.342 mean=-1.50 n=76  SELL hit=0.211 mean=-2.17 n=76
     60m BUY hit=0.474 mean=+0.60 n=76  SELL hit=0.263 mean=-4.49 n=76
    240m BUY hit=0.395 mean=+0.72 n=76  SELL hit=0.421 mean=-4.26 n=76
  Q3: n=76
      5m BUY hit=0.329 mean=-1.35 n=76  SELL hit=0.250 mean=-2.09 n=76
     60m BUY hit=0.440 mean=-0.20 n=75  SELL hit=0.253 mean=-3.85 n=75
    240m BUY hit=0.461 mean=+1.47 n=76  SELL hit=0.303 mean=-5.27 n=76
  Q4: n=76
      5m BUY hit=0.263 mean=-1.89 n=76  SELL hit=0.237 mean=-1.68 n=76
     60m BUY hit=0.276 mean=-5.02 n=76  SELL hit=0.553 mean=+1.45 n=76
    240m BUY hit=0.329 mean=-4.09 n=76  SELL hit=0.487 mean=+0.52 n=76
  later:
  Q1: n=80
      5m BUY hit=0.362 mean=-1.33 n=80  SELL hit=0.250 mean=-1.70 n=80
     60m BUY hit=0.512 mean=+0.36 n=80  SELL hit=0.412 mean=-3.37 n=80
    240m BUY hit=0.447 mean=-6.68 n=76  SELL hit=0.461 mean=+3.62 n=76
  Q2: n=93
      5m BUY hit=0.312 mean=-1.30 n=93  SELL hit=0.312 mean=-1.59 n=93
     60m BUY hit=0.452 mean=-1.30 n=93  SELL hit=0.355 mean=-1.58 n=93
    240m BUY hit=0.528 mean=-1.40 n=89  SELL hit=0.315 mean=-1.52 n=89
  Q3: n=103
      5m BUY hit=0.359 mean=-1.96 n=103  SELL hit=0.272 mean=-1.04 n=103
     60m BUY hit=0.529 mean=-1.17 n=102  SELL hit=0.294 mean=-1.85 n=102
    240m BUY hit=0.454 mean=-2.51 n=97  SELL hit=0.412 mean=-0.49 n=97
  Q4: n=91
      5m BUY hit=0.231 mean=-2.67 n=91  SELL hit=0.396 mean=-0.18 n=91
     60m BUY hit=0.330 mean=-4.05 n=91  SELL hit=0.451 mean=+1.16 n=91
    240m BUY hit=0.398 mean=-5.97 n=88  SELL hit=0.466 mean=+3.06 n=88

gross_portfolio_exposure (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=380
      5m BUY hit=0.366 mean=-1.53 n=380  SELL hit=0.282 mean=-1.58 n=380
     60m BUY hit=0.517 mean=-0.94 n=379  SELL hit=0.327 mean=-2.13 n=379
    240m BUY hit=0.477 mean=-3.16 n=363  SELL hit=0.380 mean=-0.02 n=363
  Q2: n=109
      5m BUY hit=0.284 mean=-1.72 n=109  SELL hit=0.284 mean=-2.00 n=109
     60m BUY hit=0.404 mean=-0.57 n=109  SELL hit=0.385 mean=-2.79 n=109
    240m BUY hit=0.450 mean=-0.53 n=109  SELL hit=0.303 mean=-3.37 n=109
  Q3: n=111
      5m BUY hit=0.218 mean=-2.09 n=110  SELL hit=0.291 mean=-0.96 n=110
     60m BUY hit=0.387 mean=-0.65 n=111  SELL hit=0.396 mean=-2.48 n=111
    240m BUY hit=0.405 mean=-0.72 n=111  SELL hit=0.450 mean=-2.51 n=111
  Q4: n=71
      5m BUY hit=0.296 mean=-1.99 n=71  SELL hit=0.239 mean=-1.20 n=71
     60m BUY hit=0.329 mean=-3.01 n=70  SELL hit=0.357 mean=-1.93 n=70
    240m BUY hit=0.268 mean=-2.70 n=71  SELL hit=0.535 mean=-0.21 n=71
  earlier:
  Q1: n=88
      5m BUY hit=0.466 mean=-1.15 n=88  SELL hit=0.239 mean=-2.49 n=88
     60m BUY hit=0.625 mean=+1.64 n=88  SELL hit=0.284 mean=-5.03 n=88
    240m BUY hit=0.580 mean=+1.35 n=88  SELL hit=0.261 mean=-5.11 n=88
  Q2: n=64
      5m BUY hit=0.297 mean=-1.84 n=64  SELL hit=0.234 mean=-2.48 n=64
     60m BUY hit=0.406 mean=-1.19 n=64  SELL hit=0.344 mean=-2.53 n=64
    240m BUY hit=0.391 mean=-0.39 n=64  SELL hit=0.281 mean=-4.25 n=64
  Q3: n=92
      5m BUY hit=0.220 mean=-1.66 n=91  SELL hit=0.275 mean=-1.42 n=91
     60m BUY hit=0.402 mean=-0.69 n=92  SELL hit=0.380 mean=-2.47 n=92
    240m BUY hit=0.359 mean=-0.85 n=92  SELL hit=0.467 mean=-2.44 n=92
  Q4: n=60
      5m BUY hit=0.317 mean=-1.64 n=60  SELL hit=0.217 mean=-1.61 n=60
     60m BUY hit=0.356 mean=-2.14 n=59  SELL hit=0.271 mean=-3.19 n=59
    240m BUY hit=0.283 mean=-1.51 n=60  SELL hit=0.517 mean=-1.41 n=60
  later:
  Q1: n=292
      5m BUY hit=0.336 mean=-1.65 n=292  SELL hit=0.295 mean=-1.31 n=292
     60m BUY hit=0.485 mean=-1.72 n=291  SELL hit=0.340 mean=-1.25 n=291
    240m BUY hit=0.444 mean=-4.60 n=275  SELL hit=0.418 mean=+1.61 n=275
  Q2: n=45
      5m BUY hit=0.267 mean=-1.54 n=45  SELL hit=0.356 mean=-1.31 n=45
     60m BUY hit=0.400 mean=+0.32 n=45  SELL hit=0.444 mean=-3.17 n=45
    240m BUY hit=0.533 mean=-0.73 n=45  SELL hit=0.333 mean=-2.12 n=45
  Q3: n=19 [SMALL]
      5m BUY hit=0.211 mean=-4.14 n=19  SELL hit=0.368 mean=+1.21 n=19 [SMALL]
     60m BUY hit=0.316 mean=-0.43 n=19  SELL hit=0.474 mean=-2.49 n=19 [SMALL]
    240m BUY hit=0.632 mean=-0.04 n=19  SELL hit=0.368 mean=-2.85 n=19 [SMALL]
  Q4: n=11 [SMALL]
      5m BUY hit=0.182 mean=-3.90 n=11  SELL hit=0.364 mean=+1.02 n=11 [SMALL]
     60m BUY hit=0.182 mean=-7.72 n=11  SELL hit=0.818 mean=+4.85 n=11 [SMALL]
    240m BUY hit=0.182 mean=-9.19 n=11  SELL hit=0.636 mean=+6.29 n=11 [SMALL]

same_usd_direction_count (quartile cuts from earlier unique opportunities only):
  pooled:
  Q1: n=670
      5m BUY hit=0.321 mean=-1.69 n=669  SELL hit=0.278 mean=-1.52 n=669
     60m BUY hit=0.458 mean=-1.05 n=668  SELL hit=0.352 mean=-2.27 n=668
    240m BUY hit=0.438 mean=-2.26 n=653  SELL hit=0.397 mean=-1.02 n=653
  Q4: n=1 [SMALL]
      5m BUY hit=0.000 mean=-7.90 n=1  SELL hit=1.000 mean=+5.40 n=1 [SMALL]
     60m BUY hit=0.000 mean=-1.00 n=1  SELL hit=0.000 mean=-1.30 n=1 [SMALL]
    240m BUY hit=0.000 mean=-1.60 n=1  SELL hit=0.000 mean=-0.70 n=1 [SMALL]
  earlier:
  Q1: n=303
      5m BUY hit=0.328 mean=-1.52 n=302  SELL hit=0.242 mean=-2.01 n=302
     60m BUY hit=0.460 mean=-0.40 n=302  SELL hit=0.325 mean=-3.38 n=302
    240m BUY hit=0.416 mean=-0.24 n=303  SELL hit=0.380 mean=-3.40 n=303
  Q4: n=1 [SMALL]
      5m BUY hit=0.000 mean=-7.90 n=1  SELL hit=1.000 mean=+5.40 n=1 [SMALL]
     60m BUY hit=0.000 mean=-1.00 n=1  SELL hit=0.000 mean=-1.30 n=1 [SMALL]
    240m BUY hit=0.000 mean=-1.60 n=1  SELL hit=0.000 mean=-0.70 n=1 [SMALL]
  later:
  Q1: n=367
      5m BUY hit=0.316 mean=-1.83 n=367  SELL hit=0.308 mean=-1.11 n=367
     60m BUY hit=0.456 mean=-1.58 n=366  SELL hit=0.374 mean=-1.37 n=366
    240m BUY hit=0.457 mean=-4.00 n=350  SELL hit=0.411 mean=+1.03 n=350

Categorical:
production_stub_side:
  BUY: n=360
      5m BUY hit=0.333 mean=-1.53 n=360  SELL hit=0.281 mean=-1.48 n=360
     60m BUY hit=0.514 mean=-0.44 n=358  SELL hit=0.327 mean=-2.69 n=358
    240m BUY hit=0.510 mean=+1.46 n=357  SELL hit=0.361 mean=-4.63 n=357
  SELL: n=311
      5m BUY hit=0.306 mean=-1.90 n=310  SELL hit=0.277 mean=-1.54 n=310
     60m BUY hit=0.392 mean=-1.74 n=311  SELL hit=0.379 mean=-1.80 n=311
    240m BUY hit=0.350 mean=-6.72 n=297  SELL hit=0.438 mean=+3.31 n=297

strategy_label:
  mean_reversion: n=46
      5m BUY hit=0.391 mean=-1.98 n=46  SELL hit=0.304 mean=-1.08 n=46
     60m BUY hit=0.370 mean=-3.80 n=46  SELL hit=0.478 mean=+0.72 n=46
    240m BUY hit=0.250 mean=-13.42 n=40  SELL hit=0.600 mean=+10.03 n=40
  scalp: n=37
      5m BUY hit=0.270 mean=-2.79 n=37  SELL hit=0.432 mean=-0.22 n=37
     60m BUY hit=0.405 mean=-5.01 n=37  SELL hit=0.568 mean=+1.98 n=37
    240m BUY hit=0.375 mean=-10.78 n=32  SELL hit=0.531 mean=+7.69 n=32
  swing_breakout: n=123
      5m BUY hit=0.341 mean=-1.32 n=123  SELL hit=0.203 mean=-2.44 n=123
     60m BUY hit=0.463 mean=-0.34 n=123  SELL hit=0.309 mean=-3.44 n=123
    240m BUY hit=0.463 mean=-0.61 n=123  SELL hit=0.317 mean=-3.22 n=123
  swing_mean_reversion: n=266
      5m BUY hit=0.305 mean=-1.63 n=266  SELL hit=0.286 mean=-1.49 n=266
     60m BUY hit=0.468 mean=-0.66 n=265  SELL hit=0.336 mean=-2.57 n=265
    240m BUY hit=0.447 mean=-1.90 n=266  SELL hit=0.376 mean=-1.18 n=266
  swing_trend: n=153
      5m BUY hit=0.342 mean=-1.15 n=152  SELL hit=0.217 mean=-1.92 n=152
     60m BUY hit=0.477 mean=+0.28 n=153  SELL hit=0.281 mean=-3.62 n=153
    240m BUY hit=0.497 mean=+1.57 n=153  SELL hit=0.353 mean=-4.83 n=153
  trend: n=46
      5m BUY hit=0.261 mean=-3.83 n=46  SELL hit=0.500 mean=+0.76 n=46
     60m BUY hit=0.444 mean=-3.70 n=45  SELL hit=0.489 mean=+0.67 n=45
    240m BUY hit=0.300 mean=-6.34 n=40  SELL hit=0.625 mean=+3.25 n=40

usd_direction:
  LONG: n=394
      5m BUY hit=0.325 mean=-1.65 n=394  SELL hit=0.274 mean=-1.53 n=394
     60m BUY hit=0.467 mean=-0.83 n=392  SELL hit=0.342 mean=-2.57 n=392
    240m BUY hit=0.379 mean=-1.40 n=391  SELL hit=0.430 mean=-1.84 n=391
  SHORT: n=277
      5m BUY hit=0.315 mean=-1.78 n=276  SELL hit=0.286 mean=-1.47 n=276
     60m BUY hit=0.444 mean=-1.35 n=277  SELL hit=0.365 mean=-1.85 n=277
    240m BUY hit=0.525 mean=-3.53 n=263  SELL hit=0.346 mean=+0.20 n=263

utc_block:
  00-06: n=67
      5m BUY hit=0.284 mean=-1.05 n=67  SELL hit=0.209 mean=-1.86 n=67
     60m BUY hit=0.448 mean=-0.88 n=67  SELL hit=0.254 mean=-2.07 n=67
    240m BUY hit=0.672 mean=+1.41 n=67  SELL hit=0.149 mean=-4.36 n=67
  06-12: n=201
      5m BUY hit=0.358 mean=-1.30 n=201  SELL hit=0.224 mean=-1.67 n=201
     60m BUY hit=0.478 mean=-1.57 n=201  SELL hit=0.378 mean=-1.42 n=201
    240m BUY hit=0.463 mean=-4.19 n=201  SELL hit=0.463 mean=+1.21 n=201
  12-18: n=307
      5m BUY hit=0.355 mean=-1.83 n=307  SELL hit=0.349 mean=-1.08 n=307
     60m BUY hit=0.505 mean=-0.44 n=307  SELL hit=0.401 mean=-2.47 n=307
    240m BUY hit=0.443 mean=-1.54 n=300  SELL hit=0.380 mean=-1.75 n=300
  18-24: n=96
      5m BUY hit=0.158 mean=-2.60 n=95  SELL hit=0.221 mean=-2.29 n=95
     60m BUY hit=0.266 mean=-2.05 n=94  SELL hit=0.202 mean=-3.60 n=94
    240m BUY hit=0.174 mean=-3.12 n=86  SELL hit=0.488 mean=-1.13 n=86

hour_utc:
  0: n=15 [SMALL]
     60m BUY hit=0.600 mean=+1.17 n=15  SELL hit=0.267 mean=-4.22 n=15 [SMALL]
  1: n=20 [SMALL]
     60m BUY hit=0.300 mean=-1.18 n=20  SELL hit=0.250 mean=-1.84 n=20 [SMALL]
  10: n=45
     60m BUY hit=0.489 mean=-3.73 n=45  SELL hit=0.400 mean=+0.73 n=45
  11: n=58
     60m BUY hit=0.310 mean=-2.62 n=58  SELL hit=0.534 mean=-0.40 n=58
  12: n=56
     60m BUY hit=0.482 mean=-0.08 n=56  SELL hit=0.339 mean=-2.85 n=56
  13: n=63
     60m BUY hit=0.603 mean=+1.81 n=63  SELL hit=0.317 mean=-4.70 n=63
  14: n=52
     60m BUY hit=0.404 mean=-1.06 n=52  SELL hit=0.481 mean=-1.77 n=52
  15: n=55
     60m BUY hit=0.527 mean=-1.69 n=55  SELL hit=0.418 mean=-1.27 n=55
  16: n=58
     60m BUY hit=0.483 mean=-1.06 n=58  SELL hit=0.466 mean=-1.86 n=58
  17: n=23 [SMALL]
     60m BUY hit=0.522 mean=-1.48 n=23  SELL hit=0.391 mean=-1.43 n=23 [SMALL]
  18: n=30
     60m BUY hit=0.400 mean=+0.01 n=30  SELL hit=0.233 mean=-2.93 n=30
  19: n=23 [SMALL]
     60m BUY hit=0.348 mean=-0.40 n=23  SELL hit=0.304 mean=-2.77 n=23 [SMALL]
  2: n=10 [SMALL]
     60m BUY hit=0.400 mean=-0.02 n=10  SELL hit=0.300 mean=-2.98 n=10 [SMALL]
  20: n=22 [SMALL]
     60m BUY hit=0.250 mean=-5.86 n=20  SELL hit=0.150 mean=-4.17 n=20 [SMALL]
  21: n=12 [SMALL]
     60m BUY hit=0.000 mean=-3.16 n=12  SELL hit=0.000 mean=-8.16 n=12 [SMALL]
  22: n=6 [SMALL]
     60m BUY hit=0.000 mean=-2.87 n=6  SELL hit=0.000 mean=-1.18 n=6 [SMALL]
  23: n=3 [SMALL]
     60m BUY hit=0.000 mean=-3.73 n=3  SELL hit=0.667 mean=+0.60 n=3 [SMALL]
  3: n=7 [SMALL]
     60m BUY hit=0.571 mean=+0.36 n=7  SELL hit=0.000 mean=-2.96 n=7 [SMALL]
  4: n=4 [SMALL]
     60m BUY hit=0.750 mean=+0.77 n=4  SELL hit=0.000 mean=-3.40 n=4 [SMALL]
  5: n=11 [SMALL]
     60m BUY hit=0.364 mean=-5.30 n=11  SELL hit=0.455 mean=+2.35 n=11 [SMALL]
  6: n=27 [SMALL]
     60m BUY hit=0.444 mean=-2.20 n=27  SELL hit=0.407 mean=-0.81 n=27 [SMALL]
  7: n=21 [SMALL]
     60m BUY hit=0.714 mean=+4.03 n=21  SELL hit=0.238 mean=-6.95 n=21 [SMALL]
  8: n=27 [SMALL]
     60m BUY hit=0.593 mean=+0.16 n=27  SELL hit=0.185 mean=-3.01 n=27 [SMALL]
  9: n=23 [SMALL]
     60m BUY hit=0.565 mean=-1.07 n=23  SELL hit=0.261 mean=-1.98 n=23 [SMALL]

day_of_week:
  3: n=300
      5m BUY hit=0.324 mean=-1.55 n=299  SELL hit=0.244 mean=-1.99 n=299
     60m BUY hit=0.458 mean=-0.41 n=299  SELL hit=0.321 mean=-3.37 n=299
    240m BUY hit=0.410 mean=-0.30 n=300  SELL hit=0.383 mean=-3.35 n=300
  4: n=371
      5m BUY hit=0.318 mean=-1.82 n=371  SELL hit=0.307 mean=-1.12 n=371
     60m BUY hit=0.457 mean=-1.56 n=370  SELL hit=0.376 mean=-1.39 n=370
    240m BUY hit=0.460 mean=-3.92 n=354  SELL hit=0.407 mean=+0.95 n=354

broker_backed_position_count:
  0: n=9 [SMALL]
      5m BUY hit=0.333 mean=-0.76 n=9  SELL hit=0.000 mean=-2.18 n=9 [SMALL]
     60m BUY hit=0.556 mean=+1.79 n=9  SELL hit=0.333 mean=-4.79 n=9 [SMALL]
    240m BUY hit=0.667 mean=+5.69 n=9  SELL hit=0.333 mean=-8.63 n=9 [SMALL]
  1: n=25 [SMALL]
      5m BUY hit=0.400 mean=+0.15 n=25  SELL hit=0.160 mean=-3.00 n=25 [SMALL]
     60m BUY hit=0.400 mean=-0.86 n=25  SELL hit=0.360 mean=-2.02 n=25 [SMALL]
    240m BUY hit=0.480 mean=+1.53 n=25  SELL hit=0.480 mean=-4.41 n=25 [SMALL]
  2: n=247
      5m BUY hit=0.313 mean=-1.76 n=246  SELL hit=0.305 mean=-1.33 n=246
     60m BUY hit=0.482 mean=-0.55 n=247  SELL hit=0.397 mean=-2.52 n=247
    240m BUY hit=0.482 mean=-1.10 n=247  SELL hit=0.356 mean=-2.07 n=247
  3: n=298
      5m BUY hit=0.332 mean=-1.82 n=298  SELL hit=0.268 mean=-1.63 n=298
     60m BUY hit=0.443 mean=-1.09 n=296  SELL hit=0.321 mean=-2.61 n=296
    240m BUY hit=0.385 mean=-3.82 n=286  SELL hit=0.420 mean=+0.38 n=286
  4: n=92
      5m BUY hit=0.283 mean=-1.77 n=92  SELL hit=0.304 mean=-1.11 n=92
     60m BUY hit=0.446 mean=-2.57 n=92  SELL hit=0.326 mean=-0.32 n=92
    240m BUY hit=0.448 mean=-2.33 n=87  SELL hit=0.414 mean=-0.90 n=87

CHRONOLOGICAL STABILITY:
Earlier vs later unique-opportunity halves; Q1 vs Q4 at 60m.
atr_over_price: DESCRIPTIVE CANDIDATE - UNSTABLE
  earlier: BUY Q4-Q1 hit=+0.026 mean=-0.30 n=76/76; SELL hit=+0.197
  later:   BUY Q4-Q1 hit=-0.146 mean=-6.39 n=166/93; SELL hit=+0.271
  pooled:  pooled BUY Q4-Q1 hit=-0.081 mean=-3.70 n=242/169
spread_pips: NO APPARENT INFORMATION
  earlier: BUY Q4-Q1 hit=-0.015 mean=-0.37 n=108/69; SELL hit=-0.161
  later:   BUY Q4-Q1 hit=+0.044 mean=-2.85 n=138/95; SELL hit=-0.006
  pooled:  pooled BUY Q4-Q1 hit=+0.018 mean=-1.81 n=246/164
spread_over_atr: DESCRIPTIVE CANDIDATE - UNSTABLE
  earlier: BUY Q4-Q1 hit=-0.100 mean=-0.68 n=76/75; SELL hit=-0.221
  later:   BUY Q4-Q1 hit=+0.228 mean=+6.13 n=101/159; SELL hit=-0.377
  pooled:  pooled BUY Q4-Q1 hit=+0.093 mean=+3.21 n=177/234
sma_difference_over_atr: INSUFFICIENT SAMPLE
  earlier: BUY Q4-Q1 hit=+0.197 mean=+0.22 n=76/76; SELL hit=-0.105
  later:   BUY Q4-Q1 hit=-0.057 mean=-5.16 n=27/78; SELL hit=+0.124
  pooled:  pooled BUY Q4-Q1 hit=+0.079 mean=-1.42 n=103/154
rsi: DESCRIPTIVE CANDIDATE - REPEATED
  earlier: BUY Q4-Q1 hit=-0.395 mean=-9.74 n=76/76; SELL hit=+0.421
  later:   BUY Q4-Q1 hit=-0.228 mean=-3.40 n=93/119; SELL hit=+0.137
  pooled:  pooled BUY Q4-Q1 hit=-0.302 mean=-6.16 n=169/195
macd_over_atr: NO APPARENT INFORMATION
  earlier: BUY Q4-Q1 hit=-0.079 mean=-5.56 n=76/76; SELL hit=+0.211
  later:   BUY Q4-Q1 hit=-0.054 mean=+1.32 n=76/111; SELL hit=-0.079
  pooled:  pooled BUY Q4-Q1 hit=-0.069 mean=-1.87 n=152/187
bollinger_position: DESCRIPTIVE CANDIDATE - REPEATED
  earlier: BUY Q4-Q1 hit=-0.105 mean=-5.74 n=76/76; SELL hit=+0.197
  later:   BUY Q4-Q1 hit=-0.102 mean=-2.38 n=69/136; SELL hit=+0.064
  pooled:  pooled BUY Q4-Q1 hit=-0.106 mean=-3.79 n=145/212
ret_1: NO APPARENT INFORMATION
  earlier: BUY Q4-Q1 hit=-0.224 mean=-3.31 n=76/76; SELL hit=+0.263
  later:   BUY Q4-Q1 hit=-0.073 mean=-3.29 n=79/88; SELL hit=+0.003
  pooled:  pooled BUY Q4-Q1 hit=-0.146 mean=-3.35 n=155/164
ret_15: DESCRIPTIVE CANDIDATE - REPEATED
  earlier: BUY Q4-Q1 hit=-0.259 mean=-5.48 n=76/75; SELL hit=+0.230
  later:   BUY Q4-Q1 hit=-0.099 mean=-3.18 n=100/105; SELL hit=+0.085
  pooled:  pooled BUY Q4-Q1 hit=-0.167 mean=-4.19 n=176/180
ret_30: DESCRIPTIVE CANDIDATE - REPEATED
  earlier: BUY Q4-Q1 hit=-0.368 mean=-8.04 n=76/76; SELL hit=+0.329
  later:   BUY Q4-Q1 hit=-0.183 mean=-4.40 n=80/91; SELL hit=+0.038
  pooled:  pooled BUY Q4-Q1 hit=-0.272 mean=-6.14 n=156/167
gross_portfolio_exposure: INSUFFICIENT SAMPLE
  earlier: BUY Q4-Q1 hit=-0.269 mean=-3.78 n=88/59; SELL hit=-0.013
  later:   BUY Q4-Q1 hit=-0.303 mean=-6.00 n=291/11; SELL hit=+0.478
  pooled:  pooled BUY Q4-Q1 hit=-0.189 mean=-2.08 n=379/70
same_usd_direction_count: INSUFFICIENT SAMPLE
  earlier: BUY Q4-Q1 hit=-0.460 mean=-0.60 n=302/1; SELL hit=-0.325
  later:   BUY Q4-Q1 hit=n/a mean=n/a n=366/0; SELL hit=n/a
  pooled:  pooled BUY Q4-Q1 hit=-0.458 mean=+0.05 n=668/1

Stub side chronological check (stub BUY uses BUY labels; stub SELL uses SELL labels):
  earlier: stubBUY n=142 60m hit=0.567 mean=-0.04  stubSELL n=162 60m hit=0.340 mean=-3.24
  later: stubBUY n=218 60m hit=0.479 mean=-0.71  stubSELL n=149 60m hit=0.423 mean=-0.23

TREND/MOMENTUM CONFLICT MAP:
State = sign(sma_difference) x sign(ret_1). No vote count.
pooled:
  sma_neg|ret1_neg: n=141
     60m BUY hit=0.489 mean=-0.40 n=141  SELL hit=0.305 mean=-3.20 n=141
  sma_neg|ret1_pos: n=170
     60m BUY hit=0.312 mean=-2.86 n=170  SELL hit=0.441 mean=-0.63 n=170
  sma_pos|ret1_neg: n=177
     60m BUY hit=0.542 mean=+0.09 n=177  SELL hit=0.299 mean=-3.18 n=177
  sma_pos|ret1_pos: n=183
     60m BUY hit=0.486 mean=-0.97 n=181  SELL hit=0.354 mean=-2.21 n=181
earlier:
  sma_neg|ret1_neg: n=74
     60m BUY hit=0.459 mean=+0.51 n=74  SELL hit=0.257 mean=-4.54 n=74
  sma_neg|ret1_pos: n=88
     60m BUY hit=0.284 mean=-1.74 n=88  SELL hit=0.409 mean=-2.14 n=88
  sma_pos|ret1_neg: n=70
     60m BUY hit=0.586 mean=+0.39 n=70  SELL hit=0.271 mean=-3.82 n=70
  sma_pos|ret1_pos: n=72
     60m BUY hit=0.549 mean=-0.46 n=71  SELL hit=0.338 mean=-3.22 n=71
later:
  sma_neg|ret1_neg: n=67
     60m BUY hit=0.522 mean=-1.40 n=67  SELL hit=0.358 mean=-1.70 n=67
  sma_neg|ret1_pos: n=82
     60m BUY hit=0.341 mean=-4.05 n=82  SELL hit=0.476 mean=+0.98 n=82
  sma_pos|ret1_neg: n=107
     60m BUY hit=0.514 mean=-0.10 n=107  SELL hit=0.318 mean=-2.76 n=107
  sma_pos|ret1_pos: n=111
     60m BUY hit=0.445 mean=-1.30 n=110  SELL hit=0.364 mean=-1.55 n=110
SMA/ret agreement with production stub:
agree_sma pooled:
  agrees: n=671
     60m BUY hit=0.457 mean=-1.05 n=669  SELL hit=0.351 mean=-2.27 n=669
agree_sma earlier:
  agrees: n=304
     60m BUY hit=0.459 mean=-0.40 n=303  SELL hit=0.323 mean=-3.37 n=303
agree_sma later:
  agrees: n=367
     60m BUY hit=0.456 mean=-1.58 n=366  SELL hit=0.374 mean=-1.37 n=366
agree_ret1 pooled:
  agrees: n=324
     60m BUY hit=0.488 mean=-0.72 n=322  SELL hit=0.332 mean=-2.64 n=322
  opposes: n=347
     60m BUY hit=0.429 mean=-1.35 n=347  SELL hit=0.369 mean=-1.93 n=347
agree_ret1 earlier:
  agrees: n=146
     60m BUY hit=0.503 mean=+0.03 n=145  SELL hit=0.297 mean=-3.90 n=145
  opposes: n=158
     60m BUY hit=0.418 mean=-0.80 n=158  SELL hit=0.348 mean=-2.88 n=158
agree_ret1 later:
  agrees: n=178
     60m BUY hit=0.475 mean=-1.34 n=177  SELL hit=0.362 mean=-1.61 n=177
  opposes: n=189
     60m BUY hit=0.439 mean=-1.81 n=189  SELL hit=0.386 mean=-1.14 n=189
agree_ret15 pooled:
  agrees: n=332
     60m BUY hit=0.467 mean=-1.01 n=330  SELL hit=0.342 mean=-2.37 n=330
  neutral/ambiguous: n=4 [SMALL]
     60m BUY hit=1.000 mean=+6.35 n=4  SELL hit=0.000 mean=-9.25 n=4 [SMALL]
  opposes: n=335
     60m BUY hit=0.442 mean=-1.17 n=335  SELL hit=0.364 mean=-2.10 n=335
agree_ret15 earlier:
  agrees: n=142
     60m BUY hit=0.504 mean=-0.21 n=141  SELL hit=0.291 mean=-3.74 n=141
  neutral/ambiguous: n=2 [SMALL]
     60m BUY hit=1.000 mean=+8.80 n=2  SELL hit=0.000 mean=-11.55 n=2 [SMALL]
  opposes: n=160
     60m BUY hit=0.412 mean=-0.68 n=160  SELL hit=0.356 mean=-2.94 n=160
agree_ret15 later:
  agrees: n=190
     60m BUY hit=0.439 mean=-1.61 n=189  SELL hit=0.381 mean=-1.34 n=189
  neutral/ambiguous: n=2 [SMALL]
     60m BUY hit=1.000 mean=+3.90 n=2  SELL hit=0.000 mean=-6.95 n=2 [SMALL]
  opposes: n=175
     60m BUY hit=0.469 mean=-1.61 n=175  SELL hit=0.371 mean=-1.33 n=175
agree_macd pooled:
  agrees: n=526
     60m BUY hit=0.469 mean=-0.87 n=525  SELL hit=0.349 mean=-2.43 n=525
  opposes: n=145
     60m BUY hit=0.417 mean=-1.69 n=144  SELL hit=0.361 mean=-1.68 n=144
agree_macd earlier:
  agrees: n=246
     60m BUY hit=0.459 mean=-0.32 n=246  SELL hit=0.333 mean=-3.37 n=246
  opposes: n=58
     60m BUY hit=0.456 mean=-0.73 n=57  SELL hit=0.281 mean=-3.38 n=57
agree_macd later:
  agrees: n=280
     60m BUY hit=0.477 mean=-1.36 n=279  SELL hit=0.362 mean=-1.61 n=279
  opposes: n=87
     60m BUY hit=0.391 mean=-2.31 n=87  SELL hit=0.414 mean=-0.58 n=87

VOLATILITY/SPREAD:
See quartile tables above for atr_over_price.
  classification=DESCRIPTIVE CANDIDATE - UNSTABLE
See quartile tables above for spread_pips.
  classification=NO APPARENT INFORMATION
See quartile tables above for spread_over_atr.
  classification=DESCRIPTIVE CANDIDATE - UNSTABLE

CROSS-PAIR USD CONTEXT:
same_usd_direction_count is an observation-time portfolio count, not future movement.
peer_usd_agree_frac is reconstructed from other unique V2 opportunities sharing the same completed M5 start.
Simultaneous pairs are correlated; n is not independent.
same_usd_direction_count:
  0.0: n=33
     60m BUY hit=0.424 mean=-0.70 n=33  SELL hit=0.424 mean=-2.27 n=33
  1.0: n=129
     60m BUY hit=0.438 mean=-0.59 n=128  SELL hit=0.281 mean=-3.16 n=128
  2.0: n=508
     60m BUY hit=0.465 mean=-1.18 n=507  SELL hit=0.365 mean=-2.05 n=507
  3.0: n=1 [SMALL]
     60m BUY hit=0.000 mean=-1.00 n=1  SELL hit=0.000 mean=-1.30 n=1 [SMALL]
simultaneous pair count at m5:
  1: n=102
     60m BUY hit=0.347 mean=-1.84 n=101  SELL hit=0.347 mean=-1.76 n=101
  2: n=204
     60m BUY hit=0.495 mean=-0.99 n=204  SELL hit=0.328 mean=-2.52 n=204
  3: n=201
     60m BUY hit=0.480 mean=-0.86 n=200  SELL hit=0.325 mean=-2.44 n=200
  4: n=96
     60m BUY hit=0.458 mean=-0.96 n=96  SELL hit=0.396 mean=-1.99 n=96
  5: n=50
     60m BUY hit=0.460 mean=-0.24 n=50  SELL hit=0.440 mean=-2.65 n=50
  6: n=18 [SMALL]
     60m BUY hit=0.389 mean=-2.01 n=18  SELL hit=0.444 mean=-0.97 n=18 [SMALL]
peer USD agreement quartile (earlier cuts):
  Q1: n=569
     60m BUY hit=0.477 mean=-0.91 n=568  SELL hit=0.352 mean=-2.36 n=568
  missing: n=102
     60m BUY hit=0.347 mean=-1.84 n=101  SELL hit=0.347 mean=-1.76 n=101
peer earlier:
  Q1: n=270
     60m BUY hit=0.487 mean=-0.26 n=269  SELL hit=0.323 mean=-3.38 n=269
  missing: n=34
     60m BUY hit=0.235 mean=-1.49 n=34  SELL hit=0.324 mean=-3.29 n=34
peer later:
  Q1: n=299
     60m BUY hit=0.468 mean=-1.49 n=299  SELL hit=0.378 mean=-1.45 n=299
  missing: n=68
     60m BUY hit=0.403 mean=-2.02 n=67  SELL hit=0.358 mean=-0.98 n=67
usd_direction pooled:
  LONG: n=394
     60m BUY hit=0.467 mean=-0.83 n=392  SELL hit=0.342 mean=-2.57 n=392
  SHORT: n=277
     60m BUY hit=0.444 mean=-1.35 n=277  SELL hit=0.365 mean=-1.85 n=277
usd_direction earlier:
  LONG: n=272
     60m BUY hit=0.483 mean=-0.20 n=271  SELL hit=0.325 mean=-3.37 n=271
  SHORT: n=32
     60m BUY hit=0.250 mean=-2.12 n=32  SELL hit=0.312 mean=-3.33 n=32
usd_direction later:
  LONG: n=122
     60m BUY hit=0.430 mean=-2.25 n=121  SELL hit=0.380 mean=-0.77 n=121
  SHORT: n=245
     60m BUY hit=0.469 mean=-1.25 n=245  SELL hit=0.371 mean=-1.66 n=245

TIME CONTEXT:
Diagnostic only. Not a session filter.
utc_block pooled:
  00-06: n=67
      5m BUY hit=0.284 mean=-1.05 n=67  SELL hit=0.209 mean=-1.86 n=67
     60m BUY hit=0.448 mean=-0.88 n=67  SELL hit=0.254 mean=-2.07 n=67
    240m BUY hit=0.672 mean=+1.41 n=67  SELL hit=0.149 mean=-4.36 n=67
  06-12: n=201
      5m BUY hit=0.358 mean=-1.30 n=201  SELL hit=0.224 mean=-1.67 n=201
     60m BUY hit=0.478 mean=-1.57 n=201  SELL hit=0.378 mean=-1.42 n=201
    240m BUY hit=0.463 mean=-4.19 n=201  SELL hit=0.463 mean=+1.21 n=201
  12-18: n=307
      5m BUY hit=0.355 mean=-1.83 n=307  SELL hit=0.349 mean=-1.08 n=307
     60m BUY hit=0.505 mean=-0.44 n=307  SELL hit=0.401 mean=-2.47 n=307
    240m BUY hit=0.443 mean=-1.54 n=300  SELL hit=0.380 mean=-1.75 n=300
  18-24: n=96
      5m BUY hit=0.158 mean=-2.60 n=95  SELL hit=0.221 mean=-2.29 n=95
     60m BUY hit=0.266 mean=-2.05 n=94  SELL hit=0.202 mean=-3.60 n=94
    240m BUY hit=0.174 mean=-3.12 n=86  SELL hit=0.488 mean=-1.13 n=86
utc_block earlier:
  00-06: n=4 [SMALL]
     60m BUY hit=0.500 mean=+0.25 n=4  SELL hit=0.500 mean=-3.45 n=4 [SMALL]
  06-12: n=56
     60m BUY hit=0.429 mean=-0.82 n=56  SELL hit=0.393 mean=-2.19 n=56
  12-18: n=158
     60m BUY hit=0.608 mean=+1.09 n=158  SELL hit=0.348 mean=-4.01 n=158
  18-24: n=86
     60m BUY hit=0.200 mean=-2.92 n=85  SELL hit=0.224 mean=-2.95 n=85
utc_block later:
  00-06: n=63
     60m BUY hit=0.444 mean=-0.95 n=63  SELL hit=0.238 mean=-1.98 n=63
  06-12: n=145
     60m BUY hit=0.497 mean=-1.86 n=145  SELL hit=0.372 mean=-1.12 n=145
  12-18: n=149
     60m BUY hit=0.396 mean=-2.05 n=149  SELL hit=0.456 mean=-0.84 n=149
  18-24: n=10 [SMALL]
     60m BUY hit=0.889 mean=+6.19 n=9  SELL hit=0.000 mean=-9.69 n=9 [SMALL]
day_of_week:
  3: n=300
     60m BUY hit=0.458 mean=-0.41 n=299  SELL hit=0.321 mean=-3.37 n=299
  4: n=371
     60m BUY hit=0.457 mean=-1.56 n=370  SELL hit=0.376 mean=-1.39 n=370

RL AGREEMENT/VETO AUDIT:
This is an observability experiment, NOT evidence of learned RL skill.
unique opportunities with all Q values exactly 0: 671/929
rl_action counts: {'SKIP': 206, 'SELL': 229, 'BUY': 236}
Q remaining zero means actions are epsilon/tie-driven, not a trained policy.
rl_gate pooled:
  agreed: n=239
     60m BUY hit=0.494 mean=+0.12 n=239  SELL hit=0.301 mean=-3.43 n=239
  vetoed: n=432
     60m BUY hit=0.437 mean=-1.70 n=430  SELL hit=0.379 mean=-1.63 n=430
rl_gate earlier:
  agreed: n=109
     60m BUY hit=0.505 mean=+0.23 n=109  SELL hit=0.284 mean=-3.91 n=109
  vetoed: n=195
     60m BUY hit=0.433 mean=-0.75 n=194  SELL hit=0.345 mean=-3.06 n=194
rl_gate later:
  agreed: n=130
     60m BUY hit=0.485 mean=+0.03 n=130  SELL hit=0.315 mean=-3.02 n=130
  vetoed: n=237
     60m BUY hit=0.441 mean=-2.47 n=236  SELL hit=0.407 mean=-0.45 n=236
Counterfactual using production stub side vs matching executable outcome:
  agreed 5m n=238 stub-matched hit=0.286 mean=-1.71
  agreed 60m n=239 stub-matched hit=0.452 mean=-1.24
  agreed 240m n=231 stub-matched hit=0.476 mean=+3.28
  vetoed 5m n=432 stub-matched hit=0.319 mean=-1.43
  vetoed 60m n=430 stub-matched hit=0.451 mean=-0.98
  vetoed 240m n=423 stub-matched hit=0.478 mean=+1.76
Stored data can describe random-gate suppression vs agreement, but is NOT sufficient to conclude the RL gate adds skill.

PRODUCTION-TRADE VS COUNTERFACTUAL CONTEXT:
status=SKIP
{"status": "SKIP", "dump_trades": 1614, "dump_first": "2026-03-25T13:40:32.248474", "dump_last": "2026-09-24T09:10:23.734926", "v2_first": "2026-09-24T10:26:54.809816+00:00", "reason": "live trade dump last timestamp is before V2 observation start; populations are not the same and cannot be joined reliably"}

MFE/MAE AVAILABILITY:
Path MFE/MAE fields exist on scored executable-side outcomes (research_bid_ask_path).
They are research path extrema, not production SL/TP.
  5m BUY mfe n=670 median=+0.50 mean=+1.54  mae n=670 median=+3.05 mean=+4.00
  15m BUY mfe n=671 median=+1.50 mean=+2.62  mae n=671 median=+4.10 mean=+5.52
  30m BUY mfe n=670 median=+2.60 mean=+3.97  mae n=670 median=+5.15 mean=+6.97
  60m BUY mfe n=669 median=+4.20 mean=+5.83  mae n=669 median=+6.60 mean=+8.71
  120m BUY mfe n=663 median=+6.80 mean=+8.21  mae n=663 median=+8.00 mean=+10.91
  240m BUY mfe n=654 median=+9.60 mean=+11.13  mae n=654 median=+10.85 mean=+14.98

MULTIPLE TESTING:
features examined: 24
comparisons examined: 288
A single good-looking bucket is not an edge.

CANDIDATE TABLE:
feature | hypothesis | n | horizons | earlier | later | classification | dependence
atr_over_price | higher atr_over_price vs lower atr_over_price | 411 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=+0.026 mean=-0.30 n=76/76; SELL hit=+0.197 | BUY Q4-Q1 hit=-0.146 mean=-6.39 n=166/93; SELL hit=+0.271 | DESCRIPTIVE CANDIDATE - UNSTABLE | related to spread_over_atr via ATR
spread_pips | higher spread_pips vs lower spread_pips | 410 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.015 mean=-0.37 n=108/69; SELL hit=-0.161 | BUY Q4-Q1 hit=+0.044 mean=-2.85 n=138/95; SELL hit=-0.006 | NO APPARENT INFORMATION | related to spread_over_atr
spread_over_atr | higher spread_over_atr vs lower spread_over_atr | 411 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.100 mean=-0.68 n=76/75; SELL hit=-0.221 | BUY Q4-Q1 hit=+0.228 mean=+6.13 n=101/159; SELL hit=-0.377 | DESCRIPTIVE CANDIDATE - UNSTABLE | uses spread and ATR; cost/vol
sma_difference_over_atr | higher sma_difference_over_atr vs lower sma_difference_over_atr | 257 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=+0.197 mean=+0.22 n=76/76; SELL hit=-0.105 | BUY Q4-Q1 hit=-0.057 mean=-5.16 n=27/78; SELL hit=+0.124 | INSUFFICIENT SAMPLE | uses ATR and SMA pair
rsi | higher rsi vs lower rsi | 364 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.395 mean=-9.74 n=76/76; SELL hit=+0.421 | BUY Q4-Q1 hit=-0.228 mean=-3.40 n=93/119; SELL hit=+0.137 | DESCRIPTIVE CANDIDATE - REPEATED | related to recent returns
macd_over_atr | higher macd_over_atr vs lower macd_over_atr | 339 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.079 mean=-5.56 n=76/76; SELL hit=+0.211 | BUY Q4-Q1 hit=-0.054 mean=+1.32 n=76/111; SELL hit=-0.079 | NO APPARENT INFORMATION | uses ATR; related to sma_difference_over_atr
bollinger_position | higher bollinger_position vs lower bollinger_position | 357 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.105 mean=-5.74 n=76/76; SELL hit=+0.197 | BUY Q4-Q1 hit=-0.102 mean=-2.38 n=69/136; SELL hit=+0.064 | DESCRIPTIVE CANDIDATE - REPEATED | related to mid vs recent range
ret_1 | higher ret_1 vs lower ret_1 | 319 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.224 mean=-3.31 n=76/76; SELL hit=+0.263 | BUY Q4-Q1 hit=-0.073 mean=-3.29 n=79/88; SELL hit=+0.003 | NO APPARENT INFORMATION | duplicate of ret_5
ret_15 | higher ret_15 vs lower ret_15 | 356 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.259 mean=-5.48 n=76/75; SELL hit=+0.230 | BUY Q4-Q1 hit=-0.099 mean=-3.18 n=100/105; SELL hit=+0.085 | DESCRIPTIVE CANDIDATE - REPEATED | overlaps ret_1/ret_30 path
ret_30 | higher ret_30 vs lower ret_30 | 323 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.368 mean=-8.04 n=76/76; SELL hit=+0.329 | BUY Q4-Q1 hit=-0.183 mean=-4.40 n=80/91; SELL hit=+0.038 | DESCRIPTIVE CANDIDATE - REPEATED | overlaps ret_15 path
gross_portfolio_exposure | higher gross_portfolio_exposure vs lower gross_portfolio_exposure | 449 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.269 mean=-3.78 n=88/59; SELL hit=-0.013 | BUY Q4-Q1 hit=-0.303 mean=-6.00 n=291/11; SELL hit=+0.478 | INSUFFICIENT SAMPLE | level/notional context, not price
same_usd_direction_count | higher same_usd_direction_count vs lower same_usd_direction_count | 669 | 60 primary; also computed 5-240 | BUY Q4-Q1 hit=-0.460 mean=-0.60 n=302/1; SELL hit=-0.325 | BUY Q4-Q1 hit=n/a mean=n/a n=366/0; SELL hit=n/a | INSUFFICIENT SAMPLE | correlated with simultaneous USD pairs

PROSPECTIVE HYPOTHESES WORTH FREEZING:
NONE as directional/profitability hypotheses.
QUALITY HOLD (not a trading hypothesis): ret_1 and ret_5 are the same one-bar M5 return; they must not be used as two features.
FAMILY NOTE (not frozen this stage): high recent strength (RSI/ret) showed the same 60m Q4-vs-Q1 sign in both labeled sessions. Features are correlated. Wait for a third labeled session before freezing one family definition. Not activated.

DATA SUFFICIENT FOR MODEL TRAINING: NO
DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM: NO
PRODUCTION CHANGE JUSTIFIED: NO
OANDA/API REQUESTS: 0
SOURCE DATA MODIFIED: NO
TRADING LOGIC CHANGED: NO
V2 POLICY CHANGED: NO
MODEL TRAINED: NO
FILES CHANGED:
- reports/decision_quality/_v2_internal_data_mining_stage1.py
- reports/decision_quality/_v2_internal_data_mining_stage1_results.json
- reports/decision_quality/v2_internal_data_mining_stage1.md
- tests/test_v2_internal_data_mining_stage1.py
