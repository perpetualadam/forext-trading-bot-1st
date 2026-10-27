# V2.5 Executive Summary

TIV25_COST_AWARE_RESEARCH_PARTIALLY_VERIFIED.

Implemented a causal research-only evaluator, fixed policies and entire portfolio
replays. No production strategy or broker execution is changed. No new independent
data was acquired and the user's actual broker plan remains unknown. Thresholds
were frozen before V25 replay, but design is informed by prior examined history.
No optimisation, policy selection or confidence calibration used this archive.

Across the 24 B/C/D timeframe-pricing diagnostic comparisons, 8 have
higher sample net expectancy and 14 higher portfolio net P/L than A.
These are correlated descriptive comparisons, not success rates or independent
evidence. E removes no trades: no exact redundant entry predicates were proven.
F and the adaptive selector abstain without fresh validation.

M5 observed-only diagnostic results:
- A_BASELINE: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- B_SPREAD_ATR: trades 210, net -829.491880 USD, net/trade -3.949961335350406, max fold drawdown 669.122098; rejected baseline winners 228, avoided baseline losers 495.
- C_COST_TARGET: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- D_HTF: trades 132, net -1118.779126 USD, net/trade -8.47559943623058, max fold drawdown 697.559741; rejected baseline winners 242, avoided baseline losers 491.
- E_EXACT_VOTES: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.

Research only. Production remains NO-GO.
