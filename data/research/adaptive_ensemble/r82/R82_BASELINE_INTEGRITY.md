# R.82 baseline integrity

Executed before any R.82 edit, then re-checked before the archive.

| Check | Result |
| --- | --- |
| Git HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| R.81 classification | `R81_RATE_LIMIT_AND_RECOVERY_SAFETY_VERIFIED_OFFLINE` |
| `one_session.permit` | Absent |
| Consumed-marker SHA-256 | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Isolation SHA-256 | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` |
| `forex_bot/oanda_exec.py` | `e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5` (27879 bytes) |
| `startup_recovery.py` | `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658` |
| `position_recovery.py` | `931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce` |
| `entry_capture.py` | `2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb` |
| `profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| R.81 archive | 43182 bytes, 30 members, SHA-256 `7c2218fc8ad2612741ae0e23bb0eda848e1bdebcb8e81059b1ba68653a5363dd` |

The working tree was already dirty. HEAD is not a complete copy of the operational source. `forex_bot/oanda_exec.py` is modified relative to HEAD and matches the R.81 hash. `forex_bot/broker_close_evidence.py` is an untracked working-tree file. R.82 changed only the negative closed-unit check in that file.

`test_01_baseline_and_gates` re-read the four gate files and the profit-protection hash during the Windows and Linux runs.
