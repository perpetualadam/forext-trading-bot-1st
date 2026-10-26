# R.84 baseline integrity

Recorded before the R.84 parser edit.

| Check | Result |
| --- | --- |
| Git HEAD | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| R.83 archive size | 131,780 bytes |
| R.83 members | 47 |
| R.83 manifest entries | 46 |
| R.83 CRC | No failing member |
| R.83 SHA-256 | `b01b060d90ead2a5ddaa50c85e5a8fa25613957659adaf79753d7a1bd78257d7` |
| Permit | Absent |
| Consumed marker | `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Isolation | `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54` |

Every expected operational hash matched, including `broker_close_evidence.py` at `3c879729a0c70138f6a317473767e8dfec8d2417c2d38d236478a3a8a190e9db` before the edit. That file is now `b89548e8e4f7cae1df384239294998bbe6868f6ebc14a587b631d320f4226cd9`. No other listed operational hash changed.
