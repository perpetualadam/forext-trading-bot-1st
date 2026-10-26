# R.40 ranked research directions

Only one of these should be the next build. The other three wait.

## A. Higher-timeframe trendline and market-structure research

The problem is that R.39's moving-average and fixed-window rules are not confirmed swings or causal trendlines. The local M5 files can form about 6,160–6,200 complete H1 candles and about 1,460–1,480 complete H4 candles per pair, so the clock can be studied without new downloads. What remains unknown is whether the frozen `k = 2` definition produces stable, non-repainting states, and whether those states have any economic value on fresh data. Implementation is a research module plus leakage tests. The main leakage risk is marking a pivot before its two confirmation candles close, or redrawing an old line. The main economic risk is a long hold, a weekend gap, and a spread that still has to be paid. A credible positive result at the next stage is prefix-stable swings and lines with explicit availability times, and no profit claim. A later economic claim would need fresh data and a cost-adjusted result above zero under the validation rules. Rejection follows if the implementation repaints, if gaps are filled, or if a pre-registered fresh-data test loses money.

## B. Higher-timeframe support, resistance, and range research

The problem is the R.39 range result: on EUR_USD confirmation, stops outnumbered targets 333 to 78 and the mean was negative. The open questions are establishment, reactions, false breaks, width versus spread, and higher-timeframe context. Those questions need the swing levels from A. Required data is the same six M5 files for a descriptive pass, and fresh data before any performance claim. Complexity is higher than A because a range needs two levels and repeated reactions. Leakage risk is counting a reaction that was not complete, or treating the window that contains the entry as already closed. Economic risk is the same spread, stop, and gap exposure that R.39 already lost money on, plus any new buffer chosen after seeing exits. A credible positive result is a pre-registered range label that is available only after its last reaction, followed later by a fresh-data test that survives costs. Rejection follows if the label is only a renamed 48-bar window, or if the fresh-data test fails. B is the second step, after A's definitions exist in code and pass causality tests.

## C. Expanded currency-pair data and contract verification

The problem is that six USD-linked pairs are a narrow, correlated universe, and several named crosses have no local candles. Existing evidence for expanding is only the correlation and the absence of files. Spreads, gaps, and account eligibility are unknown. Required data does not exist locally and would need a separate acquisition authorisation, plus a broker-contract check that R.40 did not perform. Complexity of the research code is low once files exist. Leakage risk is synthesizing a cross from two USD pairs. Economic risk is an unknown spread, JPY pip conventions, quote-currency conversion, and treating correlated pairs as independent samples. A credible positive result is a verified contract and a bid/ask file that passes the same integrity checks as the six. Rejection follows if the account does not list the instrument or the file fails the complete-candle rule. C is a separate data track. It should not run as a strategy project beside A.

## D. Multi-timeframe adaptive strategy architecture

The problem is how H4 context, H1 structure, and M5 timing would line up without lookahead. The architecture is specified in `09_multitimeframe_architecture.md`. R.39 already ran an adaptive selector and it lost money, including relative to the single streams. Building another selector now would multiply comparisons. Leakage risk is attaching an unfinished H4 close to earlier M5 rows. Economic risk is switching rules until one looks good on the exposed year. A credible positive result cannot be claimed until one structure definition has passed a fresh-data test. Rejection is the current state: no component has that result. D waits.

## Order

1. A, as a descriptive causality study on the existing six pairs. No entries and no profit score in that next stage.
2. B, only after A's swing clock is implemented and prefix-stable.
3. C, only under a separate authorisation to acquire data and check the account. NZD_USD is first on that verification list.
4. D, only after a single definition has a pre-registered fresh-data result.

Recommended next stage: A. Do not start it inside R.40.
