# Baseline integrity

Inspection was read-only. No file outside `r55/b3_design/` was written. No module was imported. No test was run. No network call was made.

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Dirty working tree: yes, 256 porcelain entries. Left unchanged.
- `r55/b3_design/` did not exist before this task.

## B2 Python sources

Compared with `r55/b2_offline/05_integrity_manifest.json` and the expected digests. All matched.

| File | SHA-256 |
| --- | --- |
| `request_plan.py` | `0ec38d19c4460724d9a71418c568b0178947c1b4faad31cff42156af0febe489` |
| `response_validation.py` | `e9377a43df8b65b5fb71ad51a40fcaded5eca9084fbcef257311e6463bea6002` |
| `synthetic_session.py` | `44566d5ca01ece8561809215d283a285cf73fa19d40426386450a50bfc10dfb3` |
| `synthetic_fixtures.py` | `014960cef817fde3b37134f0a69e559208dd50b53458fa75067325eb8527fcfc` |
| `test_b2_offline.py` | `c43c7537e54400bc557e9b7cf004ae44591a0d744d2f35fb8acb3bbb33830446` |

## B1 sources

| File | SHA-256 |
| --- | --- |
| `r55/b1/session_main.py` | `af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90` |
| `r55/b1/transport.py` | `3727df8494d6076a5997d88bd5be2a8fb4dc9a0a5f3428c65dc3f0e4002de20a` |
| `r55/b1/test_session.py` | `5f1998d22aee2510014fa831a6eb3f94f0af67ebbcfe7483ce0be523525b6b6d` |

## Dependency pins

| Pin | SHA-256 |
| --- | --- |
| `r51/https_adapter.py` | `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` |
| `r52/session_entry.py` | `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` |
| `r53/connector.py` | `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4` |
| `r54/session_main.py` | `50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280` |
| `r55/session_main.py` | `5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8` |
| `r48/readonly_transport.py` | `3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844` |
| `r50/connector.py` | `4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8` |
| `r50/fixtures.py` | `bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee` |

No discrepancy. Nothing was repinned.

## Live path and allowlist

`launch(["--live"])` prints `R55 B2 live entry is disabled. No credential prompt. No network connection.` and returns 2. It does not call `run_live`. `run_live` raises `R55B2_LIVE_DISABLED` as its only action. `run_session` raises that code when mode is not `offline` or when a connection class is supplied, before that class is used. `run_offline` has no connection-class parameter.

The planner allowlist is still instruments and pricing only, with `includeHomeConversions=true` only on pricing. `summary` remains in the banned set. Timeouts are constants. `timeout_enforcement` is `NOT_IMPLEMENTED_OFFLINE`.

The reported independent review, 27 passed, 0 failed, 1 deselected, was not re-run. The deselected case was described as the dependency-file check. That review is not an approval to connect.
