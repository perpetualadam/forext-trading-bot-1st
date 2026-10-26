# R.64 security review

R.64 is an offline classification of containment and of one diagnostic worker. It does not authorise a broker session and it does not change the operational supervisor.

## Baseline

- R.63 archive unchanged: 18837 bytes, SHA-256 `046f769a9a40394de6a378354905b74e714be6635529d276cf13d96aaaf736a8`.
- R.56, R.59, R.60, and R.61 gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- `one_session.consumed` is 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`.
- `one_session.permit` is absent.
- R.56 through R.63 were not modified.
- The diagnostic supervisor and worker were read and not edited.
- No `.env` file was read. No credential was loaded. No socket to OANDA was opened. No order was sent.
- No `sudo`, systemd change, cgroup-controller change, or VPS change was made.
- `cgroup.kill` of `init.scope` was not written. The guard returns `CGROUP_KILL_REFUSED` for that path.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Package

The proof of concept uses the standard library. A source scan rejects `forex_bot`, `load_dotenv`, `diagnostic_supervisor`, `sudo`, `.env`, and `api-fxtrade` in the non-test modules. The synthetic worker, which the tests did not launch, writes a local file or would start one local sleeper only after a delegated cgroup had already been confirmed. That path did not run.

`R64_SOURCE_REVIEW.zip`, 7642 bytes, SHA-256 `c80ce9dc784d5d152fd2d78bfb855d702babe6d90e6473439c0b6725af1af0b5`.

| Member | Bytes | SHA-256 |
| --- | --- | --- |
| `cgroup_lifecycle.py` | 10998 | `c0ebe0c2b9d7e0b9b5878fa0cd7cd35a125c183e1817758958daf55a39e67a15` |
| `cgroup_probe.py` | 4531 | `c98ef71a824b221719a7726e359f19a0bc10e085edc535ddf30e10e0eed99460` |
| `synthetic_worker.py` | 784 | `28f5d71451a531e900c362026a3ba5b1824c9bc6189eeba9565a51adc958cd33` |
| `test_cgroup_faults.py` | 2971 | `f7e85cbb62c91b8a836f8e4761a8e0cd4b2409ad4bce9ab85a52d4632090c566` |
| `test_cgroup_probe.py` | 3017 | `9f30febf8ccf98054da0e4262f2a7f2c0417ed637f6e00c7276ca31bc625d847` |

The reports are not members of the archive. The archive contains no permits and no diagnostic logs.

## Residual process risk

This WSL2 user cannot create the cgroup that would kill a tree. A strict open therefore does not fork. A simulated fault must not be quoted as a kernel success. If a later host creates a cgroup and the owner exits without writing `cgroup.kill`, the tree can remain. The Windows job guarantees from R.63 still depend on the last job handle and were not reimplemented here. The diagnostic worker does not spawn today; a later edit can invalidate that without any change to this package.

Nothing in R.64 is integrated into the bot.

`R64_POC_INCOMPLETE`
