# Fibonacci vs ordinary retracement depth

EXPERIMENT: Fibonacci vs ordinary retracement depth  
PRODUCTION IMPACT: **NONE**

Harness: `forex_bot/decision_quality/fibonacci_retracement.py`  
Runner: `reports/decision_quality/_fibonacci_retracement_run.py`  
Machine-readable: `reports/decision_quality/_fibonacci_retracement_results.json`  
Tests: `tests/test_fibonacci_retracement_research.py`

This is one frozen specification. No level was selected from overall results and then described as out-of-sample. Live trades were not used.

---

## CAUSAL SWING

Reused from `ema50_200_swing50_resume` (`swing_retrace_mask` in `forex_bot/decision_quality/ema_retracement.py`).

At bar index `i` (0-based):

```
start = max(0, i - 24 + 1)
end   = i + 1
swing_high = max(high[start:end])
swing_low  = min(low[start:end])
```

The slice is `[start, end)` so bar `i` is included and bar `i+1` is not. No future highs/lows enter the range. Swing length is frozen at **24** bars (not optimized).

Retrace fraction (same formula for every depth):

- BUY (EMA state +1): `(swing_high − close) / (swing_high − swing_low)`
- SELL (EMA state −1): `(close − swing_low) / (swing_high − swing_low)`

Qualify when `retrace_fraction >= depth` and close remains on the trend side of EMA200. **No per-level tolerance.**

Direction is the EMA50/200 state. The depth number never sets BUY/SELL.

Resume (identical for Fib, control, placebo): first later bar in the same EMA episode with close back through EMA50 in the trend direction. The scored event is that resume bar.

Dedup: at most one swing qualification per EMA-state episode per depth, then at most one resume. One market swing cannot emit repeated observations at the same depth.

---

## DEPTHS

Frozen before outcomes:

- Fib: 23.6, 38.2, 61.8, 78.6
- Controls: 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80
- Placebo (seed **42**, n **8**, generated then frozen): 25.7, 27.7, 46.3, 65.7, 66.4, 67.2, 71.5, 78.5

Trend state: EMA 50 / 200 (same pair as the prior swing-50% study). Occupancy: BUY ask→bid path, SELL bid→ask path, SL = 2×ATR, TP = 2R, one position per symbol.

Cuts (same `chrono_masks` 50/25/25 on pooled M5 times as the EMA retracement report):

- TRAIN ≤ `2026-03-03 12:15:00`
- VALID ≤ `2026-06-02 05:05:00`
- TEST after that

Pairs: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF.

Sanity: control 50% overall matches the published `ema50_200_swing50_resume` occupancy (n=2388, WR 0.215, exp. R −0.354, PF 0.549).

---

## RESULT TABLE

Economic occupancy (bid/ask, 2R). Forward 60m is mid→mid mean pips on the resume events in that split.

| Depth | Kind | Split | n | WR | Exp. R | PF | 60m pips |
|---:|---|---|---:|---:|---:|---:|---:|
| 20% | control | train | 1295 | 0.216 | −0.351 | 0.552 | −0.422 |
| 20% | control | valid | 580 | 0.255 | −0.234 | 0.685 | +1.140 |
| 20% | control | test | 639 | 0.210 | −0.374 | 0.526 | +0.065 |
| 20% | control | overall | 2514 | 0.224 | −0.330 | 0.575 | +0.061 |
| 23.6% | fib | train | 1293 | 0.210 | −0.369 | 0.533 | −0.492 |
| 23.6% | fib | valid | 575 | 0.257 | −0.228 | 0.693 | +0.572 |
| 23.6% | fib | test | 645 | 0.219 | −0.345 | 0.557 | +0.263 |
| 23.6% | fib | overall | 2513 | 0.223 | −0.331 | 0.574 | −0.057 |
| 25% | control | train | 1298 | 0.207 | −0.378 | 0.523 | −0.571 |
| 25% | control | valid | 574 | 0.256 | −0.232 | 0.689 | +0.665 |
| 25% | control | test | 644 | 0.213 | −0.363 | 0.538 | +0.175 |
| 25% | control | overall | 2516 | 0.220 | −0.341 | 0.563 | −0.098 |
| 30% | control | train | 1301 | 0.211 | −0.368 | 0.534 | −0.427 |
| 30% | control | valid | 572 | 0.255 | −0.234 | 0.685 | +0.860 |
| 30% | control | test | 645 | 0.209 | −0.374 | 0.526 | +0.122 |
| 30% | control | overall | 2518 | 0.220 | −0.339 | 0.565 | +0.010 |
| 35% | control | train | 1290 | 0.219 | −0.342 | 0.562 | −0.512 |
| 35% | control | valid | 570 | 0.244 | −0.268 | 0.645 | +1.051 |
| 35% | control | test | 642 | 0.209 | −0.378 | 0.522 | +0.095 |
| 35% | control | overall | 2502 | 0.222 | −0.334 | 0.570 | +0.005 |
| 38.2% | fib | train | 1291 | 0.220 | −0.340 | 0.564 | −0.481 |
| 38.2% | fib | valid | 559 | 0.245 | −0.265 | 0.649 | +1.100 |
| 38.2% | fib | test | 637 | 0.212 | −0.368 | 0.532 | +0.261 |
| 38.2% | fib | overall | 2487 | 0.224 | −0.330 | 0.574 | +0.074 |
| 40% | control | train | 1284 | 0.216 | −0.353 | 0.550 | −0.543 |
| 40% | control | valid | 560 | 0.245 | −0.266 | 0.648 | +1.264 |
| 40% | control | test | 638 | 0.215 | −0.359 | 0.542 | +0.296 |
| 40% | control | overall | 2482 | 0.222 | −0.335 | 0.569 | +0.089 |
| 45% | control | train | 1254 | 0.221 | −0.337 | 0.567 | −0.704 |
| 45% | control | valid | 559 | 0.234 | −0.297 | 0.612 | +0.672 |
| 45% | control | test | 621 | 0.208 | −0.378 | 0.522 | +0.229 |
| 45% | control | overall | 2434 | 0.221 | −0.338 | 0.566 | −0.151 |
| 50% | control | train | 1230 | 0.220 | −0.339 | 0.565 | −0.665 |
| 50% | control | valid | 548 | 0.223 | −0.332 | 0.573 | +0.812 |
| 50% | control | test | 610 | 0.198 | −0.404 | 0.496 | +0.223 |
| 50% | control | overall | 2388 | 0.215 | −0.354 | 0.549 | −0.099 |
| 55% | control | train | 1184 | 0.218 | −0.346 | 0.557 | −0.824 |
| 55% | control | valid | 537 | 0.218 | −0.346 | 0.557 | +0.370 |
| 55% | control | test | 596 | 0.183 | −0.450 | 0.448 | +0.128 |
| 55% | control | overall | 2317 | 0.209 | −0.373 | 0.528 | −0.303 |
| 60% | control | train | 1140 | 0.218 | −0.347 | 0.556 | −0.588 |
| 60% | control | valid | 523 | 0.220 | −0.340 | 0.564 | +0.779 |
| 60% | control | test | 580 | 0.181 | −0.457 | 0.442 | +0.420 |
| 60% | control | overall | 2243 | 0.209 | −0.374 | 0.527 | −0.008 |
| 61.8% | fib | train | 1126 | 0.215 | −0.355 | 0.548 | −0.506 |
| 61.8% | fib | valid | 518 | 0.216 | −0.351 | 0.552 | +0.916 |
| 61.8% | fib | test | 573 | 0.175 | −0.476 | 0.423 | +0.361 |
| 61.8% | fib | overall | 2217 | 0.205 | −0.386 | 0.515 | +0.052 |
| 65% | control | train | 1090 | 0.204 | −0.389 | 0.512 | −0.540 |
| 65% | control | valid | 504 | 0.228 | −0.315 | 0.591 | +0.817 |
| 65% | control | test | 560 | 0.177 | −0.470 | 0.430 | +0.314 |
| 65% | control | overall | 2154 | 0.202 | −0.393 | 0.508 | −0.000 |
| 70% | control | train | 1042 | 0.205 | −0.384 | 0.517 | −0.399 |
| 70% | control | valid | 481 | 0.206 | −0.383 | 0.518 | +0.964 |
| 70% | control | test | 531 | 0.175 | −0.473 | 0.425 | +0.435 |
| 70% | control | overall | 2054 | 0.198 | −0.407 | 0.493 | +0.136 |
| 75% | control | train | 994 | 0.201 | −0.396 | 0.504 | −0.450 |
| 75% | control | valid | 467 | 0.212 | −0.364 | 0.538 | +0.809 |
| 75% | control | test | 507 | 0.197 | −0.408 | 0.491 | +0.506 |
| 75% | control | overall | 1968 | 0.203 | −0.392 | 0.509 | +0.095 |
| 78.6% | fib | train | 958 | 0.211 | −0.367 | 0.534 | −0.132 |
| 78.6% | fib | valid | 457 | 0.208 | −0.376 | 0.525 | +1.055 |
| 78.6% | fib | test | 494 | 0.190 | −0.429 | 0.470 | +0.331 |
| 78.6% | fib | overall | 1909 | 0.205 | −0.386 | 0.515 | +0.272 |
| 80% | control | train | 944 | 0.213 | −0.361 | 0.541 | −0.029 |
| 80% | control | valid | 451 | 0.204 | −0.388 | 0.513 | +0.979 |
| 80% | control | test | 486 | 0.193 | −0.420 | 0.480 | +0.235 |
| 80% | control | overall | 1881 | 0.206 | −0.383 | 0.518 | +0.280 |

Every cell is negative expectancy after costs. Shallower depths lose less on TEST than deeper depths (about −0.35 to −0.37 R near 20–40% vs about −0.42 to −0.48 R near 60–80%). That is a depth gradient, not a Fib spike.

---

## FIB-vs-NEIGHBOR TABLE

Predeclared pairs. “Beats both” requires Fib expectancy > each neighbor by **0.05 R** on that split.

| Fib | Lower | Fib exp. R | Upper | Valid beats both | Test beats both |
|---:|---:|---:|---:|---|---|
| 23.6 | 20% −0.234 / test −0.374 | valid −0.228 / test −0.345 | 25% −0.232 / test −0.363 | NO | NO |
| 38.2 | 35% −0.268 / test −0.378 | valid −0.265 / test −0.368 | 40% −0.266 / test −0.359 | NO | NO |
| 61.8 | 60% −0.340 / test −0.457 | valid −0.351 / test −0.476 | 65% −0.315 / test −0.470 | NO | NO |
| 78.6 | 75% −0.364 / test −0.408 | valid −0.376 / test −0.429 | 80% −0.388 / test −0.420 | NO | NO |

No Fibonacci level is a local peak versus both neighbors on validation **or** test. 23.6 and 38.2 sit between their controls. 61.8 is slightly **worse** than both neighbors on test. 78.6 is between 75 and 80 on test.

---

## PAIR STABILITY

Overall (all splits) economic expectancy R by symbol. All six are negative at Fib and at shallow/deep controls.

| Depth | EUR_USD | GBP_USD | USD_JPY | AUD_USD | USD_CAD | USD_CHF |
|---:|---:|---:|---:|---:|---:|---:|
| 20% | −0.284 | −0.386 | −0.348 | −0.241 | −0.475 | −0.239 |
| 23.6% | −0.296 | −0.363 | −0.295 | −0.296 | −0.465 | −0.263 |
| 38.2% | −0.310 | −0.352 | −0.279 | −0.287 | −0.479 | −0.268 |
| 50% | −0.235 | −0.342 | −0.282 | −0.369 | −0.516 | −0.377 |
| 61.8% | −0.395 | −0.341 | −0.250 | −0.381 | −0.511 | −0.430 |
| 78.6% | −0.367 | −0.383 | −0.215 | −0.389 | −0.452 | −0.498 |
| 80% | −0.350 | −0.370 | −0.207 | −0.398 | −0.474 | −0.492 |

USD_CAD is the weakest pair at every listed depth. No Fib level flips any pair to a positive occupancy expectancy.

---

## SIDE STABILITY

Overall occupancy:

| Depth | BUY n | BUY exp. R | SELL n | SELL exp. R |
|---:|---:|---:|---:|---:|
| 23.6% | 1245 | −0.327 | 1268 | −0.334 |
| 38.2% | 1229 | −0.322 | 1258 | −0.338 |
| 50% | 1190 | −0.339 | 1198 | −0.369 |
| 61.8% | 1102 | −0.363 | 1115 | −0.408 |
| 78.6% | 951 | −0.356 | 958 | −0.414 |

BUY and SELL both lose. Deeper levels are slightly worse on SELL. Not a one-sided artifact.

---

## PLACEBO RESULT

Seed 42, eight depths drawn uniformly in 20–80% excluding the frozen grid.

| Depth | Valid n | Valid exp. R | Test n | Test exp. R | Overall exp. R |
|---:|---:|---:|---:|---:|---:|
| 25.7% | 573 | −0.236 | 646 | −0.370 | −0.348 |
| 27.7% | 573 | −0.257 | 650 | −0.374 | −0.357 |
| 46.3% | 557 | −0.343 | 619 | −0.369 | −0.347 |
| 65.7% | 503 | −0.326 | 557 | −0.472 | −0.402 |
| 66.4% | 499 | −0.333 | 552 | −0.478 | −0.405 |
| 67.2% | 493 | −0.325 | 548 | −0.480 | −0.403 |
| 71.5% | 473 | −0.359 | 526 | −0.440 | −0.385 |
| 78.5% | 459 | −0.379 | 494 | −0.423 | −0.388 |

Placebos track the same curve as nearby controls (shallow ~−0.37 test R; deep ~−0.42 to −0.48). They do not underperform Fibonacci in a Fib-specific way.

---

## FINAL RESEARCH CONCLUSION

**B) GENERIC RETRACEMENT-DEPTH EFFECT, NOT FIB-SPECIFIC**

After costs, every depth loses. Test expectancy gets worse as the required pullback deepens. Fibonacci values lie on that curve and do not beat both neighbors on validation and test (predeclared 0.05 R margin). Placebos behave like their neighbors. Mid-to-mid 60m means are sometimes positive in validation/test; that is not an after-cost edge and is not unique to Fib.

This is not a “best Fib level.” Conclusion B does **not** authorize deployment.

PRODUCTION CODE CHANGED: NO  
LIVE STRATEGY CHANGED: NO  
OANDA ORDERS SENT: NO  
DOCKER RESTARTED: NO
