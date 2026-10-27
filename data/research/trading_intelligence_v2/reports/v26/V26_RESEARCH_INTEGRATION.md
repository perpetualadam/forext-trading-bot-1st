# V2.6 Research Integration

load_dataset verifies archive commits and original raw bytes, reconstructs
existing core.Bar values and reuses historical_quality and mtf_features.prepare.
The older V23 public-source importer deliberately refuses OANDA URLs; it was not
weakened. The new adapter verifies this dedicated archive contract instead.
Synthetic integration exercises all six pairs and M15/H1/H4 aggregation.

Guarded evaluate_independent reuses v25_engine, Evaluator, Provider, fixed policy
definitions and existing execution accounting. It refuses synthetic input,
unreviewed market closures, insufficient coverage, overlapping or unproven history.
Policy source seal: b835b87c7bb3cae9fd22ba5684bec0f5c9b907ef3e866d92a7a59bbcb54e05fd. Immutable first-performance-inspection receipt
precedes feature/performance evaluation and blocks a second first-access claim.
No operational loop, broker execution module, strategy/sizing/SL/TP change or new
backtester was introduced. Actual independent evaluation remains NOT_EXECUTED.

Production remains NO-GO.
