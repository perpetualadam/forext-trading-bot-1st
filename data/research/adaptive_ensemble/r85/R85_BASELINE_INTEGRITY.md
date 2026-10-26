# R.85 Baseline Integrity

Evidence classes: source inspection of the working tree before the R.85 edits; archive inspection of `data/research/adaptive_ensemble/r84/R84_SOURCE_REVIEW.zip`; executed hash checks inside `test_01_baseline_hashes_and_gates`.

## Git

HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Branch `main`. The working tree was already dirty before R.85. It was not cleaned, committed, reset, or stashed.

## R.84 archive

| Property | Observed |
| --- | --- |
| Size | 118,712 bytes |
| Members | 44 |
| Manifest entries | 43 |
| SHA-256 mismatches | 0 |
| CRC errors | none |
| SHA-256 | `f259b60689045ea1a6b7d7d3b8785a3201f7c789d03ff56cd57594c94e4ff951` |

These matched the expected R.84 archive before any R.85 edit.

## Hashes that stayed at the R.84 values

| File | SHA-256 |
| --- | --- |
| `forex_bot/oanda_exec.py` | `e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5` |
| `forex_bot/startup_recovery.py` | `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658` |
| `forex_bot/entry_journal.py` | `961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |

Isolation harness `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54`. Consumed-marker digest `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. The marker body was not printed. `one_session.permit` was absent.

## Hashes that moved because of R.85

| File | R.84 SHA-256 | R.85 SHA-256 |
| --- | --- | --- |
| `forex_bot/broker_close_evidence.py` | `b89548e8e4f7cae1df384239294998bbe6868f6ebc14a587b631d320f4226cd9` | `2f01fed308a3bf2f111b2bfad8a8610d45ec6bac92264c46877f08d7efd73bc8` |
| `forex_bot/position_recovery.py` | `931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce` | `decab95661526606038856ad1a99b71c54897473bd7120cfa384a8d01db910a3` |
| `forex_bot/entry_capture.py` | `2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb` | `ccf5506b4ff0c381013e3894504104c417aa58804372cbfcd7f3d1b588fb200b` |
| `forex_bot/close_journal.py` | `4593b42c27b099bc87a225bc7de50b6a9908d41dca5464889f9f26e5d500ef9b` | `b5dafd6f7d04e50ef2c4ee993d08733f8d60a73a31f3dbfd7844ab60c2a35483` |
| `forex_bot/positions.py` | `b9da0d1da27e298919eff3a889ff4ec83a53baf95b320876839207ab6827153e` | `afd62ac98c593ee8d75871c12b421d489061b84113724923cdb6f4950edfe36a` |
| `forex_bot/bot_loop.py` | `fcf7fa240dcd6b2883d49884eeef6c97dfc98857851572d5d088dbf5207d5aa5` | `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81` |

The signed-unit function still rejects a positive fill beside a negative reduction and still does not assign `units = abs(`. That was executed in `test_47` and `test_48`.

No unexpected baseline mismatch stopped the stage. The hash movement above is the intended R.85 diff.
