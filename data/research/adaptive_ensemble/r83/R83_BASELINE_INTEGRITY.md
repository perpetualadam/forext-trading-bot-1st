# R.83 baseline integrity

Recorded before the R.83 edits.

| Check | Result |
| --- | --- |
| Git HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| Permit | Absent |
| Consumed marker | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Isolation | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` |
| R.82 archive | 34407 bytes, 28 members, 27 manifest entries, `5890ffa249611c9af18bc869349275b1c5f0cc455955ff5534c0d6c7a903a0d9` |
| `oanda_exec.py` | `e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5` |
| `broker_close_evidence.py` | `3c879729a0c70138f6a317473767e8dfec8d2417c2d38d236478a3a8a190e9db` |
| `startup_recovery.py` | `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658` |
| `position_recovery.py` | `931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce` |
| `entry_capture.py` | `2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb` |
| `profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `entry_journal.py` before edit | `aea5b74e0f431a90b1bd410d650295a5b79d4d901f77391234cd9ddaa5653a07` |
| `close_journal.py` | `4593b42c27b099bc87a225bc7de50b6a9908d41dca5464889f9f26e5d500ef9b` |
| `bot_loop.py` | `fcf7fa240dcd6b2883d49884eeef6c97dfc98857851572d5d088dbf5207d5aa5` |
| `positions.py` before edit | `ac33eca30201f283369196f06e97ed34da343225a011348505f6e379fc71099c` |

The working tree was already dirty. HEAD is not the operational source. The R.82 archive did not contain the operational modules. This stage's archive does.

`entry_journal.py` is now `961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd`. `positions.py` is now `b9da0d1da27e298919eff3a889ff4ec83a53baf95b320876839207ab6827153e`. Those two changes are the R.83 corrections. No other listed operational hash changed.
