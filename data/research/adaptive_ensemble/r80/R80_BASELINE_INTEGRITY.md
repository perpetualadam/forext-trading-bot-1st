# R.80 baseline integrity

Evidence class: static verification before the R.80 edit, then a post-edit recheck of every file that R.80 was required to leave unchanged.

Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
Branch: `main`
Working tree: dirty before R.80. Porcelain line count after the R.80 files: 299. Nothing was committed, reset, cleaned, or stashed.

R.79 archive `data/research/adaptive_ensemble/r79/R79_SOURCE_REVIEW.zip`:

- Size 59208 bytes.
- SHA-256 `db57746669dbaa5f8c2d5b9031c1835bc43f98cd2f530288db16225dbd4d436c`.
- 32 members.
- Manifest mismatches: 0.

Unchanged operational hashes after the R.80 edit:

| File | SHA-256 | Result |
| --- | --- | --- |
| `forex_bot/startup_recovery.py` | `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658` | match |
| `forex_bot/position_recovery.py` | `931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce` | match |
| `forex_bot/entry_capture.py` | `2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb` | match |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` | match |
| isolation harness | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` | match |
| consumed marker | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` | match, 10 bytes, contents not printed |

`forex_bot/oanda_exec.py` was `309d3de315a835d997b8557a317c33344b88ebd36f7e3e5453e3579acf3dbac5` at the R.79 baseline and is now `ce9eb935bde93ba18a5ca68e26fc304db1ff6b160be22a3827ca8ee11714a297`. That is the only operational source change.

`one_session.permit` is absent. `R80_BASELINE_VERIFIED`: PASS.
