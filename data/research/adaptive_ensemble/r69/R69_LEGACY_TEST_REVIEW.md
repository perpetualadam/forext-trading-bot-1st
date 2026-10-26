# R.69 legacy test review

These modules import `forex_bot.reconciliation` or `forex_bot.config` through the normal package path and use pytest. They were not executed. Running them under the project pytest entry would load the real config module. They were not rewritten.

## `tests/test_reconcile_conflict.py`

| Test | Class | Safer expectation |
| --- | --- | --- |
| `test_import_still_refuses_to_mutate_paper_in_place` | Still valid | Paper row remains |
| `test_displace_then_import_uses_broker_identity` | Obsolete | `displace_paper_position` still exists, but after it the import must land in `broker_observations` with `observation_only`, not in `positions` |
| `test_case_b_conflict_displaces_paper_and_imports_broker` | Obsolete | Paper stays. Observation is separate. No displace snapshot is required. Mismatch text may still say the local row is paper-like |
| `test_case_a_match_keeps_live_identity` | Still valid for a permitted live row | Live identity remains when the broker net matches |
| `test_case_c_imports_when_local_empty` | Obsolete | `positions` stays empty. `broker_observations["EUR_USD"]` is the record |
| `test_case_d_log_only_keeps_local_broker_backed_when_broker_flat` | Still valid | Permitted live row remains when action is `log_only` |
| `test_case_d_auto_fix_drops_broker_backed_when_broker_flat` | Still describes current live behaviour | A permitted live row is still removed. This is the unresolved disappear path, not the observation rule |
| `test_case_e_preserves_paper_when_broker_flat` | Still valid | Paper remains |
| `test_paper_open_blocked_after_broker_snapshot` | Still valid | A remembered broker net still blocks a new paper open |
| `test_paper_open_allowed_before_any_snapshot` | Still valid | |
| `test_paper_open_blocked_when_local_already_broker_backed` | Still valid | |
| `test_usd_guard_counts_imported_not_displaced_paper` | Obsolete | The paper row is still the resident row, so the guard must count the paper row, not a displaced import |
| `test_fallback_sl_tp_not_claimed_as_broker` | Intent still valid, lookup obsolete | Assert `sl_source == "local_fallback"` on the observation, not on `positions` |
| `test_trade_details_preferred_for_sl_tp_and_open_time` | Intent still valid, lookup obsolete | Assert those fields on the observation |
| `test_restart_window_paper_cannot_hide_live_broker_position` | Needs a fresh read before any edit | Do not weaken it. Re-home broker identity assertions onto the observation if the test expected a managed import |
| `test_gbp_usd_same_conflict_path` | Same as Case B | Paper kept |
| `test_parse_oanda_open_time_nanoseconds` | Still valid | Parser only |

## `tests/test_execution_safety.py`

| Test | Class |
| --- | --- |
| Paper and window fill-path tests | Still valid. They do not require a managed import |
| `test_reconcile_cannot_convert_paper_metadata_to_live` | Still valid. Paper metadata remains |
| Live-open tests that monkeypatch the order function | Not run. They are about entry refusal, not R.68. Execute only under a harness that records `PositionClose` and `OrderCreate` |

## `tests/test_live_position_management.py`

| Test | Class |
| --- | --- |
| Quote, MFE, and profit-protection tests that build their own `Position` | Still valid. They do not need a broker |
| `test_restart_import_does_not_manufacture_mfe` | Obsolete lookup. The seeded MFE assertion belongs on `broker_observations["USD_JPY"]`, and that object must stay out of `positions` |
| `test_pricing_snapshot_parses_one_batched_response` | Still a parser test. Run it only with a stubbed HTTP layer |

No operational code was changed to satisfy these tests. New expectations live in `r69/poc/test_r69_integration.py`.
