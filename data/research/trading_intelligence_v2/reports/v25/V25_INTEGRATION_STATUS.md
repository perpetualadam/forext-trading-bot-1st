# V2.5 Integration Status

Explicit research call path: v25_run.py --v25-evaluate -> v25_pipeline ->
v25_engine decision_evaluator hook -> v25_adapter -> decision_quality.evaluate.
The hook is after baseline constraints/sizing and before entry acceptance;
it adds no authority and does not bypass existing rejection. Decision records,
baseline counterfactuals, costs, trades and independent V24 ledgers are emitted.
Baseline A/E comparisons are checked against the unchanged V24 replay.

All older source/report files remain preserved; v25_engine is a separate observed
research copy. An AST-boundary test removes only the optional hook and requires
identity to V24. No operational strategy selection, broker execution, position
ownership, recovery, permit, gate or production state is integrated or changed.
Records=19356 reconciled trades, maximum accounting residual
1.3362e-11; record digest 31f1db65c44aa3708127e97e90a210330e4a273cb1c06fa734d7bd0e20d96589.
Production integration is disabled and unapproved.

Research only. Production remains NO-GO.
