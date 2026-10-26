# R.40 range and breakout research questions

## What R.39 already showed

R.39 is unchanged. On EUR_USD confirmation from 2026-05-01, the frozen range stream resolved 561 trades with mean fractional return about −0.000133. The exit counts were 333 stops, 78 targets, and 150 time exits. Trend, breakout, and the adaptive selector were also negative on that window, on the earlier design window, and on all six pairs. Always abstaining beat every stream. Those figures are prior results. They were not recomputed here.

The range rule bought in the lower quarter of a 48-bar M5 window and sold in the upper quarter. The stop sat one spread outside the window boundary. The target was the window midpoint. A reward filter required at least one-to-one and at least two spreads of target distance. The maximum hold was 12 M5 bars.

The imbalance between stops and targets is a property of that recorded run. It is not, by itself, a measurement of which design choice caused the loss.

## Questions that remain open

These are hypotheses. None was refitted or replayed.

1. Was the 48-bar window a range that had already been established by repeated reactions, or only a low efficiency ratio?
2. Did the boundary stay in place after the entry, or was the entry the start of a move through it?
3. How many prior reactions did the same level have, counted only after each reaction candle had completed?
4. How often did a close beyond the boundary return inside, and how long after the break was that return known?
5. How did the window width compare with the spread on the entry bar? R.39 required four spreads. That filter still lost money, so repeating it with a new multiple would be a new search.
6. Was the stop inside ordinary penetration of a level, and would a stop beyond a confirmed swing have changed the trade set? Answering that requires a new frozen definition and a later authorised evaluation.
7. Was the midpoint closer or farther than the stop in the accepted trades, and did time exits dominate when the midpoint was far? The 150 time exits show that one hour was often too short for the midpoint. They do not show the correct holding time.
8. Did the range end before the entry, using only information available at the signal?
9. Would a completed H4 state have classified the same M5 window differently? R.39 had no H4 candle and no confirmed swing state.

## Trend and breakout limits

R.39 trend state used a 5-bar and 20-bar M5 average and an efficiency cutoff. R.39 breakout used the prior 20 M5 bars, excluding the current bar. Stops and targets for both were ATR multiples. The hold was 12 M5 bars, which is one hour. Confirmation was one timeframe. Those choices can describe a short push. They do not identify a pullback that remains a higher low, a trendline touch, a break of a confirmed range, a return back inside that range, or a change from range to trend.

A later design should keep those six situations as separate labels:

- Trend continuation: the existing confirmed trend state remains intact.
- Pullback: a new swing against the trend is still a higher low or a lower high.
- Trendline bounce: a completed touch of an already available line, with the close back on the original side.
- Structural breakout: a completed close beyond an already available range boundary.
- Failed breakout: a later completed close back inside, within a pre-registered number of candles.
- Range-to-trend transition: a range was known, then a breakout confirms and the swing state becomes a trend.

Each label needs its own availability time. A selector that switches among them is a later architecture. R.39's selector already lost money, so a new selector is not the next experiment. No regime model was trained in R.40.
