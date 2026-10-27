# R.87D remaining risks

Production remains NO-GO. Wrapper restoration and all cloud test-helper repairs are not transferred by these edits. Exact R.86 seal mismatch remains. Six-test compatibility is statically plausible but not operationally verified; offline evidence test_33 is coupled to current mismatch and needs transparent separate review before restoration.

The offline coordinator uses an in-memory lock and trusted synthetic evidence. It does not authenticate broker snapshots, approve freshness, coordinate processes, persist intents, recover crashes, or implement R.87 fencing/R.88. Source/metadata checks cannot certify live runtime gate state; no production state was opened.

GitHub CI currently runs only pytest under tests/; offline_exposure is excluded by pytest.ini testpaths. Therefore OFFLINE_COORDINATOR_CI_COVERAGE_MISSING applies. The parent main commit has an already failed test job. Even if another run succeeds, absence of offline coverage prevents the strongest classification. CI workflow changes would be a separately scoped change, not silently added to this commit.

Do not treat a local passing result as full application health or trading authorisation. No package installation, real/practice broker requests, journal/DB access, strategy/sizing/SL/TP/profit-protection/weekend changes, gate/permit/marker changes are part of this task.
