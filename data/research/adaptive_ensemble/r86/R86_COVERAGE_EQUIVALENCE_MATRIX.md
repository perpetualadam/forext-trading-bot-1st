# R.86 Coverage Equivalence Matrix

| Phase | Coverage | Evidence |
| --- | --- | --- |
| Baseline and gates | EQUIVALENT_COVERAGE | `test_01` through `test_06` plus the hash command |
| Snapshot source audit | EQUIVALENT_COVERAGE | Source inspection recorded in the audit. No live fetch |
| Provenance fields | STRONGER_COVERAGE | Implemented and executed. Recovery suitability stays false |
| Completeness | EQUIVALENT_COVERAGE | Unknown, incomplete, failed, and stale are distinct. Verified-complete is refused |
| Pagination | PARTIAL_COVERAGE | Supplied page records are classified. The adapter still has no page cursor |
| Freshness | PARTIAL_COVERAGE | Local clocks and stale labels are tested. Broker transaction order is not |
| Exposure categories | EQUIVALENT_COVERAGE | Five categories, null unknown units, Decimal quantities |
| Partial, full, and ambiguous reporting | EQUIVALENT_COVERAGE | `test_26` through `test_34` and both cycle tests |
| Portfolio metric | PARTIAL_COVERAGE | Existing metric left unchanged. Separate report is not connected to the cycle |
| Multi-instrument | EQUIVALENT_COVERAGE | Separate instruments and directions. No raw total |
| Invariants | EQUIVALENT_COVERAGE | Twenty invariants executed |
| Recovery boundary | EQUIVALENT_COVERAGE | Report cannot grant authority. Lock design unchanged |
| Operational cycle | EQUIVALENT_COVERAGE | Real `_execute_bot_cycle` with the isolation harness |
| Profit protection | EQUIVALENT_COVERAGE | Hash unchanged and ratchet 40 retained |
| Live broker completeness | MISSING_COVERAGE | No network access was authorised |

`COMPLETE` labels inside older startup fixtures remain synthetic or syntactic. They were not promoted.
