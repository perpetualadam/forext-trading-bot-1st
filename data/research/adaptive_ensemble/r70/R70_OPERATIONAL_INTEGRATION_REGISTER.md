# R.70 Operational Integration Register

Source inspection of the operational tree and the R.56–R.69 research tree. A passing research test is not treated as operational integration.

Legend: operational means the trading-bot modules under `forex_bot/` and `main.py`. Research means `data/research/`. Documentation-only means a design with no operational code.

## Source-gate restrictions

| Field | Value |
| --- | --- |
| Research stage | R.56, repeated in R.59, R.60, R.61 |
| Improvement | `REAL_SESSION_SOURCE_ENABLEMENT` stays false unless a separate authorisation changes it |
| Current location | Research gates: `r56/phase6_connection_enablement/live_session_gate.py`, `r59/live_session_gate.py`, `r60/live_session_gate.py`, `r61/live_session_gate.py` |
| Operationally integrated | Not applicable to the trading loop. The flags are research source gates, and they are still false |
| Operational evidence | No operational module reads these flags. The bot's own entry block is separate |
| Tests | Research offline suites in those stages. Not re-run in R.70. Source text still assigns `False` |
| Remaining gap | The gates do not wrap `main.py` |
| Production necessity | Required to remain off |
| Recommended stage | Stage 10 assessment. Do not flip the flag in an implementation stage |
| Dependencies | None for keeping it false |

## Operational entry refusal

| Field | Value |
| --- | --- |
| Research stage | R.66 finding R66-01, confirmed through R.69 |
| Improvement | New production entries return `status="blocked"` |
| Current location | Operational `forex_bot/bot_loop.py` |
| Operationally integrated | Yes |
| Operational evidence | `evaluate_one_instrument_iteration` blocked statuses. `continue_existing_production_broker` is compared and is not assigned |
| Tests | R.69 source check, skipped tail execution. R.70 source check. Hash unchanged: `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51` |
| Remaining gap | The tail itself was not executed. That is intentional |
| Production necessity | Required |
| Recommended stage | Keep blocked through Stage 10 |
| Dependencies | None |

## Broker position ownership

| Field | Value |
| --- | --- |
| Research stage | R.67A design, R.68 operational predicate |
| Improvement | Management permission is false for observations, imports, empty kinds, and unknown kinds |
| Current location | Operational `forex_bot/positions.py` `position_management_permitted` |
| Operationally integrated | Yes for the predicate |
| Operational evidence | `observation_only` short-circuits. `reconcile_import` is refused. Allowed kinds are paper, simulated, window_paper, live, synthetic |
| Tests | R.68 31 tests, 1 skipped. R.69 and R.70 call the real predicate |
| Remaining gap | Clearing the flag in memory would make a live kind permitted. No operational writer does that. Restart does not persist the predicate |
| Production necessity | Required |
| Recommended stage | Done for the predicate. Persistence belongs to Stage 6 |
| Dependencies | None for the predicate |

## Observation-only reconciliation

| Field | Value |
| --- | --- |
| Research stage | R.68 |
| Improvement | A broker discovery is stored in `broker_observations` and does not occupy the managed book |
| Current location | Operational `forex_bot/positions.py` `import_position_from_broker` and `forex_bot/reconciliation.py` case C |
| Operationally integrated | Yes |
| Operational evidence | Import forces `observation_kind=reconcile_import` and `observation_only=True`. Case B keeps paper. Case C does not increment fixes. `auto_fix` skips non-permitted rows |
| Tests | R.68, R.69, R.70 discovery and paper-preservation tests |
| Remaining gap | A later valid empty snapshot does not delete the observation, and it also does not prove the broker position closed because of this bot |
| Production necessity | Required |
| Recommended stage | Integrated. Close attribution is Stage 3 |
| Dependencies | R.68 predicate |

## Snapshot completeness

| Field | Value |
| --- | --- |
| Research stage | R.69 defect, R.70 correction |
| Improvement | Only a complete OpenPositions body can publish a broker book |
| Current location | Operational `forex_bot/reconciliation.py` |
| Operationally integrated | Yes for the OpenPositions reconcile path |
| Operational evidence | `_interpret_open_positions`, `_publish_snapshot`, reconcile error branch before `_apply_position_convergence` |
| Tests | R.70 26 tests. R.69 `test_10` and `test_12` updated and passing |
| Remaining gap | No broker timestamp. Report dictionary can race. `_remember_broker_snapshot` is unguarded. Shadow local restore still uses `or []`. Linux not executed |
| Production necessity | Required |
| Recommended stage | Stage 1, this stage, offline only |
| Dependencies | R.68 so a complete book still cannot grant management |

## Broker stop evidence

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-03, R.67A/C4 |
| Improvement | Distinguish a real broker stop from an absent or unknown stop section |
| Current location | Operational `forex_bot/live_manage.py` `broker_sl_tp_hit` returns false. Parser stores a price when present |
| Operationally integrated | No |
| Operational evidence | `broker_sl_tp_hit` is a constant false. No broker stop order is placed |
| Tests | Not an R.70 test. Source unchanged |
| Remaining gap | `UNPROTECTED_CONFIRMED` is design-only. Absent stop data is not a confirmed unprotected state in the operational parser |
| Production necessity | Required |
| Recommended stage | Stage 2 |
| Dependencies | Snapshot completeness, so a bad position read is not used as stop evidence |

## Local fallback stop handling

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-05, R.67A |
| Improvement | Local stop and take-profit prices are references, not broker protection |
| Current location | Operational `forex_bot/profit_protection.py` and local position fields |
| Operationally integrated | Partial. The prices exist and are used locally. They are not labelled as broker protection in a dedicated state |
| Operational evidence | Profit protection runs for a permitted row inside `_evaluate_impl` after the R.68 guard |
| Tests | R.69 manage path reached profit protection for a permitted paper row. Formulas were not changed |
| Remaining gap | A local trigger can still be mistaken for a broker stop in operations |
| Production necessity | Required |
| Recommended stage | Stage 2 |
| Dependencies | Broker stop evidence |

## Close-result confirmation

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-10, R.67B, R.67C C1/C2 |
| Improvement | Remove local live state only after evidence of closed units for this operation |
| Current location | Design in R.67B. Operational disappear helper in `forex_bot/broker_exit.py` |
| Operationally integrated | No |
| Operational evidence | `account_disappeared_broker_position` can pop a permitted row when trade resolution is pending. R.70 does not call it for an invalid snapshot. A valid empty snapshot still can |
| Tests | R.70 observes the valid-empty drop and records it as unsafe |
| Remaining gap | `positions: []` is not close attribution |
| Production necessity | Required |
| Recommended stage | Stage 3 |
| Dependencies | Stage 1 so only a complete empty book can reach this path. Stage 3 must still not treat that book as fill proof |

## Ambiguous-close duplicate prevention

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-11, R.67B, R.67C C3 |
| Improvement | One close identity, persisted, blocks a second close while the outcome is unknown |
| Current location | Design only. Operational `PositionClose` has no idempotency key |
| Operationally integrated | No |
| Operational evidence | `oanda_client` close request construction has no client id. Not edited |
| Tests | Not implemented |
| Remaining gap | A timeout can be retried as a new close |
| Production necessity | Required |
| Recommended stage | Stage 4 |
| Dependencies | Stage 3 confirmation rules |

## Partial-fill handling

| Field | Value |
| --- | --- |
| Research stage | R.67B / R.67C |
| Improvement | A partial close keeps the remaining units and does not look fully closed |
| Current location | Design only |
| Operationally integrated | No |
| Operational evidence | No durable partial-fill state in the operational book |
| Tests | Research model only, not the bot |
| Remaining gap | Unit adjustment on a valid book can resize a permitted row without a fill identity |
| Production necessity | Required |
| Recommended stage | Stages 3 and 4 |
| Dependencies | Close identity |

## Position identity and attribution

| Field | Value |
| --- | --- |
| Research stage | R.67C C7, R.68 |
| Improvement | A position's broker trade ids and the operation that closed it are separate facts |
| Current location | Operational trade-id strings on observations and live rows. Attribution design only |
| Operationally integrated | Partial |
| Operational evidence | Import copies trade ids onto the observation. They do not grant management |
| Tests | R.69 multiple-id observation. R.70 missing ids allowed |
| Remaining gap | No link from a closing transaction to a bot close attempt |
| Production necessity | Required |
| Recommended stage | Stage 4 |
| Dependencies | Stage 3 |

## Restart recovery

| Field | Value |
| --- | --- |
| Research stage | R.66, R.67B |
| Improvement | Recover unresolved closes and broker-backed positions after process restart |
| Current location | Positions are process memory. Startup loads orders, not positions |
| Operationally integrated | No |
| Operational evidence | `positions` and `broker_observations` are dicts in `positions.py`. No position table was added |
| Tests | Not implemented |
| Remaining gap | A restart loses the observation book and any in-memory generation |
| Production necessity | Required |
| Recommended stage | Stage 6 |
| Dependencies | Stages 3 and 4, plus a reviewed persistence design. PostgreSQL is not yet integration-tested |

## Reconciliation concurrency

| Field | Value |
| --- | --- |
| Research stage | R.69 observation, R.70 generation guard |
| Improvement | An older OpenPositions response must not replace a newer published book |
| Current location | Operational generation counter in `reconciliation.py` |
| Operationally integrated | Partial |
| Operational evidence | `_begin_snapshot_request` and `_publish_snapshot` |
| Tests | R.70 event-ordered cases. See `R70_CONCURRENCY_REPORT.md` |
| Remaining gap | No wall-clock freshness. Report dict race. No lock across convergence or the manage path |
| Production necessity | Required |
| Recommended stage | Stage 5 for the remaining consistency work |
| Dependencies | Stage 1 publication rules |

## Account currency verification

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-07, account adapter research |
| Improvement | Refuse exposure that is not in the account currency or that lacks a conversion |
| Current location | `forex_bot/oanda_account_adapter.py` checks an injected account document. It is not the OpenPositions reconcile path |
| Operationally integrated | Partial, and not on the live reconcile path |
| Operational evidence | Adapter returns `broker_currency_mismatch` and `exposure_conversion_missing` for injected documents |
| Tests | Not run in R.70. Adapter was not edited |
| Remaining gap | Reconcile does not verify account currency before treating units as comparable |
| Production necessity | Required |
| Recommended stage | Stage 7 |
| Dependencies | Do not change sizing formulas until the currency evidence is specified |

## FX notional and position-sizing correctness

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-07 |
| Improvement | Notional, margin, and unit conversion match the account currency and the broker's unit semantics |
| Current location | Operational sizing code, unchanged |
| Operationally integrated | No correction |
| Operational evidence | R.70 did not modify formulas |
| Tests | Not a profitability or sizing validation |
| Remaining gap | USD assumptions remain |
| Production necessity | Required |
| Recommended stage | Stage 7 |
| Dependencies | Account currency evidence |

## Order submission idempotency

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-11, R.67B |
| Improvement | A repeated close or entry uses a stable client identity |
| Current location | Operational client requests. `PositionClose` has no idempotency key. `Units` rejects `ALL` |
| Operationally integrated | No |
| Operational evidence | Request classes unchanged |
| Tests | Not implemented |
| Remaining gap | Retry can duplicate a close |
| Production necessity | Required |
| Recommended stage | Stage 4 |
| Dependencies | Close-operation identity |

## Cross-platform runtime testing

| Field | Value |
| --- | --- |
| Research stage | R.60–R.65 containment, R.69–R.70 bot import |
| Improvement | The same operational suite passes on Windows and Linux with the declared dependencies |
| Current location | Windows offline pass. WSL2 import failure |
| Operationally integrated | Partial |
| Operational evidence | Windows executed the real modules. WSL2 stopped at `oandapyV20` |
| Tests | See `R70_CROSS_PLATFORM_REPORT.md` |
| Remaining gap | `LINUX_INTEGRATION_NOT_VERIFIED` |
| Production necessity | Required before any hosted run |
| Recommended stage | Stage 8 |
| Dependencies | A compatible environment without weakening isolation |

## PostgreSQL persistence and recovery

| Field | Value |
| --- | --- |
| Research stage | R.66, reconcile metadata helpers |
| Improvement | Durable reconcile metadata and recovery that survive restart |
| Current location | Operational `forex_bot/database.py`. Harness blocks connect |
| Operationally integrated | Code exists. Integration is not verified |
| Operational evidence | `upsert_reconcile_metadata` is skipped when `PERSIST_RECONCILE_STATE=0`. `clear_pending` still attempts connect and logs `PostgreSQL unavailable` |
| Tests | Refusal only. No migration. No real database |
| Remaining gap | `POSTGRESQL_INTEGRATION_NOT_TESTED` |
| Production necessity | Required if restart recovery uses Postgres |
| Recommended stage | Stage 6, after a separate persistence review |
| Dependencies | Stages 3–5 so durable rows have a safe meaning |

## Strategy validation and profitability evidence

| Field | Value |
| --- | --- |
| Research stage | R.66 R66-19 |
| Improvement | Out-of-sample performance, costs, drawdown, and walk-forward evidence |
| Current location | Not assessed |
| Operationally integrated | Not applicable |
| Operational evidence | No strategy module was changed. No performance number was produced |
| Tests | None in R.70 |
| Remaining gap | Safety work is not a profitability result |
| Production necessity | Required before any trading decision, and separate from execution safety |
| Recommended stage | Parallel research. Not Stage 1–8 execution work |
| Dependencies | Do not invent results |

## R.56–R.65 process-containment research

| Field | Value |
| --- | --- |
| Research stage | R.56 through R.65 |
| Improvement | Process-tree containment, cleanup, and cgroup experiments for research workers |
| Current location | Research modules under `data/research/adaptive_ensemble/r56` through `r65` |
| Operationally integrated | No. This is intentional |
| Operational evidence | `forex_bot/` does not import those supervisors |
| Tests | Historical research suites. Not re-run here. Linux descendant containment and cgroup delegation were unverified in those stages |
| Remaining gap | The experiments are not a trading-bot architecture. Integrating them would be a separate decision |
| Production necessity | Research-only for the current bot. A future hosted worker may need an operations design; that is not this register's implementation item |
| Recommended stage | Leave isolated. Do not place it on the trading implementation path |
| Dependencies | None inside R.70 |

## Register conclusion

Operationally present and offline-tested for the narrow claims: entry refusal, the R.68 ownership predicate, observation-only import, and R.70 OpenPositions completeness on Windows.

Still required before production, and not implemented: broker stop evidence, close confirmation, ambiguous-close identity, partial fills, restart recovery, remaining concurrency control, currency and sizing evidence, order idempotency, Linux operational execution, and PostgreSQL integration.

Intentionally not part of the bot: R.56–R.65 containment supervisors.
