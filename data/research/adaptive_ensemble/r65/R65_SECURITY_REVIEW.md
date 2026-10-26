# R.65 security review

The only new code is under `data/research/adaptive_ensemble/r65/poc/`. It classifies cgroup mkdir results and compares five R.61 file hashes. It does not start the bot, open a socket, or read `.env`.

## Unchanged controls

- R.56, R.59, R.60, and R.61 gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- `one_session.consumed` is 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`.
- `one_session.permit` is absent.
- R.56 through R.64 were not modified. The R.64 archive is 7642 bytes, SHA-256 `c80ce9dc784d5d152fd2d78bfb855d702babe6d90e6473439c0b6725af1af0b5`.
- No strategy, stop, size, risk, execution, or supervisor edit.
- No `sudo` and no cgroup configuration change.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

The R.65 modules do not name `forex_bot`, `load_dotenv`, the diagnostic supervisor, `sudo`, `.env`, or `api-fxtrade`. The eligibility record cannot turn the default policy off. A hash mismatch yields `NOT_ELIGIBLE`.

## Archive

`R65_SOURCE_REVIEW.zip`, 4917 bytes, SHA-256 `084f5e4f4104e8fcfb687d713acc04c5ea2aa0587faffa6a93d3f96e526606ae`.

| Member | Bytes | SHA-256 |
| --- | --- | --- |
| `cgroup_denial.py` | 3276 | `49bfeb28c23d419c868ac63d1c09ab8e0410babfe12aed35d1e00b8437993184` |
| `worker_eligibility.py` | 1972 | `45d0a70f485b53c682e0b803f7db92441be1ff7c9f234a7dfcbbe9742d2f650c` |
| `test_cgroup_denial.py` | 3402 | `bfacae2ab86ac4cd89800c64ba6e0876a3c6bc76f5e763a6d5a474bf2d2b99f5` |
| `test_worker_eligibility.py` | 2161 | `729abaa9bd28f963217506f72ec4e368c2174d8851366ef6ccbd69c588f3b9f6` |

No credentials, logs, permits, or copies of R.56–R.64 are in the archive.

## Residual risk

The historical R.64 test still fails on a host whose mkdir returns errno 30. R.65 covers that case by injection and by classifying a live errno, without editing the old test. Research packages remain unintegrated. Direct-child eligibility is a hash check, not a running containment domain. A blocked `CreateProcess` or `fork` is still not cancellable. Linux descendant containment is still unverified.
