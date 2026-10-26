# R.81 baseline integrity

Checked before the edit.

Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
Branch: `main`
Working tree: dirty. Nothing was committed, reset, cleaned, or stashed.

R.80 archive `R80_SOURCE_REVIEW.zip`: 48957 bytes, 28 members, SHA-256 `bc937a41aa01ce91f07cd4a20ae7ec2faadc239f01a9cc2be3156c5b305c8ba8`.

Pre-edit `forex_bot/oanda_exec.py`: `ce9eb935bde93ba18a5ca68e26fc304db1ff6b160be22a3827ca8ee11714a297`.

Unchanged after the edit:

| File | SHA-256 |
| --- | --- |
| `forex_bot/startup_recovery.py` | `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658` |
| `forex_bot/position_recovery.py` | `931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce` |
| `forex_bot/entry_capture.py` | `2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| isolation harness | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` |
| consumed marker | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |

`one_session.permit` is absent. Marker contents were not printed.

Post-edit `oanda_exec.py`: `e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5`.

`R81_BASELINE_VERIFIED`: PASS.
