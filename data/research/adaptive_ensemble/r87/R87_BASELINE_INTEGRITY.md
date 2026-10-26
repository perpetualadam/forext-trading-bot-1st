# R.87 Baseline Integrity

Evidence: hash and archive inspection before any R.87 source edit. No operational file was modified in this stage.

## Git

| Item | Expected | Observed |
| --- | --- | --- |
| Branch | `main` | `main` |
| HEAD | `d080d897945bc44fa37c02caab504ed707146bec` | `4d2394378b47a2237b1c02d19e1c715e49d30185` |

HEAD is two commits after the expected baseline: `3495fe5` and `4d23943`. The working tree also has later local edits in the prospective scheduler audit and state files. Those files were not opened for content and were not changed by this stage.

## Archive

`data/research/adaptive_ensemble/r86/R86_SOURCE_REVIEW.zip` matches the expected record.

| Property | Observed |
| --- | --- |
| Size | 162,048 bytes |
| Members | 46 |
| Manifest entries | 45 |
| Mismatches | 0 |
| Extra members | 0 |
| CRC | clean |
| SHA-256 | `148335440859321f9a89ac9ee02a264c61ec48cb996282d87424b662728364e5` |

The archived `forex_bot/bot_loop.py` digest is `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81`.

## Operational hashes

Every expected file matched except `forex_bot/bot_loop.py`.

| File | Result |
| --- | --- |
| `forex_bot/oanda_exec.py` | match |
| `forex_bot/broker_close_evidence.py` | match |
| `forex_bot/startup_recovery.py` | match |
| `forex_bot/position_recovery.py` | match |
| `forex_bot/entry_capture.py` | match |
| `forex_bot/entry_journal.py` | match |
| `forex_bot/close_journal.py` | match |
| `forex_bot/positions.py` | match |
| `forex_bot/bot_loop.py` | mismatch |
| `forex_bot/profit_protection.py` | match |
| `forex_bot/recovery_owner_lock.py` | match |
| `forex_bot/exposure_report.py` | match |
| `forex_bot/portfolio_exposure.py` | match |
| `forex_bot/reconciliation.py` | match |

Working-tree `bot_loop.py` SHA-256 is `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`.

The difference against the archive is a module-level `fetch_ohlcv` wrapper. `_load_decision_candles` now calls that wrapper instead of importing `oanda_client.fetch_ohlcv` inside the function. This change was already committed. It is not an R.87 edit.

Isolation harness matches `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54`.

The consumed-marker digest matches `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. `one_session.permit` is absent.

## Stop

`R87_BASELINE_VERIFIED` is FAIL. The recovery-evidence workstream stopped before any operational edit.
