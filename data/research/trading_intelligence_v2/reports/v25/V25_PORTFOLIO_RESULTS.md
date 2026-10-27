# V2.5 Portfolio Results

Full-replay M5 observed-only comparison:
- A_BASELINE: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- B_SPREAD_ATR: trades 210, net -829.491880 USD, net/trade -3.949961335350406, max fold drawdown 669.122098; rejected baseline winners 228, avoided baseline losers 495.
- C_COST_TARGET: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- D_HTF: trades 132, net -1118.779126 USD, net/trade -8.47559943623058, max fold drawdown 697.559741; rejected baseline winners 242, avoided baseline losers 491.
- E_EXACT_VOTES: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.

Original V24 cost control reproduced: 829 trades,
gross -108.118650558, net -6204.763853417 USD.
The report includes four entry timeframes and two explicitly labelled cost
conditions, with fixed A profit-protection comparisons. Other five M5 strategies
are unfiltered frequency controls only, not optimised policy candidates.
Full source-backed portfolio paths include cash, margin, risk, same-USD-direction
capacity, stop-first ambiguity and exit timing. Avoided losers alone do not
establish an improvement; rejected winners and newly available trades matter.
Some lower activity can reduce losses without producing positive expectancy.

Research only. Production remains NO-GO.
