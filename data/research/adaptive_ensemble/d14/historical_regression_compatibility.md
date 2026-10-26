# Historical regression compatibility

- D.2: EXECUTED_PASS (30), inside 133 passed in 13.09s.
- D.3: EXECUTED_PASS (35), same run.
- D.4: EXECUTED_PASS (50), same run.
- D.7: EXECUTED_PASS (18), same run.
- Safety-repair: EXECUTED_PASS (23). The unconfigured start test also passed (24 total with that one test).
- D.5: HISTORICAL_HASH_PIN_CONFLICT (15).
- D.6: HISTORICAL_HASH_PIN_CONFLICT (12).
- D.8: HISTORICAL_HASH_PIN_CONFLICT (7).
- D.9: HISTORICAL_HASH_PIN_CONFLICT (6). New D.14 ownership checks passed.
- D.10: HISTORICAL_HASH_PIN_CONFLICT (14) and HISTORICAL_DEFECT_ASSERTION_CONFLICT for the old overlap assertion.
- D.11: HISTORICAL_HASH_PIN_CONFLICT (31). New D.14 worker and database checks passed.
- D.12: HISTORICAL_HASH_PIN_CONFLICT (16) and HISTORICAL_DEFECT_ASSERTION_CONFLICT.
- D.13: HISTORICAL_HASH_PIN_CONFLICT (8). The test that requires refusal to stay invisible is also HISTORICAL_CONTRACT_ASSERTION_CONFLICT. It stopped at the telegram hash pin. New D.14 tests cover the corrected behaviour.

Total historical setup errors: 109 in 1.45s. They are not passes. The historical tests were not edited.
