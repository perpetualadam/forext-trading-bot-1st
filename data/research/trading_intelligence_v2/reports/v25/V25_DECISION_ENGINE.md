# V2.5 Decision Engine

decision_quality.Request carries instrument, side, decision/feature/quote
times, explicit completion, current bid/ask, ATR, stop/target, horizon, units,
pricing, account, strategy, regime, volatility/momentum and completed context.
Evaluator returns ACCEPT, REJECT_COST, REJECT_RISK, REJECT_DATA, REJECT_SIGNAL
or ABSTAIN_UNCERTAIN with reason, inputs and metric trace. No probability is
assigned and no realised outcome is accepted as input.

Inputs reject missing/nonfinite quotes/ATR, nonpositive ATR, crossed/stale/future
quotes, incomplete/future/stale features, invalid geometry/capacity or unavailable
FX conversion. Quotes have the existing research 300-second maximum age; features
must be available within the current M5 decision interval. Context uses actual
completed M15/H1/H4 timestamps, never an unfinished candle. Documented pricing
without applicability abstains; explicit hypothetical scenarios remain labelled.

v25_adapter.Evaluator constructs requests at the research engine hook after
baseline sizing/constraints and before entry acceptance. Existing constraints
retain precedence. Baseline A and E are verified against the frozen V24 replay's
metrics, equity and every trade field except new decision metadata. Frequency
annotations are recorded on copies, never on engine state.

Research only. Production remains NO-GO.
