# STAGE R.39 — MARKET REGIME DETECTION AND ADAPTIVE TREND/RANGE STRATEGY RESEARCH REPORT

## Overall classification

`R39_MARKET_REGIME_STRATEGY_RESEARCH_COMPLETED`

No strategy merits further independent validation. The adaptive selector did not produce a cost-adjusted advantage.

## Branch, HEAD and preservation

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- The working tree was already dirty. Unrelated changes were left in place.
- R.24–R.38 evidence was not modified.
- All six strategies remain inactive and unauthorised for live trading.
- The quant stub still returns `quant_stub_removed`.
- An unseen reinforcement-learning state still returns `UNAVAILABLE`.
- Operational hashes are unchanged, including `ai_ensemble.py` `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa`, `rl_agent.py` `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e`, and `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`.
- The R.30 simulator file was not edited.

## Frozen protocol and source hashes

Protocol SHA-256, written before the economic scores were interpreted: `006e21c8725d0e287c2d9c655da9ba52b97a94143c43db9820e3def3a53e592a`.

Research module: `forex_bot/research/learning/regimes.py` `f3d2ffdbe77e17808e30b3d034b5b681fd631426349dbbd107c4f4c83cfdc0ea`.

All six M5 files matched the R.35 inventory hashes. EUR/USD is `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`. USD/JPY uses pip size 0.01. The other pairs use 0.0001. Timestamps are unique, ordered, and UTC.

The design window ends before 1 March 2026, with trades whose holding window would cross that boundary removed. The confirmation window starts on 1 May 2026. Thresholds were not fit on either window. Both windows are slices of the same researched year.

## Regime detector design

Version `r39.regime.v1`. Each label uses 48 completed M5 bars. A gap inside that window, a non-finite price, or a negative spread returns `UNCERTAIN`.

- `BREAKOUT`: the midpoint closes more than half a spread beyond the prior 48-bar high or low. The current bar is not part of that boundary.
- `TREND`: directional efficiency is at least 0.35, the 48-bar move is at least two spreads, and the second half of the window has higher highs and higher lows, or lower highs and lower lows, in agreement with the move.
- `RANGE`: efficiency is at most 0.20 and the prior range is at least four spreads wide.
- Anything else is `UNCERTAIN`.

Breakout is applied before trend, and trend before range. The detector does not read a future return.

## Range strategy rules

Version `r39.range.v1`. Support and resistance are the prior 48-bar low and high, excluding the decision bar. The range must be at least four spreads wide and the window efficiency must be at most 0.20. A close already outside that boundary produces no trade.

A buy requires a bullish completed bar in the lower quarter of the range. A sell requires a bearish completed bar in the upper quarter. The stop is one spread outside the touched boundary. The target is the range midpoint. The planned reward must be at least twice the spread and at least as large as the risk. Otherwise the signal is `NO_TRADE`.

## Trend and breakout adapters

The trend adapter copies the inactive research rule: buy when the 5-bar average is above the 20-bar average and the midpoint is at or above the fast average; sell for the mirror case. It does not change `strategy.active`.

The breakout adapter copies the inactive swing-breakout rule with a fixed 20-bar window that excludes the current bar. A close above the prior high is a buy. A close below the prior low is a sell.

Both use a one-ATR stop and a 1.5-ATR target, the same reward filter, and the same 12-bar maximum hold. Entry is the next bar’s open. A buy pays the ask and exits on the bid. A sell receives the bid and exits on the ask. One position is open at a time. A bar that touches both stop and target is booked at the stop. A gap makes the outcome unevaluable. These exit distances differ from the range strategy’s boundary stop, and that difference is part of the frozen specification. The selector does not receive a cheaper spread or a later entry than the standalone strategies.

## Regime distribution

On the EUR/USD confirmation window, 25,040 labelled bars fell into:

| Regime | Bars | Share | Average run |
| --- | ---: | ---: | ---: |
| RANGE | 16,157 | 64.5% | 12.2 bars |
| UNCERTAIN | 6,940 | 27.7% | 4.9 bars |
| TREND | 992 | 4.0% | 3.9 bars |
| BREAKOUT | 951 | 3.8% | 1.3 bars |

The other five pairs have the same shape: range is the common label, breakout runs last about one bar, and trend runs last about four bars. Frequency is not evidence that a regime is tradable. No separate, pre-existing regime reference was available, so these counts are descriptions of the detector, not an accuracy score.

## Signal and abstention counts

EUR/USD confirmation, after the cost filter and one-position rule:

| Stream | Trades | Cost-filter rejections | Gap skips | Unevaluable holds |
| --- | ---: | ---: | ---: | ---: |
| Range | 561 | 1,056 | 3 | 1 |
| Trend | 3,074 | 5,161 | 5 | 7 |
| Breakout | 1,119 | 1,039 | 1 | 2 |
| Selector | 1,046 | 1,301 | 3 | 1 |

`UNCERTAIN` forces `NO_TRADE`. The selector therefore trades less often than the trend rule alone.

## Matched strategy comparison

Means are fractional next-bar bid/ask returns per resolved trade. The block bootstrap uses blocks of five trades, 200 replicates, and seed 3901. Always abstaining has mean zero.

EUR/USD confirmation:

| Stream | Trades | Mean | Bootstrap low | Win rate | Max drawdown | Half-pip mean | One-pip mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Range | 561 | −0.000133 | −0.000164 | 0.301 | 0.075 | −0.000220 | −0.000306 |
| Trend | 3,074 | −0.000135 | −0.000145 | 0.196 | 0.417 | −0.000222 | −0.000309 |
| Breakout | 1,119 | −0.000157 | −0.000175 | 0.174 | 0.177 | −0.000243 | −0.000330 |
| Selector | 1,046 | −0.000158 | −0.000180 | 0.221 | 0.166 | −0.000245 | −0.000332 |
| Always abstain | 0 | 0 |  |  |  |  |  |

The same four streams are negative on the design window as well. EUR/USD design means are about −0.000138 for range, −0.000138 for trend, −0.000160 for breakout, and −0.000157 for the selector.

These figures are not the R.31 screening totals. This stage adds next-bar bid/ask fills, explicit stops and targets, a 12-bar hold, a reward filter, and a single open position.

## Adaptive-selector results

The frozen map is trend to the trend rule, range to the range rule, breakout to the breakout rule, and uncertain to no trade. It was not changed after seeing which rule made money.

On EUR/USD confirmation the selector’s mean is −0.000158. That is weaker than the range rule alone and the trend rule alone. Restricting each rule to its detected regime did not remove the loss. The bootstrap interval stays below zero.

## Results by instrument and period

Every confirmation mean on AUD/USD, GBP/USD, USD/CAD, USD/CHF, and USD/JPY is negative for all four streams. The design window is negative on those pairs as well. Extra cost makes every figure more negative. The pairs share the year and the dollar, so this is one repeated loss, not six separate proofs.

## Spread and additional-cost sensitivity

The recorded bid/ask result is already negative. Adding half a pip per side, and then one pip per side, widens the loss on every stream and every pair. A narrow range is rejected before entry when the midpoint target is not at least two spreads away and the reward is not at least the risk. That filter removed 1,056 EUR/USD range signals and 1,301 selector signals in the confirmation window. The trades that remained still lost money.

Recorded spreads are not a full OANDA GBP spread-betting cost, financing, slippage, or margin model. No account balance was used. A larger balance would not change the negative fractional return.

## Uncertainty estimates

Every EUR/USD confirmation bootstrap lower bound is below zero, and every stream has more than 30 trades. The loss is not a handful of trades. Overlapping regime labels were reduced by allowing one position at a time. The six pairs are not treated as independent samples.

## Research-journal findings

EUR/USD confirmation outcomes:

- Range: 333 stops, 78 targets, 150 time exits.
- Trend: 2,412 stops, 532 targets, 120 time exits, 10 ambiguous bars.
- Breakout: 911 stops, 179 targets, 24 time exits, 5 ambiguous bars.
- Selector: 753 stops, 144 targets, 145 time exits, 4 ambiguous bars.

Stops are recorded as range-boundary failures, trend reversals, or failed breakouts according to the strategy that was open. They are not recorded as proof that the regime label itself was false. Ambiguous bars are losses at the stop. The regime-label digest for EUR/USD is `64590498d141b6135554f1b23c1fe62285fc373464c5faf26f71b28859a7fb9a`.

## Focused tests and offline regressions

`tests/test_r39_regimes.py`: 9 passed. Coverage includes hashes and pip size, uncertain warmup, prefix stability, a future-return fixture, breakout boundaries that exclude the current bar, no-trade under `UNCERTAIN`, reward-to-risk, next-bar ask entry, ambiguous bars, gaps, and the unchanged inactive strategies, stub, and reinforcement-learning gate.

R.8–R.38 offline suites exited 0. R.10 passed on the first attempt. R.28 database scripts were not run.

## Whether any strategy merits further independent validation

No. None of the four configurations cleared a positive confirmation mean, a bootstrap lower bound above zero, and a half-pip mean above zero. The other instruments agree on the sign of the loss.

## Remaining limitations

The detector’s thresholds were declared in advance and were not shown to be a unique description of market state. Range is the most common label because the efficiency cutoff is strict, not because most hours are a tradeable channel. Trend and breakout exits use ATR distances, while the range exit uses the channel midpoint, so part of the difference between streams is the exit rule. The year has already been used in earlier research. One open position reduces trade count and also skips later signals.

## Recommended R.40 direction

Do not start R.40 from this result. Selecting among these rules with a causal regime label did not repair the negative cost-adjusted returns. Another pass over thresholds on this same year would be a search, not a new test.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**
