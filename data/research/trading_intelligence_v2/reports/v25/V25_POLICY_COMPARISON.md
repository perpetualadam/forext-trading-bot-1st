# V2.5 Policy Comparison

Small fixed hypothesis set, not a parameter grid:
A unchanged baseline; B spread/ATR<=0.25; C estimated cost/target<=0.25;
D all completed M15/H1/H4 trend states agree with entry; E exact-vote consolidation.
Both quarter-budget thresholds are illustrative, frozen before first V25 replay,
informed by prior research, not independent calibration or optimal parameters.
No alternative thresholds were tried. F combined policy remains disabled without
fresh training/validation support. No archive-fitted threshold or selector exists.

M5 observed-only:
- A_BASELINE: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- B_SPREAD_ATR: trades 210, net -829.491880 USD, net/trade -3.949961335350406, max fold drawdown 669.122098; rejected baseline winners 228, avoided baseline losers 495.
- C_COST_TARGET: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.
- D_HTF: trades 132, net -1118.779126 USD, net/trade -8.47559943623058, max fold drawdown 697.559741; rejected baseline winners 242, avoided baseline losers 491.
- E_EXACT_VOTES: trades 807, net -4210.742405 USD, net/trade -5.217772496477808, max fold drawdown 2391.279123; rejected baseline winners 0, avoided baseline losers 0.

policy_comparison.json contains accepted entries, rejected candidates and reasons,
acceptance rates, avoided baseline losers/rejected winners, unknown counterfactuals,
gross/net expectancy, R, PF, win rate, drawdown, total net/cost, exposure and turnover.
It labels candidate rejection separately from an executed trade. Rejections can
change all subsequent capacity, sizing and outcomes: every case replays its entire
portfolio, never subtracts rejected P/L from A. Full fold/by-instrument/session/
regime/duration diagnostics are in outputs/v25/full_summary.json.

Research only. Production remains NO-GO.
